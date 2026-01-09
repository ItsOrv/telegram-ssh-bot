"""Inline keyboard builders"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict, Optional


def get_main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Main menu - Connect button at top"""
    keyboard = [
        [
            InlineKeyboardButton("🔌 Connect", callback_data="menu_connect")
        ],
        [
            InlineKeyboardButton("Server Management", callback_data="menu_servers"),
            InlineKeyboardButton("Execute Command", callback_data="menu_execute")
        ],
        [
            InlineKeyboardButton("Preset Commands", callback_data="menu_presets"),
            InlineKeyboardButton("Help", callback_data="menu_help")
        ]
    ]
    if is_admin:
        keyboard.append([
            InlineKeyboardButton("Admin Menu", callback_data="admin_menu")
        ])
    return InlineKeyboardMarkup(keyboard)


def get_servers_menu_keyboard() -> InlineKeyboardMarkup:
    """Server management menu"""
    keyboard = [
        [
            InlineKeyboardButton("Add Server", callback_data="server_add"),
            InlineKeyboardButton("Server List", callback_data="server_list")
        ],
        [
            InlineKeyboardButton("Connect", callback_data="server_connect"),
            InlineKeyboardButton("Disconnect", callback_data="server_disconnect")
        ],
        [
            InlineKeyboardButton("Back", callback_data="menu_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_server_list_keyboard(servers: List[Dict], action: str = "select") -> InlineKeyboardMarkup:
    """Build server list keyboard"""
    keyboard = []
    for server in servers:
        server_id = server.get("id")
        server_name = server.get("name", "Unnamed")
        callback_data = f"{action}_server_{server_id}"
        keyboard.append([InlineKeyboardButton(server_name, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("Back", callback_data="menu_servers")])
    return InlineKeyboardMarkup(keyboard)

def get_connect_menu_keyboard(servers: List[Dict]) -> InlineKeyboardMarkup:
    """Connect menu keyboard - Direct Connect at top, then server list"""
    keyboard = [
        [
            InlineKeyboardButton("🔗 Direct Connect", callback_data="direct_connect")
        ]
    ]
    
    # Add saved servers
    if servers:
        for server in servers:
            server_id = server.get("id")
            server_name = server.get("name", "Unnamed")
            keyboard.append([
                InlineKeyboardButton(server_name, callback_data=f"connect_to_{server_id}")
            ])
    
    keyboard.append([InlineKeyboardButton("Back", callback_data="menu_main")])
    return InlineKeyboardMarkup(keyboard)


def get_server_actions_keyboard(server_id: int) -> InlineKeyboardMarkup:
    """Server action buttons"""
    keyboard = [
        [
            InlineKeyboardButton("Edit", callback_data=f"server_edit_{server_id}"),
            InlineKeyboardButton("Delete", callback_data=f"server_delete_{server_id}")
        ],
        [
            InlineKeyboardButton("Back", callback_data="server_list")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_confirm_keyboard(action: str, item_id: int) -> InlineKeyboardMarkup:
    """Build confirm/cancel keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("Confirm", callback_data=f"confirm_{action}_{item_id}"),
            InlineKeyboardButton("Cancel", callback_data=f"cancel_{action}_{item_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_presets_menu_keyboard() -> InlineKeyboardMarkup:
    """Preset commands menu"""
    keyboard = [
        [
            InlineKeyboardButton("Add Command", callback_data="preset_add"),
            InlineKeyboardButton("Command List", callback_data="preset_list")
        ],
        [
            InlineKeyboardButton("Back", callback_data="menu_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_preset_list_keyboard(presets: List[Dict]) -> InlineKeyboardMarkup:
    """Preset command list keyboard"""
    keyboard = []
    for preset in presets:
        preset_id = preset.get("id")
        preset_name = preset.get("name", "Unnamed")
        keyboard.append([
            InlineKeyboardButton(
                preset_name,
                callback_data=f"preset_execute_{preset_id}"
            ),
            InlineKeyboardButton(
                "Delete",
                callback_data=f"preset_delete_{preset_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("Back", callback_data="menu_presets")])
    return InlineKeyboardMarkup(keyboard)


def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Admin menu"""
    keyboard = [
        [
            InlineKeyboardButton("Public Mode", callback_data="admin_toggle_public"),
            InlineKeyboardButton("Statistics", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton("Back", callback_data="menu_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_keyboard(callback_data: str = "menu_main") -> InlineKeyboardMarkup:
    """Back button"""
    keyboard = [[InlineKeyboardButton("Back", callback_data=callback_data)]]
    return InlineKeyboardMarkup(keyboard)
