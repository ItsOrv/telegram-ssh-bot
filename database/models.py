"""SQLAlchemy models"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """User model"""
    __tablename__ = "users"
    
    
    user_id = Column(Integer, primary_key=True, unique=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    public_mode_enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    servers = relationship("Server", back_populates="user", cascade="all, delete-orphan")
    preset_commands = relationship("PresetCommand", back_populates="user", cascade="all, delete-orphan")
    connections = relationship("Connection", back_populates="user", cascade="all, delete-orphan")


class Server(Base):
    """Server model"""
    __tablename__ = "servers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    name = Column(String(100), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, default=22, nullable=False)
    username = Column(String(100), nullable=False)
    encrypted_password = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="servers")
    connections = relationship("Connection", back_populates="server", cascade="all, delete-orphan")


class PresetCommand(Base):
    """Preset command model"""
    __tablename__ = "preset_commands"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    name = Column(String(100), nullable=False)
    command = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="preset_commands")


class BlockedCommand(Base):
    """Blocked command model (global)"""
    __tablename__ = "blocked_commands"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    pattern = Column(String(255), unique=True, nullable=False)
    description = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Connection(Base):
    """Connection status model"""
    __tablename__ = "connections"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, unique=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)
    connected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="connections")
    server = relationship("Server", back_populates="connections")
