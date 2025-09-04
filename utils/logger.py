"""Logging configuration for Music Sorter"""
import logging
import sys
from pathlib import Path
from config import config

def setup_logging():
    """Configure logging for the application"""
    log_level = config.get('logging.level', 'INFO')
    log_file = config.get('logging.file', 'music_sorter.log')
    
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set third-party loggers to WARNING to reduce noise
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('fastapi').setLevel(logging.WARNING)
    
    return logging.getLogger('music_sorter')

# Initialize logging
logger = setup_logging()