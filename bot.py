"""Main entry point for Telegram SSH bot"""
import asyncio
import logging
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
 connect_menu,
 connect_to_server,
 server_disconnect,
 direct_connect_start,
 direct_connect_host,
 direct_connect_port,
 direct_connect_username,
 direct_connect_password,
 cancel,
 cancel_connect,
 WAITING_SERVER_NAME,
 WAITING_SERVER_HOST,
 WAITING_SERVER_PORT,
 WAITING_SERVER_USERNAME,
 WAITING_SERVER_PASSWORD,
 WAITING_EDIT_VALUE,
 WAITING_DIRECT_HOST,
 WAITING_DIRECT_PORT,
 WAITING_DIRECT_USERNAME,
 WAITING_DIRECT_PASSWORD
)
from handlers.command_handlers import (
    execute_command_menu,
    execute_command,
    check_connection_status,
    send_input_menu,
    send_input
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
from utils.message_helpers import retry_send_message
from ssh.manager import ssh_manager

# Logging settings
logging.basicConfig(
 format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
 level=logging.INFO
)
logger = logging.getLogger(__name__)

# Rate limiting
from utils.rate_limiter import check_rate_limit, check_command_rate_limit, cleanup_rate_limits

async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
 """Check user access"""
 user_id = update.effective_user.id
 
 # Check rate limit
 if not check_rate_limit(user_id):
     try:
         await retry_send_message(
             lambda: update.message.reply_text("Rate limit exceeded. Please wait.")
         )
     except Exception as e:
         logger.error(f"Failed to send rate limit message: {e}")
     return False
 
 # Check admin access
 if settings.is_admin(user_id):
     return True
 
 # Check public mode (cached to reduce DB load)
 try:
     from utils.public_mode_cache import get_public_mode_cached
     public_mode_enabled = await get_public_mode_cached()
     if public_mode_enabled:
         return True
 except Exception as e:
     logger.warning(f"Error checking public mode: {e}")
     pass
 
 # In inactive mode, only admins have access
 try:
     await retry_send_message(
         lambda: update.message.reply_text("Bot is currently only active for admins.")
     )
 except Exception as e:
     logger.error(f"Failed to send inactive mode message: {e}")
 return False

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Command /start"""
 if update.message.chat.type != "private":
     try:
         await retry_send_message(
             lambda: update.message.reply_text("This bot can only be used in private chat.")
         )
     except Exception as e:
         logger.error(f"Failed to send private chat message: {e}")
     return
 
 # Check access
 if not await check_access(update, context):
     return
 
 user_id = update.effective_user.id
 
 # Create or update user (run in thread to avoid blocking)
 try:
     def _create_user():
         with db_manager.get_session() as session:
             user = session.query(User).filter_by(user_id=user_id).first()
             if not user:
                 user = User(
                     user_id=user_id,
                     is_admin=settings.is_admin(user_id)
                 )
                 session.add(user)
                 # Context manager will commit automatically
             return user
     
     await asyncio.to_thread(_create_user)
 except Exception as e:
     logger.error(f"Error creating user: {e}")
 
 welcome_message = """
🤖 *Welcome to SSH Bot!*

This bot allows you to manage and execute commands on SSH servers.

To get started, use the menu below:
"""
 
 is_admin = settings.is_admin(user_id)
 try:
     await retry_send_message(
         lambda: update.message.reply_text(
             welcome_message,
             reply_markup=get_main_menu_keyboard(is_admin=is_admin),
             parse_mode="Markdown"
         )
     )
 except Exception as e:
     logger.error(f"Failed to send welcome message: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Command /help"""
 if update.message.chat.type != "private":
     try:
         await retry_send_message(
             lambda: update.message.reply_text("This bot can only be used in private chat.")
         )
     except Exception as e:
         logger.error(f"Failed to send private chat message: {e}")
     return
 
 # Check access
 if not await check_access(update, context):
     return
 
 user_id = update.effective_user.id
 is_admin = settings.is_admin(user_id)
 
 try:
     await retry_send_message(
         lambda: update.message.reply_text(
             get_help_message(),
             parse_mode="Markdown",
             reply_markup=get_main_menu_keyboard(is_admin=is_admin)
         )
     )
 except Exception as e:
     logger.error(f"Failed to send help message: {e}")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """General handler for callback queries"""
 query = update.callback_query
 if not query:
     return
 
 # Answer callback query immediately to prevent timeout
 try:
     await query.answer()
 except Exception as e:
     logger.warning(f"Error answering callback query: {e}")
     # Continue anyway
 
 data = query.data
 
 # Check access (except for Main menu) - use cache to avoid DB on every button click
 if data not in ["menu_main", "menu_help"]:
     user_id = update.effective_user.id
     if not settings.is_admin(user_id):
         try:
             from utils.public_mode_cache import get_public_mode_cached
             public_mode_enabled = await get_public_mode_cached()
             if not public_mode_enabled:
                 from utils.message_helpers import safe_edit_message
                 await safe_edit_message(
                     update,
                     context,
                     "Bot is currently only active for admins."
                 )
                 return
         except Exception as e:
             logger.error(f"Error checking access: {e}")
             from utils.message_helpers import safe_edit_message
             await safe_edit_message(
                 update,
                 context,
                 "Error Check access."
             )
             return
 
 # Handle callbacks
 user_id = update.effective_user.id
 is_admin = settings.is_admin(user_id)
 
 if data == "menu_main":
     welcome_message = "🤖 *Welcome to SSH Bot!*\n\nThis bot allows you to manage and execute commands on SSH servers.\n\nTo get started, use the menu below:"
     from utils.message_helpers import safe_edit_message
     await safe_edit_message(
         update,
         context,
         welcome_message,
         reply_markup=get_main_menu_keyboard(is_admin=is_admin),
         parse_mode="Markdown"
     )
 elif data == "menu_help":
     from utils.message_helpers import safe_edit_message
     await safe_edit_message(
         update,
         context,
         get_help_message(),
         reply_markup=get_main_menu_keyboard(is_admin=is_admin),
         parse_mode="Markdown"
     )
 elif data == "menu_servers":
     # Cancel any ongoing connection
     from utils.connection_helpers import cancel_ongoing_connection
     cancel_ongoing_connection(update.effective_user.id, context)
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
 elif data == "menu_connect":
     # Cancel any ongoing connection
     from utils.connection_helpers import cancel_ongoing_connection
     cancel_ongoing_connection(update.effective_user.id, context)
     await connect_menu(update, context)
 elif data == "server_connect":
     await server_connect(update, context)
 elif data == "direct_connect":
     await direct_connect_start(update, context)
 elif data.startswith("connect_to_"):
     await connect_to_server(update, context)
 elif data == "server_disconnect":
     await server_disconnect(update, context)
 elif data == "cancel_connect":
     await cancel_connect(update, context)
 elif data == "menu_execute":
     await execute_command_menu(update, context)
 elif data == "menu_send_input":
     await send_input_menu(update, context)
 elif data == "reset_screen":
     from handlers.command_handlers import reset_screen
     await reset_screen(update, context)
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

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """General error handler"""
    error = context.error
    error_type = type(error).__name__
    error_msg = str(error) if error else ""
    
    # Always log errors for debugging
    logger.error(f"Exception while handling an update: {error}", exc_info=error)
    
    # Handle specific Telegram errors
    # Check for TimedOut errors (network issues)
    if error_type == "TimedOut" or "TimedOut" in error_msg or "Timed out" in error_msg:
        logger.warning(f"Telegram API timeout error (network issue): {error_msg}")
        # Don't crash on timeout - just log and continue
        return
    
    # Handle other Telegram API errors
    if hasattr(error, 'message'):
        error_msg = str(error.message)
        
        # Ignore common non-critical errors
        if "Message is not modified" in error_msg:
            logger.debug("Message not modified (ignored)")
            return
        if "Query is too old" in error_msg or "query id is invalid" in error_msg:
            logger.debug("Query timeout (ignored)")
            return
        if "Bad Request: message to edit not found" in error_msg:
            logger.debug("Message to edit not found (ignored)")
            return
        if "TimedOut" in error_msg or "Timed out" in error_msg:
            logger.warning(f"Telegram API timeout: {error_msg}")
            return
        
        # For callback queries, try to answer if not already answered
        if update and update.callback_query:
            try:
                await update.callback_query.answer(
                    "⚠️ An error occurred. Please try again.",
                    show_alert=False
                )
            except Exception as e:
                logger.debug(f"Error answering callback query: {e}")
                pass
            return
    
    # For other errors, try to send error message
    if update and update.effective_message:
        try:
            await retry_send_message(
                lambda: update.effective_message.reply_text(
                    "⚠️ An error occurred. Please try again."
                )
            )
        except Exception as e:
            logger.warning(f"Error sending error message: {e}")
            pass

async def cleanup_task(context):
    """Periodic cleanup task"""
    try:
        # run in thread
        await asyncio.to_thread(ssh_manager.cleanup_idle_connections)
        
        # Clean up old log files
        from utils.cleanup import cleanup_old_log_files
        await asyncio.to_thread(cleanup_old_log_files, max_age_hours=24)
        
        # Clean up rate limiting dictionaries
        await asyncio.to_thread(cleanup_rate_limits)
    except Exception as e:
        logger.error(f"Error in cleanup task: {e}")

def main():
    """Main function"""
    import signal
    import sys
    
    # Setup graceful shutdown handler
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal, cleaning up...")
        try:
            ssh_manager.disconnect_all()
            db_manager.close()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
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
    
    # Setup default thread pool executor for asyncio.to_thread to handle concurrent connections
    # Use THREAD_POOL_MAX_WORKERS from settings (env) - default 15 for low-resource servers
    import concurrent.futures
    default_executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=settings.THREAD_POOL_MAX_WORKERS,
        thread_name_prefix="bot_default_executor"
    )
    # Set default executor - create new event loop for main() function
    # Note: In main() function (synchronous), we need to create a new event loop
    # Using new_event_loop() to avoid DeprecationWarning
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_default_executor(default_executor)
    logger.info(f"Default thread pool executor configured with {settings.THREAD_POOL_MAX_WORKERS} workers")
    
    # Create Application with increased timeouts for network issues
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=60,  # Increased for slow networks
        write_timeout=60,  # Increased for slow networks
        connect_timeout=60,  # Increased for slow networks
        pool_timeout=60  # Increased for slow networks
    )
    application = Application.builder().token(settings.TELEGRAM_TOKEN).request(request).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", check_connection_status))
    application.add_handler(CommandHandler("send", send_input))
    
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
    )
    application.add_handler(add_preset_conv)
    
    # ConversationHandler for Direct Connect
    direct_connect_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(direct_connect_start, pattern="^direct_connect$")],
        states={
            WAITING_DIRECT_HOST: [MessageHandler(filters.TEXT & ~filters.COMMAND, direct_connect_host)],
            WAITING_DIRECT_PORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, direct_connect_port)],
            WAITING_DIRECT_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, direct_connect_username)],
            WAITING_DIRECT_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, direct_connect_password)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern="^cancel_"),
            CallbackQueryHandler(cancel, pattern="^menu_connect$"),
            CallbackQueryHandler(cancel, pattern="^menu_main$"),
            CommandHandler("cancel", cancel)
        ],
    )
    application.add_handler(direct_connect_conv)
    
    # Handler for command execution (must be after conversation handlers)
    async def execute_command_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        # If a connection attempt is in progress for this user, don't try to run commands.
        # With background connect tasks, users might send messages while connecting.
        if context.user_data.get(f"connecting_{user_id}") is not None:
            try:
                await retry_send_message(
                    lambda: update.effective_message.reply_text(
                        "🔄 در حال اتصال به سرور هستید. لطفاً صبر کنید یا اتصال را کنسل کنید."
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to send 'connecting' message: {e}")
            return

        # Skip if user is in conversation
        if (context.user_data.get("edit_server_id") or 
            context.user_data.get("new_server_name") or 
            context.user_data.get("new_preset_name") or
            context.user_data.get("direct_host")):
            return
        # Check if waiting for input
        if context.user_data.get("waiting_for_input"):
            await send_input(update, context)
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
    try:
        # Retry initialization up to 5 times with exponential backoff
        import time
        max_init_retries = 5
        for init_attempt in range(max_init_retries):
            try:
                logger.info(f"Initialization attempt {init_attempt + 1}/{max_init_retries}")
                application.run_polling(
                    allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=True,
                    close_loop=False,
                    bootstrap_retries=3  # Retry bootstrap up to 3 times
                )
                break  # Success, exit retry loop
            except Exception as init_error:
                error_type = type(init_error).__name__
                error_msg = str(init_error)
                
                # Check if it's a timeout/network error during initialization
                if (error_type == "TimedOut" or "TimedOut" in error_msg or 
                    "Timed out" in error_msg or "Network" in error_msg):
                    if init_attempt < max_init_retries - 1:
                        wait_time = (2 ** init_attempt) * 5  # 5s, 10s, 20s, 40s, 80s
                        logger.warning(
                            f"Initialization timeout (attempt {init_attempt + 1}/{max_init_retries}). "
                            f"Retrying in {wait_time}s..."
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Failed to initialize after {max_init_retries} attempts: {init_error}")
                        raise
                else:
                    # For non-network errors, don't retry
                    logger.error(f"Non-retryable initialization error: {init_error}")
                    raise
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        
        # Check if it's a network/timeout error - log but don't retry (let process manager handle it)
        if error_type == "TimedOut" or "TimedOut" in error_msg or "Timed out" in error_msg:
            logger.warning(f"Bot stopped due to network timeout: {error_msg}")
            logger.info("Bot will exit. Please restart manually or use a process manager.")
        else:
            # For other errors, log and exit
            logger.error(f"Bot stopped due to error: {e}", exc_info=e)
        raise

if __name__ == "__main__":
 main()

