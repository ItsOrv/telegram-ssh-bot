"""Command execution and interaction"""
import logging
import paramiko
import threading
import time
import re
from typing import Optional, Tuple, Callable
from config.settings import settings
from ssh.manager import ssh_manager
from ssh.utils import close_ssh_streams, execute_ssh_command_safe
from utils.constants import (
    POLL_INTERVAL, UPDATE_INTERVAL, COMMAND_WAIT_TIME,
    MAX_NO_CHANGE_COUNT, CONTINUOUS_COMMAND_THRESHOLD,
    SSH_COMMAND_TIMEOUT, SSH_SCREEN_CHECK_TIMEOUT, SSH_LOG_READ_TIMEOUT
)

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
                stdout_text, stderr_text, success = execute_ssh_command_safe(
                    ssh_client,
                    command,
                    timeout=settings.COMMAND_TIMEOUT
                )
                if not success:
                    return False, "", stderr_text or "Command execution failed"
                return True, stdout_text or "", stderr_text or ""
            
            # Setup screen logfile for capturing output
            log_file = f"/tmp/sshbot_log_{user_id}"
            
            # Enable logging in screen session (if not already enabled)
            stdout_log, _, _ = execute_ssh_command_safe(
                ssh_client,
                f"screen -S {screen_session} -X logfile {log_file} && screen -S {screen_session} -X log on 2>/dev/null || true",
                timeout=SSH_SCREEN_CHECK_TIMEOUT
            )
            
            # Get current log size before command
            stdout_size, _, _ = execute_ssh_command_safe(
                ssh_client,
                f"wc -c < {log_file} 2>/dev/null || echo 0",
                timeout=SSH_LOG_READ_TIMEOUT
            )
            initial_size = int(stdout_size.strip() or 0) if stdout_size else 0
            
            # Escape command for screen -X stuff (escape single quotes and newlines)
            escaped_command = command.replace("'", "'\"'\"'").replace('\n', '\\n').replace('\r', '')
            
            # Send command to screen session
            execute_ssh_command_safe(
                ssh_client,
                f"screen -S {screen_session} -X stuff '{escaped_command}\\n'",
                timeout=SSH_COMMAND_TIMEOUT
            )
            
            # Wait a bit for command to execute
            time.sleep(COMMAND_WAIT_TIME)
            
            # Get output from log file with shorter timeout for initial read
            stdout_text, stderr_text, _ = execute_ssh_command_safe(
                ssh_client,
                f"tail -c +{initial_size} {log_file} 2>/dev/null || echo ''",
                timeout=min(settings.COMMAND_TIMEOUT, 30)  # Max 30s for initial read
            )
            stdout_text = stdout_text or ""
            stderr_text = stderr_text or ""
            
            return True, stdout_text, stderr_text
        
        except paramiko.SSHException as e:
            return False, "", f"SSH error: {str(e)}"
        except Exception as e:
            return False, "", f"Command execution error: {str(e)}"
    
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
                stdout_text, stderr_text, success = execute_ssh_command_safe(
                    ssh_client,
                    command,
                    timeout=settings.COMMAND_TIMEOUT
                )
                if not success:
                    return False, "", stderr_text or "Command execution failed"
                return True, stdout_text or "", stderr_text or ""
            
            # Setup screen logfile for capturing output
            log_file = f"/tmp/sshbot_log_{user_id}"
            
            # Enable logging in screen session (if not already enabled)
            execute_ssh_command_safe(
                ssh_client,
                f"screen -S {screen_session} -X logfile {log_file} && screen -S {screen_session} -X log on 2>/dev/null || true",
                timeout=SSH_SCREEN_CHECK_TIMEOUT
            )
            
            # Get current log size before command
            stdout_size, _, _ = execute_ssh_command_safe(
                ssh_client,
                f"wc -c < {log_file} 2>/dev/null || echo 0",
                timeout=SSH_LOG_READ_TIMEOUT
            )
            initial_size = int(stdout_size.strip() or 0) if stdout_size else 0
            
            # Escape command for screen -X stuff (escape single quotes and newlines)
            escaped_command = command.replace("'", "'\"'\"'").replace('\n', '\\n').replace('\r', '')
            
            # Send command to screen session
            execute_ssh_command_safe(
                ssh_client,
                f"screen -S {screen_session} -X stuff '{escaped_command}\\n'",
                timeout=SSH_COMMAND_TIMEOUT
            )
            
            # Poll log file directly for real-time updates
            # This method works better for continuous commands like ping
            stdout_lines = []
            stderr_lines = []
            last_read_size = initial_size
            max_poll_time = settings.COMMAND_TIMEOUT
            start_time = time.time()
            last_update_time = time.time()
            
            # Function to read new content from log file
            def read_new_log_content():
                nonlocal last_read_size
                try:
                    # Get current log size
                    stdout_size, _, _ = execute_ssh_command_safe(
                        ssh_client,
                        f"wc -c < {log_file} 2>/dev/null || echo {last_read_size}",
                        timeout=SSH_LOG_READ_TIMEOUT
                    )
                    current_size = int(stdout_size.strip() or last_read_size) if stdout_size else last_read_size
                    
                    if current_size > last_read_size:
                        # Read new content
                        stdout_read, _, _ = execute_ssh_command_safe(
                            ssh_client,
                            f"tail -c +{last_read_size + 1} {log_file} 2>/dev/null || echo ''",
                            timeout=SSH_LOG_READ_TIMEOUT
                        )
                        new_content = stdout_read or ""
                        last_read_size = current_size
                        return new_content
                    return ""
                except Exception as e:
                    logger.debug(f"Error reading log file: {e}")
                    return ""
            
            # Poll loop - read log file continuously
            no_change_count = 0  # Count consecutive polls with no change
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
                    stdout_check, _, _ = execute_ssh_command_safe(
                        ssh_client,
                        f"wc -c < {log_file} 2>/dev/null || echo {last_size_check}",
                        timeout=SSH_LOG_READ_TIMEOUT
                    )
                    current_size = int(stdout_check.strip() or last_size_check) if stdout_check else last_size_check
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
                if no_change_count >= MAX_NO_CHANGE_COUNT and len(stdout_lines) > 0:
                    # Check if this might be a continuous command (like ping, top, etc.)
                    # If we got output recently, it might be continuous
                    time_since_last_output = time.time() - last_update_time
                    if time_since_last_output < CONTINUOUS_COMMAND_THRESHOLD:
                        # Got output recently, might be continuous command - continue
                        no_change_count = MAX_NO_CHANGE_COUNT - 2  # Reset but not completely
                        continue
                    
                    # Command likely finished, but wait a bit more to be sure
                    time.sleep(COMMAND_WAIT_TIME)
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
                if current_time - last_update_time >= UPDATE_INTERVAL:
                    # Trigger periodic update
                    update_callback("", "")  # Empty chunk triggers periodic update
                    last_update_time = current_time
                
                # Sleep between polls
                time.sleep(POLL_INTERVAL)
            
            # Get final output from log file
            try:
                stdout_final, _, _ = execute_ssh_command_safe(
                    ssh_client,
                    f"tail -c +{initial_size + 1} {log_file} 2>/dev/null || echo ''",
                    timeout=SSH_LOG_READ_TIMEOUT
                )
                final_output = stdout_final or ""
                
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
            
            # Send input to screen session
            execute_ssh_command_safe(
                ssh_client,
                f"screen -S {screen_session} -X stuff '{escaped_input}\\n'",
                timeout=SSH_COMMAND_TIMEOUT
            )
            
            return True, "Input sent to screen session"
        
        except Exception as e:
            return False, f"Input send error: {str(e)}"

# Global instance
ssh_executor = SSHExecutor()
