"""
Prepare data for EDA by scanning, deduplicating, and migrating audio files
"""
import logging
import sys
from pathlib import Path
import time

from database.db import db_manager
from modules.indexer import FileIndexer
from modules.deduplicator import DuplicateDetector
from modules.metadata import MetadataExtractor
from modules.migrator import FileMigrator
from config import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('eda_data_prep.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def prepare_eda_data(source_dir: str, target_dir: str, reset_db: bool = True):
    """
    Prepare data for EDA analysis
    
    Args:
        source_dir: Source directory to scan (e.g., D:\OLD OLD Backups\Music\ALL MUSIC)
        target_dir: Target directory for migrated files (e.g., F:\data_test)
        reset_db: Whether to reset the database before scanning
    """
    logger.info("="*60)
    logger.info("STARTING EDA DATA PREPARATION")
    logger.info(f"Source: {source_dir}")
    logger.info(f"Target: {target_dir}")
    logger.info("="*60)
    
    # Reset database if requested
    if reset_db:
        logger.info("Resetting database...")
        db_manager.reset_database()
        logger.info("Database reset complete")
    
    # Phase 1: Scan source directory
    logger.info("\n=== PHASE 1: SCANNING ===")
    indexer = FileIndexer()
    
    def scan_progress(data):
        if data.get('progress', 0) % 100 == 0:
            logger.info(f"Scan progress: {data.get('progress', 0)}/{data.get('total', 0)}")
    
    indexer.set_progress_callback(scan_progress)
    
    scan_result = indexer.index_directory(source_dir, resume=False)
    logger.info(f"Scan complete: {scan_result.get('files_added', 0)} files indexed")
    
    # Phase 2: Extract metadata
    logger.info("\n=== PHASE 2: METADATA EXTRACTION ===")
    metadata_extractor = MetadataExtractor()
    
    def metadata_progress(data):
        if data.get('progress', 0) % 100 == 0:
            logger.info(f"Metadata progress: {data.get('progress', 0)}/{data.get('total', 0)}")
    
    metadata_extractor.set_progress_callback(metadata_progress)
    
    metadata_result = metadata_extractor.extract_all_metadata()
    logger.info(f"Metadata extraction complete: {metadata_result.get('extracted', 0)} extracted")
    
    # Phase 3: Find duplicates
    logger.info("\n=== PHASE 3: DUPLICATE DETECTION ===")
    duplicate_detector = DuplicateDetector()
    
    def duplicate_progress(data):
        if data.get('progress', 0) % 100 == 0:
            logger.info(f"Duplicate detection progress: {data.get('progress', 0)}/{data.get('total', 0)}")
    
    duplicate_detector.set_progress_callback(duplicate_progress)
    
    duplicate_result = duplicate_detector.find_duplicates()
    logger.info(f"Duplicate detection complete: {duplicate_result.get('total_groups', 0)} duplicate groups found")
    
    # Phase 4: Migrate files to target directory
    logger.info("\n=== PHASE 4: FILE MIGRATION ===")
    file_migrator = FileMigrator()
    file_migrator.target_base = Path(target_dir)
    
    # Create target directory if it doesn't exist
    file_migrator.target_base.mkdir(parents=True, exist_ok=True)
    
    def migration_progress(data):
        if data.get('progress', 0) % 50 == 0:
            logger.info(f"Migration progress: {data.get('progress', 0)}/{data.get('total', 0)}")
    
    file_migrator.set_progress_callback(migration_progress)
    
    # Skip duplicates during migration to keep dataset clean
    migration_result = file_migrator.migrate_library(skip_duplicates=True)
    logger.info(f"Migration complete: {migration_result.get('files_copied', 0)} files migrated")
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("EDA DATA PREPARATION COMPLETE")
    logger.info(f"Total files scanned: {scan_result.get('files_added', 0)}")
    logger.info(f"Metadata extracted: {metadata_result.get('extracted', 0)}")
    logger.info(f"Duplicate groups: {duplicate_result.get('total_groups', 0)}")
    logger.info(f"Files migrated: {migration_result.get('files_copied', 0)}")
    logger.info(f"Target directory: {target_dir}")
    logger.info("="*60)
    
    return {
        'scan_result': scan_result,
        'metadata_result': metadata_result,
        'duplicate_result': duplicate_result,
        'migration_result': migration_result
    }

if __name__ == "__main__":
    # Default paths - can be overridden via command line
    source = r"D:\OLD OLD Backups\Music\ALL MUSIC"
    target = r"F:\data_test"
    
    if len(sys.argv) > 1:
        source = sys.argv[1]
    if len(sys.argv) > 2:
        target = sys.argv[2]
    
    start_time = time.time()
    result = prepare_eda_data(source, target, reset_db=True)
    elapsed = time.time() - start_time
    
    logger.info(f"\nTotal time: {elapsed/60:.2f} minutes")