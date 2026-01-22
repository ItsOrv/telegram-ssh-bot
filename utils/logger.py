"""Logging utilities for command execution and security events"""
import logging
import functools
from datetime import datetime
from typing import Optional
from database.connection import db_manager
from database.models import CommandHistory

# Setup command execution logger
command_logger = logging.getLogger("command_execution")
command_logger.setLevel(logging.INFO)

# Setup security logger
security_logger = logging.getLogger("security")
security_logger.setLevel(logging.WARNING)


def log_command_execution(
    user_id: int,
    command: str,
    success: bool,
    output_length: int = 0,
    error_length: int = 0,
    execution_time: Optional[float] = None,
    server_id: Optional[int] = None
):
    """
    Log command execution to database and file logger
    
    Args:
        user_id: Telegram user ID
        command: Command that was executed
        success: Whether command executed successfully
        output_length: Length of stdout output
        error_length: Length of stderr output
        execution_time: Execution time in seconds
        server_id: Server ID if connected
    """
    try:
        # Log to file
        command_logger.info(
            f"User {user_id} executed command: {command[:100]} "
            f"(success={success}, time={execution_time}s)"
        )
        
        # Save to database
        with db_manager.get_session() as session:
            history_entry = CommandHistory(
                user_id=user_id,
                server_id=server_id,
                command=command[:1000],  # Limit command length for storage
                success=success,
                output_length=output_length,
                error_length=error_length,
                execution_time=int(execution_time) if execution_time else None,
                executed_at=datetime.utcnow()
            )
            session.add(history_entry)
            session.commit()
    except Exception as e:
        # Don't fail command execution if logging fails
        command_logger.error(f"Failed to log command execution: {e}", exc_info=True)


def log_security_event(event_type: str, user_id: int, details: str):
    """
    Log security-related events
    
    Args:
        event_type: Type of security event (e.g., 'dangerous_command', 'auth_failure')
        user_id: Telegram user ID
        details: Event details
    """
    security_logger.warning(
        f"Security event [{event_type}] - User {user_id}: {details}"
    )


def log_command_decorator(func):
    """Decorator to automatically log command executions"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        import time
        start_time = time.time()
        
        # Extract user_id and command from arguments
        user_id = kwargs.get('user_id') or (args[1] if len(args) > 1 else None)
        command = kwargs.get('command') or (args[2] if len(args) > 2 else None)
        
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Extract success and output info from result
            if isinstance(result, tuple) and len(result) >= 2:
                success = result[0]
                stdout = result[1] if len(result) > 1 else ""
                stderr = result[2] if len(result) > 2 else ""
                
                log_command_execution(
                    user_id=user_id,
                    command=command or "",
                    success=success,
                    output_length=len(stdout) if stdout else 0,
                    error_length=len(stderr) if stderr else 0,
                    execution_time=execution_time
                )
            
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            log_command_execution(
                user_id=user_id,
                command=command or "",
                success=False,
                error_length=len(str(e)),
                execution_time=execution_time
            )
            raise
    
    return wrapper


