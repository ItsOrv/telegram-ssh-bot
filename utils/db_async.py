"""Async database operations helper"""
import asyncio
from typing import Callable, TypeVar, Any
from database.connection import db_manager

T = TypeVar('T')


async def run_db_operation(func: Callable[[], T]) -> T:
    """
    Run database operation in thread pool to avoid blocking event loop
    
    Args:
        func: Function that performs database operation (should use db_manager.get_session())
    
    Returns:
        Result of the function
    """
    return await asyncio.to_thread(func)

