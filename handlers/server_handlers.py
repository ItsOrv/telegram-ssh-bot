"""Server management handlers"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from typing import Dict
from database.connection import db_manager
from database.models import User, Server
from security.encryption import encrypt_password
from security.validator import validate_server_info, validate_ip, validate_port
from ssh.manager import ssh_manager
from utils.keyboards import (
 get_servers_menu_keyboard,
 get_server_list_keyboard,
 get_server_actions_keyboard,
 get_confirm_keyboard,
 get_back_keyboard,
 get_connect_menu_keyboard
)
from utils.messages import (
 get_server_info_message,
 get_connection_status_message,
 get_error_message,
 get_success_message
)
from config.settings import settings

# States for ConversationHandler
(WAITING_SERVER_NAME, WAITING_SERVER_HOST, WAITING_SERVER_PORT,
 WAITING_SERVER_USERNAME, WAITING_SERVER_PASSWORD,
 WAITING_EDIT_VALUE,
 WAITING_DIRECT_HOST, WAITING_DIRECT_PORT, WAITING_DIRECT_USERNAME, WAITING_DIRECT_PASSWORD) = range(10)

async def ensure_user_exists(user_id: int, session):
 """Ensure user exists in database"""
 user = session.query(User).filter_by(user_id=user_id).first()
 if not user:
     user = User(user_id=user_id, is_admin=user_id in settings.ADMIN_IDS)
     session.add(user)
     session.commit()
 return user

async def servers_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Server management menu"""
 if update.message and update.message.chat.type != "private":
     await update.message.reply_text("This command can only be used in private chat.")
     return
 
 query = update.callback_query
 if query:
     await query.answer()
     await query.edit_message_text(
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
 
 # Validate host
 is_valid_ip, ip_error = validate_ip(host)
 if not is_valid_ip and (not host or len(host) > 255):
     await update.message.reply_text(
         "Invalid IP address or Hostname. Enter again:",
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
     with db_manager.get_session() as session:
         # Ensure user exists
         user = await ensure_user_exists(user_id, session)
 
         # Encrypt password
         encrypted_password = encrypt_password(user_id, password)
 
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
         session.commit()
 
         # Clear temporary data
         context.user_data.clear()
 
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
     context.user_data.clear()
     return ConversationHandler.END

async def list_servers(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Server list"""
 query = update.callback_query
 if query:
     await query.answer()
 
 user_id = update.effective_user.id
 
 try:
     with db_manager.get_session() as session:
         servers = session.query(Server).filter_by(user_id=user_id).all()
 
         if not servers:
             message = "No servers.\n\nYou can add a new server from the Server Management menu."
             if query:
                 await query.edit_message_text(
                     message,
                     reply_markup=get_back_keyboard("menu_servers")
                 )
             else:
                 await update.message.reply_text(
                     message,
                     reply_markup=get_back_keyboard("menu_servers")
                 )
             return
 
         servers_list = [
             {"id": server.id, "name": server.name}
             for server in servers
         ]
 
         keyboard = get_server_list_keyboard(servers_list, "server_select")
 
         message = "*Server list:*\n\nSelect server:"
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

async def server_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Select server"""
 query = update.callback_query
 await query.answer()
 
 server_id = int(query.data.split("_")[-1])
 user_id = update.effective_user.id
 
 try:
     with db_manager.get_session() as session:
         server = session.query(Server).filter_by(id=server_id, user_id=user_id).first()
 
         if not server:
             await query.edit_message_text(
                 "Server not found.",
                 reply_markup=get_back_keyboard("server_list")
             )
             return
 
         message = get_server_info_message(server.name, server.host, server.port, server.username)
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
     with db_manager.get_session() as session:
         server = session.query(Server).filter_by(id=server_id, user_id=user_id).first()
 
         if not server:
             await query.edit_message_text(
                 "Server not found.",
                 reply_markup=get_back_keyboard("server_list")
             )
             return
 
         context.user_data["delete_server_id"] = server_id
         keyboard = get_confirm_keyboard("server_delete", server_id)
 
         await query.edit_message_text(
             f"Delete server *{server.name}*?",
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
     with db_manager.get_session() as session:
         server = session.query(Server).filter_by(id=server_id, user_id=user_id).first()
 
         if not server:
             await query.edit_message_text(
                 "Server not found.",
                 reply_markup=get_back_keyboard("server_list")
             )
             return
 
         server_name = server.name
         session.delete(server)
         session.commit()
 
         await query.edit_message_text(
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
        with db_manager.get_session() as session:
            servers = session.query(Server).filter_by(user_id=user_id).all()
            
            servers_list = [
                {"id": server.id, "name": server.name}
                for server in servers
            ]
            
            keyboard = get_connect_menu_keyboard(servers_list)
            
            message = "*Connect to Server*\n\nSelect a saved server or use Direct Connect:"
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

async def server_connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Connect to server (legacy - redirects to connect_menu)"""
    await connect_menu(update, context)

async def direct_connect_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start direct connect process"""
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
    
    # Validate host
    is_valid_ip, ip_error = validate_ip(host)
    if not is_valid_ip and (not host or len(host) > 255):
        await update.message.reply_text(
            "Invalid IP address or Hostname. Enter again:",
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
    host = context.user_data.get("direct_host")
    port = context.user_data.get("direct_port", 22)
    username = context.user_data.get("direct_username")
    
    if not all([host, username, password]):
        await update.message.reply_text(
            "Error: Missing information. Please try again.",
            reply_markup=get_back_keyboard("menu_connect")
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    # Create temporary server object for connection
    temp_server = Server(
        id=0,  # Temporary ID
        user_id=user_id,
        name="Direct Connection",
        host=host,
        port=port,
        username=username,
        encrypted_password=encrypt_password(user_id, password)
    )
    
    # Connect
    try:
        success, message = ssh_manager.connect(user_id, temp_server)
        
        if success:
            await update.message.reply_text(
                f"✅ {message}",
                reply_markup=get_back_keyboard("menu_main"),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ {message}",
                reply_markup=get_back_keyboard("menu_connect"),
                parse_mode="Markdown"
            )
    except Exception as e:
        await update.message.reply_text(
            get_error_message(f"Connection error: {str(e)}"),
            reply_markup=get_back_keyboard("menu_connect"),
            parse_mode="Markdown"
        )
    
    # Clear temporary data
    context.user_data.clear()
    return ConversationHandler.END

async def connect_to_server(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Connect to server selected"""
 query = update.callback_query
 await query.answer()
 
 server_id = int(query.data.split("_")[-1])
 user_id = update.effective_user.id
 
 try:
     with db_manager.get_session() as session:
         server = session.query(Server).filter_by(id=server_id, user_id=user_id).first()
 
         if not server:
             await query.edit_message_text(
                 "Server not found.",
                 reply_markup=get_back_keyboard("menu_servers")
             )
             return
 
         # Connect
         success, message = ssh_manager.connect(user_id, server)
 
         await query.edit_message_text(
            message,
            reply_markup=get_back_keyboard("menu_main"),
            parse_mode="Markdown"
        )
 
 except Exception as e:
     await query.edit_message_text(
         get_error_message(str(e)),
         reply_markup=get_back_keyboard("menu_servers"),
         parse_mode="Markdown"
     )

async def server_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
 """Disconnect"""
 query = update.callback_query
 if query:
     await query.answer()
 
 user_id = update.effective_user.id
 
 success, message = ssh_manager.disconnect(user_id)
 
 if query:
     await query.edit_message_text(
         message,
         reply_markup=get_back_keyboard("menu_main"),
         parse_mode="Markdown"
     )
 else:
     if update.effective_message:
         await update.effective_message.reply_text(
             message,
             reply_markup=get_back_keyboard("menu_servers"),
             parse_mode="Markdown"
         )
     elif update.message:
         await update.message.reply_text(
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
     with db_manager.get_session() as session:
         server = session.query(Server).filter_by(id=server_id, user_id=user_id).first()
 
         if not server:
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
 
         await query.edit_message_text(
             f"*Editing server: {server.name}*\n\nSelect field to edit:",
             reply_markup=InlineKeyboardMarkup(keyboard),
             parse_mode="Markdown"
         )
 
 except Exception as e:
     await query.edit_message_text(
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
     with db_manager.get_session() as session:
         server = session.query(Server).filter_by(id=server_id, user_id=user_id).first()
 
         if not server:
             await query.edit_message_text(
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
             "name": server.name,
             "host": server.host,
             "port": str(server.port),
             "username": server.username,
             "password": "***"
         }
 
         await query.edit_message_text(
             f"*Editing {field_names[field]}*\n\n"
             f"Current value: `{current_values[field]}`\n\n"
             f"Enter new value:",
             reply_markup=get_back_keyboard(f"server_select_{server_id}"),
             parse_mode="Markdown"
         )
 
         return WAITING_EDIT_VALUE
 
 except Exception as e:
     await query.edit_message_text(
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
     context.user_data.clear()
     return ConversationHandler.END
 
 user_id = update.effective_user.id
 new_value = update.message.text.strip()
 
 try:
     with db_manager.get_session() as session:
         server = session.query(Server).filter_by(id=server_id, user_id=user_id).first()
 
         if not server:
             await update.message.reply_text(
                 "Server not found.",
                 reply_markup=get_back_keyboard("server_list")
             )
             context.user_data.clear()
             return ConversationHandler.END
 
         # Validate and update
         if field == "name":
             if len(new_value) > 100:
                 await update.message.reply_text(
                     "Server name max 100 characters.",
                     reply_markup=get_back_keyboard(f"server_select_{server_id}")
                 )
                 return WAITING_EDIT_VALUE
             server.name = new_value
 
         elif field == "host":
             is_valid_ip, ip_error = validate_ip(new_value)
             if not is_valid_ip and (not new_value or len(new_value) > 255):
                 await update.message.reply_text(
                     f"{ip_error or 'Invalid host'}",
                     reply_markup=get_back_keyboard(f"server_select_{server_id}")
                 )
                 return WAITING_EDIT_VALUE
             server.host = new_value
 
         elif field == "port":
             try:
                 port = int(new_value)
                 is_valid, error = validate_port(port)
                 if not is_valid:
                     await update.message.reply_text(
                         f"{error}",
                         reply_markup=get_back_keyboard(f"server_select_{server_id}")
                     )
                     return WAITING_EDIT_VALUE
                 server.port = port
             except ValueError:
                 await update.message.reply_text(
                     "Port must be a number.",
                     reply_markup=get_back_keyboard(f"server_select_{server_id}")
                 )
                 return WAITING_EDIT_VALUE
 
         elif field == "username":
             if not new_value or len(new_value) > 100:
                 await update.message.reply_text(
                     "Invalid username.",
                     reply_markup=get_back_keyboard(f"server_select_{server_id}")
                 )
                 return WAITING_EDIT_VALUE
             server.username = new_value
 
         elif field == "password":
             if not new_value:
                 await update.message.reply_text(
                     "Password cannot be empty.",
                     reply_markup=get_back_keyboard(f"server_select_{server_id}")
                 )
                 return WAITING_EDIT_VALUE
             # Encrypt new password
             server.encrypted_password = encrypt_password(user_id, new_value)
 
         session.commit()
 
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
     context.user_data.clear()
     return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

