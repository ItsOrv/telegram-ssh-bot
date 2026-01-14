"""SQLAlchemy models"""
from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, ForeignKey, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """User model"""
    __tablename__ = "users"
    
    
    user_id = Column(BigInteger, primary_key=True, unique=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    public_mode_enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    servers = relationship("Server", back_populates="user", cascade="all, delete-orphan")
    preset_commands = relationship("PresetCommand", back_populates="user", cascade="all, delete-orphan")
    connections = relationship("Connection", back_populates="user", cascade="all, delete-orphan")
    command_history = relationship("CommandHistory", backref="user_ref")
    
    # Indexes
    __table_args__ = (
        Index('idx_users_user_id', 'user_id'),
    )


class Server(Base):
    """Server model"""
    __tablename__ = "servers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
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
    command_history = relationship("CommandHistory", backref="server_ref")
    
    # Indexes
    __table_args__ = (
        Index('idx_servers_user_id', 'user_id'),
        Index('idx_servers_id', 'id'),
    )


class PresetCommand(Base):
    """Preset command model"""
    __tablename__ = "preset_commands"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    name = Column(String(100), nullable=False)
    command = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="preset_commands")
    
    # Indexes
    __table_args__ = (
        Index('idx_preset_commands_user_id', 'user_id'),
    )


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
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, unique=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)
    connected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="connections")
    server = relationship("Server", back_populates="connections")


class CommandHistory(Base):
    """Command execution history model"""
    __tablename__ = "command_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=True)
    command = Column(Text, nullable=False)
    success = Column(Boolean, nullable=False)
    output_length = Column(Integer, default=0)
    error_length = Column(Integer, default=0)
    execution_time = Column(Integer, nullable=True)  # in seconds
    executed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    user = relationship("User")
    server = relationship("Server")
    
    # Indexes
    __table_args__ = (
        Index('idx_command_history_user_executed', 'user_id', 'executed_at'),
        Index('idx_command_history_server', 'server_id'),
    )
