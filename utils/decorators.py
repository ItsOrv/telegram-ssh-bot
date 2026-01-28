"""Decorators for common handler patterns"""
import functools
from telegram import Update
from telegram.ext import ContextTypes
from ssh.manager import ssh_manager
from utils.messages import get_connection_status_message
from utils.keyboards import get_back_keyboard
from utils.message_helpers import retry_send_message


def require_connection(func):
    """Decorator to require active SSH connection"""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        if not ssh_manager.is_connected(user_id):
            message = f"{get_connection_status_message(False)}\n\nConnect to a server first."
            
            query = update.callback_query
            if query:
                try:
                    await query.answer()
                    await retry_send_message(
                        lambda: query.edit_message_text(
                            message,
                            reply_markup=get_back_keyboard("menu_main"),
                            parse_mode="Markdown"
                        )
                    )
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to send connection required message: {e}")
            else:
                try:
                    if update.effective_message:
                        await retry_send_message(
                            lambda: update.effective_message.reply_text(
                                message,
                                reply_markup=get_back_keyboard("menu_main"),
                                parse_mode="Markdown"
                            )
                        )
                    elif update.message:
                        await retry_send_message(
                            lambda: update.message.reply_text(
                                message,
                                reply_markup=get_back_keyboard("menu_main"),
                                parse_mode="Markdown"
                            )
                        )
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to send connection required message: {e}")
            return None
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper


