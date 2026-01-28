"""Admin management handlers"""
from telegram import Update
from telegram.ext import ContextTypes
from database.connection import db_manager
from database.models import User, Server, PresetCommand
from config.settings import settings
from utils.keyboards import get_admin_menu_keyboard, get_back_keyboard
from utils.messages import get_error_message
from utils.db_helpers import ensure_user_exists_sync, run_db_operation
from utils.message_helpers import safe_edit_message, safe_reply_or_edit

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Admin menu"""
 query = update.callback_query
 if query:
     await query.answer()
 
 
 user_id = update.effective_user.id
 
 # Check admin access
 if not settings.is_admin(user_id):
     message = "You do not have admin access."
     await safe_reply_or_edit(update, context, message)
     return
 
 message = "*Admin menu*\n\nSelect an option:"
 await safe_reply_or_edit(
     update,
     context,
     message,
     reply_markup=get_admin_menu_keyboard(),
     parse_mode="Markdown"
 )

async def toggle_public_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle public/private bot mode"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Check admin access
    if not settings.is_admin(user_id):
        await query.edit_message_text(
            "You do not have admin access.",
            reply_markup=get_back_keyboard("menu_main")
        )
        return
    
    try:
        # Run database operations in thread to avoid blocking
        def _toggle_public_mode():
            with db_manager.get_session() as session:
                # Get or create admin user
                user = ensure_user_exists_sync(user_id, session)

                # Toggle mode
                user.public_mode_enabled = not user.public_mode_enabled
                # Context manager will commit automatically
                return "enabled" if user.public_mode_enabled else "disabled"
        
        new_status = await run_db_operation(_toggle_public_mode)
        from utils.public_mode_cache import invalidate_public_mode_cache
        invalidate_public_mode_cache()
        message = f"Public mode *{new_status}*."
        
        await safe_edit_message(
            update,
            context,
            message,
            reply_markup=get_back_keyboard("menu_main"),
            parse_mode="Markdown"
        )
    
    except Exception as e:
        await safe_edit_message(
            update,
            context,
            get_error_message(str(e)),
            reply_markup=get_back_keyboard("menu_main"),
            parse_mode="Markdown"
        )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Usage statistics"""
 query = update.callback_query
 if query:
     await query.answer()
 
 user_id = update.effective_user.id
 
 # Check admin access
 if not settings.is_admin(user_id):
     message = "You do not have admin access."
     await safe_reply_or_edit(update, context, message)
     return
 
 try:
     # Run database queries in thread to avoid blocking
     def _get_stats():
         with db_manager.get_session() as session:
             total_users = session.query(User).count()
             total_servers = session.query(Server).count()
             total_presets = session.query(PresetCommand).count()
             
             # Check public mode
             admin_user = session.query(User).filter_by(user_id=user_id).first()
             public_mode = admin_user.public_mode_enabled if admin_user else False
             
             return total_users, total_servers, total_presets, public_mode
     
     total_users, total_servers, total_presets, public_mode = await run_db_operation(_get_stats)
     
     message = f"""
*Bot Statistics*

*Users:* {total_users}
*Servers:* {total_servers}
*Preset Commands:* {total_presets}
*Public Mode:* {'enabled' if public_mode else 'disabled'}
"""

     await safe_reply_or_edit(
         update,
         context,
         message,
         reply_markup=get_back_keyboard("menu_main"),
         parse_mode="Markdown"
     )
 
 except Exception as e:
     error_msg = get_error_message(str(e))
     await safe_reply_or_edit(update, context, error_msg, parse_mode="Markdown")

