"""Connection management helper functions"""
from telegram.ext import ContextTypes
from ssh.manager import ssh_manager
from utils.constants import (
    ADD_SERVER_KEYS,
    DIRECT_CONNECT_KEYS,
    EDIT_SERVER_KEYS,
    PRESET_KEYS,
)


def clear_conversation_keys(context: ContextTypes.DEFAULT_TYPE, keys: tuple) -> None:
    """Remove only conversation-specific keys from user_data (avoids wiping other state)."""
    for key in keys:
        context.user_data.pop(key, None)


def cancel_ongoing_connection(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any ongoing connection attempt for a user"""
    connecting_key = f"connecting_{user_id}"
    if connecting_key in context.user_data:
        cancel_event = context.user_data[connecting_key]
        if cancel_event:
            cancel_event.set()
            ssh_manager.cancel_connection(user_id)
        del context.user_data[connecting_key]


def clear_add_server_keys(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear keys used by add-server conversation."""
    clear_conversation_keys(context, ADD_SERVER_KEYS)


def clear_direct_connect_keys(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear keys used by direct-connect conversation (and cancel connecting state)."""
    cancel_ongoing_connection(user_id, context)
    clear_conversation_keys(context, DIRECT_CONNECT_KEYS)


def clear_edit_server_keys(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear keys used by edit-server conversation."""
    clear_conversation_keys(context, EDIT_SERVER_KEYS)


def clear_preset_keys(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear keys used by add-preset conversation."""
    clear_conversation_keys(context, PRESET_KEYS)


def clear_all_conversation_keys(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear all conversation-related keys (for generic cancel)."""
    cancel_ongoing_connection(user_id, context)
    clear_conversation_keys(context, ADD_SERVER_KEYS)
    clear_conversation_keys(context, DIRECT_CONNECT_KEYS)
    clear_conversation_keys(context, EDIT_SERVER_KEYS)
    clear_conversation_keys(context, PRESET_KEYS)


