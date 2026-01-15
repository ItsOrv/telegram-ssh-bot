"""Command execution and interaction"""
import logging
import paramiko
import threading
import time
import re
from typing import Optional, Tuple, Callable
from config.settings import settings
from ssh.manager import ssh_manager

logger = logging.getLogger(__name__)

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
        Execute command on server in screen session
        Returns: (success, stdout, stderr)
        """
        ssh_client = ssh_manager.get_connection(user_id)
        if not ssh_client:
            return False, "", "No active connection. Connect to a server first."
        
        try:
            # Get screen session name from connection info
            info = ssh_manager.get_connection_info(user_id)
            screen_session = info.get("screen_session") if info else None
            
            if not screen_session:
                # Fallback: execute command directly
                logger.warning(f"No screen session for user {user_id}, using direct execution")
                stdin, stdout, stderr = ssh_client.exec_command(command, timeout=settings.COMMAND_TIMEOUT)
                stdout_text = stdout.read().decode('utf-8', errors='replace')
                stderr_text = stderr.read().decode('utf-8', errors='replace')
                return True, stdout_text, stderr_text
            
            # Setup screen logfile for capturing output
            log_file = f"/tmp/sshbot_log_{user_id}"
            
            # Enable logging in screen session (if not already enabled)
            stdin_log, stdout_log, stderr_log = ssh_client.exec_command(
                f"screen -S {screen_session} -X logfile {log_file} && screen -S {screen_session} -X log on 2>/dev/null || true",
                timeout=3
            )
            stdout_log.read()
            
            # Get current log size before command
            stdin_size, stdout_size, stderr_size = ssh_client.exec_command(
                f"wc -c < {log_file} 2>/dev/null || echo 0",
                timeout=3
            )
            initial_size = int(stdout_size.read().decode('utf-8', errors='replace').strip() or 0)
            
            # Escape command for screen -X stuff (escape single quotes and newlines)
            escaped_command = command.replace("'", "'\"'\"'").replace('\n', '\\n').replace('\r', '')
            
            # Send command to screen session
            stdin_cmd, stdout_cmd, stderr_cmd = ssh_client.exec_command(
                f"screen -S {screen_session} -X stuff '{escaped_command}\\n'",
                timeout=3
            )
            stdout_cmd.read()
            
            # Wait a bit for command to execute (reduced from 1s to 0.5s)
            time.sleep(0.5)
            
            # Get output from log file with shorter timeout for initial read
            stdin, stdout, stderr = ssh_client.exec_command(
                f"tail -c +{initial_size} {log_file} 2>/dev/null || echo ''",
                timeout=min(settings.COMMAND_TIMEOUT, 30)  # Max 30s for initial read
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
        Execute command with real-time output updates in screen session
        update_callback will be called with (stdout_chunk, stderr_chunk) as command runs
        Returns: (success, final_stdout, final_stderr)
        """
        ssh_client = ssh_manager.get_connection(user_id)
        if not ssh_client:
            return False, "", "No active connection. Connect to a server first."
        
        try:
            # Get screen session name from connection info
            info = ssh_manager.get_connection_info(user_id)
            screen_session = info.get("screen_session") if info else None
            
            if not screen_session:
                # Fallback: execute command directly (no real-time updates)
                logger.warning(f"No screen session for user {user_id}, using direct execution")
                stdin, stdout, stderr = ssh_client.exec_command(command, timeout=settings.COMMAND_TIMEOUT)
                stdout_text = stdout.read().decode('utf-8', errors='replace')
                stderr_text = stderr.read().decode('utf-8', errors='replace')
                return True, stdout_text, stderr_text
            
            # Setup screen logfile for capturing output
            log_file = f"/tmp/sshbot_log_{user_id}"
            
            # Enable logging in screen session (if not already enabled)
            stdin_log, stdout_log, stderr_log = ssh_client.exec_command(
                f"screen -S {screen_session} -X logfile {log_file} && screen -S {screen_session} -X log on 2>/dev/null || true",
                timeout=3
            )
            stdout_log.read()
            
            # Get current log size before command
            stdin_size, stdout_size, stderr_size = ssh_client.exec_command(
                f"wc -c < {log_file} 2>/dev/null || echo 0",
                timeout=3
            )
            initial_size = int(stdout_size.read().decode('utf-8', errors='replace').strip() or 0)
            
            # Escape command for screen -X stuff (escape single quotes and newlines)
            escaped_command = command.replace("'", "'\"'\"'").replace('\n', '\\n').replace('\r', '')
            
            # Send command to screen session
            stdin_cmd, stdout_cmd, stderr_cmd = ssh_client.exec_command(
                f"screen -S {screen_session} -X stuff '{escaped_command}\\n'",
                timeout=3
            )
            stdout_cmd.read()
            
            # Poll log file directly for real-time updates
            # This method works better for continuous commands like ping
            stdout_lines = []
            stderr_lines = []
            last_read_size = initial_size
            poll_interval = 0.5  # Poll every 0.5 seconds
            max_poll_time = settings.COMMAND_TIMEOUT
            start_time = time.time()
            last_update_time = time.time()
            update_interval = 1.0  # Update display every 1 second
            
            # Function to read new content from log file
            def read_new_log_content():
                nonlocal last_read_size
                try:
                    # Get current log size
                    stdin_size, stdout_size, stderr_size = ssh_client.exec_command(
                        f"wc -c < {log_file} 2>/dev/null || echo {last_read_size}",
                        timeout=2
                    )
                    current_size = int(stdout_size.read().decode('utf-8', errors='replace').strip() or last_read_size)
                    
                    if current_size > last_read_size:
                        # Read new content
                        stdin_read, stdout_read, stderr_read = ssh_client.exec_command(
                            f"tail -c +{last_read_size + 1} {log_file} 2>/dev/null || echo ''",
                            timeout=2
                        )
                        new_content = stdout_read.read().decode('utf-8', errors='replace')
                        last_read_size = current_size
                        return new_content
                    return ""
                except Exception as e:
                    logger.debug(f"Error reading log file: {e}")
                    return ""
            
            # Poll loop - read log file continuously
            no_change_count = 0  # Count consecutive polls with no change
            max_no_change = 6  # If no change for 3 seconds (6 * 0.5s), command likely finished
            last_size_check = initial_size
            
            while time.time() - start_time < max_poll_time:
                # Read new content from log
                new_content = read_new_log_content()
                
                if new_content:
                    # Process new lines and send to callback
                    lines = new_content.split('\n')
                    new_lines = []
                    for line in lines:
                        if line.strip():
                            cleaned_line = strip_ansi_codes(line)
                            stdout_lines.append(cleaned_line)  # Keep for final output
                            new_lines.append(cleaned_line)  # Send to callback
                            last_update_time = time.time()
                    
                    # Call callback with new lines to trigger update
                    if new_lines:
                        # Send all new lines to callback - callback will add them to output_lines
                        new_content_str = "\n".join(new_lines)
                        update_callback(new_content_str, "")  # Send actual content to callback
                    no_change_count = 0  # Reset counter when we get new content
                else:
                    no_change_count += 1
                
                # Check if log file size changed
                try:
                    stdin_check, stdout_check, stderr_check = ssh_client.exec_command(
                        f"wc -c < {log_file} 2>/dev/null || echo {last_size_check}",
                        timeout=1
                    )
                    current_size = int(stdout_check.read().decode('utf-8', errors='replace').strip() or last_size_check)
                    if current_size != last_size_check:
                        no_change_count = 0  # Reset if size changed
                        last_size_check = current_size
                except Exception as e:
                    logger.debug(f"Error checking log file size: {e}")
                    pass
                
                # For continuous commands like ping, we need to keep polling
                # Only break if we're sure command is finished (no output for a long time)
                # For continuous commands, they will keep producing output, so no_change_count won't reach max
                # But we still need a way to detect when simple commands finish
                if no_change_count >= max_no_change and len(stdout_lines) > 0:
                    # Check if this might be a continuous command (like ping, top, etc.)
                    # If we got output recently, it might be continuous
                    time_since_last_output = time.time() - last_update_time
                    if time_since_last_output < 5:
                        # Got output recently, might be continuous command - continue
                        no_change_count = max_no_change - 2  # Reset but not completely
                        continue
                    
                    # Command likely finished, but wait a bit more to be sure
                    time.sleep(0.5)
                    # Check one more time
                    final_check = read_new_log_content()
                    if not final_check:
                        # No new content, command is done
                        logger.debug(f"Command finished early (no change detected)")
                        break
                    else:
                        # Got new content, continue
                        no_change_count = 0
                
                # Periodic update even if no new content (for continuous commands)
                current_time = time.time()
                if current_time - last_update_time >= update_interval:
                    # Trigger periodic update
                    update_callback("", "")  # Empty chunk triggers periodic update
                    last_update_time = current_time
                
                # Sleep between polls
                time.sleep(poll_interval)
            
            # Get final output from log file
            try:
                stdin_final, stdout_final, stderr_final = ssh_client.exec_command(
                    f"tail -c +{initial_size + 1} {log_file} 2>/dev/null || echo ''",
                    timeout=3
                )
                final_output = stdout_final.read().decode('utf-8', errors='replace')
                
                if final_output and len(final_output.strip()) > 0:
                    # Use final output from log (most complete)
                    stdout_text = strip_ansi_codes(final_output)
                else:
                    # Fallback to collected lines
                    stdout_text = '\n'.join(stdout_lines)
                
                stderr_text = ""  # Screen log doesn't separate stderr
            except Exception as e:
                logger.debug(f"Error getting final output: {e}")
                # Fallback to collected lines
                stdout_text = '\n'.join(stdout_lines)
                stderr_text = ""
            
            # Note: stdin, stdout, stderr are not defined in this scope
            # They are only used in read_new_log_content() function
            # No need to close them here
            
            return True, stdout_text, stderr_text
        
        except paramiko.SSHException as e:
            return False, "", f"SSH error: {str(e)}"
        except Exception as e:
            return False, "", f"Command execution error: {str(e)}"
    
    @staticmethod
    def send_input(user_id: int, input_text: str) -> Tuple[bool, str]:
        """
        Send input to active screen session
        Returns: (success, message)
        """
        ssh_client = ssh_manager.get_connection(user_id)
        if not ssh_client:
            return False, "No active connection"
        
        try:
            # Escape input for screen -X stuff (escape single quotes and newlines)
            escaped_input = input_text.replace("'", "'\"'\"'").replace('\n', '\\n').replace('\r', '')
            
            # Get screen session name from connection info
            info = ssh_manager.get_connection_info(user_id)
            screen_session = info.get("screen_session") if info else None
            
            if not screen_session:
                return False, "No active screen session"
            
            # Send input to screen session - reduced timeout
            stdin, stdout, stderr = ssh_client.exec_command(
                f"screen -S {screen_session} -X stuff '{escaped_input}\\n'",
                timeout=3
            )
            stdout.read()
            
            return True, "Input sent to screen session"
        
        except Exception as e:
            return False, f"Input send error: {str(e)}"

# Global instance
ssh_executor = SSHExecutor()
