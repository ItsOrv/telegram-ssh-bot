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
    # thread pool size
    THREAD_POOL_MAX_WORKERS: int = int(os.getenv("THREAD_POOL_MAX_WORKERS", "15"))
    
    # IP whitelist (optional)
    IP_WHITELIST: List[str] = [
        ip.strip()
        for ip in os.getenv("IP_WHITELIST", "").split(",")
        if ip.strip()
    ]
    
    @classmethod
    def validate(cls) -> tuple[bool, List[str]]:
        """Check if settings are valid"""
        import re
        errors = []
        
        if not cls.TELEGRAM_TOKEN:
            errors.append("TELEGRAM_TOKEN is required")
        elif not re.match(r'^\d+:[A-Za-z0-9_-]+$', cls.TELEGRAM_TOKEN):
            errors.append("TELEGRAM_TOKEN format is invalid (expected format: BOT_ID:BOT_TOKEN)")
        
        if not cls.ADMIN_IDS:
            errors.append("At least one ADMIN_ID is required")
        else:
            for admin_id in cls.ADMIN_IDS:
                if not isinstance(admin_id, int) or admin_id <= 0:
                    errors.append(f"Invalid ADMIN_ID: {admin_id} (must be positive integer)")
        
        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL is required")
        else:
            # Validate DATABASE_URL format
            if not cls.DATABASE_URL.startswith(('postgresql://', 'postgresql+psycopg2://')):
                errors.append("DATABASE_URL must start with 'postgresql://' or 'postgresql+psycopg2://'")
            # Check for required components
            if '@' not in cls.DATABASE_URL or ':' not in cls.DATABASE_URL.split('@')[-1]:
                errors.append("DATABASE_URL format is invalid (expected: postgresql://user:password@host:port/dbname)")
        
        if not cls.MASTER_ENCRYPTION_KEY or len(cls.MASTER_ENCRYPTION_KEY) < 32:
            errors.append("MASTER_ENCRYPTION_KEY must be at least 32 characters")
        
        # Validate numeric settings
        if cls.COMMAND_TIMEOUT <= 0:
            errors.append("COMMAND_TIMEOUT must be positive")
        if cls.CONNECTION_TIMEOUT <= 0:
            errors.append("CONNECTION_TIMEOUT must be positive")
        if cls.MAX_COMMAND_LENGTH <= 0:
            errors.append("MAX_COMMAND_LENGTH must be positive")
        if cls.RATE_LIMIT_PER_MINUTE <= 0:
            errors.append("RATE_LIMIT_PER_MINUTE must be positive")
        if cls.THREAD_POOL_MAX_WORKERS < 1 or cls.THREAD_POOL_MAX_WORKERS > 128:
            errors.append("THREAD_POOL_MAX_WORKERS must be between 1 and 128")
        
        return len(errors) == 0, errors
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in cls.ADMIN_IDS


# Create global instance
settings = Settings()
