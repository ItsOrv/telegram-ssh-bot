"""SSH connection management"""
import logging
import paramiko
import threading
import asyncio
from typing import Optional, Dict
from datetime import datetime, timedelta, timezone
from config.settings import settings
from database.connection import db_manager
from database.models import Connection as DBConnection
from security.encryption import decrypt_password
from ssh.utils import close_ssh_streams, execute_ssh_command_safe
from utils.constants import (
    SSH_CONNECTION_TIMEOUT, SSH_SCREEN_CHECK_TIMEOUT,
    SCREEN_SESSION_PREFIX, SCREEN_SESSION_HASH_LENGTH,
    CANCEL_CHECK_INTERVAL, MAX_CONCURRENT_SSH_CONNECTIONS
)

logger = logging.getLogger(__name__)

class SSHManager:
    """SSH connection management for each user"""
    
    def __init__(self):
        self._connections: Dict[int, paramiko.SSHClient] = {}
        self._connection_info: Dict[int, Dict] = {} # {user_id: {server_id, server_name, connected_at}}
        self._cancel_events: Dict[int, threading.Event] = {}  # Track cancel events for connections
        self._connecting_users: set[int] = set()  # Track users currently connecting
        self._lock = threading.Lock()  # Lock for thread-safe access to connection dictionaries
        # Semaphore to limit concurrent SSH connections (prevents thread pool exhaustion)
        # Note: This is a threading.Semaphore, not asyncio.Semaphore, since connect() runs in thread pool
        self._connection_semaphore = threading.Semaphore(MAX_CONCURRENT_SSH_CONNECTIONS)
    
    def connect(self, user_id: int, server_data: Dict, max_retries: int = 3, cancel_event: Optional[threading.Event] = None) -> tuple[bool, str]:
        """
        Connect to server with retry mechanism
        Args:
            user_id: User ID
            server_data: Dictionary with server info: {id, name, host, port, username, encrypted_password}
            max_retries: Maximum retry attempts
            cancel_event: Threading event to check for cancellation
        Returns: (success, message)
        """
        # Thread-safe check if already connected or connecting
        with self._lock:
            if user_id in self._connections:
                return False, "You are already connected to a server. Please disconnect first."
            
            # Check if already connecting
            if user_id in self._connecting_users:
                return False, "A connection attempt is already in progress. Please wait or cancel it first."
            
            # Mark as connecting
            self._connecting_users.add(user_id)
            
            # Create cancel event if not provided
            if cancel_event is None:
                cancel_event = threading.Event()
                self._cancel_events[user_id] = cancel_event
            else:
                self._cancel_events[user_id] = cancel_event
        
        # Acquire semaphore to limit concurrent connections (prevents thread pool exhaustion)
        # This ensures we don't have too many blocking SSH connections at once
        semaphore_acquired = False
        try:
            # Try to acquire semaphore with timeout check for cancellation
            # Use a small timeout to check cancel_event periodically
            import time
            semaphore_timeout = 0.5  # Check every 0.5 seconds
            max_wait_time = 30  # Maximum wait time for semaphore (30 seconds)
            waited_time = 0
            
            while waited_time < max_wait_time:
                if cancel_event.is_set():
                    with self._lock:
                        if user_id in self._cancel_events:
                            del self._cancel_events[user_id]
                        if user_id in self._connecting_users:
                            self._connecting_users.remove(user_id)
                    return False, "Connection cancelled"
                
                # Try to acquire semaphore (non-blocking)
                if self._connection_semaphore.acquire(blocking=False):
                    semaphore_acquired = True
                    break
                
                # Wait a bit before retrying
                time.sleep(semaphore_timeout)
                waited_time += semaphore_timeout
            
            if not semaphore_acquired:
                with self._lock:
                    if user_id in self._cancel_events:
                        del self._cancel_events[user_id]
                    if user_id in self._connecting_users:
                        self._connecting_users.remove(user_id)
                return False, "Too many concurrent connection attempts. Please try again in a moment."
        
        except Exception as semaphore_error:
            logger.error(f"Error acquiring connection semaphore for user {user_id}: {semaphore_error}")
            with self._lock:
                if user_id in self._cancel_events:
                    del self._cancel_events[user_id]
                if user_id in self._connecting_users:
                    self._connecting_users.remove(user_id)
            return False, "Connection error. Please try again."
        
        # Retry mechanism with exponential backoff
        last_error = None
        ssh_client = None
        for attempt in range(max_retries):
            # Check if cancelled before each attempt
            if cancel_event.is_set():
                    logger.info(f"Connection cancelled by user {user_id}")
                    # Clean up any partial connection
                    with self._lock:
                        if user_id in self._cancel_events:
                            del self._cancel_events[user_id]
                        if user_id in self._connecting_users:
                            self._connecting_users.remove(user_id)
                    if ssh_client:
                        try:
                            ssh_client.close()
                        except Exception:
                            pass
                    if semaphore_acquired:
                        self._connection_semaphore.release()
                    return False, "Connection cancelled"
            
            try:
                # Decrypt password
                password = decrypt_password(user_id, server_data["encrypted_password"])
                
                # Create SSH client
                ssh_client = paramiko.SSHClient()
                ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # Connect with optimized timeout
                # Note: paramiko.connect() is blocking, but we check cancel_event before and after
                ssh_client.connect(
                    hostname=server_data["host"],
                    port=server_data["port"],
                    username=server_data["username"],
                    password=password,
                    timeout=SSH_CONNECTION_TIMEOUT,
                    look_for_keys=False,
                    allow_agent=False,
                    banner_timeout=10  # Add banner timeout
                )
                
                # Check if cancelled after connection
                if cancel_event.is_set():
                    logger.info(f"Connection cancelled by user {user_id} after successful connect")
                    ssh_client.close()
                    ssh_client = None
                    with self._lock:
                        if user_id in self._cancel_events:
                            del self._cancel_events[user_id]
                        if user_id in self._connecting_users:
                            self._connecting_users.remove(user_id)
                    if semaphore_acquired:
                        self._connection_semaphore.release()
                    return False, "Connection cancelled"
                
                # Connection successful
                break
            except paramiko.AuthenticationException as e:
                # Don't retry authentication errors
                with self._lock:
                    if user_id in self._cancel_events:
                        del self._cancel_events[user_id]
                    if user_id in self._connecting_users:
                        self._connecting_users.remove(user_id)
                if semaphore_acquired:
                    self._connection_semaphore.release()
                return False, "Authentication error. Invalid username or password."
            except (paramiko.SSHException, Exception) as e:
                # Check if cancelled during error handling
                if cancel_event.is_set():
                    logger.info(f"Connection cancelled by user {user_id} during error handling")
                    with self._lock:
                        if user_id in self._cancel_events:
                            del self._cancel_events[user_id]
                        if user_id in self._connecting_users:
                            self._connecting_users.remove(user_id)
                    if semaphore_acquired:
                        self._connection_semaphore.release()
                    return False, "Connection cancelled"
                
                last_error = e
                if attempt < max_retries - 1:
                        # Exponential backoff: wait 1s, 2s, 4s
                        wait_time = 2 ** attempt
                        logger.warning(f"Connection attempt {attempt + 1} failed for {server_data['host']}, retrying in {wait_time}s: {e}")
                        import time
                        # Check cancel during wait
                        checks_per_second = int(1.0 / CANCEL_CHECK_INTERVAL)
                        for _ in range(wait_time * checks_per_second):
                            if cancel_event.is_set():
                                with self._lock:
                                    if user_id in self._cancel_events:
                                        del self._cancel_events[user_id]
                                    if user_id in self._connecting_users:
                                        self._connecting_users.remove(user_id)
                                if semaphore_acquired:
                                    self._connection_semaphore.release()
                                return False, "Connection cancelled"
                        time.sleep(CANCEL_CHECK_INTERVAL)
                else:
                    # Last attempt failed
                    with self._lock:
                        if user_id in self._cancel_events:
                            del self._cancel_events[user_id]
                        if user_id in self._connecting_users:
                            self._connecting_users.remove(user_id)
                    if semaphore_acquired:
                        self._connection_semaphore.release()
                    if isinstance(e, paramiko.SSHException):
                        return False, f"SSH error: {str(e)}"
                    else:
                        return False, f"Connection error: {str(e)}"
        
        # Check if cancelled before proceeding with setup
        if cancel_event.is_set():
                logger.info(f"Connection cancelled by user {user_id} before setup")
                if ssh_client:
                    ssh_client.close()
                with self._lock:
                    if user_id in self._cancel_events:
                        del self._cancel_events[user_id]
                    if user_id in self._connecting_users:
                        self._connecting_users.remove(user_id)
                if semaphore_acquired:
                    self._connection_semaphore.release()
                return False, "Connection cancelled"
        
        # If we get here, connection was successful
        try:
            # Thread-safe save connection
            with self._lock:
                # Remove cancel event and connecting flag as connection is successful
                if user_id in self._cancel_events:
                    del self._cancel_events[user_id]
                if user_id in self._connecting_users:
                    self._connecting_users.remove(user_id)
                
                # Save connection
                self._connections[user_id] = ssh_client
                self._connection_info[user_id] = {
                    "server_id": server_data["id"],
                    "server_name": server_data["name"],
                    "connected_at": datetime.now(timezone.utc)
                }
            
            # Setup screen session with unique name - optimized
            import os
            import hashlib
            # Generate unique screen session name based on user_id and process ID
            session_hash = hashlib.md5(f"{user_id}_{os.getpid()}".encode()).hexdigest()[:SCREEN_SESSION_HASH_LENGTH]
            screen_session_name = f"{SCREEN_SESSION_PREFIX}{session_hash}"
            
            try:
                # Check if screen is available
                stdout_check, _, _ = execute_ssh_command_safe(
                    ssh_client,
                    "which screen >/dev/null 2>&1 && echo 'available' || echo 'notfound'",
                    timeout=SSH_SCREEN_CHECK_TIMEOUT
                )
                screen_available = stdout_check and stdout_check.strip() == 'available'
                
                if screen_available:
                    # Check if screen session exists
                    stdout, _, _ = execute_ssh_command_safe(
                        ssh_client,
                        f"screen -list | grep -q '{screen_session_name}' || echo 'notfound'",
                        timeout=SSH_SCREEN_CHECK_TIMEOUT
                    )
                    screen_exists = stdout and stdout.strip() != 'notfound'
                    
                    if not screen_exists:
                        # Create new screen session
                        execute_ssh_command_safe(
                            ssh_client,
                            f"screen -dmS {screen_session_name} bash",
                            timeout=SSH_SCREEN_CHECK_TIMEOUT
                        )
                    # If exists, we'll just attach to it when needed
                    
                    # Store screen session name in connection info
                    with self._lock:
                        if user_id in self._connection_info:
                            self._connection_info[user_id]["screen_session"] = screen_session_name
                else:
                    logger.warning(f"Screen not available on server {server_data['host']}, command execution may be limited")
                    with self._lock:
                        if user_id in self._connection_info:
                            self._connection_info[user_id]["screen_session"] = None
            except Exception as e:
                # Screen might not be available, continue anyway
                logger.debug(f"Screen setup skipped: {e}")
                with self._lock:
                    if user_id in self._connection_info:
                        self._connection_info[user_id]["screen_session"] = None
            
            # Save to database (context manager auto-commits, no need for manual commit)
            # Note: This is blocking but necessary for consistency
            # It's already in a thread pool, so it won't block event loop
            try:
                with db_manager.get_session() as session:
                    # Remove old connection if exists
                    old_connection = session.query(DBConnection).filter_by(user_id=user_id).first()
                    if old_connection:
                        session.delete(old_connection)
                        # Context manager will commit
                    
                    # Create new connection
                    new_connection = DBConnection(
                        user_id=user_id,
                        server_id=server_data["id"]
                    )
                    session.add(new_connection)
                    # Context manager will commit automatically
            except Exception as db_error:
                # If DB save fails, log but don't fail connection
                logger.warning(f"Failed to save connection to database for user {user_id}: {db_error}")
            
            # Release semaphore before returning success (connection is saved)
            if semaphore_acquired:
                self._connection_semaphore.release()
            return True, f"Successfully connected to server {server_data['name']}"
        
        except Exception as setup_error:
            # Handle any errors during setup (screen, database, etc.)
            logger.error(f"Error during connection setup for user {user_id}: {setup_error}")
            if ssh_client:
                try:
                    ssh_client.close()
                except Exception:
                    pass
            with self._lock:
                if user_id in self._connecting_users:
                    self._connecting_users.remove(user_id)
                if user_id in self._cancel_events:
                    del self._cancel_events[user_id]
            if semaphore_acquired:
                self._connection_semaphore.release()
            return False, f"Connection setup error: {str(setup_error)}"
        finally:
            # Always release semaphore when done (success or failure)
            # This ensures semaphore is released even if an unexpected exception occurs
            # Note: We check semaphore_acquired again here as a safety net
            if semaphore_acquired:
                try:
                    self._connection_semaphore.release()
                except Exception:
                    pass  # Ignore errors releasing semaphore (might already be released)
    
    def cancel_connection(self, user_id: int):
        """Cancel ongoing connection attempt"""
        # Thread-safe cancel
        with self._lock:
            if user_id in self._cancel_events:
                cancel_event = self._cancel_events[user_id]
                cancel_event.set()
                logger.info(f"Cancel signal sent for user {user_id} connection")
            # Note: Don't remove from _connecting_users here - let connect() do it
    
    def disconnect(self, user_id: int) -> tuple[bool, str]:
        """
        Disconnect from server
        Returns: (success, message)
        """
        # Cancel any ongoing connection
        self.cancel_connection(user_id)
        
        # Thread-safe disconnect
        with self._lock:
            if user_id not in self._connections:
                return False, "No active connection"
            
            # Get connection reference and remove from dictionary (outside lock for closing)
            ssh_client = self._connections[user_id]
            del self._connections[user_id]
            if user_id in self._connection_info:
                del self._connection_info[user_id]
        
        # Close connection outside lock to avoid blocking other threads
        try:
            ssh_client.close()
        except Exception as close_error:
            logger.warning(f"Error closing SSH connection for user {user_id}: {close_error}")
        
        # Remove from database (context manager auto-commits)
        try:
            with db_manager.get_session() as session:
                connection = session.query(DBConnection).filter_by(user_id=user_id).first()
                if connection:
                    session.delete(connection)
                    # Context manager will commit automatically
        except Exception as db_error:
            logger.warning(f"Error removing database connection for user {user_id}: {db_error}")
        
        return True, "Connection closed"
    
    def is_connected(self, user_id: int, perform_health_check: bool = False) -> bool:
        """
        Check connection status
        Args:
            user_id: User ID
            perform_health_check: If True, performs a blocking health check (use only in threads)
        """
        # Thread-safe check
        with self._lock:
            # Check if connecting (not yet connected)
            if user_id in self._connecting_users:
                return False
            
            if user_id not in self._connections:
                return False
            
            # Get connection reference (we'll check it outside the lock to avoid holding lock during blocking operations)
            ssh_client = self._connections.get(user_id)
        
        if not ssh_client:
            return False
        
        # Check if connection is still active (outside lock to avoid blocking other threads)
        # Use try-except with timeout to avoid blocking
        try:
            # get_transport() and is_active() are usually non-blocking, but wrap in try-except
            # to handle any edge cases where they might block
            transport = ssh_client.get_transport()
            if transport is None:
                # No transport means connection is closed
                self._cleanup_connection(user_id)
                return False
            
            # is_active() is a simple property check, should be non-blocking
            is_active = transport.is_active()
            if not is_active:
                # Connection closed, cleanup
                self._cleanup_connection(user_id)
                return False
            
            # Only perform health check if explicitly requested (and in thread)
            if perform_health_check:
                stdin = stdout = stderr = None
                try:
                    # Try to execute a simple command to verify connection
                    from utils.constants import HEALTH_CHECK_TIMEOUT
                    stdout, _, success = execute_ssh_command_safe(
                        ssh_client,
                        "echo 'health_check'",
                        timeout=HEALTH_CHECK_TIMEOUT
                    )
                    if not success:
                        logger.warning(f"Health check failed for user {user_id}")
                        self._cleanup_connection(user_id)
                        return False
                    return True
                except Exception as health_error:
                    logger.warning(f"Health check failed for user {user_id}: {health_error}")
                    # Connection might be dead, cleanup
                    self._cleanup_connection(user_id)
                    return False
            else:
                # Just check transport status (non-blocking)
                return True
        except Exception as e:
            # If any error occurs (including potential blocking), assume connection is dead
            logger.warning(f"Error checking connection for user {user_id}: {e}")
            self._cleanup_connection(user_id)
            return False
    
    def get_connection(self, user_id: int) -> Optional[paramiko.SSHClient]:
        """Get SSH connection"""
        # Thread-safe get connection
        with self._lock:
            if user_id not in self._connections:
                return None
            return self._connections.get(user_id)
    
    def get_connection_info(self, user_id: int) -> Optional[Dict]:
        """Get connection information"""
        # Thread-safe get connection info (return copy to avoid race conditions)
        with self._lock:
            if user_id not in self._connection_info:
                return None
            # Return a copy to avoid race conditions if dictionary is modified
            return dict(self._connection_info.get(user_id))
    
    def _cleanup_connection(self, user_id: int):
        """Remove closed connection"""
        try:
            # Thread-safe cleanup - get reference and remove from dict
            ssh_client = None
            with self._lock:
                if user_id in self._connections:
                    ssh_client = self._connections[user_id]
                    del self._connections[user_id]
                if user_id in self._connection_info:
                    del self._connection_info[user_id]
            
            # Close connection outside lock to avoid blocking
            if ssh_client:
                try:
                    ssh_client.close()
                except Exception:
                    pass  # Ignore errors when closing
            
            # Database cleanup (outside lock to avoid blocking)
            try:
                with db_manager.get_session() as session:
                    connection = session.query(DBConnection).filter_by(user_id=user_id).first()
                    if connection:
                        session.delete(connection)
            except Exception as db_error:
                logger.warning(f"Error cleaning up database connection for user {user_id}: {db_error}")
        except Exception as e:
            logger.warning(f"Error cleaning up connection for user {user_id}: {e}")
            pass
    
    def cleanup_idle_connections(self):
        """Cleanup idle connections (non-blocking check)"""
        current_time = datetime.now(timezone.utc)
        timeout = timedelta(seconds=settings.CONNECTION_TIMEOUT)
        
        # Thread-safe: get list of connections to check
        with self._lock:
            connection_info_copy = dict(self._connection_info)
            connections_copy = dict(self._connections)
        
        users_to_disconnect = []
        for user_id, info in connection_info_copy.items():
            if current_time - info["connected_at"] > timeout:
                users_to_disconnect.append(user_id)
            else:
                # Quick non-blocking check - just verify transport is active
                if user_id in connections_copy:
                    try:
                        ssh_client = connections_copy[user_id]
                        transport = ssh_client.get_transport()
                        if not transport or not transport.is_active():
                            users_to_disconnect.append(user_id)
                    except Exception:
                        users_to_disconnect.append(user_id)
        
        for user_id in users_to_disconnect:
            self._cleanup_connection(user_id)
    
    def disconnect_all(self):
        """Disconnect all connections"""
        # Thread-safe: get list of all user IDs
        with self._lock:
            user_ids = list(self._connections.keys())
        
        for user_id in user_ids:
            self._cleanup_connection(user_id)

# Global instance
ssh_manager = SSHManager()
