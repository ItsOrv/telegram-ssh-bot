"""Command execution and interaction"""
import paramiko
from typing import Optional, Tuple
from config.settings import settings
from ssh.manager import ssh_manager


class SSHExecutor:
    """SSH command execution"""
    
    @staticmethod
    def execute_command(user_id: int, command: str) -> Tuple[bool, str, str]:
        """
        Execute command on server
        Returns: (success, stdout, stderr)
        """
        ssh_client = ssh_manager.get_connection(user_id)
        if not ssh_client:
            return False, "", "❌ No active connection. Please connect to a server first."
        
        try:
            # Execute command
            stdin, stdout, stderr = ssh_client.exec_command(
                command,
                timeout=settings.COMMAND_TIMEOUT,
                get_pty=True
            )
            
            # Read output
            stdout_text = stdout.read().decode('utf-8', errors='replace')
            stderr_text = stderr.read().decode('utf-8', errors='replace')
            
            # Close
            stdin.close()
            stdout.close()
            stderr.close()
            
            return True, stdout_text, stderr_text
        
        except paramiko.SSHException as e:
            return False, "", f"❌ SSH error: {str(e)}"
        except Exception as e:
            return False, "", f"❌ Command execution error: {str(e)}"
    
    @staticmethod
    def execute_interactive(user_id: int, command: str) -> Tuple[bool, str]:
        """
        Execute interactive command
        Returns: (success, output)
        """
        ssh_client = ssh_manager.get_connection(user_id)
        if not ssh_client:
            return False, "❌ No active connection. Please connect to a server first."
        
        try:
            # Create channel
            transport = ssh_client.get_transport()
            if not transport:
                return False, "❌ Error getting transport"
            
            channel = transport.open_session()
            channel.get_pty(term='xterm', width=80, height=24)
            channel.exec_command(command)
            
            # Read output
            output = ""
            while True:
                if channel.recv_ready():
                    data = channel.recv(4096).decode('utf-8', errors='replace')
                    output += data
                elif channel.exit_status_ready():
                    break
                else:
                    import time
                    time.sleep(0.1)
            
            channel.close()
            return True, output
        
        except Exception as e:
            return False, f"❌ Interactive command execution error: {str(e)}"
    
    @staticmethod
    def send_input(user_id: int, input_text: str) -> Tuple[bool, str]:
        """
        Send input to active session
        Returns: (success, message)
        """
        ssh_client = ssh_manager.get_connection(user_id)
        if not ssh_client:
            return False, "❌ No active connection"
        
        try:
            # For interactive commands, we need an active channel
            # This is a simple implementation and can be improved
            transport = ssh_client.get_transport()
            if not transport:
                return False, "❌ Error getting transport"
            
            # Execute command with input
            stdin, stdout, stderr = ssh_client.exec_command(
                f"echo '{input_text}'",
                get_pty=True
            )
            
            stdin.write(input_text + '\n')
            stdin.flush()
            
            output = stdout.read().decode('utf-8', errors='replace')
            
            stdin.close()
            stdout.close()
            stderr.close()
            
            return True, output
        
        except Exception as e:
            return False, f"❌ Input send error: {str(e)}"


# Global instance
ssh_executor = SSHExecutor()
