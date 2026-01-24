#!/usr/bin/env python3
"""Migration script to change user_id from INTEGER to BIGINT"""
import sys
from sqlalchemy import text
from config.settings import settings
from database.connection import db_manager

def migrate():
    """Migrate user_id columns from INTEGER to BIGINT"""
    print("Starting migration: user_id INTEGER -> BIGINT")
    
    # Validate settings
    is_valid, errors = settings.validate()
    if not is_valid:
        print("Error in settings:")
        for error in errors:
            print(f" - {error}")
        return False
    
    try:
        # Initialize database connection
        db_manager.initialize()
        
        # Get database connection
        engine = db_manager.engine
        
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                print("Altering users.user_id...")
                conn.execute(text("""
                    ALTER TABLE users 
                    ALTER COLUMN user_id TYPE BIGINT;
                """))
                
                print("Altering servers.user_id...")
                conn.execute(text("""
                    ALTER TABLE servers 
                    ALTER COLUMN user_id TYPE BIGINT;
                """))
                
                print("Altering preset_commands.user_id...")
                conn.execute(text("""
                    ALTER TABLE preset_commands 
                    ALTER COLUMN user_id TYPE BIGINT;
                """))
                
                print("Altering connections.user_id...")
                conn.execute(text("""
                    ALTER TABLE connections 
                    ALTER COLUMN user_id TYPE BIGINT;
                """))
                
                # Commit transaction
                trans.commit()
                print("✅ Migration completed successfully!")
                return True
                
            except Exception as e:
                trans.rollback()
                print(f"❌ Error during migration: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)

