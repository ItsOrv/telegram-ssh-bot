"""Server management handlers"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import logging
import asyncio
from database.connection import db_manager
from database.models import Server
from security.encryption import encrypt_password
from security.validator import validate_server_info, validate_ip, validate_port, validate_hostname
from ssh.manager import ssh_manager
from utils.keyboards import (
 get_servers_menu_keyboard,
 get_server_list_keyboard,
 get_server_actions_keyboard,
 get_confirm_keyboard,
 get_back_keyboard,
 get_connect_menu_keyboard,
 get_cancel_connect_keyboard
)
from utils.messages import (
 get_server_info_message,
 get_connection_status_message,
 get_error_message
)
from utils.db_helpers import ensure_user_exists_sync, run_db_operation
from utils.message_helpers import safe_edit_message, safe_reply_or_edit
from utils.connection_helpers import (
    clear_add_server_keys,
    clear_direct_connect_keys,
    clear_edit_server_keys,
    clear_all_conversation_keys,
)

logger = logging.getLogger(__name__)
from config.settings import settings

# States for ConversationHandler
(WAITING_SERVER_NAME, WAITING_SERVER_HOST, WAITING_SERVER_PORT,
 WAITING_SERVER_USERNAME, WAITING_SERVER_PASSWORD,
 WAITING_EDIT_VALUE,
 WAITING_DIRECT_HOST, WAITING_DIRECT_PORT, WAITING_DIRECT_USERNAME, WAITING_DIRECT_PASSWORD) = range(10)

async def servers_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Server management menu"""
 if update.message and update.message.chat.type != "private":
     await update.message.reply_text("This command can only be used in private chat.")
     return
 
 query = update.callback_query
 if query:
     await query.answer()
     await safe_edit_message(
         update,
         context,
         "*Server Management*\n\nSelect an option:",
         reply_markup=get_servers_menu_keyboard(),
         parse_mode="Markdown"
     )

async def add_server_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Start adding server"""
 query = update.callback_query
 if query:
     await query.answer()
 
 await update.effective_message.reply_text(
     "*Add new server*\n\nEnter server name:",
     reply_markup=get_back_keyboard("menu_servers"),
     parse_mode="Markdown"
 )
 return WAITING_SERVER_NAME

async def add_server_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Get server name"""
 server_name = update.message.text.strip()
 if len(server_name) > 100:
     await update.message.reply_text(
         "Server name max 100 characters. Enter again:",
         reply_markup=get_back_keyboard("menu_servers")
     )
     return WAITING_SERVER_NAME
 
 context.user_data["new_server_name"] = server_name
 await update.message.reply_text(
 f"Name: *{server_name}*\n\nEnter IP or hostname:",
 reply_markup=get_back_keyboard("menu_servers"),
 parse_mode="Markdown"
 )
 return WAITING_SERVER_HOST

async def add_server_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get Host"""
    host = update.message.text.strip()
    
    # Validate host (IP or hostname)
    is_valid_ip, ip_error = validate_ip(host)
    if not is_valid_ip:
        is_valid_hostname, hostname_error = validate_hostname(host)
        if not is_valid_hostname:
            await update.message.reply_text(
                f"Invalid IP address or hostname: {hostname_error or ip_error}. Enter again:",
                reply_markup=get_back_keyboard("menu_servers")
            )
            return WAITING_SERVER_HOST
    
    context.user_data["new_server_host"] = host
    await update.message.reply_text(
        f"Host: *{host}*\n\nEnter port (default: 22):",
        reply_markup=get_back_keyboard("menu_servers"),
        parse_mode="Markdown"
    )
    return WAITING_SERVER_PORT

async def add_server_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Get port"""
 port_text = update.message.text.strip()
 
 if not port_text:
     port = 22
 else:
     try:
         port = int(port_text)
         is_valid, error = validate_port(port)
         if not is_valid:
             await update.message.reply_text(
                 f"{error}\n\nEnter again:",
                 reply_markup=get_back_keyboard("menu_servers")
             )
             return WAITING_SERVER_PORT
     except ValueError:
         await update.message.reply_text(
             "Port must be a number. Enter again:",
             reply_markup=get_back_keyboard("menu_servers")
         )
         return WAITING_SERVER_PORT
 
 context.user_data["new_server_port"] = port
 await update.message.reply_text(
 f"Port: *{port}*\n\nEnter username:",
 reply_markup=get_back_keyboard("menu_servers"),
 parse_mode="Markdown"
 )
 return WAITING_SERVER_USERNAME

async def add_server_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Get username"""
 username = update.message.text.strip()
 
 if not username or len(username) > 100:
     await update.message.reply_text(
         "Invalid username. Enter again:",
         reply_markup=get_back_keyboard("menu_servers")
     )
     return WAITING_SERVER_USERNAME
 
 context.user_data["new_server_username"] = username
 await update.message.reply_text(
 f"Username: *{username}*\n\nEnter password:",
 reply_markup=get_back_keyboard("menu_servers"),
 parse_mode="Markdown"
 )
 return WAITING_SERVER_PASSWORD

async def add_server_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Get password and save server"""
 password = update.message.text
 
 # Collect information
 server_name = context.user_data.get("new_server_name")
 host = context.user_data.get("new_server_host")
 port = context.user_data.get("new_server_port", 22)
 username = context.user_data.get("new_server_username")
 
 # Full validation
 is_valid, error = validate_server_info(host, port, username, password)
 if not is_valid:
     await update.message.reply_text(
         f"{error}\n\nPlease start again.",
         reply_markup=get_back_keyboard("menu_servers")
     )
     context.user_data.clear()
     return ConversationHandler.END
 
 user_id = update.effective_user.id
 
 try:
     # Encrypt password first (before database operation)
     encrypted_password = encrypt_password(user_id, password)
     
     # Run database operation in thread to avoid blocking
     def _add_server():
         with db_manager.get_session() as session:
             # Ensure user exists
             ensure_user_exists_sync(user_id, session)
             
             # Create new server
             new_server = Server(
                 user_id=user_id,
                 name=server_name,
                 host=host,
                 port=port,
                 username=username,
                 encrypted_password=encrypted_password
             )
             session.add(new_server)
             # Context manager will commit automatically
     
     await run_db_operation(_add_server)

     clear_add_server_keys(context)

     await update.message.reply_text(
         f"server *{server_name}* added.",
         reply_markup=get_back_keyboard("menu_servers"),
         parse_mode="Markdown"
     )
     return ConversationHandler.END
 
 except Exception as e:
     await update.message.reply_text(
         f"Error adding server: {str(e)}",
         reply_markup=get_back_keyboard("menu_servers")
     )
     clear_add_server_keys(context)
     return ConversationHandler.END

async def list_servers(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Server list"""
 query = update.callback_query
 if query:
     await query.answer()
 
 user_id = update.effective_user.id
 
 try:
     # Extract server data while still in session context
     def _get_servers_data():
         with db_manager.get_session() as session:
             servers = session.query(Server).filter_by(user_id=user_id).all()
             # Extract all needed data while session is active
             return [{"id": server.id, "name": server.name} for server in servers]
     
     servers_list = await run_db_operation(_get_servers_data)

     if not servers_list:
         message = "No servers.\n\nYou can add a new server from the Server Management menu."
         await safe_reply_or_edit(
             update,
             context,
             message,
             reply_markup=get_back_keyboard("menu_servers")
         )
         return

     keyboard = get_server_list_keyboard(servers_list, "server_select")
 
     message = "*Server list:*\n\nSelect server:"
     await safe_reply_or_edit(
         update,
         context,
         message,
         reply_markup=keyboard,
         parse_mode="Markdown"
     )
 
 except Exception as e:
     error_msg = get_error_message(str(e))
     await safe_reply_or_edit(update, context, error_msg, parse_mode="Markdown")

async def server_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Select server"""
 query = update.callback_query
 await query.answer()
 
 server_id = int(query.data.split("_")[-1])
 user_id = update.effective_user.id
 
 try:
     # Run database query in thread to avoid blocking
    def _get_server_data():
        with db_manager.get_session() as session:
            server = session.query(Server).filter_by(id=server_id, user_id=user_id).first()
            if not server:
                return None
            # Extract data while session is active
            return {
                "name": server.name,
                "host": server.host,
                "port": server.port,
                "username": server.username
            }
    
    server_data = await run_db_operation(_get_server_data)

    if not server_data:
        await query.edit_message_text(
            "Server not found.",
            reply_markup=get_back_keyboard("server_list")
        )
        return

    message = get_server_info_message(server_data["name"], server_data["host"], server_data["port"], server_data["username"])
    keyboard = get_server_actions_keyboard(server_id)

    await query.edit_message_text(
        message,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
 
 except Exception as e:
     await query.edit_message_text(
         get_error_message(str(e)),
         parse_mode="Markdown"
     )

async def server_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete server (with confirmation)"""
    query = update.callback_query
    await query.answer()
    
    server_id = int(query.data.split("_")[-1])
    user_id = update.effective_user.id
    
    try:
        # Run database query in thread to avoid blocking
        def _get_server_name():
            with db_manager.get_session() as session:
                server = session.query(Server).filter_by(id=server_id, user_id=user_id).first()
                if not server:
                    return None
                # Extract name while session is active
                return server.name
        
        server_name = await run_db_operation(_get_server_name)

        if not server_name:
            await query.edit_message_text(
                "Server not found.",
                reply_markup=get_back_keyboard("server_list")
            )
            return

        context.user_data["delete_server_id"] = server_id
        keyboard = get_confirm_keyboard("server_delete", server_id)

        await query.edit_message_text(
            f"Delete server *{server_name}*?",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    except Exception as e:
        await query.edit_message_text(
            get_error_message(str(e)),
            parse_mode="Markdown"
        )

async def server_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Confirm Delete server"""
 query = update.callback_query
 await query.answer()
 
 server_id = int(query.data.split("_")[-1])
 user_id = update.effective_user.id
 
 try:
     # Run database operation in thread to avoid blocking
     def _delete_server():
         with db_manager.get_session() as session:
             server = session.query(Server).filter_by(id=server_id, user_id=user_id).first()
             if server:
                 server_name = server.name
                 session.delete(server)
                 # Context manager will commit automatically
                 return server_name
             return None
     
     server_name = await run_db_operation(_delete_server)
     
     if not server_name:
         await query.edit_message_text(
             "Server not found.",
             reply_markup=get_back_keyboard("server_list"),
             parse_mode="Markdown"
         )
         return
     
     await safe_edit_message(
         update,
         context,
         f"server *{server_name}* deleted.",
         reply_markup=get_back_keyboard("server_list"),
         parse_mode="Markdown"
     )
 
 except Exception as e:
     await query.edit_message_text(
         get_error_message(str(e)),
         parse_mode="Markdown"
     )

async def connect_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Connect menu - shows Direct Connect and saved servers"""
    query = update.callback_query
    if query:
        await query.answer()
    
    user_id = update.effective_user.id
    
    # Check existing connection
    if ssh_manager.is_connected(user_id):
        info = ssh_manager.get_connection_info(user_id)
        server_name = info.get("server_name", "Unknown") if info else "Unknown"
        message = f"You are already connected to: {server_name}\n\nDisconnect first to connect to another server."
        if query:
            await query.edit_message_text(
                message,
                reply_markup=get_back_keyboard("menu_main"),
                parse_mode="Markdown"
            )
        else:
            await update.effective_message.reply_text(
                message,
                reply_markup=get_back_keyboard("menu_main"),
                parse_mode="Markdown"
            )
        return
    
    try:
        # db in thread
        def _get_servers_data():
            with db_manager.get_session() as session:
                servers = session.query(Server).filter_by(user_id=user_id).all()
                # Extract data while session is active
                return [{"id": server.id, "name": server.name} for server in servers]
        
        servers_list = await run_db_operation(_get_servers_data)
        
        keyboard = get_connect_menu_keyboard(servers_list)
        
        message = "*Connect to Server*\n\nSelect a saved server or use Direct Connect:"
        await safe_reply_or_edit(
            update,
            context,
            message,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    except Exception as e:
        error_msg = get_error_message(str(e))
        await safe_reply_or_edit(update, context, error_msg, parse_mode="Markdown")

async def server_connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Connect to server (legacy - redirects to connect_menu)"""
    await connect_menu(update, context)

async def direct_connect_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start direct connect process"""
    query = update.callback_query
    if query:
        await query.answer()
    
    user_id = update.effective_user.id
    
    # Check existing connection or ongoing connection attempt
    if ssh_manager.is_connected(user_id):
        info = ssh_manager.get_connection_info(user_id)
        server_name = info.get("server_name", "Unknown") if info else "Unknown"
        message = f"You are already connected to: {server_name}\n\nDisconnect first to connect to another server."
        if query:
            await query.edit_message_text(
                message,
                reply_markup=get_back_keyboard("menu_connect"),
                parse_mode="Markdown"
            )
        return ConversationHandler.END
    
    # Check if connection attempt is in progress
    if f"connecting_{user_id}" in context.user_data:
        message = "A connection attempt is already in progress. Please wait or cancel it first."
        if query:
            await query.edit_message_text(
                message,
                reply_markup=get_back_keyboard("menu_connect"),
                parse_mode="Markdown"
            )
        return ConversationHandler.END
    
    if query:
        await query.edit_message_text(
            "*Direct Connect*\n\nEnter IP address or hostname:",
            reply_markup=get_back_keyboard("menu_connect"),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "*Direct Connect*\n\nEnter IP address or hostname:",
            reply_markup=get_back_keyboard("menu_connect"),
            parse_mode="Markdown"
        )
    
    return WAITING_DIRECT_HOST

async def direct_connect_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get host for direct connect"""
    host = update.message.text.strip()
    
    # Validate host (IP or hostname)
    is_valid_ip, ip_error = validate_ip(host)
    if not is_valid_ip:
        is_valid_hostname, hostname_error = validate_hostname(host)
        if not is_valid_hostname:
            await update.message.reply_text(
                f"Invalid IP address or hostname: {hostname_error or ip_error}. Enter again:",
                reply_markup=get_back_keyboard("menu_connect")
            )
            return WAITING_DIRECT_HOST
    
    context.user_data["direct_host"] = host
    await update.message.reply_text(
        f"Host: *{host}*\n\nEnter port (default: 22):",
        reply_markup=get_back_keyboard("menu_connect"),
        parse_mode="Markdown"
    )
    return WAITING_DIRECT_PORT

async def direct_connect_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get port for direct connect"""
    port_text = update.message.text.strip()
    
    if not port_text:
        port = 22
    else:
        try:
            port = int(port_text)
            is_valid, error = validate_port(port)
            if not is_valid:
                await update.message.reply_text(
                    f"{error}\n\nEnter again:",
                    reply_markup=get_back_keyboard("menu_connect")
                )
                return WAITING_DIRECT_PORT
        except ValueError:
            await update.message.reply_text(
                "Port must be a number. Enter again:",
                reply_markup=get_back_keyboard("menu_connect")
            )
            return WAITING_DIRECT_PORT
    
    context.user_data["direct_port"] = port
    await update.message.reply_text(
        f"Port: *{port}*\n\nEnter username:",
        reply_markup=get_back_keyboard("menu_connect"),
        parse_mode="Markdown"
    )
    return WAITING_DIRECT_USERNAME

async def direct_connect_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get username for direct connect"""
    username = update.message.text.strip()
    
    if not username or len(username) > 100:
        await update.message.reply_text(
            "Invalid username. Enter again:",
            reply_markup=get_back_keyboard("menu_connect")
        )
        return WAITING_DIRECT_USERNAME
    
    context.user_data["direct_username"] = username
    await update.message.reply_text(
        f"Username: *{username}*\n\nEnter password:",
        reply_markup=get_back_keyboard("menu_connect"),
        parse_mode="Markdown"
    )
    return WAITING_DIRECT_PASSWORD

async def direct_connect_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get password and connect"""
    password = update.message.text.strip()
    
    if not password:
        await update.message.reply_text(
            "Password cannot be empty. Enter again:",
            reply_markup=get_back_keyboard("menu_connect")
        )
        return WAITING_DIRECT_PASSWORD
    
    user_id = update.effective_user.id
    
    # Check if already connected or connecting
    if ssh_manager.is_connected(user_id):
        info = ssh_manager.get_connection_info(user_id)
        server_name = info.get("server_name", "Unknown") if info else "Unknown"
        await update.message.reply_text(
            f"You are already connected to: {server_name}\n\nDisconnect first to connect to another server.",
            reply_markup=get_back_keyboard("menu_connect"),
            parse_mode="Markdown"
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    # Check if connection attempt is in progress
    if f"connecting_{user_id}" in context.user_data:
        await update.message.reply_text(
            "A connection attempt is already in progress. Please wait or cancel it first.",
            reply_markup=get_back_keyboard("menu_connect"),
            parse_mode="Markdown"
        )
        return WAITING_DIRECT_PASSWORD
    
    host = context.user_data.get("direct_host")
    port = context.user_data.get("direct_port", 22)
    username = context.user_data.get("direct_username")
    
    if not all([host, username, password]):
        await update.message.reply_text(
            "Error: Missing information. Please try again.",
            reply_markup=get_back_keyboard("menu_connect")
        )
        clear_direct_connect_keys(user_id, context)
        return ConversationHandler.END
    
    # Create temporary server data dict for connection
    temp_server_data = {
        "id": 0,  # Temporary ID
        "name": "Direct Connection",
        "host": host,
        "port": port,
        "username": username,
        "encrypted_password": encrypt_password(user_id, password)
    }
    
    # Show connecting message first
    connecting_msg = await update.message.reply_text(
        f"🔄 Connecting to {host}...",
        reply_markup=get_cancel_connect_keyboard(),
        parse_mode="Markdown"
    )
    
    # Create cancel event for this connection
    import threading
    cancel_event = threading.Event()
    context.user_data[f"connecting_{user_id}"] = cancel_event
    
    # IMPORTANT: Don't await the (potentially slow) connect here.
    # PTB processes updates sequentially by default, so awaiting connect would "freeze" the bot for other messages.
    async def _do_connect_direct():
        try:
            success, message = await asyncio.to_thread(
                ssh_manager.connect,
                user_id,
                temp_server_data,
                cancel_event=cancel_event
            )

            # Format message based on success
            if success:
                formatted_message = f"✅ {message}"
                keyboard = get_back_keyboard("menu_main")
            else:
                formatted_message = f"❌ {message}"
                keyboard = get_back_keyboard("menu_connect")

            # Edit connecting message with result
            try:
                await connecting_msg.edit_text(
                    formatted_message,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
            except Exception as edit_error:
                # If edit fails, try to send new message
                error_str = str(edit_error)
                if "not modified" not in error_str.lower():
                    try:
                        await update.message.reply_text(
                            formatted_message,
                            reply_markup=keyboard,
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.warning(f"Error sending connection message: {e}")
        except Exception as e:
            error_msg = get_error_message(f"Connection error: {str(e)}")
            try:
                await connecting_msg.edit_text(
                    error_msg,
                    reply_markup=get_back_keyboard("menu_connect"),
                    parse_mode="Markdown"
                )
            except Exception:
                try:
                    await update.message.reply_text(
                        error_msg,
                        reply_markup=get_back_keyboard("menu_connect"),
                        parse_mode="Markdown"
                    )
                except Exception as e2:
                    logger.warning(f"Error sending error message: {e2}")
        finally:
            # Clean up only keys related to direct connect flow
            context.user_data.pop(f"connecting_{user_id}", None)
            context.user_data.pop("direct_host", None)
            context.user_data.pop("direct_port", None)
            context.user_data.pop("direct_username", None)
            context.user_data.pop("direct_password", None)

    # Schedule in background so the bot stays responsive
    context.application.create_task(_do_connect_direct())
    return ConversationHandler.END

async def connect_to_server(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Connect to server selected"""
    query = update.callback_query
    await query.answer()
    
    server_id = int(query.data.split("_")[-1])
    user_id = update.effective_user.id
    
    # Check if already connected or connecting
    if ssh_manager.is_connected(user_id):
        info = ssh_manager.get_connection_info(user_id)
        server_name = info.get("server_name", "Unknown") if info else "Unknown"
        await query.edit_message_text(
            f"You are already connected to: {server_name}\n\nDisconnect first to connect to another server.",
            reply_markup=get_back_keyboard("menu_servers"),
            parse_mode="Markdown"
        )
        return
    
    # Check if connection attempt is in progress
    if f"connecting_{user_id}" in context.user_data:
        await query.edit_message_text(
            "A connection attempt is already in progress. Please wait or cancel it first.",
            reply_markup=get_back_keyboard("menu_servers"),
            parse_mode="Markdown"
        )
        return
    
    try:
        # Run database query in thread to avoid blocking and extract data
        def _get_server_data():
            with db_manager.get_session() as session:
                server = session.query(Server).filter_by(id=server_id, user_id=user_id).first()
                if not server:
                    return None
                # Extract all needed data while session is active
                return {
                    "id": server.id,
                    "name": server.name,
                    "host": server.host,
                    "port": server.port,
                    "username": server.username,
                    "encrypted_password": server.encrypted_password
                }
        
        server_data = await run_db_operation(_get_server_data)
        
        if not server_data:
            await query.edit_message_text(
                "Server not found.",
                reply_markup=get_back_keyboard("menu_servers")
            )
            return
        
        # Show connecting message first
        try:
            await query.edit_message_text(
                f"🔄 Connecting to {server_data['name']}...",
                reply_markup=get_cancel_connect_keyboard(),
                parse_mode="Markdown"
            )
        except Exception:
            # Ignore if message is same or edit fails
            pass
        
        # Create cancel event for this connection
        import threading
        cancel_event = threading.Event()
        context.user_data[f"connecting_{user_id}"] = cancel_event
        
        # IMPORTANT: Don't await connect here; run it in background so bot remains responsive.
        async def _do_connect_saved_server():
            try:
                success, message = await asyncio.to_thread(
                    ssh_manager.connect,
                    user_id,
                    server_data,
                    cancel_event=cancel_event
                )

                formatted_message = f"✅ {message}" if success else f"❌ {message}"
                await safe_edit_message(
                    update,
                    context,
                    formatted_message,
                    reply_markup=get_back_keyboard("menu_main") if success else get_back_keyboard("menu_servers"),
                    parse_mode="Markdown"
                )
            except Exception as e:
                error_msg = get_error_message(str(e))
                await safe_edit_message(
                    update,
                    context,
                    error_msg,
                    reply_markup=get_back_keyboard("menu_servers"),
                    parse_mode="Markdown"
                )
            finally:
                context.user_data.pop(f"connecting_{user_id}", None)

        context.application.create_task(_do_connect_saved_server())
        return
    
    except Exception as e:
        error_msg = get_error_message(str(e))
        await safe_edit_message(
            update,
            context,
            error_msg,
            reply_markup=get_back_keyboard("menu_servers"),
            parse_mode="Markdown"
        )

async def server_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Disconnect"""
 query = update.callback_query
 if query:
     await query.answer()
 
 user_id = update.effective_user.id
 
 # disconnect in thread
 success, message = await asyncio.to_thread(ssh_manager.disconnect, user_id)
 
 if query:
     await safe_edit_message(
         update,
         context,
         message,
         reply_markup=get_back_keyboard("menu_main"),
         parse_mode="Markdown"
     )
 else:
     await safe_reply_or_edit(
         update,
         context,
         message,
         reply_markup=get_back_keyboard("menu_servers"),
         parse_mode="Markdown"
     )

async def server_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Editing server"""
    query = update.callback_query
    await query.answer()
    
    server_id = int(query.data.split("_")[-1])
    user_id = update.effective_user.id
    
    try:
        # Run database query in thread to avoid blocking
        def _get_server_name():
            with db_manager.get_session() as session:
                server = session.query(Server).filter_by(id=server_id, user_id=user_id).first()
                if not server:
                    return None
                # Extract name while session is active
                return server.name
        
        server_name = await run_db_operation(_get_server_name)

        if not server_name:
            await query.edit_message_text(
                "Server not found.",
                reply_markup=get_back_keyboard("server_list")
            )
            return

        context.user_data["edit_server_id"] = server_id
        
        keyboard = [
            [
                InlineKeyboardButton("name", callback_data=f"edit_field_name_{server_id}"),
                InlineKeyboardButton("Host", callback_data=f"edit_field_host_{server_id}")
            ],
            [
                InlineKeyboardButton("Port", callback_data=f"edit_field_port_{server_id}"),
                InlineKeyboardButton("Username", callback_data=f"edit_field_username_{server_id}")
            ],
            [
                InlineKeyboardButton("Password", callback_data=f"edit_field_password_{server_id}")
            ],
            [
                InlineKeyboardButton("Back", callback_data=f"server_select_{server_id}")
            ]
        ]

        await safe_edit_message(
            update,
            context,
            f"*Editing server: {server_name}*\n\nSelect field to edit:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    except Exception as e:
        await safe_edit_message(
            update,
            context,
            get_error_message(str(e)),
            parse_mode="Markdown"
        )

async def edit_field_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Select field for editing"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    field = parts[2] # name, host, port, username, password
    server_id = int(parts[-1])
    user_id = update.effective_user.id
    
    try:
        # Run database query in thread to avoid blocking
        def _get_server_data():
            with db_manager.get_session() as session:
                server = session.query(Server).filter_by(id=server_id, user_id=user_id).first()
                if not server:
                    return None
                # Extract data while session is active
                return {
                    "name": server.name,
                    "host": server.host,
                    "port": str(server.port),
                    "username": server.username
                }
        
        server_data = await run_db_operation(_get_server_data)

        if not server_data:
            await safe_edit_message(
                update,
                context,
                "Server not found.",
                reply_markup=get_back_keyboard("server_list")
            )
            return ConversationHandler.END

        context.user_data["edit_server_id"] = server_id
        context.user_data["edit_field"] = field
        
        field_names = {
            "name": "Server name",
            "host": "IP address or Hostname",
            "port": "port",
            "username": "name username",
            "password": "password"
        }
        
        current_values = {
            "name": server_data["name"],
            "host": server_data["host"],
            "port": server_data["port"],
            "username": server_data["username"],
            "password": "***"
        }
        
        await safe_edit_message(
            update,
            context,
            f"*Editing {field_names[field]}*\n\n"
            f"Current value: `{current_values[field]}`\n\n"
            f"Enter new value:",
            reply_markup=get_back_keyboard(f"server_select_{server_id}"),
            parse_mode="Markdown"
        )
        
        return WAITING_EDIT_VALUE

    except Exception as e:
        await safe_edit_message(
            update,
            context,
            get_error_message(str(e)),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

async def edit_field_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get new value and save"""
    server_id = context.user_data.get("edit_server_id")
    field = context.user_data.get("edit_field")
    
    if not server_id or not field:
        await update.message.reply_text(
            "Error getting information. Please try again.",
            reply_markup=get_back_keyboard("server_list")
        )
        clear_edit_server_keys(context)
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    new_value = update.message.text.strip()
    
    try:
        # Validate input first (before database operation)
        validation_error = None
        if field == "name":
            if len(new_value) > 100:
                validation_error = "Server name max 100 characters."
        elif field == "host":
            is_valid_ip, ip_error = validate_ip(new_value)
            if not is_valid_ip:
                is_valid_hostname, hostname_error = validate_hostname(new_value)
                if not is_valid_hostname:
                    validation_error = f"{hostname_error or ip_error or 'Invalid host'}"
        elif field == "port":
            try:
                port = int(new_value)
                is_valid, error = validate_port(port)
                if not is_valid:
                    validation_error = error
            except ValueError:
                validation_error = "Port must be a number."
        elif field == "username":
            if not new_value or len(new_value) > 100:
                validation_error = "Invalid username."
        elif field == "password":
            if not new_value:
                validation_error = "Password cannot be empty."
        
        if validation_error:
            await update.message.reply_text(
                validation_error,
                reply_markup=get_back_keyboard(f"server_select_{server_id}")
            )
            return WAITING_EDIT_VALUE
        
        # Run database update in thread to avoid blocking
        def _update_server():
            with db_manager.get_session() as session:
                server = session.query(Server).filter_by(id=server_id, user_id=user_id).first()
                if not server:
                    return False, "Server not found."
                
                # Update field
                if field == "name":
                    server.name = new_value
                elif field == "host":
                    server.host = new_value
                elif field == "port":
                    server.port = int(new_value)
                elif field == "username":
                    server.username = new_value
                elif field == "password":
                    # Encrypt new password
                    server.encrypted_password = encrypt_password(user_id, new_value)
                
                # Context manager will commit automatically
                return True, "Field updated."
        
        success, message = await run_db_operation(_update_server)
        
        if not success:
            await update.message.reply_text(
                message,
                reply_markup=get_back_keyboard("server_list")
            )
            context.user_data.clear()
            return ConversationHandler.END
        
        # Clear temporary data
        context.user_data.clear()
        
        await update.message.reply_text(
            f"Field updated.",
            reply_markup=get_back_keyboard(f"server_select_{server_id}"),
            parse_mode="Markdown"
        )
        
        return ConversationHandler.END
    
    except Exception as e:
        await update.message.reply_text(
            get_error_message(f"Error editing: {str(e)}"),
            reply_markup=get_back_keyboard("server_list"),
            parse_mode="Markdown"
        )
        clear_edit_server_keys(context)
        return ConversationHandler.END

async def cancel_connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel ongoing connection"""
    query = update.callback_query
    if query:
        await query.answer()
    
    user_id = update.effective_user.id
    
    # Cancel any ongoing connection
    from utils.connection_helpers import cancel_ongoing_connection
    cancel_ongoing_connection(user_id, context)
    
    message = "❌ Connection cancelled."
    keyboard = get_back_keyboard("menu_connect")
    
    await safe_reply_or_edit(
        update,
        context,
        message,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel operation"""
    user_id = update.effective_user.id
    
    # Cancel any ongoing connection
    from utils.connection_helpers import cancel_ongoing_connection
    cancel_ongoing_connection(user_id, context)
    
    query = update.callback_query
    if query:
        await query.answer()
    
    clear_all_conversation_keys(user_id, context)
    
    message = "Operation cancelled."
    await safe_reply_or_edit(update, context, message)
    
    return ConversationHandler.END

