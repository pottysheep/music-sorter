"""File hashing utilities for duplicate detection"""
import hashlib
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def calculate_file_hash(file_path: Path, chunk_size_mb: int = 1) -> Optional[str]:
    """
    Calculate MD5 hash of first N MB of file for quick duplicate detection
    
    Args:
        file_path: Path to file
        chunk_size_mb: Size in MB to read for hashing (default 1MB)
    
    Returns:
        MD5 hash string or None if error
    """
    try:
        chunk_size = chunk_size_mb * 1024 * 1024  # Convert to bytes
        hasher = hashlib.md5()
        
        with open(file_path, 'rb') as f:
            # Read only first chunk for performance
            chunk = f.read(chunk_size)
            if chunk:
                hasher.update(chunk)
                # Add file size to hash for better uniqueness
                hasher.update(str(file_path.stat().st_size).encode())
        
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Error hashing file {file_path}: {e}")
        return None

def calculate_full_file_hash(file_path: Path) -> Optional[str]:
    """
    Calculate MD5 hash of entire file (slower but more accurate)
    
    Args:
        file_path: Path to file
    
    Returns:
        MD5 hash string or None if error
    """
    try:
        hasher = hashlib.md5()
        chunk_size = 8192  # 8KB chunks for reading
        
        with open(file_path, 'rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Error hashing file {file_path}: {e}")
        return None

def verify_file_copy(source: Path, target: Path) -> bool:
    """
    Verify that a file was copied correctly by comparing hashes
    
    Args:
        source: Source file path
        target: Target file path
    
    Returns:
        True if hashes match, False otherwise
    """
    try:
        source_hash = calculate_full_file_hash(source)
        target_hash = calculate_full_file_hash(target)
        
        if source_hash and target_hash:
            return source_hash == target_hash
        return False
    except Exception as e:
        logger.error(f"Error verifying file copy: {e}")
        return False