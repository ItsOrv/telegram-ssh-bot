"""Settings and environment variables management"""
import os
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings:
    """Settings management class"""
    
    # Telegram Bot
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    
    # Admin Configuration
    ADMIN_IDS: List[int] = [
        int(admin_id.strip())
        for admin_id in os.getenv("ADMIN_IDS", "").split(",")
        if admin_id.strip().isdigit()
    ]
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://user:password@localhost:5432/telegram_ssh_bot"
    )
    
    # Security
    MASTER_ENCRYPTION_KEY: str = os.getenv("MASTER_ENCRYPTION_KEY", "")
    
    # Bot Settings
    COMMAND_TIMEOUT: int = int(os.getenv("COMMAND_TIMEOUT", "300"))
    CONNECTION_TIMEOUT: int = int(os.getenv("CONNECTION_TIMEOUT", "1800"))
    MAX_COMMAND_LENGTH: int = int(os.getenv("MAX_COMMAND_LENGTH", "1000"))
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
    
    # Optional IP Whitelist
    IP_WHITELIST: List[str] = [
        ip.strip()
        for ip in os.getenv("IP_WHITELIST", "").split(",")
        if ip.strip()
    ]
    
    @classmethod
    def validate(cls) -> tuple[bool, List[str]]:
        """Validate settings"""
        errors = []
        
        if not cls.TELEGRAM_TOKEN:
            errors.append("TELEGRAM_TOKEN is required")
        
        if not cls.ADMIN_IDS:
            errors.append("At least one ADMIN_ID is required")
        
        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL is required")
        
        if not cls.MASTER_ENCRYPTION_KEY or len(cls.MASTER_ENCRYPTION_KEY) < 32:
            errors.append("MASTER_ENCRYPTION_KEY must be at least 32 characters")
        
        return len(errors) == 0, errors
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in cls.ADMIN_IDS


# Create global instance
settings = Settings()
