"""Command execution handlers"""
from telegram import Update
from telegram.ext import ContextTypes
from ssh.manager import ssh_manager
from ssh.executor import ssh_executor
from security.validator import validate_command, sanitize_input
from utils.messages import format_command_output, get_error_message, get_warning_message, get_connection_status_message
from utils.keyboards import get_back_keyboard
from config.settings import settings


async def execute_command_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command execution menu"""
    query = update.callback_query
    if query:
        await query.answer()
    
    user_id = update.effective_user.id
    
    # Check connection
    if not ssh_manager.is_connected(user_id):
        info = ssh_manager.get_connection_info(user_id)
        message = f"❌ {get_connection_status_message(False)}\n\nPlease connect to a server first."
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
        return
    
    info = ssh_manager.get_connection_info(user_id)
    server_name = info.get("server_name", "Unknown") if info else "Unknown"
    
    message = f"⚡ **Execute Command**\n\n✅ Connected to: **{server_name}**\n\nPlease enter the command:"
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


async def execute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute command"""
    if update.message.chat.type != "private":
        await update.message.reply_text("❌ This command can only be used in private chat.")
        return
    
    user_id = update.effective_user.id
    command = update.message.text.strip()
    
    # Check connection
    if not ssh_manager.is_connected(user_id):
        await update.message.reply_text(
            f"❌ {get_connection_status_message(False)}\n\nPlease connect to a server first.",
            reply_markup=get_back_keyboard("menu_main")
        )
        return
    
    # Validate command
    is_valid, warning, error = validate_command(command)
    
    if not is_valid:
        await update.message.reply_text(
            get_error_message(error or "Invalid command"),
            reply_markup=get_back_keyboard("menu_main"),
            parse_mode="Markdown"
        )
        return
    
    # Show warning if exists
    if warning:
        await update.message.reply_text(
            get_warning_message(warning),
            parse_mode="Markdown"
        )
    
    # Sanitize command
    cleaned_command = sanitize_input(command)
    
    # Show status
    status_msg = await update.message.reply_text("⏳ Executing command...")
    
    try:
        # Execute command
        success, stdout, stderr = ssh_executor.execute_command(user_id, cleaned_command)
        
        if not success:
            await status_msg.edit_text(
                get_error_message(stderr or "Command execution error"),
                parse_mode="Markdown"
            )
            return
        
        # Format output
        output_text = ""
        
        if stdout:
            output_text += f"**Output:**\n{format_command_output(stdout)}\n\n"
        
        if stderr:
            output_text += f"**Error:**\n{format_command_output(stderr)}\n\n"
        
        if not stdout and not stderr:
            output_text = "✅ Command executed successfully (no output)"
        
        # Limit message length (max 4096 characters for Telegram)
        if len(output_text) > 4000:
            output_text = output_text[:4000] + "\n\n... (output truncated)"
        
        await status_msg.edit_text(
            output_text,
            parse_mode="Markdown",
            reply_markup=get_back_keyboard("menu_main")
        )
    
    except Exception as e:
        await status_msg.edit_text(
            get_error_message(f"Command execution error: {str(e)}"),
            parse_mode="Markdown"
        )


async def check_connection_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check connection status"""
    user_id = update.effective_user.id
    
    if ssh_manager.is_connected(user_id):
        info = ssh_manager.get_connection_info(user_id)
        server_name = info.get("server_name", "Unknown") if info else "Unknown"
        message = get_connection_status_message(True, server_name)
    else:
        message = get_connection_status_message(False)
    
    await update.message.reply_text(
        message,
        reply_markup=get_back_keyboard("menu_main"),
        parse_mode="Markdown"
    )
