"""Message helper functions to reduce code duplication"""
import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TimedOut, NetworkError
from typing import Optional

logger = logging.getLogger(__name__)


async def retry_send_message(
    send_func,
    max_retries: int = 3,
    initial_delay: float = 1.0
):
    """
    Retry sending a message with exponential backoff on timeout/network errors
    
    Args:
        send_func: Async function that sends the message
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before retry
    
    Returns:
        Result of send_func if successful
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            return await send_func()
        except (TimedOut, NetworkError) as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = initial_delay * (2 ** attempt)
                logger.warning(
                    f"Network error on attempt {attempt + 1}/{max_retries}: {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"Failed to send message after {max_retries} attempts: {e}")
                raise
        except Exception as e:
            # For non-network errors, don't retry
            logger.error(f"Non-retryable error sending message: {e}")
            raise
    
    # Should never reach here, but just in case
    if last_error:
        raise last_error


async def safe_edit_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    reply_markup=None,
    parse_mode: Optional[str] = None
) -> bool:
    """
    Safely edit message with fallback to reply_text if edit fails
    Includes retry logic for network errors
    
    Returns:
        True if message was edited, False if replied
    """
    query = update.callback_query
    
    if not query:
        return False
    
    try:
        # Try to edit with retry
        await retry_send_message(
            lambda: query.edit_message_text(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        )
        return True
    except Exception as e:
        error_str = str(e)
        # Ignore "Message is not modified" error - it means content is already correct
        if "not modified" in error_str.lower():
            logger.debug(f"Message not modified (ignored): {error_str}")
            return True
        
        # For other errors, try to send new message with retry
        logger.warning(f"Error editing message: {e}, trying to send new message")
        try:
            await retry_send_message(
                lambda: query.message.reply_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            )
            return False
        except Exception as e2:
            logger.error(f"Failed to send message after edit error: {e2}")
            return False


async def safe_reply_or_edit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    reply_markup=None,
    parse_mode: Optional[str] = None
):
    """
    Reply to message or edit existing message based on update type
    Includes retry logic for network errors
    """
    query = update.callback_query
    
    if query:
        await safe_edit_message(update, context, text, reply_markup, parse_mode)
    else:
        if update.effective_message:
            await retry_send_message(
                lambda: update.effective_message.reply_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            )
        elif update.message:
            await retry_send_message(
                lambda: update.message.reply_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            )


