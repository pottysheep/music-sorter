"""File indexing module with checkpointing support"""
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any
import logging

from sqlalchemy import func
from database.db import db_manager
from database.models import File, Checkpoint
from utils.io_optimizer import get_files_sorted_by_location, batch_files, estimate_file_count
from utils.hashing import calculate_file_hash
from config import config

logger = logging.getLogger(__name__)

class FileIndexer:
    def __init__(self):
        self.batch_size = config.get('source.batch_size', 100)
        self.checkpoint_interval = config.get('checkpoint.interval', 100)
        self.checkpoint_enabled = config.get('checkpoint.enabled', True)
        self.progress_callback = None
        self.should_stop = False
        
    def set_progress_callback(self, callback):
        """Set callback for progress updates"""
        self.progress_callback = callback
    
    def stop(self):
        """Signal to stop indexing"""
        self.should_stop = True
    
    def index_directory(self, directory: str, resume: bool = True) -> Dict[str, Any]:
        """
        Index all audio files in a directory with checkpointing
        
        Args:
            directory: Path to directory to index
            resume: Whether to resume from checkpoint
        
        Returns:
            Dictionary with indexing results
        """
        start_time = time.time()
        directory_path = Path(directory)
        
        if not directory_path.exists():
            raise ValueError(f"Directory {directory} does not exist")
        
        # Estimate total files for progress reporting
        logger.info(f"Estimating file count in {directory}...")
        total_files, total_size = estimate_file_count(directory_path)
        logger.info(f"Found approximately {total_files} audio files ({total_size / 1024 / 1024 / 1024:.2f} GB)")
        
        # Check for existing checkpoint
        checkpoint_data = None
        processed_files = set()
        files_processed = 0
        
        if resume and self.checkpoint_enabled:
            checkpoint_data = self._load_checkpoint('index', directory)
            if checkpoint_data:
                processed_files = set(checkpoint_data.get('processed_files', []))
                files_processed = checkpoint_data.get('progress', 0)
                logger.info(f"Resuming from checkpoint: {files_processed} files already processed")
        
        # Start indexing
        files_added = 0
        files_skipped = 0
        errors = []
        last_checkpoint = time.time()
        
        try:
            # Get files sorted by location for optimal HDD access
            file_generator = get_files_sorted_by_location(directory_path)
            
            # Process in batches
            for batch in batch_files(file_generator, self.batch_size):
                if self.should_stop:
                    logger.info("Indexing stopped by user")
                    break
                
                with db_manager.get_session() as session:
                    for file_path in batch:
                        if self.should_stop:
                            break
                        
                        # Skip if already processed
                        if str(file_path) in processed_files:
                            files_skipped += 1
                            continue
                        
                        try:
                            # Check if file already exists in database
                            existing = session.query(File).filter_by(source_path=str(file_path)).first()
                            if existing:
                                files_skipped += 1
                                processed_files.add(str(file_path))
                                continue
                            
                            # Get file stats
                            stat = file_path.stat()
                            
                            # Calculate hash for duplicate detection
                            file_hash = calculate_file_hash(
                                file_path, 
                                config.get('deduplication.hash_chunk_size_mb', 1)
                            )
                            
                            # Create file record
                            file_record = File(
                                source_path=str(file_path),
                                file_size=stat.st_size,
                                modified_date=datetime.fromtimestamp(stat.st_mtime),
                                file_hash=file_hash,
                                status='indexed'
                            )
                            
                            session.add(file_record)
                            files_added += 1
                            files_processed += 1
                            processed_files.add(str(file_path))
                            
                        except Exception as e:
                            logger.error(f"Error indexing {file_path}: {e}")
                            errors.append(str(file_path))
                    
                    # Commit batch
                    session.commit()
                
                # Update progress
                if self.progress_callback:
                    self.progress_callback({
                        'operation': 'index',
                        'progress': files_processed,
                        'total': total_files,
                        'message': f"Processing: {files_added} new, {files_skipped} skipped, {len(errors)} errors (Total: {files_processed}/{total_files})",
                        'files_added': files_added,
                        'files_skipped': files_skipped,
                        'errors': len(errors)
                    })
                
                # Save checkpoint periodically
                if self.checkpoint_enabled and time.time() - last_checkpoint > 10:  # Every 10 seconds
                    self._save_checkpoint('index', directory, {
                        'processed_files': list(processed_files),
                        'progress': files_processed,
                        'total': total_files
                    })
                    last_checkpoint = time.time()
        
        except Exception as e:
            logger.error(f"Fatal error during indexing: {e}")
            raise
        
        finally:
            # Save final checkpoint
            if self.checkpoint_enabled:
                if files_processed >= total_files or self.should_stop:
                    self._clear_checkpoint('index', directory)
                else:
                    self._save_checkpoint('index', directory, {
                        'processed_files': list(processed_files),
                        'progress': files_processed,
                        'total': total_files
                    })
        
        elapsed_time = time.time() - start_time
        
        return {
            'files_added': files_added,
            'files_skipped': files_skipped,
            'errors': len(errors),
            'error_files': errors[:10],  # Return first 10 errors
            'total_processed': files_processed,
            'elapsed_time': elapsed_time,
            'files_per_second': files_processed / elapsed_time if elapsed_time > 0 else 0
        }
    
    def _save_checkpoint(self, operation: str, directory: str, data: Dict[str, Any]):
        """Save checkpoint to database"""
        try:
            with db_manager.get_session() as session:
                # Find existing checkpoint or create new
                checkpoint = session.query(Checkpoint).filter_by(
                    operation=operation,
                    state=directory
                ).first()
                
                if checkpoint:
                    checkpoint.progress = data.get('progress', 0)
                    checkpoint.total = data.get('total', 0)
                    checkpoint.checkpoint_data = data
                    checkpoint.updated_at = datetime.utcnow()
                else:
                    checkpoint = Checkpoint(
                        operation=operation,
                        state=directory,
                        progress=data.get('progress', 0),
                        total=data.get('total', 0),
                        checkpoint_data=data
                    )
                    session.add(checkpoint)
                
                session.commit()
                logger.debug(f"Checkpoint saved: {operation} - {data.get('progress', 0)}/{data.get('total', 0)}")
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")
    
    def _load_checkpoint(self, operation: str, directory: str) -> Optional[Dict[str, Any]]:
        """Load checkpoint from database"""
        try:
            with db_manager.get_session() as session:
                checkpoint = session.query(Checkpoint).filter_by(
                    operation=operation,
                    state=directory
                ).first()
                
                if checkpoint:
                    logger.info(f"Found checkpoint: {checkpoint.progress}/{checkpoint.total}")
                    return checkpoint.checkpoint_data
                
        except Exception as e:
            logger.error(f"Error loading checkpoint: {e}")
        
        return None
    
    def _clear_checkpoint(self, operation: str, directory: str):
        """Clear checkpoint from database"""
        try:
            with db_manager.get_session() as session:
                checkpoint = session.query(Checkpoint).filter_by(
                    operation=operation,
                    state=directory
                ).first()
                
                if checkpoint:
                    session.delete(checkpoint)
                    session.commit()
                    logger.debug(f"Checkpoint cleared: {operation}")
        except Exception as e:
            logger.error(f"Error clearing checkpoint: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get indexing statistics from database"""
        try:
            with db_manager.get_session() as session:
                total_files = session.query(File).count()
                total_size = session.query(func.sum(File.file_size)).scalar() or 0
                
                # Group by status
                status_counts = {}
                for status, count in session.query(File.status, func.count()).group_by(File.status):
                    status_counts[status] = count
                
                return {
                    'total_files': total_files,
                    'total_size_gb': total_size / 1024 / 1024 / 1024,
                    'status_counts': status_counts
                }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}