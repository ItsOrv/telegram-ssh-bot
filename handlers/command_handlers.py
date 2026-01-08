"""Command execution handlers"""
import asyncio
import time
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
     message = f"{get_connection_status_message(False)}\n\nConnect to a server first."
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
 
 # Create keyboard with Send Input button
 from telegram import InlineKeyboardButton, InlineKeyboardMarkup
 keyboard = [
     [InlineKeyboardButton("📤 Send Input", callback_data="menu_send_input")],
     [InlineKeyboardButton("🔙 Back", callback_data="menu_main")]
 ]
 reply_markup = InlineKeyboardMarkup(keyboard)
 
 message = f"*Execute Command*\n\nConnected to: *{server_name}*\n\nEnter command:\n\n💡 Tip: Use /send <input> to send input to interactive commands"
 if query:
     await query.edit_message_text(
         message,
         reply_markup=reply_markup,
         parse_mode="Markdown"
     )
 else:
     await update.message.reply_text(
         message,
         reply_markup=reply_markup,
         parse_mode="Markdown"
     )

async def execute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Execute command with real-time output updates"""
 if update.message.chat.type != "private":
     await update.message.reply_text("This command can only be used in private chat.")
     return
 
 user_id = update.effective_user.id
 command = update.message.text.strip()
 
 # Check connection
 if not ssh_manager.is_connected(user_id):
     await update.message.reply_text(
         f"{get_connection_status_message(False)}\n\nConnect to a server first.",
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
 
 # Show initial status
 status_msg = await update.message.reply_text("Executing command...")
 
 # Store output lines for real-time updates
 output_lines = []
 error_lines = []
 command_start_time = time.time()  # Track when command started
 last_update_time = time.time()
 update_lock = asyncio.Lock()
 update_interval = 2.0  # Update every 2 seconds - always
 show_executing_duration = 2.0  # Show "Executing..." for first 2 seconds only
 command_running = True

 async def update_message_display(force_update=False):
     """Update message with last 4 lines - always update every 2 seconds"""
     nonlocal last_update_time
     async with update_lock:
         try:
             # Get all lines (stdout + stderr combined)
             all_lines = []
             
             # Add stdout lines
             for line in output_lines:
                 all_lines.append(line)
             
             # Add stderr lines with prefix
             for line in error_lines:
                 all_lines.append(f"[ERROR] {line}")
             
             # Check if we should show "Executing..." (only first 2 seconds)
             current_time = time.time()
             elapsed_time = current_time - command_start_time
             show_executing = elapsed_time < show_executing_duration
             
             # Get last 4 lines
             if all_lines:
                 last_4_lines = all_lines[-4:]
             else:
                 # No output yet
                 if show_executing:
                     last_4_lines = ["Waiting for output..."]
                 else:
                     last_4_lines = ["No output yet..."]
             
             # Format output - escape for HTML (safer than Markdown)
             escaped_lines = []
             for line in last_4_lines:
                 # Escape HTML special characters only
                 escaped_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                 escaped_lines.append(escaped_line)
             
             # Format output using HTML - only show "Executing..." for first 2 seconds
             if show_executing:
                 display_text = "<b>Executing...</b>\n\n"
             else:
                 display_text = ""  # No "Executing..." after 2 seconds
             
             # Build display text with code block using HTML
             code_block_content = "\n".join(escaped_lines)
             display_text += f"<pre><code>{code_block_content}</code></pre>"
             
             # Limit length
             if len(display_text) > 4000:
                 display_text = display_text[:4000] + "\n\n... (truncated)"
             
             try:
                 await status_msg.edit_text(
                     display_text,
                     parse_mode="HTML"
                 )
             except Exception as parse_error:
                 # If HTML parsing fails, try without parse_mode (plain text)
                 try:
                     if show_executing:
                         display_text_plain = "Executing...\n\n" + "\n".join(last_4_lines)
                     else:
                         display_text_plain = "\n".join(last_4_lines)
                     if len(display_text_plain) > 4000:
                         display_text_plain = display_text_plain[:4000] + "\n\n... (truncated)"
                     await status_msg.edit_text(display_text_plain)
                 except Exception as e2:
                     # If still fails, try with minimal content
                     try:
                         await status_msg.edit_text("Command output (parsing error)")
                     except:
                         pass  # Ignore if still fails
             
             # Update timestamp
             last_update_time = time.time()
         except Exception as e:
             # Ignore edit errors (message might be too similar or rate limited)
             pass

 # Background task to update every 2 seconds - always update
 async def periodic_update():
     """Periodically update message every 2 seconds"""
     nonlocal command_running, update_interval
     while command_running:
         await asyncio.sleep(update_interval)  # Wait exactly 2 seconds
         if command_running:  # Check again after sleep
             await update_message_display(force_update=True)
 
 def output_callback(stdout_chunk: str, stderr_chunk: str):
     """Callback for real-time output updates"""
     nonlocal output_lines, error_lines, last_update_time
     
     has_new_data = False
     
     if stdout_chunk:
         # Add new lines to output
         for line in stdout_chunk.split('\n'):
             if line.strip():
                 output_lines.append(line)
                 has_new_data = True
     
     if stderr_chunk:
         # Add new lines to errors
         for line in stderr_chunk.split('\n'):
             if line.strip():
                 error_lines.append(line)
                 has_new_data = True
     
     # Update immediately if new data, or trigger periodic update if empty (from executor's 2-second check)
     if has_new_data:
         last_update_time = time.time()
     
     # Always try to update (will check if needed in update_message_display)
     try:
         loop = asyncio.get_event_loop()
         if loop.is_running():
             asyncio.create_task(update_message_display(force_update=has_new_data))
     except:
         pass
 
 try:
     # Start periodic update task
     update_task = asyncio.create_task(periodic_update())
     
     # Execute command with real-time updates
     success, stdout, stderr = ssh_executor.execute_command_realtime(
         user_id, 
         cleaned_command, 
         output_callback
     )
     
     # Stop periodic update task
     command_running = False
     update_task.cancel()
     try:
         await update_task
     except asyncio.CancelledError:
         pass
 
     if not success:
         # Escape error message for HTML (safer)
         error_msg = stderr or "Command execution error"
         error_msg = error_msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
         try:
             await status_msg.edit_text(
                 f"<b>Error:</b> {error_msg}",
                 parse_mode="HTML"
             )
         except:
             # If HTML fails, use plain text
             await status_msg.edit_text(get_error_message(error_msg))
         return
 
     # Final update with complete output - use HTML for safety
     output_text = ""

     if stdout:
         # Escape HTML characters and limit length - show LAST part
         stdout_escaped = stdout.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
         if len(stdout_escaped) > 3500:
             # Get last 3500 characters (most recent output)
             stdout_escaped = "... (output truncated)\n\n" + stdout_escaped[-3500:]
         output_text += f"<b>Output:</b>\n<pre><code>{stdout_escaped}</code></pre>\n\n"

     if stderr:
         # Escape HTML characters and limit length - show LAST part
         stderr_escaped = stderr.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
         if len(stderr_escaped) > 3500:
             # Get last 3500 characters (most recent output)
             stderr_escaped = "... (output truncated)\n\n" + stderr_escaped[-3500:]
         output_text += f"<b>Error:</b>\n<pre><code>{stderr_escaped}</code></pre>\n\n"

     if not stdout and not stderr:
         output_text = "Command executed (no output)"

     # Limit total message length (max 4096 characters for Telegram)
     if len(output_text) > 4000:
         output_text = output_text[:4000] + "\n\n... (output truncated)"

     try:
         await status_msg.edit_text(
             output_text,
             parse_mode="HTML",
             reply_markup=get_back_keyboard("menu_main")
         )
     except Exception as html_error:
         # If HTML fails, use plain text (no parsing) - show LAST part
         output_text_plain = ""
         if stdout:
             if len(stdout) > 3500:
                 stdout_plain = "... (truncated)\n\n" + stdout[-3500:]
             else:
                 stdout_plain = stdout
             output_text_plain += f"Output:\n{stdout_plain}\n\n"
         if stderr:
             if len(stderr) > 3500:
                 stderr_plain = "... (truncated)\n\n" + stderr[-3500:]
             else:
                 stderr_plain = stderr
             output_text_plain += f"Error:\n{stderr_plain}\n\n"
         if not stdout and not stderr:
             output_text_plain = "Command executed (no output)"
         if len(output_text_plain) > 4000:
             output_text_plain = output_text_plain[:4000] + "\n\n... (output truncated)"
         try:
             await status_msg.edit_text(
                 output_text_plain,
                 reply_markup=get_back_keyboard("menu_main")
             )
         except:
             # Last resort: minimal message
             await status_msg.edit_text(
                 "Command completed. Output too large or parsing error.",
                 reply_markup=get_back_keyboard("menu_main")
             )
 
 except Exception as e:
     # Escape error message for HTML (safer)
     error_msg = f"Command execution error: {str(e)}"
     error_msg = error_msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
     try:
         await status_msg.edit_text(
             f"<b>Error:</b> {error_msg}",
             parse_mode="HTML"
         )
     except:
         # If HTML parsing fails, send without parse_mode
         await status_msg.edit_text(get_error_message(error_msg))

async def send_input_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu for sending input to interactive command"""
    query = update.callback_query
    if query:
        await query.answer()
    
    user_id = update.effective_user.id
    
    # Check connection
    if not ssh_manager.is_connected(user_id):
        message = f"{get_connection_status_message(False)}\n\nConnect to a server first."
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
    
    message = f"*Send Input to Screen*\n\nConnected to: *{server_name}*\n\nEnter input to send to the active screen session:"
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
    
    # Set flag to indicate we're waiting for input
    context.user_data["waiting_for_input"] = True

async def send_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send input to active screen session"""
    if update.message.chat.type != "private":
        await update.message.reply_text("This command can only be used in private chat.")
        return
    
    user_id = update.effective_user.id
    
    # Check if we're waiting for input (from menu) or if it's a direct command
    if not context.user_data.get("waiting_for_input") and not update.message.text.startswith("/send"):
        return  # Not in input mode
    
    # Check connection
    if not ssh_manager.is_connected(user_id):
        await update.message.reply_text(
            get_connection_status_message(False),
            reply_markup=get_back_keyboard("menu_main"),
            parse_mode="Markdown"
        )
        context.user_data["waiting_for_input"] = False
        return
    
    # Get input text
    input_text = update.message.text
    if input_text.startswith("/send "):
        input_text = input_text[7:]  # Remove "/send " prefix
    elif input_text.startswith("/send"):
        # Just "/send" without text, wait for next message
        await update.message.reply_text(
            "Please enter the input to send to the screen session:",
            reply_markup=get_back_keyboard("menu_main")
        )
        context.user_data["waiting_for_input"] = True
        return
    
    if not input_text.strip():
        await update.message.reply_text(
            "Input cannot be empty. Please enter the input to send:",
            reply_markup=get_back_keyboard("menu_main")
        )
        return
    
    # Send input to screen session
    status_msg = await update.message.reply_text("Sending input to screen session...")
    
    try:
        success, message = ssh_executor.send_input(user_id, input_text)
        
        if success:
            await status_msg.edit_text(
                f"✅ Input sent successfully!\n\nInput: `{input_text}`",
                reply_markup=get_back_keyboard("menu_main"),
                parse_mode="Markdown"
            )
        else:
            await status_msg.edit_text(
                f"❌ Error sending input: {message}",
                reply_markup=get_back_keyboard("menu_main")
            )
    except Exception as e:
        await status_msg.edit_text(
            f"❌ Error: {str(e)}",
            reply_markup=get_back_keyboard("menu_main")
        )
    
    # Clear waiting flag
    context.user_data["waiting_for_input"] = False

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
