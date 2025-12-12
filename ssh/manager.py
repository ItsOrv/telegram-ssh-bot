"""SSH connection management"""
import paramiko
from typing import Optional, Dict
from datetime import datetime, timedelta
from config.settings import settings
from database.connection import db_manager
from database.models import Server, Connection as DBConnection
from security.encryption import decrypt_password


class SSHManager:
    """SSH connection management for each user"""
    
    def __init__(self):
        self._connections: Dict[int, paramiko.SSHClient] = {}
        self._connection_info: Dict[int, Dict] = {}  # {user_id: {server_id, server_name, connected_at}}
    
    def connect(self, user_id: int, server: Server) -> tuple[bool, str]:
        """
        Connect to server
        Returns: (success, message)
        """
        # Check if already connected
        if user_id in self._connections:
            return False, "You are already connected to a server. Please disconnect first."
        
        try:
            # Decrypt password
            password = decrypt_password(user_id, server.encrypted_password)
            
            # Create SSH client
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect
            ssh_client.connect(
                hostname=server.host,
                port=server.port,
                username=server.username,
                password=password,
                timeout=10,
                look_for_keys=False,
                allow_agent=False
            )
            
            # Save connection
            self._connections[user_id] = ssh_client
            self._connection_info[user_id] = {
                "server_id": server.id,
                "server_name": server.name,
                "connected_at": datetime.utcnow()
            }
            
            # Save to database
            with db_manager.get_session() as session:
                # Remove old connection if exists
                old_connection = session.query(DBConnection).filter_by(user_id=user_id).first()
                if old_connection:
                    session.delete(old_connection)
                
                # Create new connection
                new_connection = DBConnection(
                    user_id=user_id,
                    server_id=server.id
                )
                session.add(new_connection)
            
            return True, f"✅ Successfully connected to server {server.name}"
        
        except paramiko.AuthenticationException:
            return False, "❌ Authentication error. Invalid username or password."
        except paramiko.SSHException as e:
            return False, f"❌ SSH error: {str(e)}"
        except Exception as e:
            return False, f"❌ Connection error: {str(e)}"
    
    def disconnect(self, user_id: int) -> tuple[bool, str]:
        """
        Disconnect from server
        Returns: (success, message)
        """
        if user_id not in self._connections:
            return False, "❌ No active connection"
        
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
            
            return True, "✅ Connection closed"
        
        except Exception as e:
            return False, f"❌ Disconnect error: {str(e)}"
    
    def is_connected(self, user_id: int) -> bool:
        """Check connection"""
        if user_id not in self._connections:
            return False
        
        # Check if connection is still active
        try:
            ssh_client = self._connections[user_id]
            transport = ssh_client.get_transport()
            if transport and transport.is_active():
                return True
            else:
                # Connection closed, cleanup
                self._cleanup_connection(user_id)
                return False
        except:
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
        except:
            pass
    
    def cleanup_idle_connections(self):
        """Cleanup idle connections"""
        current_time = datetime.utcnow()
        timeout = timedelta(seconds=settings.CONNECTION_TIMEOUT)
        
        users_to_disconnect = []
        for user_id, info in self._connection_info.items():
            if current_time - info["connected_at"] > timeout:
                users_to_disconnect.append(user_id)
        
        for user_id in users_to_disconnect:
            self._cleanup_connection(user_id)
    
    def disconnect_all(self):
        """Disconnect all connections"""
        for user_id in list(self._connections.keys()):
            self._cleanup_connection(user_id)


# Global instance
ssh_manager = SSHManager()
