"""Cleanup utilities for log files and temporary data"""
import os
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def cleanup_old_log_files(max_age_hours: int = 24, log_dir: str = "/tmp"):
    """
    Clean up old log files
    
    Args:
        max_age_hours: Maximum age of log files in hours
        log_dir: Directory containing log files
    """
    try:
        log_path = Path(log_dir)
        if not log_path.exists():
            return
        
        cutoff_time = time.time() - (max_age_hours * 3600)
        cleaned_count = 0
        
        # Find all sshbot log files
        for log_file in log_path.glob("sshbot_log_*"):
            try:
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    cleaned_count += 1
            except Exception as e:
                logger.debug(f"Error removing log file {log_file}: {e}")
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old log files")
    except Exception as e:
        logger.warning(f"Error during log file cleanup: {e}")


def cleanup_user_log_file(user_id: int, log_dir: str = "/tmp"):
    """
    Clean up log file for a specific user
    
    Args:
        user_id: User ID
        log_dir: Directory containing log files
    """
    try:
        log_file = Path(log_dir) / f"sshbot_log_{user_id}"
        if log_file.exists():
            log_file.unlink()
            logger.debug(f"Cleaned up log file for user {user_id}")
    except Exception as e:
        logger.debug(f"Error cleaning up log file for user {user_id}: {e}")


