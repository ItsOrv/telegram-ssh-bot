"""SSH connection management"""
import logging
import paramiko
from typing import Optional, Dict
from datetime import datetime, timedelta, timezone
from config.settings import settings
from database.connection import db_manager
from database.models import Server, Connection as DBConnection
from security.encryption import decrypt_password

logger = logging.getLogger(__name__)

class SSHManager:
    """SSH connection management for each user"""
    
    def __init__(self):
        self._connections: Dict[int, paramiko.SSHClient] = {}
        self._connection_info: Dict[int, Dict] = {} # {user_id: {server_id, server_name, connected_at}}
    
    def connect(self, user_id: int, server: Server, max_retries: int = 3) -> tuple[bool, str]:
        """
        Connect to server with retry mechanism
        Returns: (success, message)
        """
        # Check if already connected
        if user_id in self._connections:
            return False, "You are already connected to a server. Please disconnect first."
        
        # Retry mechanism with exponential backoff
        last_error = None
        for attempt in range(max_retries):
            try:
                # Decrypt password
                password = decrypt_password(user_id, server.encrypted_password)
                
                # Create SSH client
                ssh_client = paramiko.SSHClient()
                ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # Connect with optimized timeout
                ssh_client.connect(
                    hostname=server.host,
                    port=server.port,
                    username=server.username,
                    password=password,
                    timeout=15,  # Increased from 10 to 15 for slow connections
                    look_for_keys=False,
                    allow_agent=False,
                    banner_timeout=10  # Add banner timeout
                )
                
                # Connection successful
                break
            except paramiko.AuthenticationException as e:
                # Don't retry authentication errors
                return False, "Authentication error. Invalid username or password."
            except (paramiko.SSHException, Exception) as e:
                last_error = e
                if attempt < max_retries - 1:
                    # Exponential backoff: wait 1s, 2s, 4s
                    wait_time = 2 ** attempt
                    logger.warning(f"Connection attempt {attempt + 1} failed for {server.host}, retrying in {wait_time}s: {e}")
                    import time
                    time.sleep(wait_time)
                else:
                    # Last attempt failed
                    if isinstance(e, paramiko.SSHException):
                        return False, f"SSH error: {str(e)}"
                    else:
                        return False, f"Connection error: {str(e)}"
        
        # If we get here, connection was successful
        try:
            
            # Save connection
            self._connections[user_id] = ssh_client
            self._connection_info[user_id] = {
                "server_id": server.id,
                "server_name": server.name,
                "connected_at": datetime.now(timezone.utc)
            }
            
            # Setup screen session with unique name - optimized
            import os
            import hashlib
            # Generate unique screen session name based on user_id and process ID
            session_hash = hashlib.md5(f"{user_id}_{os.getpid()}".encode()).hexdigest()[:8]
            screen_session_name = f"sshbot_{session_hash}"
            
            try:
                # Check if screen is available
                stdin_check, stdout_check, stderr_check = ssh_client.exec_command(
                    "which screen >/dev/null 2>&1 && echo 'available' || echo 'notfound'",
                    timeout=2
                )
                screen_available = stdout_check.read().decode('utf-8', errors='replace').strip() == 'available'
                
                if screen_available:
                    # Check if screen session exists - reduced timeout
                    stdin, stdout, stderr = ssh_client.exec_command(
                        f"screen -list | grep -q '{screen_session_name}' || echo 'notfound'",
                        timeout=3
                    )
                    screen_exists = stdout.read().decode('utf-8', errors='replace').strip() != 'notfound'
                    
                    if not screen_exists:
                        # Create new screen session - reduced timeout
                        stdin, stdout, stderr = ssh_client.exec_command(
                            f"screen -dmS {screen_session_name} bash",
                            timeout=3
                        )
                        stdout.read()  # Wait for command to complete
                    # If exists, we'll just attach to it when needed
                    
                    # Store screen session name in connection info
                    self._connection_info[user_id]["screen_session"] = screen_session_name
                else:
                    logger.warning(f"Screen not available on server {server.host}, command execution may be limited")
                    self._connection_info[user_id]["screen_session"] = None
            except Exception as e:
                # Screen might not be available, continue anyway
                logger.debug(f"Screen setup skipped: {e}")
                self._connection_info[user_id]["screen_session"] = None
                pass
            
            # Save to database
            with db_manager.get_session() as session:
                # Remove old connection if exists
                old_connection = session.query(DBConnection).filter_by(user_id=user_id).first()
                if old_connection:
                    session.delete(old_connection)
                    session.commit()  # Commit delete before inserting new one
                
                # Create new connection
                new_connection = DBConnection(
                    user_id=user_id,
                    server_id=server.id
                )
                session.add(new_connection)
                session.commit()  # Commit the new connection
            
            return True, f"Successfully connected to server {server.name}"
        
        except paramiko.AuthenticationException:
            return False, "Authentication error. Invalid username or password."
        except paramiko.SSHException as e:
            return False, f"SSH error: {str(e)}"
        except Exception as e:
            return False, f"Connection error: {str(e)}"
    
    def disconnect(self, user_id: int) -> tuple[bool, str]:
        """
        Disconnect from server
        Returns: (success, message)
        """
        if user_id not in self._connections:
            return False, "No active connection"
        
        try:
            # Close connection
            ssh_client = self._connections[user_id]
            ssh_client.close()
            
            # Remove from dictionary
            del self._connections[user_id]
            if user_id in self._connection_info:
                del self._connection_info[user_id]
            
            # Remove from database
            with db_manager.get_session() as session:
                connection = session.query(DBConnection).filter_by(user_id=user_id).first()
                if connection:
                    session.delete(connection)
                    session.commit()
            
            return True, "Connection closed"
        
        except Exception as e:
            return False, f"Disconnect error: {str(e)}"
    
    def is_connected(self, user_id: int, perform_health_check: bool = False) -> bool:
        """
        Check connection status
        Args:
            user_id: User ID
            perform_health_check: If True, performs a blocking health check (use only in threads)
        """
        if user_id not in self._connections:
            return False
        
        # Check if connection is still active
        try:
            ssh_client = self._connections[user_id]
            transport = ssh_client.get_transport()
            if transport and transport.is_active():
                # Only perform health check if explicitly requested (and in thread)
                if perform_health_check:
                    try:
                        # Try to execute a simple command to verify connection
                        stdin, stdout, stderr = ssh_client.exec_command("echo 'health_check'", timeout=2)
                        stdout.read()
                        return True
                    except Exception as health_error:
                        logger.warning(f"Health check failed for user {user_id}: {health_error}")
                        # Connection might be dead, cleanup
                        self._cleanup_connection(user_id)
                        return False
                else:
                    # Just check transport status (non-blocking)
                    return True
            else:
                # Connection closed, cleanup
                self._cleanup_connection(user_id)
                return False
        except Exception as e:
            logger.warning(f"Error checking connection for user {user_id}: {e}")
            self._cleanup_connection(user_id)
            return False
    
    def get_connection(self, user_id: int) -> Optional[paramiko.SSHClient]:
        """Get SSH connection"""
        if not self.is_connected(user_id):
            return None
        return self._connections.get(user_id)
    
    def get_connection_info(self, user_id: int) -> Optional[Dict]:
        """Get connection information"""
        if not self.is_connected(user_id):
            return None
        return self._connection_info.get(user_id)
    
    def _cleanup_connection(self, user_id: int):
        """Remove closed connection"""
        try:
            if user_id in self._connections:
                ssh_client = self._connections[user_id]
                ssh_client.close()
                del self._connections[user_id]
            if user_id in self._connection_info:
                del self._connection_info[user_id]
            
            with db_manager.get_session() as session:
                connection = session.query(DBConnection).filter_by(user_id=user_id).first()
                if connection:
                    session.delete(connection)
        except Exception as e:
            logger.warning(f"Error cleaning up connection for user {user_id}: {e}")
            pass
    
    def cleanup_idle_connections(self):
        """Cleanup idle connections (non-blocking check)"""
        current_time = datetime.now(timezone.utc)
        timeout = timedelta(seconds=settings.CONNECTION_TIMEOUT)
        
        users_to_disconnect = []
        for user_id, info in list(self._connection_info.items()):
            if current_time - info["connected_at"] > timeout:
                users_to_disconnect.append(user_id)
            else:
                # Quick non-blocking check - just verify transport is active
                if user_id in self._connections:
                    try:
                        ssh_client = self._connections[user_id]
                        transport = ssh_client.get_transport()
                        if not transport or not transport.is_active():
                            users_to_disconnect.append(user_id)
                    except Exception:
                        users_to_disconnect.append(user_id)
        
        for user_id in users_to_disconnect:
            self._cleanup_connection(user_id)
    
    def disconnect_all(self):
        """Disconnect all connections"""
        for user_id in list(self._connections.keys()):
            self._cleanup_connection(user_id)

# Global instance
ssh_manager = SSHManager()
