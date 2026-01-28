"""In-memory cache for public_mode to reduce DB load on every callback."""
import time
from typing import Optional

_cache_value: Optional[bool] = None
_cache_time: Optional[float] = None
CACHE_TTL_SECONDS = 45  # Refresh from DB at most every 45 seconds


async def get_public_mode_cached() -> bool:
    """Return public_mode, from cache if valid else from DB. Reduces DB queries significantly."""
    global _cache_value, _cache_time
    now = time.monotonic()
    if _cache_value is not None and _cache_time is not None and (now - _cache_time) < CACHE_TTL_SECONDS:
        return _cache_value
    from utils.db_helpers import run_db_operation
    from database.connection import db_manager
    from database.models import User
    from config.settings import settings

    def _fetch():
        with db_manager.get_session() as session:
            admin_user = session.query(User).filter_by(
                user_id=settings.ADMIN_IDS[0] if settings.ADMIN_IDS else 0
            ).first()
            return bool(admin_user and admin_user.public_mode_enabled)

    _cache_value = await run_db_operation(_fetch)
    _cache_time = now
    return _cache_value


def invalidate_public_mode_cache() -> None:
    """Call after admin toggles public mode so next read gets fresh value."""
    global _cache_value, _cache_time
    _cache_value = None
    _cache_time = None
