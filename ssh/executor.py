"""Command execution and interaction"""
import paramiko
import threading
import time
import re
from typing import Optional, Tuple, Callable
from config.settings import settings
from ssh.manager import ssh_manager

def strip_ansi_codes(text: str) -> str:
    """Remove ANSI escape codes from text"""
    if not text:
        return text
    # Remove ANSI escape sequences
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

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
            return False, "", "No active connection. Connect to a server first."
        
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
            return False, "", f"SSH error: {str(e)}"
        except Exception as e:
            return False, "", f"Command execution error: {str(e)}"
    
    @staticmethod
    def execute_interactive(user_id: int, command: str) -> Tuple[bool, str]:
        """
        Execute interactive command
        Returns: (success, output)
        """
        ssh_client = ssh_manager.get_connection(user_id)
        if not ssh_client:
            return False, "No active connection. Connect to a server first."
        
        try:
            # Create channel
            transport = ssh_client.get_transport()
            if not transport:
                return False, "Error getting transport"
            
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
            return False, f"Interactive command execution error: {str(e)}"
    
    @staticmethod
    def execute_command_realtime(user_id: int, command: str, update_callback: Callable[[str, str], None]) -> Tuple[bool, str, str]:
        """
        Execute command with real-time output updates
        update_callback will be called with (stdout_chunk, stderr_chunk) as command runs
        Returns: (success, final_stdout, final_stderr)
        """
        ssh_client = ssh_manager.get_connection(user_id)
        if not ssh_client:
            return False, "", "No active connection. Connect to a server first."
        
        try:
            # Execute command
            stdin, stdout, stderr = ssh_client.exec_command(
                command,
                timeout=settings.COMMAND_TIMEOUT,
                get_pty=True
            )
            
            # Read output in real-time
            stdout_lines = []
            stderr_lines = []
            last_line = ""
            last_update_time = time.time()
            update_interval = 2.0  # Update every 2 seconds if last line hasn't changed
            lines_lock = threading.Lock()
            
            def read_stream(stream, lines_list, is_stderr=False):
                """Read from stream and update lines"""
                nonlocal last_line, last_update_time
                buffer = ""
                while True:
                    try:
                        chunk = stream.read(1)
                        if not chunk:
                            break
                        buffer += chunk.decode('utf-8', errors='replace')
                        
                        # Process complete lines
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            # Strip ANSI codes
                            line = strip_ansi_codes(line)
                            with lines_lock:
                                lines_list.append(line)
                                last_line = line
                                last_update_time = time.time()
                            
                            # Call update callback immediately for new lines
                            if is_stderr:
                                update_callback("", line)
                            else:
                                update_callback(line, "")
                    except:
                        break
                
                # Process remaining buffer
                if buffer:
                    # Strip ANSI codes
                    buffer = strip_ansi_codes(buffer)
                    with lines_lock:
                        lines_list.append(buffer)
                        last_line = buffer
                        last_update_time = time.time()
                    
                    # Call update callback for remaining buffer
                    if is_stderr:
                        update_callback("", buffer)
                    else:
                        update_callback(buffer, "")
            
            # Start reading threads
            stdout_thread = threading.Thread(target=read_stream, args=(stdout, stdout_lines, False))
            stderr_thread = threading.Thread(target=read_stream, args=(stderr, stderr_lines, True))
            
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            
            stdout_thread.start()
            stderr_thread.start()
            
            # Monitor and update every 2 seconds - always trigger periodic updates
            last_periodic_update = time.time()
            while stdout_thread.is_alive() or stderr_thread.is_alive():
                time.sleep(0.5)
                current_time = time.time()
                
                # Every 2 seconds, trigger update with current output (even if no new lines)
                if current_time - last_periodic_update >= update_interval:
                    with lines_lock:
                        # Trigger callback to update display with current output
                        update_callback("", "")  # Empty chunks trigger periodic update
                    last_periodic_update = current_time
            
            # Wait for threads to finish
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
            
            # Get final output (strip ANSI codes from final output too)
            stdout_text = '\n'.join([strip_ansi_codes(line) for line in stdout_lines])
            stderr_text = '\n'.join([strip_ansi_codes(line) for line in stderr_lines])
            
            # Close
            stdin.close()
            stdout.close()
            stderr.close()
            
            return True, stdout_text, stderr_text
        
        except paramiko.SSHException as e:
            return False, "", f"SSH error: {str(e)}"
        except Exception as e:
            return False, "", f"Command execution error: {str(e)}"
    
    @staticmethod
    def send_input(user_id: int, input_text: str) -> Tuple[bool, str]:
        """
        Send input to active session
        Returns: (success, message)
        """
        ssh_client = ssh_manager.get_connection(user_id)
        if not ssh_client:
            return False, "No active connection"
        
        try:
            # For interactive commands, we need an active channel
            # This is a simple implementation and can be improved
            transport = ssh_client.get_transport()
            if not transport:
                return False, "Error getting transport"
            
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
            return False, f"Input send error: {str(e)}"

# Global instance
ssh_executor = SSHExecutor()
