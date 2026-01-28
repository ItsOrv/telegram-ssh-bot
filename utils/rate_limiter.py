"""Rate limiting utilities"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from config.settings import settings
from utils.constants import COMMAND_RATE_LIMIT_DIVISOR, MIN_COMMAND_RATE_LIMIT

# Rate limiting dictionaries
user_requests = defaultdict(list)
command_executions = defaultdict(list)


def check_rate_limit(user_id: int) -> bool:
    """Check rate limit for general requests"""
    now = datetime.now(timezone.utc)
    minute_ago = now - timedelta(minutes=1)
    
    # Remove old ones
    user_requests[user_id] = [t for t in user_requests[user_id] if t > minute_ago]
    
    if len(user_requests[user_id]) >= settings.RATE_LIMIT_PER_MINUTE:
        return False
    
    user_requests[user_id].append(now)
    return True


def check_command_rate_limit(user_id: int) -> bool:
    """Check rate limit for command execution (more restrictive)"""
    now = datetime.now(timezone.utc)
    minute_ago = now - timedelta(minutes=1)
    
    # Remove old ones
    command_executions[user_id] = [t for t in command_executions[user_id] if t > minute_ago]
    
    # Limit command executions to 10 per minute (more restrictive than general requests)
    command_limit = min(settings.RATE_LIMIT_PER_MINUTE // COMMAND_RATE_LIMIT_DIVISOR, MIN_COMMAND_RATE_LIMIT)
    
    if len(command_executions[user_id]) >= command_limit:
        return False
    
    command_executions[user_id].append(now)
    return True


def cleanup_rate_limits():
    """Clean up old rate limit entries to prevent memory leaks"""
    now = datetime.now(timezone.utc)
    minute_ago = now - timedelta(minutes=1)
    
    # Clean up user_requests
    for user_id in list(user_requests.keys()):
        user_requests[user_id] = [t for t in user_requests[user_id] if t > minute_ago]
        if not user_requests[user_id]:
            del user_requests[user_id]
    
    # Clean up command_executions
    for user_id in list(command_executions.keys()):
        command_executions[user_id] = [t for t in command_executions[user_id] if t > minute_ago]
        if not command_executions[user_id]:
            del command_executions[user_id]


