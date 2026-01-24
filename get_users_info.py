#!/usr/bin/env python3
"""Get user information from Telegram API"""
import sys
import os
from config.settings import settings
from database.connection import db_manager
from database.models import User
from telegram import Bot
import asyncio

async def get_user_info():
    """Get user information from database and Telegram"""
    # Validate settings
    is_valid, errors = settings.validate()
    if not is_valid:
        print("Error in settings:")
        for error in errors:
            print(f" - {error}")
        return
    
    # Initialize database
    try:
        db_manager.initialize()
    except Exception as e:
        print(f"Error initializing database: {e}")
        return
    
    # Create bot instance
    bot = Bot(token=settings.TELEGRAM_TOKEN)
    
    # Get all users from database
    with db_manager.get_session() as session:
        users = session.query(User).order_by(User.created_at.desc()).all()
        
        print(f"\n{'='*80}")
        print(f"لیست کاربران ربات ({len(users)} کاربر)")
        print(f"{'='*80}\n")
        
        for user in users:
            try:
                # Get user info from Telegram
                chat = await bot.get_chat(user.user_id)
                username = chat.username if chat.username else "بدون نام کاربری"
                first_name = chat.first_name if chat.first_name else "بدون نام"
                last_name = chat.last_name if chat.last_name else ""
                full_name = f"{first_name} {last_name}".strip()
                
                # Format output
                admin_status = "✅ ادمین" if user.is_admin else "❌ کاربر عادی"
                public_mode = "✅ فعال" if user.public_mode_enabled else "❌ غیرفعال"
                
                print(f"User ID: {user.user_id}")
                print(f"  نام: {full_name}")
                print(f"  نام کاربری: @{username}" if username != "بدون نام کاربری" else "  نام کاربری: ندارد")
                print(f"  وضعیت: {admin_status}")
                print(f"  حالت عمومی: {public_mode}")
                print(f"  تاریخ ثبت‌نام: {user.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print()
                
            except Exception as e:
                # If can't get user info, show basic info
                admin_status = "✅ ادمین" if user.is_admin else "❌ کاربر عادی"
                public_mode = "✅ فعال" if user.public_mode_enabled else "❌ غیرفعال"
                
                print(f"User ID: {user.user_id}")
                print(f"  نام: (در دسترس نیست - {str(e)})")
                print(f"  وضعیت: {admin_status}")
                print(f"  حالت عمومی: {public_mode}")
                print(f"  تاریخ ثبت‌نام: {user.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print()

if __name__ == "__main__":
    asyncio.run(get_user_info())

