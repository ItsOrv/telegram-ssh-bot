"""Admin management handlers"""
from telegram import Update
from telegram.ext import ContextTypes
from database.connection import db_manager
from database.models import User
from config.settings import settings
from utils.keyboards import get_admin_menu_keyboard, get_back_keyboard
from utils.messages import get_error_message, get_success_message
from handlers.server_handlers import ensure_user_exists


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin menu"""
    query = update.callback_query
    if query:
        await query.answer()
    
    
    user_id = update.effective_user.id
    
    # Check admin access
    if not settings.is_admin(user_id):
        message = "❌ You do not have admin access."
        if query:
            await query.edit_message_text(message)
        else:
            await update.message.reply_text(message)
        return
    
    if query:
        await query.edit_message_text(
            "⚙️ **Admin menu**\n\nPlease select an option:",
            reply_markup=get_admin_menu_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "⚙️ **Admin menu**\n\nPlease select an option:",
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
            "❌ You do not have admin access.",
            reply_markup=get_back_keyboard("menu_main")
        )
        return
    
    try:
        with db_manager.get_session() as session:
            # Get or create admin user
            user = session.query(User).filter_by(user_id=user_id).first()
            if not user:
                user = await ensure_user_exists(user_id, session)
            
            # Toggle mode
            user.public_mode_enabled = not user.public_mode_enabled
            session.commit()
            
            new_status = "enabled" if user.public_mode_enabled else "disabled"
            message = f"✅ Public mode **{new_status}**."
            
            await query.edit_message_text(
                message,
                reply_markup=get_back_keyboard("menu_main"),
                parse_mode="Markdown"
            )
    
    except Exception as e:
        await query.edit_message_text(
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
        message = "❌ You do not have admin access."
        if query:
            await query.edit_message_text(message)
        else:
            await update.message.reply_text(message)
        return
    
    try:
        with db_manager.get_session() as session:
            total_users = session.query(User).count()
            total_servers = session.query(User).join(User.servers).count()
            total_presets = session.query(User).join(User.preset_commands).count()
            
            # Check public mode
            admin_user = session.query(User).filter_by(user_id=user_id).first()
            public_mode = admin_user.public_mode_enabled if admin_user else False
            
            message = f"""
📊 **Bot Statistics**

👥 **Users:** {total_users}
🖥️ **Servers:** {total_servers}
📝 **Preset Commands:** {total_presets}
🌐 **Public Mode:** {'enabled' if public_mode else 'disabled'}
"""
            
            if query:
                await query.edit_message_text(
                    message,
                    reply_markup=get_back_keyboard("menu_main"),
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    message,
                    reply_markup=get_back_keyboard("menu_main"),
                    parse_mode="Markdown"
                )
    
    except Exception as e:
        error_msg = get_error_message(str(e))
        if query:
            await query.edit_message_text(error_msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(error_msg, parse_mode="Markdown")

