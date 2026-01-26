"""Database helper functions to reduce code duplication"""
import asyncio
from typing import Callable, TypeVar, Any
from database.connection import db_manager
from database.models import User
from config.settings import settings

T = TypeVar('T')


def ensure_user_exists_sync(user_id: int, session) -> User:
    """Ensure user exists in database (synchronous version for thread execution)"""
    user = session.query(User).filter_by(user_id=user_id).first()
    if not user:
        user = User(user_id=user_id, is_admin=user_id in settings.ADMIN_IDS)
        session.add(user)
        # Context manager will commit automatically
    return user


async def ensure_user_exists(user_id: int) -> User:
    """Ensure user exists in database (async wrapper)"""
    def _ensure():
        with db_manager.get_session() as session:
            return ensure_user_exists_sync(user_id, session)
    
    return await asyncio.to_thread(_ensure)


async def run_db_operation(operation: Callable[[], T]) -> T:
    """
    Run database operation in thread pool to avoid blocking event loop
    
    Args:
        operation: Function that performs database operation (should use db_manager.get_session())
    
    Returns:
        Result of the operation
    """
    return await asyncio.to_thread(operation)


