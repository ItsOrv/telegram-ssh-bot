"""Command and input validation"""
import re
import ipaddress
from typing import Tuple, Optional
from config.settings import settings


# List of dangerous commands
DANGEROUS_COMMANDS = [
    r'rm\s+-rf\s+/',
    r'rm\s+-rf\s+~',
    r'rm\s+-rf\s+\*',
    r'format\s+',
    r'mkfs\s+',
    r'dd\s+if=',
    r'>\s+/dev/',
    r':\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;',
    r'wget\s+.*\s+\|\s+sh',
    r'curl\s+.*\s+\|\s+sh',
    r'chmod\s+777',
    r'chmod\s+-R\s+777',
    r'sudo\s+rm\s+-rf',
    r'sudo\s+mkfs',
    r'sudo\s+format',
]


def validate_ip(ip: str) -> Tuple[bool, Optional[str]]:
    """Validate IP address"""
    try:
        ipaddress.ip_address(ip)
        return True, None
    except ValueError:
        return False, "Invalid IP address"


def validate_port(port: int) -> Tuple[bool, Optional[str]]:
    """Validate port"""
    if 1 <= port <= 65535:
        return True, None
    return False, "Port must be between 1 and 65535"


def validate_command(command: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate command
    Returns: (is_valid, warning_message, error_message)
    """
    if not command or not command.strip():
        return False, None, "Command cannot be empty"
    
    # Length limit
    if len(command) > settings.MAX_COMMAND_LENGTH:
        return False, None, f"Command length must not exceed {settings.MAX_COMMAND_LENGTH} characters"
    
    # Check dangerous commands
    command_lower = command.lower().strip()
    for dangerous_pattern in DANGEROUS_COMMANDS:
        if re.search(dangerous_pattern, command_lower, re.IGNORECASE):
            return False, None, f"Dangerous command detected: {dangerous_pattern}"
    
    # Clean suspicious control characters
    control_chars = ['\x00', '\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07',
                     '\x08', '\x0b', '\x0c', '\x0e', '\x0f', '\x10', '\x11', '\x12',
                     '\x13', '\x14', '\x15', '\x16', '\x17', '\x18', '\x19', '\x1a',
                     '\x1b', '\x1c', '\x1d', '\x1e', '\x1f', '\x7f']
    
    has_control_chars = any(char in command for char in control_chars)
    if has_control_chars:
        # Remove control characters
        cleaned_command = ''.join(char for char in command if char not in control_chars)
        warning = "Control characters were removed from command"
        return True, warning, None
    
    return True, None, None


def sanitize_input(text: str) -> str:
    """Sanitize input from suspicious characters"""
    if not text:
        return ""
    
    # Remove control characters
    control_chars = ['\x00', '\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07',
                     '\x08', '\x0b', '\x0c', '\x0e', '\x0f', '\x10', '\x11', '\x12',
                     '\x13', '\x14', '\x15', '\x16', '\x17', '\x18', '\x19', '\x1a',
                     '\x1b', '\x1c', '\x1d', '\x1e', '\x1f', '\x7f']
    
    cleaned = ''.join(char for char in text if char not in control_chars)
    
    # Remove extra whitespace
    cleaned = ' '.join(cleaned.split())
    
    return cleaned


def validate_server_info(host: str, port: int, username: str, password: str) -> Tuple[bool, Optional[str]]:
    """Validate server information"""
    # Validate IP
    is_valid_ip, ip_error = validate_ip(host)
    if not is_valid_ip:
        # Might be hostname, simple check
        if not host or len(host) > 255:
            return False, "Invalid host"
    
    # Validate port
    is_valid_port, port_error = validate_port(port)
    if not is_valid_port:
        return False, port_error
    
    # Validate username
    if not username or len(username) > 100:
        return False, "Invalid username"
    
    # Validate password
    if not password:
        return False, "Password cannot be empty"
    
    return True, None
