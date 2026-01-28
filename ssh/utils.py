"""SSH utility functions to reduce code duplication"""
from typing import Optional, Tuple
import paramiko


def close_ssh_streams(stdin=None, stdout=None, stderr=None):
    """
    Safely close SSH streams to prevent resource leaks
    
    Args:
        stdin: stdin stream (optional)
        stdout: stdout stream (optional)
        stderr: stderr stream (optional)
    """
    for stream in [stdin, stdout, stderr]:
        if stream:
            try:
                stream.close()
            except Exception:
                pass  # Ignore errors when closing streams


def execute_ssh_command_safe(
    ssh_client: paramiko.SSHClient,
    command: str,
    timeout: int = 3
) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Execute SSH command safely with proper resource cleanup
    
    Args:
        ssh_client: SSH client instance
        command: Command to execute
        timeout: Command timeout in seconds
    
    Returns:
        Tuple of (stdout_text, stderr_text, success)
    """
    stdin = stdout = stderr = None
    try:
        stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
        stdout_text = stdout.read().decode('utf-8', errors='replace')
        stderr_text = stderr.read().decode('utf-8', errors='replace')
        return stdout_text, stderr_text, True
    except Exception as e:
        return None, str(e), False
    finally:
        close_ssh_streams(stdin, stdout, stderr)


