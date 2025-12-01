"""Helper messages and formatting"""
from typing import Optional


def format_command_output(output: str, max_length: int = 4000) -> str:
    """Format command output"""
    if not output:
        return "Empty output"
    
    # Limit output length
    if len(output) > max_length:
        output = output[:max_length] + "\n\n... (output truncated)"
    
    # Escape markdown characters
    output = output.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("]", "\\]")
    output = output.replace("(", "\\(").replace(")", "\\)").replace("~", "\\~")
    output = output.replace("`", "\\`").replace(">", "\\>").replace("#", "\\#")
    output = output.replace("+", "\\+").replace("-", "\\-").replace("=", "\\=")
    output = output.replace("|", "\\|").replace("{", "\\{").replace("}", "\\}")
    output = output.replace(".", "\\.").replace("!", "\\!")
    
    return f"```\n{output}\n```"


def get_help_message() -> str:
    """Main help message"""
    return """
🤖 **SSH Bot Guide**

**Main Commands:**
• `/start` - Start the bot and show main menu
• `/help` - Show this help message

**Server Management:**
• Add new server with IP, username and password
• View server list
• Edit or delete server
• Connect/disconnect to server

**Command Execution:**
• Execute commands on connected server
• Support for interactive commands
• Receive output and errors

**Preset Commands:**
• Add frequently used commands
• Quick command execution

**Security Notes:**
• Dangerous commands are blocked
• Inputs are validated
• Command length limits

To get started, use the main menu.
"""


def get_server_info_message(name: str, host: str, port: int, username: str) -> str:
    """Format server information"""
    return f"""
🖥️ **Server Information**

**Name:** {name}
**Host:** `{host}`
**Port:** `{port}`
**Username:** `{username}`
"""


def get_connection_status_message(connected: bool, server_name: Optional[str] = None) -> str:
    """Connection status message"""
    if connected and server_name:
        return f"✅ Connected to server: **{server_name}**"
    return "❌ No active connection"


def get_error_message(error: str) -> str:
    """Format error message"""
    return f"❌ **Error:** {error}"


def get_success_message(message: str) -> str:
    """Format success message"""
    return f"✅ {message}"


def get_warning_message(message: str) -> str:
    """Format warning message"""
    return f"⚠️ **Warning:** {message}"
