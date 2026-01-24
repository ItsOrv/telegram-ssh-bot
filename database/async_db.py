"""Async database operations wrapper"""
import asyncio
from typing import Callable, Any
from database.connection import db_manager


async def run_db_operation(func: Callable) -> Any:
    """
    Run database operation in thread pool to avoid blocking event loop
    
    Args:
        func: Function that performs database operation (should use db_manager.get_session())
    
    Returns:
        Result of the function
    """
    return await asyncio.to_thread(func)


def db_operation(func: Callable) -> Callable:
    """
    Decorator to automatically run database operations in thread pool
    """
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    return wrapper

