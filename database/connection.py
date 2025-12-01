"""PostgreSQL connection management"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from contextlib import contextmanager
from typing import Generator
from config.settings import settings
from database.models import Base


class DatabaseManager:
    """Database connection and session management"""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialized = False
    
    def initialize(self):
        """Initialize database connection"""
        if self._initialized:
            return
        
        try:
            # Create engine
            self.engine = create_engine(
                settings.DATABASE_URL,
                poolclass=NullPool,
                echo=False,
                pool_pre_ping=True
            )
            
            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            # Create tables
            Base.metadata.create_all(bind=self.engine)
            
            self._initialized = True
        except Exception as e:
            raise RuntimeError(f"Database connection error: {str(e)}")
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Context manager for session"""
        if not self._initialized:
            self.initialize()
        
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_session_direct(self) -> Session:
        """Get session directly (without context manager)"""
        if not self._initialized:
            self.initialize()
        return self.SessionLocal()
    
    def close(self):
        """Close connection"""
        if self.engine:
            self.engine.dispose()
            self._initialized = False


# Global instance
db_manager = DatabaseManager()
