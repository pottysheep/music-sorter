"""I/O optimization utilities for HDD operations"""
import os
from pathlib import Path
from typing import List, Generator, Tuple
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

def get_files_sorted_by_location(directory: Path) -> Generator[Path, None, None]:
    """
    Yield files sorted by their physical location on disk to minimize seeks
    
    Args:
        directory: Root directory to scan
    
    Yields:
        File paths sorted by directory for sequential access
    """
    # Group files by directory for sequential access
    files_by_dir = defaultdict(list)
    
    try:
        # Collect all files grouped by parent directory
        for root, dirs, files in os.walk(directory):
            root_path = Path(root)
            for file in files:
                file_path = root_path / file
                # Filter for audio files
                if file_path.suffix.lower() in {'.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.wma'}:
                    files_by_dir[root_path].append(file_path)
        
        # Sort directories and yield files sequentially
        for dir_path in sorted(files_by_dir.keys()):
            # Sort files within directory for predictable access
            for file_path in sorted(files_by_dir[dir_path]):
                yield file_path
    
    except Exception as e:
        logger.error(f"Error scanning directory {directory}: {e}")

def batch_files(files: Generator[Path, None, None], batch_size: int = 100) -> Generator[List[Path], None, None]:
    """
    Batch files for processing to optimize I/O operations
    
    Args:
        files: Generator of file paths
        batch_size: Number of files per batch
    
    Yields:
        Batches of file paths
    """
    batch = []
    for file_path in files:
        batch.append(file_path)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    
    # Yield remaining files
    if batch:
        yield batch

def estimate_file_count(directory: Path) -> Tuple[int, int]:
    """
    Quickly estimate the number of audio files and total size
    
    Args:
        directory: Directory to scan
    
    Returns:
        Tuple of (file_count, total_size_bytes)
    """
    file_count = 0
    total_size = 0
    
    try:
        for root, dirs, files in os.walk(directory):
            root_path = Path(root)
            for file in files:
                if Path(file).suffix.lower() in {'.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.wma'}:
                    file_count += 1
                    try:
                        file_path = root_path / file
                        total_size += file_path.stat().st_size
                    except:
                        pass  # Skip files we can't stat
    except Exception as e:
        logger.error(f"Error estimating file count: {e}")
    
    return file_count, total_size

def optimize_path_for_windows(path: str) -> str:
    """
    Optimize file path for Windows file system
    
    Args:
        path: Original file path
    
    Returns:
        Optimized path string
    """
    # Remove illegal characters for Windows
    illegal_chars = '<>:"|?*'
    for char in illegal_chars:
        path = path.replace(char, '_')
    
    # Trim trailing dots and spaces
    path = path.rstrip('. ')
    
    # Limit path length (Windows MAX_PATH is 260)
    if len(path) > 250:
        # Keep extension
        ext = Path(path).suffix
        path = path[:250 - len(ext)] + ext
    
    return path