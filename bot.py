"""Main entry point for Telegram SSH bot"""
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import (
 Application,
 CommandHandler,
 CallbackQueryHandler,
 MessageHandler,
 ConversationHandler,
 ContextTypes,
 filters
)
from config.settings import settings
from database.connection import db_manager
from database.models import User
from handlers.server_handlers import (
 servers_menu,
 add_server_start,
 add_server_name,
 add_server_host,
 add_server_port,
 add_server_username,
 add_server_password,
 list_servers,
 server_select,
 server_edit,
 edit_field_select,
 edit_field_value,
 server_delete,
 server_delete_confirm,
 server_connect,
 connect_to_server,
 server_disconnect,
 cancel,
 WAITING_SERVER_NAME,
 WAITING_SERVER_HOST,
 WAITING_SERVER_PORT,
 WAITING_SERVER_USERNAME,
 WAITING_SERVER_PASSWORD,
 WAITING_EDIT_VALUE
)
from handlers.command_handlers import (
 execute_command_menu,
 execute_command,
 check_connection_status
)
from handlers.preset_handlers import (
 presets_menu,
 add_preset_start,
 add_preset_name,
 add_preset_command,
 list_presets,
 preset_execute,
 preset_delete,
 preset_delete_confirm,
 cancel_preset,
 WAITING_PRESET_NAME,
 WAITING_PRESET_COMMAND
)
from handlers.admin_handlers import (
 admin_menu,
 toggle_public_mode,
 admin_stats
)
from utils.keyboards import get_main_menu_keyboard
from utils.messages import get_help_message
from ssh.manager import ssh_manager

# Logging settings
logging.basicConfig(
 format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
 level=logging.INFO
)
logger = logging.getLogger(__name__)

# Rate limiting
user_requests = defaultdict(list)

def check_rate_limit(user_id: int) -> bool:
 """Check rate limit"""
 now = datetime.now(timezone.utc)
 minute_ago = now - timedelta(minutes=1)
 
 # Remove old ones
 user_requests[user_id] = [t for t in user_requests[user_id] if t > minute_ago]
 
 if len(user_requests[user_id]) >= settings.RATE_LIMIT_PER_MINUTE:
     return False
 
 user_requests[user_id].append(now)
 return True

async def check_access(update: Update, context) -> bool:
 """Check user access"""
 user_id = update.effective_user.id
 
 # Check rate limit
 if not check_rate_limit(user_id):
     await update.message.reply_text(
         "Rate limit exceeded. Please wait."
     )
     return False
 
 # Check admin access
 if settings.is_admin(user_id):
     return True
 
 # Check public mode
 try:
     with db_manager.get_session() as session:
         admin_user = session.query(User).filter_by(
             user_id=settings.ADMIN_IDS[0] if settings.ADMIN_IDS else 0
         ).first()
 
         if admin_user and admin_user.public_mode_enabled:
             return True
 except:
     pass
 
 # In inactive mode, only admins have access
 await update.message.reply_text(
     "Bot is currently only active for admins."
 )
 return False

async def start_command(update: Update, context):
 """Command /start"""
 if update.message.chat.type != "private":
     await update.message.reply_text("This bot can only be used in private chat.")
     return
 
 # Check access
 if not await check_access(update, context):
     return
 
 user_id = update.effective_user.id
 
 # Create or update user
 try:
     with db_manager.get_session() as session:
         user = session.query(User).filter_by(user_id=user_id).first()
         if not user:
             user = User(
                 user_id=user_id,
                 is_admin=settings.is_admin(user_id)
             )
             session.add(user)
             session.commit()
 except Exception as e:
     logger.error(f"Error creating user: {e}")
 
 welcome_message = """
🤖 *Welcome to SSH Bot!*

This bot allows you to manage and execute commands on SSH servers.

To get started, use the menu below:
"""
 
 is_admin = settings.is_admin(user_id)
 await update.message.reply_text(
 welcome_message,
 reply_markup=get_main_menu_keyboard(is_admin=is_admin),
 parse_mode="Markdown"
 )

async def help_command(update: Update, context):
 """Command /help"""
 if update.message.chat.type != "private":
     await update.message.reply_text("This bot can only be used in private chat.")
     return
 
 # Check access
 if not await check_access(update, context):
     return
 
 user_id = update.effective_user.id
 is_admin = settings.is_admin(user_id)
 
 await update.message.reply_text(
 get_help_message(),
 parse_mode="Markdown",
 reply_markup=get_main_menu_keyboard(is_admin=is_admin)
 )

async def callback_query_handler(update: Update, context):
 """General handler for callback queries"""
 query = update.callback_query
 await query.answer()
 
 data = query.data
 
 # Check access (except for Main menu)
 if data not in ["menu_main", "menu_help"]:
     user_id = update.effective_user.id
     if not settings.is_admin(user_id):
         try:
             with db_manager.get_session() as session:
                 admin_user = session.query(User).filter_by(
                     user_id=settings.ADMIN_IDS[0] if settings.ADMIN_IDS else 0
                 ).first()
 
                 if not (admin_user and admin_user.public_mode_enabled):
                     await query.edit_message_text(
                         "Bot is currently only active for admins."
                     )
                     return
         except:
             await query.edit_message_text(
                 "Error Check access."
             )
             return
 
 # Handle callbacks
 user_id = update.effective_user.id
 is_admin = settings.is_admin(user_id)
 
 if data == "menu_main":
     await query.edit_message_text(
         "🤖 *Main menu*\n\nSelect an option:",
         reply_markup=get_main_menu_keyboard(is_admin=is_admin),
         parse_mode="Markdown"
     )
 elif data == "menu_help":
     await query.edit_message_text(
         get_help_message(),
         reply_markup=get_main_menu_keyboard(is_admin=is_admin),
         parse_mode="Markdown"
     )
 elif data == "menu_servers":
     await servers_menu(update, context)
 elif data == "server_add":
     await add_server_start(update, context)
 elif data == "server_list":
     await list_servers(update, context)
 elif data.startswith("server_select_"):
     await server_select(update, context)
 elif data.startswith("server_edit_"):
     await server_edit(update, context)
 # edit_field_ is managed by ConversationHandler
 elif data.startswith("server_delete_"):
     await server_delete(update, context)
 elif data.startswith("confirm_server_delete_"):
     await server_delete_confirm(update, context)
 elif data == "server_connect":
     await server_connect(update, context)
 elif data.startswith("connect_to_"):
     await connect_to_server(update, context)
 elif data == "server_disconnect":
     await server_disconnect(update, context)
 elif data == "menu_execute":
     await execute_command_menu(update, context)
 elif data == "menu_presets":
     await presets_menu(update, context)
 elif data == "preset_add":
     await add_preset_start(update, context)
 elif data == "preset_list":
     await list_presets(update, context)
 elif data.startswith("preset_execute_"):
     await preset_execute(update, context)
 elif data.startswith("preset_delete_"):
     await preset_delete(update, context)
 elif data.startswith("confirm_preset_delete_"):
     await preset_delete_confirm(update, context)
 elif data == "admin_toggle_public":
     await toggle_public_mode(update, context)
 elif data == "admin_stats":
     await admin_stats(update, context)
 elif data == "admin_menu":
     await admin_menu(update, context)
 elif data.startswith("cancel_"):
     await cancel(update, context)

async def error_handler(update: Update, context):
 """General error handler"""
 logger.error(f"Exception while handling an update: {context.error}")
 
 if update and update.effective_message:
     try:
         await update.effective_message.reply_text(
             "An error occurred. Please try again."
         )
     except:
         pass

async def cleanup_task(context):
 """Periodic cleanup task"""
 try:
     ssh_manager.cleanup_idle_connections()
 except Exception as e:
     logger.error(f"Error in cleanup task: {e}")

def main():
 """Main function"""
 # Validate settings
 is_valid, errors = settings.validate()
 if not is_valid:
     logger.error("Error in settings:")
     for error in errors:
         logger.error(f" - {error}")
     return
 
 # Initialize database
 try:
     db_manager.initialize()
     logger.info("Database initialized")
 except Exception as e:
     logger.error(f"Error Initialize database: {e}")
     return
 
 # Create Application
 application = Application.builder().token(settings.TELEGRAM_TOKEN).build()
 
 # Register handlers
 application.add_handler(CommandHandler("start", start_command))
 application.add_handler(CommandHandler("help", help_command))
 application.add_handler(CommandHandler("status", check_connection_status))
 
 # ConversationHandler for adding server
 add_server_conv = ConversationHandler(
 entry_points=[CallbackQueryHandler(add_server_start, pattern="^server_add$")],
 states={
 WAITING_SERVER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_server_name)],
 WAITING_SERVER_HOST: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_server_host)],
 WAITING_SERVER_PORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_server_port)],
 WAITING_SERVER_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_server_username)],
 WAITING_SERVER_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_server_password)],
 },
 fallbacks=[
 CallbackQueryHandler(cancel, pattern="^cancel_"),
 CallbackQueryHandler(cancel, pattern="^menu_servers$"),
 CommandHandler("cancel", cancel)
 ],
 per_message=False,
 )
 application.add_handler(add_server_conv)
 
 # ConversationHandler for Editing server
 edit_server_conv = ConversationHandler(
 entry_points=[CallbackQueryHandler(edit_field_select, pattern="^edit_field_")],
 states={
 WAITING_EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_field_value)],
 },
 fallbacks=[
 CallbackQueryHandler(cancel, pattern="^cancel_"),
 CallbackQueryHandler(cancel, pattern="^server_select_"),
 CommandHandler("cancel", cancel)
 ],
 per_message=False,
 )
 application.add_handler(edit_server_conv)
 
 # ConversationHandler for adding preset command
 add_preset_conv = ConversationHandler(
 entry_points=[CallbackQueryHandler(add_preset_start, pattern="^preset_add$")],
 states={
 WAITING_PRESET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_preset_name)],
 WAITING_PRESET_COMMAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_preset_command)],
 },
 fallbacks=[
 CallbackQueryHandler(cancel_preset, pattern="^cancel_"),
 CallbackQueryHandler(cancel_preset, pattern="^menu_presets$")
 ],
 per_message=False,
 )
 application.add_handler(add_preset_conv)
 
 # Handler for command execution (must be after conversation handlers)
 async def execute_command_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
     # Skip if user is in conversation
     if context.user_data.get("edit_server_id") or context.user_data.get("new_server_name") or context.user_data.get("new_preset_name"):
         return
     await execute_command(update, context)
 
 application.add_handler(MessageHandler(
 filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
 execute_command_filter
 ))
 
 # Handler for callback queries
 application.add_handler(CallbackQueryHandler(callback_query_handler))
 
 # Error handler
 application.add_error_handler(error_handler)
 
 # Start cleanup task (if job_queue is available)
 if application.job_queue:
     application.job_queue.run_repeating(
         cleanup_task,
         interval=300,
         first=300
     )
     logger.info("Cleanup task scheduled")
 else:
     logger.warning("JobQueue not available, cleanup task disabled")
 
 # Start bot
 logger.info("🚀 bot Starting...")
 application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
 main()

