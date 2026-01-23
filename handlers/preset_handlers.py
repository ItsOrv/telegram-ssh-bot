"""Preset command handlers"""
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database.connection import db_manager
from database.models import User, PresetCommand
from security.validator import validate_command, sanitize_input
from ssh.manager import ssh_manager
from ssh.executor import ssh_executor
from utils.keyboards import (
 get_presets_menu_keyboard,
 get_preset_list_keyboard,
 get_back_keyboard,
 get_confirm_keyboard
)
from utils.messages import get_error_message, get_success_message, format_command_output, get_connection_status_message
from config.settings import settings

async def ensure_user_exists(user_id: int, session):
 """Ensure user exists in database"""
 user = session.query(User).filter_by(user_id=user_id).first()
 if not user:
     user = User(user_id=user_id, is_admin=user_id in settings.ADMIN_IDS)
     session.add(user)
     session.commit()
 return user

# States for ConversationHandler
(WAITING_PRESET_NAME, WAITING_PRESET_COMMAND) = range(2)

async def presets_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Preset commands menu"""
 query = update.callback_query
 if query:
     await query.answer()
     await query.edit_message_text(
         "*Preset Commands*\n\nSelect an option:",
         reply_markup=get_presets_menu_keyboard(),
         parse_mode="Markdown"
     )

async def add_preset_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Start adding preset command"""
 query = update.callback_query
 if query:
     await query.answer()
 
 await update.effective_message.reply_text(
     "*Add preset command*\n\nPlease enter command name:",
     reply_markup=get_back_keyboard("menu_presets"),
     parse_mode="Markdown"
 )
 return WAITING_PRESET_NAME

async def add_preset_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Get preset command name"""
 preset_name = update.message.text.strip()
 
 if not preset_name or len(preset_name) > 100:
     await update.message.reply_text(
         "name Invalid command (max 100 chars). Enter again:",
         reply_markup=get_back_keyboard("menu_presets")
     )
     return WAITING_PRESET_NAME
 
 context.user_data["new_preset_name"] = preset_name
 await update.message.reply_text(
 f"Name: *{preset_name}*\n\nEnter command:",
 reply_markup=get_back_keyboard("menu_presets"),
 parse_mode="Markdown"
 )
 return WAITING_PRESET_COMMAND

async def add_preset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get command and save"""
    command = update.message.text.strip()
    preset_name = context.user_data.get("new_preset_name")
    
    # Check command length
    from config.settings import settings
    if len(command) > settings.MAX_COMMAND_LENGTH:
        await update.message.reply_text(
            get_error_message(f"Command length must not exceed {settings.MAX_COMMAND_LENGTH} characters"),
            reply_markup=get_back_keyboard("menu_presets"),
            parse_mode="Markdown"
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    # Check command
    is_valid, warning, error = validate_command(command)
    
    if not is_valid:
        await update.message.reply_text(
            get_error_message(error or "Invalid command"),
            reply_markup=get_back_keyboard("menu_presets"),
            parse_mode="Markdown"
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    # Show warning if exists
    if warning:
        await update.message.reply_text(
            f"*Warning:* {warning}\n\nDo you want to continue?",
            reply_markup=get_back_keyboard("menu_presets"),
            parse_mode="Markdown"
        )
    
    user_id = update.effective_user.id
    
    try:
        # Sanitize command
        cleaned_command = sanitize_input(command)
        
        with db_manager.get_session() as session:
            # Ensure user exists
            user = await ensure_user_exists(user_id, session)
            
            # Create new preset command
            new_preset = PresetCommand(
                user_id=user_id,
                name=preset_name,
                command=cleaned_command
            )
            session.add(new_preset)
            session.commit()
        
        # Clear temporary data
        context.user_data.clear()
        
        await update.message.reply_text(
            f"preset command *{preset_name}* added.",
            reply_markup=get_back_keyboard("menu_presets"),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    except Exception as e:
        await update.message.reply_text(
            get_error_message(f"Error adding command: {str(e)}"),
            reply_markup=get_back_keyboard("menu_presets"),
            parse_mode="Markdown"
        )
        context.user_data.clear()
        return ConversationHandler.END

async def list_presets(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Preset commands list"""
 query = update.callback_query
 if query:
     await query.answer()
 
 user_id = update.effective_user.id
 
 try:
     with db_manager.get_session() as session:
         presets = session.query(PresetCommand).filter_by(user_id=user_id).all()
 
         if not presets:
             message = "No preset commands.\n\nYou can add a new command from the Preset Commands menu."
             if query:
                 await query.edit_message_text(
                     message,
                     reply_markup=get_back_keyboard("menu_presets")
                 )
             else:
                 await update.message.reply_text(
                     message,
                     reply_markup=get_back_keyboard("menu_presets")
                 )
             return
 
         presets_list = [
             {"id": preset.id, "name": preset.name, "command": preset.command}
             for preset in presets
         ]
 
         keyboard = get_preset_list_keyboard(presets_list)
 
         message = "*Preset commands list:*\n\nSelect command:"
         if query:
             await query.edit_message_text(
                 message,
                 reply_markup=keyboard,
                 parse_mode="Markdown"
             )
         else:
             await update.message.reply_text(
                 message,
                 reply_markup=keyboard,
                 parse_mode="Markdown"
             )
 
 except Exception as e:
     error_msg = get_error_message(str(e))
     if query:
         await query.edit_message_text(error_msg, parse_mode="Markdown")
     else:
         await update.message.reply_text(error_msg, parse_mode="Markdown")

async def preset_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute command preset"""
    query = update.callback_query
    await query.answer()
    
    preset_id = int(query.data.split("_")[-1])
    user_id = update.effective_user.id
    
    # Check connection
    if not ssh_manager.is_connected(user_id):
        await query.edit_message_text(
            f"{get_connection_status_message(False)}\n\nConnect to a server first.",
            reply_markup=get_back_keyboard("preset_list"),
            parse_mode="Markdown"
        )
        return
    
    try:
        with db_manager.get_session() as session:
            preset = session.query(PresetCommand).filter_by(id=preset_id, user_id=user_id).first()
            
            if not preset:
                await query.edit_message_text(
                    "Preset command not found.",
                    reply_markup=get_back_keyboard("preset_list")
                )
            return
            
            # Show executing message
            await query.edit_message_text(f"Executing: *{preset.name}*...", parse_mode="Markdown")
            
            # Execute command with logging
            import time
            from utils.logger import log_command_execution
            from ssh.manager import ssh_manager
            
            command_start_time = time.time()
            # Run in thread to avoid blocking event loop
            import asyncio
            success, stdout, stderr = await asyncio.to_thread(ssh_executor.execute_command, user_id, preset.command)
            execution_time = time.time() - command_start_time
            
            # Log command execution
            info = ssh_manager.get_connection_info(user_id)
            server_id = info.get("server_id") if info else None
            
            log_command_execution(
                user_id=user_id,
                command=preset.command,
                success=success,
                output_length=len(stdout) if stdout else 0,
                error_length=len(stderr) if stderr else 0,
                execution_time=execution_time,
                server_id=server_id
            )
            
            if not success:
                await query.edit_message_text(
                    get_error_message(stderr or "Command execution error"),
                    reply_markup=get_back_keyboard("preset_list"),
                    parse_mode="Markdown"
                )
                return
            
            # Format output
            output_text = f"*Command:* `{preset.command}`\n\n"
            
            if stdout:
                output_text += f"*Output:*\n{format_command_output(stdout)}\n\n"
            
            if stderr:
                output_text += f"*Error:*\n{format_command_output(stderr)}\n\n"
            
            if not stdout and not stderr:
                output_text += "Command executed (no output)"
            
            # Limit message length
            if len(output_text) > 4000:
                output_text = output_text[:4000] + "\n\n... (Output truncated)"
            
            await query.edit_message_text(
                output_text,
                parse_mode="Markdown",
                reply_markup=get_back_keyboard("preset_list")
            )
    
    except Exception as e:
        await query.edit_message_text(
            get_error_message(f"Error executing command: {str(e)}"),
            reply_markup=get_back_keyboard("preset_list"),
            parse_mode="Markdown"
        )

async def preset_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Delete preset command (with confirmation)"""
 query = update.callback_query
 await query.answer()
 
 preset_id = int(query.data.split("_")[-1])
 user_id = update.effective_user.id
 
 try:
     with db_manager.get_session() as session:
         preset = session.query(PresetCommand).filter_by(id=preset_id, user_id=user_id).first()
 
         if not preset:
             await query.edit_message_text(
                 "Preset command not found.",
                 reply_markup=get_back_keyboard("preset_list")
             )
             return
 
         context.user_data["delete_preset_id"] = preset_id
         keyboard = get_confirm_keyboard("preset_delete", preset_id)
 
         await query.edit_message_text(
             f"Delete command *{preset.name}*?",
             reply_markup=keyboard,
             parse_mode="Markdown"
         )
 
 except Exception as e:
     await query.edit_message_text(
         get_error_message(str(e)),
         parse_mode="Markdown"
     )

async def preset_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Confirm Delete preset command"""
 query = update.callback_query
 await query.answer()
 
 preset_id = int(query.data.split("_")[-1])
 user_id = update.effective_user.id
 
 try:
     with db_manager.get_session() as session:
         preset = session.query(PresetCommand).filter_by(id=preset_id, user_id=user_id).first()
 
         if not preset:
             await query.edit_message_text(
                 "Preset command not found.",
                 reply_markup=get_back_keyboard("preset_list")
             )
             return
 
         preset_name = preset.name
         session.delete(preset)
         session.commit()
 
         await query.edit_message_text(
             f"preset command *{preset_name}* deleted.",
             reply_markup=get_back_keyboard("preset_list"),
             parse_mode="Markdown"
         )
 
 except Exception as e:
     await query.edit_message_text(
         get_error_message(str(e)),
         parse_mode="Markdown"
     )

async def cancel_preset(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Cancel operation"""
 query = update.callback_query
 if query:
     await query.answer()
 
 context.user_data.clear()
 
 message = "Operation cancelled."
 if query:
     await query.edit_message_text(message)
 else:
     await update.message.reply_text(message)
 
 return ConversationHandler.END

