"""Smart file migration module with resume capability"""
import shutil
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging
import re

from sqlalchemy import select
from database.db import db_manager
from database.models import File, Migration, Metadata, Duplicate
from utils.hashing import verify_file_copy
from utils.io_optimizer import optimize_path_for_windows
from config import config

logger = logging.getLogger(__name__)

class FileMigrator:
    def __init__(self):
        self.target_base = Path(config.get('target.base_path', 'F:/music production'))
        self.io_threads = config.get('target.io_threads', 4)
        self.progress_callback = None
        self.should_stop = False
        self.test_mode = False
    
    def set_progress_callback(self, callback):
        """Set callback for progress updates"""
        self.progress_callback = callback
    
    def stop(self):
        """Signal to stop migration"""
        self.should_stop = True
    
    def test_migration(self) -> List[Dict[str, str]]:
        """
        Test migration without actually copying files
        Returns list of source->target mappings
        """
        self.test_mode = True
        result = self.migrate_library()
        self.test_mode = False
        return result.get('test_mappings', [])
    
    def migrate_library(self, skip_duplicates: bool = True) -> Dict[str, Any]:
        """
        Migrate music library to organized structure
        
        Args:
            skip_duplicates: Whether to skip non-primary duplicates
        
        Returns:
            Dictionary with migration results
        """
        logger.info(f"Starting library migration to {self.target_base}")
        
        if not self.test_mode:
            # Create target directory if it doesn't exist
            self.target_base.mkdir(parents=True, exist_ok=True)
        
        migrated = 0
        skipped = 0
        failed = 0
        errors = []
        test_mappings = []
        
        try:
            with db_manager.get_session() as session:
                # Get files to migrate
                query = session.query(File).filter(
                    File.status.in_(['indexed', 'analyzed'])
                )
                
                if skip_duplicates:
                    # Get primary file IDs from duplicates
                    primary_ids = select(Duplicate.file_id).filter(
                        Duplicate.is_primary == True
                    )
                    
                    # Get non-duplicate files and primary duplicates
                    non_dup_files = query.outerjoin(
                        Duplicate, File.id == Duplicate.file_id
                    ).filter(
                        (Duplicate.file_id.is_(None)) | (File.id.in_(primary_ids))
                    ).all()
                    
                    files = non_dup_files
                else:
                    files = query.all()
                
                total_files = len(files)
                logger.info(f"Migrating {total_files} files (skip_duplicates={skip_duplicates})")
                
                for i, file in enumerate(files):
                    if self.should_stop:
                        logger.info("Migration stopped by user")
                        break
                    
                    # Check if already migrated
                    existing_migration = session.query(Migration).filter_by(
                        file_id=file.id,
                        status='completed'
                    ).first()
                    
                    if existing_migration:
                        skipped += 1
                        continue
                    
                    # Get metadata for organization
                    metadata = session.query(Metadata).filter_by(file_id=file.id).first()
                    
                    # Determine target path
                    target_path = self._get_target_path(file, metadata)
                    
                    if self.test_mode:
                        test_mappings.append({
                            'source': file.source_path,
                            'target': str(target_path)
                        })
                        migrated += 1
                    else:
                        # Perform actual migration
                        success = self._migrate_file(file, target_path)
                        
                        if success:
                            # Record migration in database
                            migration = Migration(
                                file_id=file.id,
                                source_path=file.source_path,
                                target_path=str(target_path),
                                status='completed',
                                started_at=datetime.utcnow(),
                                completed_at=datetime.utcnow()
                            )
                            session.add(migration)
                            
                            # Update file status
                            file.status = 'migrated'
                            
                            migrated += 1
                        else:
                            failed += 1
                            errors.append(file.source_path)
                    
                    # Commit periodically
                    if not self.test_mode and i % 10 == 0:
                        session.commit()
                    
                    # Update progress
                    if self.progress_callback:
                        self.progress_callback({
                            'operation': 'migration',
                            'progress': i + 1,
                            'total': total_files,
                            'message': f"Migrating: {i + 1}/{total_files}"
                        })
                
                if not self.test_mode:
                    session.commit()
        
        except Exception as e:
            logger.error(f"Fatal error during migration: {e}")
            raise
        
        result = {
            'migrated': migrated,
            'skipped': skipped,
            'failed': failed,
            'errors': len(errors),
            'error_files': errors[:10]
        }
        
        if self.test_mode:
            result['test_mappings'] = test_mappings[:100]  # Return first 100 for preview
        
        logger.info(f"Migration complete: {migrated} migrated, {skipped} skipped, {failed} failed")
        
        return result
    
    def _get_target_path(self, file: File, metadata: Optional[Metadata]) -> Path:
        """
        Determine target path based on metadata
        
        Structure: Artist/original_filename.ext
        or: Unknown/original_filename.ext
        
        Keeps original filename, only organizes by artist folder
        """
        source_path = Path(file.source_path)
        
        # Get artist (or use Unknown)
        artist = "Unknown"
        if metadata and metadata.artist:
            artist = self._sanitize_name(metadata.artist)
        
        # Keep original filename
        filename = source_path.name
        
        # Optimize for Windows file system (just in case the original has issues)
        filename = optimize_path_for_windows(filename)
        
        # Build complete path - just artist/original_filename
        target_path = self.target_base / artist / filename
        
        return target_path
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize name for file system"""
        # Remove/replace illegal characters
        illegal_chars = '<>:"|?*/'
        for char in illegal_chars:
            name = name.replace(char, '_')
        
        # Remove leading/trailing dots and spaces
        name = name.strip('. ')
        
        # Limit length
        if len(name) > 100:
            name = name[:100]
        
        # Replace multiple spaces/underscores
        name = re.sub(r'[\s_]+', ' ', name)
        
        return name
    
    def _migrate_file(self, file: File, target_path: Path) -> bool:
        """
        Copy file to target location with verification
        
        Args:
            file: File record
            target_path: Target path
        
        Returns:
            True if successful, False otherwise
        """
        try:
            source_path = Path(file.source_path)
            
            if not source_path.exists():
                logger.error(f"Source file does not exist: {source_path}")
                return False
            
            # Create target directory
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if target already exists
            if target_path.exists():
                # Check if it's the same file
                if target_path.stat().st_size == source_path.stat().st_size:
                    logger.info(f"File already exists at target: {target_path}")
                    return True
                else:
                    # Add number suffix to avoid overwrite
                    base = target_path.stem
                    ext = target_path.suffix
                    counter = 1
                    while target_path.exists():
                        target_path = target_path.parent / f"{base}_{counter}{ext}"
                        counter += 1
            
            # Copy file
            logger.debug(f"Copying {source_path} to {target_path}")
            shutil.copy2(source_path, target_path)
            
            # Verify copy if configured
            if config.get('migration.verify', True):
                if not verify_file_copy(source_path, target_path):
                    logger.error(f"File verification failed: {target_path}")
                    # Remove corrupted copy
                    try:
                        target_path.unlink()
                    except:
                        pass
                    return False
            
            logger.debug(f"Successfully migrated: {target_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error migrating file {file.source_path}: {e}")
            return False
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status from database"""
        try:
            with db_manager.get_session() as session:
                total = session.query(File).count()
                migrated = session.query(Migration).filter_by(status='completed').count()
                
                # Get recent migrations
                recent = session.query(Migration).filter_by(
                    status='completed'
                ).order_by(Migration.completed_at.desc()).limit(10).all()
                
                recent_files = []
                for mig in recent:
                    recent_files.append({
                        'source': mig.source_path,
                        'target': mig.target_path,
                        'completed_at': mig.completed_at.isoformat() if mig.completed_at else None
                    })
                
                return {
                    'total_files': total,
                    'migrated_files': migrated,
                    'progress_percentage': (migrated / total * 100) if total > 0 else 0,
                    'recent_migrations': recent_files
                }
        
        except Exception as e:
            logger.error(f"Error getting migration status: {e}")
            return {}