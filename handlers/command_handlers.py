"""Command execution handlers"""
import asyncio
import time
import concurrent.futures
import logging
from telegram import Update
from telegram.ext import ContextTypes
from ssh.manager import ssh_manager
from ssh.executor import ssh_executor
from security.validator import validate_command, sanitize_input
from utils.messages import format_command_output, get_error_message, get_warning_message, get_connection_status_message
from utils.keyboards import get_back_keyboard, get_command_output_keyboard
from utils.logger import log_command_execution, log_security_event
from config.settings import settings

logger = logging.getLogger(__name__)

# Thread pool executor for blocking operations
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

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
    
    # Check command execution rate limit
    from bot import check_command_rate_limit
    if not check_command_rate_limit(user_id):
        await update.message.reply_text(
            "⚠️ Rate limit exceeded for command execution. Please wait a moment before executing another command.",
            reply_markup=get_back_keyboard("menu_main")
        )
        return
    
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
        # Log security event for blocked command
        log_security_event("blocked_command", user_id, f"Command blocked: {command[:100]}")
        await update.message.reply_text(
            get_error_message(error or "Invalid command"),
            reply_markup=get_back_keyboard("menu_main"),
            parse_mode="Markdown"
        )
        return
    
    # Show warning if exists
    if warning:
        log_security_event("command_warning", user_id, f"Warning for command: {command[:100]}")
        await update.message.reply_text(
            get_warning_message(warning),
            parse_mode="Markdown"
        )

    # Sanitize command
    cleaned_command = sanitize_input(command)

    # Cancel any previous command execution task for this user
    if f"command_task_{user_id}" in context.user_data:
        prev_task = context.user_data.get(f"command_task_{user_id}")
        if prev_task and not prev_task.done():
            prev_task.cancel()
            # Wait a bit for task to cancel (with timeout)
            try:
                await asyncio.wait_for(prev_task, timeout=0.5)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        # Clear previous command state
        context.user_data[f"command_running_{user_id}"] = False
        # Remove old task reference
        if f"command_task_{user_id}" in context.user_data:
            del context.user_data[f"command_task_{user_id}"]

    # Show initial status - simple message that will be replaced
    status_msg = await update.message.reply_text("⏳ Running...")

    # Store the latest status message for this user - this ensures only latest message updates
    context.user_data[f"latest_status_msg_{user_id}"] = status_msg

    # Store output lines for real-time updates
    output_lines = []
    error_lines = []
    command_start_time = time.time()  # Track when command started
    last_update_time = time.time()
    update_lock = asyncio.Lock()
    update_interval = 0.5  # Update every 0.5 seconds for faster updates
    show_executing_duration = 2.0  # Show "Executing..." for first 2 seconds only
    command_running = True
    context.user_data[f"command_running_{user_id}"] = True
    last_displayed_content = ""  # Track last displayed content to avoid unnecessary updates

    async def update_message_display(force_update=False):
        """Update message with last 4 lines - only update when content changes"""
        nonlocal last_update_time, command_running, output_lines, error_lines, status_msg, command_start_time, show_executing_duration, update_lock, last_displayed_content
        
        # Check if this is still the latest command (don't update old messages)
        if not command_running or not context.user_data.get(f"command_running_{user_id}", False):
            return
        
        # CRITICAL: Only update if this is the latest status message for this user
        # This ensures only the most recent command output updates, not old ones
        latest_msg = context.user_data.get(f"latest_status_msg_{user_id}")
        if latest_msg is None:
            # No latest message stored, don't update
            return
        if latest_msg.message_id != status_msg.message_id:
            # This is an old message from a previous command, don't update it
            return
        
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
                
                # Only update if we have actual output - don't show "no output yet" messages
                if not all_lines:
                    # No output yet, don't update message unnecessarily
                    return
                
                # Get last 4 lines (as requested)
                last_4_lines = all_lines[-4:] if len(all_lines) >= 4 else all_lines
                
                # Format output - escape for HTML (safer than Markdown)
                escaped_lines = []
                for line in last_4_lines:
                    # Escape HTML special characters only
                    escaped_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    escaped_lines.append(escaped_line)
                
                # Simple format - just show output, no "Executing..." message
                code_block_content = "\n".join(escaped_lines)
                display_text = f"<pre><code>{code_block_content}</code></pre>"
                
                # Only update if content has changed (to avoid unnecessary edits)
                # But always update if force_update is True (when new data arrives)
                if display_text == last_displayed_content and not force_update:
                    return
                
                # For force_update, always update even if text seems same (content might have changed)
                # This is important for continuous commands where last 4 lines might be same but new lines added
                
                # Limit length
                if len(display_text) > 4000:
                    display_text = display_text[:4000] + "\n\n... (truncated)"
                
                try:
                    await status_msg.edit_text(
                        display_text,
                        parse_mode="HTML",
                        reply_markup=get_command_output_keyboard()
                    )
                    # Update last displayed content only if edit was successful
                    last_displayed_content = display_text
                except Exception as parse_error:
                    # Handle "Message is not modified" error gracefully
                    error_str = str(parse_error)
                    if "not modified" in error_str.lower():
                        # Message is same, this is fine - just update our tracking
                        last_displayed_content = display_text
                        return
                    # If HTML parsing fails, try with more aggressive escaping
                    try:
                        # More aggressive HTML escaping
                        safe_code_content = "\n".join(escaped_lines).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        safe_display_text = f"<pre><code>{safe_code_content}</code></pre>"
                        if len(safe_display_text) > 4000:
                            safe_display_text = safe_display_text[:4000] + "\n\n... (truncated)"
                        await status_msg.edit_text(
                            safe_display_text,
                            parse_mode="HTML",
                            reply_markup=get_command_output_keyboard()
                        )
                        last_displayed_content = safe_display_text
                    except Exception as e2:
                        # Ignore edit errors to avoid spam
                        logger.debug(f"Failed to edit message with safe HTML: {e2}")
                        pass
                
                # Update timestamp
                last_update_time = time.time()
            except Exception as e:
                # Ignore edit errors (message might be too similar or rate limited)
                logger.debug(f"Error updating message display: {e}")
                pass

    # Background task to update periodically - but only when needed
    async def periodic_update():
        """Periodically check for updates every 0.5 seconds"""
        nonlocal command_running, update_interval, status_msg
        try:
            while command_running and context.user_data.get(f"command_running_{user_id}", False):
                try:
                    await asyncio.sleep(update_interval)  # Wait 0.5 seconds
                except asyncio.CancelledError:
                    # Task was cancelled, exit cleanly
                    break
                except Exception as e:
                    # Event loop might be closed, exit
                    logger.debug(f"Periodic update error: {e}")
                    break
                
                # Check if this is still the latest command
                if not command_running or not context.user_data.get(f"command_running_{user_id}", False):
                    break
                
                try:
                    # CRITICAL: Verify this is still the latest status message
                    # Only update the most recent command output, not old ones
                    latest_msg = context.user_data.get(f"latest_status_msg_{user_id}")
                    if latest_msg is None:
                        # No latest message, stop updating
                        break
                    if latest_msg.message_id == status_msg.message_id:
                        # This is still the latest message, safe to update
                        await update_message_display(force_update=False)
                    else:
                        # This is an old command message, stop updating immediately
                        break
                except asyncio.CancelledError:
                    # Task was cancelled, exit cleanly
                    break
                except Exception as e:
                    # Error updating, exit to avoid hanging
                    logger.debug(f"Error in periodic update loop: {e}")
                    break
        except asyncio.CancelledError:
            # Task was cancelled, this is expected
            pass
        except Exception as e:
            # Any other error, exit cleanly
            logger.debug(f"Periodic update task error: {e}")
            pass

    def output_callback(stdout_chunk: str, stderr_chunk: str):
        """Callback for real-time output updates - triggers immediate update"""
        nonlocal output_lines, error_lines, last_update_time
        
        # Note: In executor, lines are already added to stdout_lines before calling callback
        # So we don't need to add them here - we just trigger the update
        # The callback is called with empty chunks to trigger display refresh
        
        if stdout_chunk:
            # Add new lines to output (if executor didn't add them already)
            for line in stdout_chunk.split('\n'):
                if line.strip():
                    output_lines.append(line)
        
        if stderr_chunk:
            # Add new lines to errors
            for line in stderr_chunk.split('\n'):
                if line.strip():
                    error_lines.append(line)
        
        # Always trigger update when callback is called
        # This ensures display is refreshed with latest content from output_lines
        last_update_time = time.time()
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Force update to refresh display with latest 4 lines
                asyncio.create_task(update_message_display(force_update=True))
        except Exception as e:
            logger.debug(f"Error triggering update in callback: {e}")
            pass

    command_start_time = time.time()
    try:
        # Start periodic update task
        update_task = asyncio.create_task(periodic_update())
        context.user_data[f"command_task_{user_id}"] = update_task
        
        # Execute command with real-time updates in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        success, stdout, stderr = await loop.run_in_executor(
            _executor,
            ssh_executor.execute_command_realtime,
            user_id,
            cleaned_command,
            output_callback
        )
        
        # Log command execution
        execution_time = time.time() - command_start_time
        info = ssh_manager.get_connection_info(user_id)
        server_id = info.get("server_id") if info else None
        
        log_command_execution(
            user_id=user_id,
            command=cleaned_command,
            success=success,
            output_length=len(stdout) if stdout else 0,
            error_length=len(stderr) if stderr else 0,
            execution_time=execution_time,
            server_id=server_id
        )
        
        # Stop periodic update task
        command_running = False
        context.user_data[f"command_running_{user_id}"] = False
        
        # Cancel and wait for update task to finish
        if not update_task.done():
            update_task.cancel()
            try:
                await asyncio.wait_for(update_task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            except Exception as e:
                logger.debug(f"Error cancelling update task: {e}")
                pass
        
        # Clean up task reference
        if f"command_task_{user_id}" in context.user_data:
            del context.user_data[f"command_task_{user_id}"]

        if not success:
            # Escape error message for HTML (safer)
            error_msg = stderr or "Command execution error"
            error_msg = error_msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            # Limit error message length
            if len(error_msg) > 3500:
                error_msg = error_msg[:3500] + "\n\n... (truncated)"
            try:
                await status_msg.edit_text(
                    f"<b>Error:</b>\n<pre><code>{error_msg}</code></pre>",
                    parse_mode="HTML",
                    reply_markup=get_command_output_keyboard()
                )
            except Exception as edit_error:
                logger.warning(f"Failed to edit error message: {edit_error}")
                # If HTML fails, try with simpler HTML
                try:
                    await status_msg.edit_text(
                        f"<b>Error:</b> {error_msg[:1000]}",
                        parse_mode="HTML",
                        reply_markup=get_command_output_keyboard()
                    )
                except Exception as e2:
                    logger.warning(f"Failed to edit error message (fallback): {e2}")
                    # Last resort
                    await status_msg.edit_text(
                        "Command execution error",
                        reply_markup=get_command_output_keyboard()
                    )
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
                reply_markup=get_command_output_keyboard()
            )
        except Exception as html_error:
            logger.warning(f"HTML parsing error: {html_error}")
            # If HTML fails, try to fix and retry with HTML
            try:
                # More aggressive escaping
                if stdout:
                    stdout_escaped = stdout.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
                    if len(stdout_escaped) > 3500:
                        stdout_escaped = "... (truncated)\n\n" + stdout_escaped[-3500:]
                    output_text = f"<b>Output:</b>\n<pre><code>{stdout_escaped}</code></pre>"
                else:
                    output_text = "<b>Output:</b>\n<pre><code>No output</code></pre>"
                
                if stderr:
                    stderr_escaped = stderr.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
                    if len(stderr_escaped) > 3500:
                        stderr_escaped = "... (truncated)\n\n" + stderr_escaped[-3500:]
                    output_text += f"\n\n<b>Error:</b>\n<pre><code>{stderr_escaped}</code></pre>"
                
                if len(output_text) > 4000:
                    output_text = output_text[:4000] + "\n\n... (truncated)"
                
                await status_msg.edit_text(
                    output_text,
                    parse_mode="HTML",
                    reply_markup=get_command_output_keyboard()
                )
            except Exception as e2:
                logger.warning(f"Failed to edit with fixed HTML: {e2}")
                # Last resort: minimal HTML message with keyboard
                try:
                    await status_msg.edit_text(
                        "<b>Command completed</b>\n\n<pre><code>Output too large or parsing error</code></pre>",
                        parse_mode="HTML",
                        reply_markup=get_command_output_keyboard()
                    )
                except Exception as e3:
                    logger.warning(f"Failed to edit with minimal HTML: {e3}")
                    await status_msg.edit_text(
                        "Command completed. Output too large or parsing error.",
                        reply_markup=get_command_output_keyboard()
                    )
    except Exception as e:
        # Log error
        execution_time = time.time() - command_start_time
        logger.error(f"Command execution error for user {user_id}: {e}", exc_info=True)
        
        info = ssh_manager.get_connection_info(user_id)
        server_id = info.get("server_id") if info else None
        
        log_command_execution(
            user_id=user_id,
            command=cleaned_command,
            success=False,
            error_length=len(str(e)),
            execution_time=execution_time,
            server_id=server_id
        )
        
        # Escape error message for HTML (safer)
        error_msg = f"Command execution error: {str(e)}"
        error_msg = error_msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if len(error_msg) > 3500:
            error_msg = error_msg[:3500] + "\n\n... (truncated)"
        try:
            await status_msg.edit_text(
                f"<b>Error:</b>\n<pre><code>{error_msg}</code></pre>",
                parse_mode="HTML",
                reply_markup=get_command_output_keyboard()
            )
        except Exception as edit_error:
            logger.warning(f"Failed to edit error message: {edit_error}")
            # If HTML parsing fails, try simpler HTML
            try:
                await status_msg.edit_text(
                    f"<b>Error:</b> {error_msg[:1000]}",
                    parse_mode="HTML",
                    reply_markup=get_command_output_keyboard()
                )
            except Exception:
                # Last resort
                await status_msg.edit_text(
                    "Command execution error",
                    reply_markup=get_command_output_keyboard()
                )

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
            # Escape input for security (prevent XSS/injection)
            escaped_input = input_text.replace("`", "\\`").replace("*", "\\*").replace("_", "\\_")
            await status_msg.edit_text(
                f"✅ Input sent successfully!\n\nInput: `{escaped_input}`",
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


async def reset_screen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset screen session - close and create new one"""
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
    
    # Get SSH connection
    ssh_client = ssh_manager.get_connection(user_id)
    if not ssh_client:
        message = "Error: No active connection."
        if query:
            await query.edit_message_text(
                message,
                reply_markup=get_back_keyboard("menu_main")
            )
        return
    
    try:
        # Get screen session name from connection info
        info = ssh_manager.get_connection_info(user_id)
        screen_session = info.get("screen_session") if info else None
        
        if not screen_session:
            message = "No active screen session to reset."
            if query:
                await query.edit_message_text(
                    message,
                    reply_markup=get_back_keyboard("menu_main")
                )
            return
        
        # Show processing message
        if query:
            try:
                await query.edit_message_text("🔄 Resetting screen session...")
            except Exception as e:
                logger.debug(f"Error editing reset message: {e}")
                pass
        
        # Run reset operations in thread to avoid blocking
        def _reset_screen_sync():
            """Synchronous reset screen operations"""
            # Kill existing screen session - try multiple methods
            try:
                stdin_kill, stdout_kill, stderr_kill = ssh_client.exec_command(
                    f"screen -S {screen_session} -X quit 2>/dev/null || true",
                    timeout=3
                )
                stdout_kill.read()
                stderr_kill.read()
            except Exception as e:
                logger.debug(f"Error killing screen session: {e}")
                pass
            
            # Also try pkill as backup
            try:
                stdin_pkill, stdout_pkill, stderr_pkill = ssh_client.exec_command(
                    f"pkill -f 'screen.*{screen_session}' 2>/dev/null || true",
                    timeout=2
                )
                stdout_pkill.read()
            except Exception as e:
                logger.debug(f"Error pkill screen session: {e}")
                pass
            
            # Wait a bit for screen to close completely
            time.sleep(1)
            
            # Verify screen is closed
            try:
                stdin_check, stdout_check, stderr_check = ssh_client.exec_command(
                    f"screen -list | grep -q '{screen_session}' && echo 'exists' || echo 'notfound'",
                    timeout=2
                )
                check_result = stdout_check.read().decode('utf-8', errors='replace').strip()
                if check_result == 'exists':
                    # Screen still exists, force kill
                    ssh_client.exec_command(f"pkill -9 -f 'screen.*{screen_session}' 2>/dev/null || true", timeout=2)
                    time.sleep(0.5)
            except Exception as e:
                logger.debug(f"Error force killing screen: {e}")
                pass
            
            # Create new screen session
            stdin_new, stdout_new, stderr_new = ssh_client.exec_command(
                f"screen -dmS {screen_session} bash",
                timeout=3
            )
            stdout_new.read()
            stderr_new.read()
            
            # Wait a bit for screen to initialize
            time.sleep(0.5)
            
            # Verify screen was created
            try:
                stdin_verify, stdout_verify, stderr_verify = ssh_client.exec_command(
                    f"screen -list | grep -q '{screen_session}' && echo 'created' || echo 'failed'",
                    timeout=2
                )
                verify_result = stdout_verify.read().decode('utf-8', errors='replace').strip()
                if verify_result != 'created':
                    raise Exception("Failed to create new screen session")
            except Exception as verify_error:
                raise Exception(f"Screen verification failed: {str(verify_error)}")
            
            # Clear log file
            log_file = f"/tmp/sshbot_log_{user_id}"
            try:
                stdin_clear, stdout_clear, stderr_clear = ssh_client.exec_command(
                    f"rm -f {log_file} 2>/dev/null || true",
                    timeout=2
                )
                stdout_clear.read()
            except Exception as e:
                logger.debug(f"Error clearing log file: {e}")
                pass
        
        # Run in thread
        await asyncio.to_thread(_reset_screen_sync)
        
        message = "✅ Screen session reset successfully!\n\nA new clean screen session has been created."
        
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
        error_msg = f"❌ Error resetting screen: {str(e)}"
        if query:
            await query.edit_message_text(
                error_msg,
                reply_markup=get_back_keyboard("menu_main")
            )
        else:
            await update.message.reply_text(
                error_msg,
                reply_markup=get_back_keyboard("menu_main")
            )
