"""Database connection and session management"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from pathlib import Path
import logging
from typing import Generator

from database.models import Base
from config import config

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.db_path = config.get('database.path', 'music_library.db')
        self.engine = None
        self.SessionLocal = None
        self.init_database()
    
    def init_database(self):
        """Initialize database connection and create tables"""
        # Create database directory if it doesn't exist
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create engine
        self.engine = create_engine(
            f'sqlite:///{self.db_path}',
            connect_args={'check_same_thread': False},
            echo=False
        )
        
        # Create tables
        Base.metadata.create_all(bind=self.engine)
        
        # Create session factory
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        logger.info(f"Database initialized at {self.db_path}")
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get database session context manager"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()
    
    def get_db(self) -> Session:
        """Get database session for FastAPI dependency injection"""
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    def reset_database(self):
        """Drop all tables and recreate them"""
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database reset complete")
    
    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")

# Global database manager instance
db_manager = DatabaseManager()