"""REST API routes for Music Sorter"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging
import os
from pathlib import Path

from database.db import db_manager
from modules.indexer import FileIndexer
from modules.deduplicator import DuplicateDetector
from modules.metadata import MetadataExtractor
from modules.migrator import FileMigrator
from modules.audio_analysis import AudioAnalyzer
from modules.classifier import AudioClassifier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# Global instances
file_indexer = FileIndexer()
duplicate_detector = DuplicateDetector()
metadata_extractor = MetadataExtractor()
file_migrator = FileMigrator()
audio_analyzer = AudioAnalyzer()
audio_classifier = AudioClassifier()

# Request/Response models
class ScanRequest(BaseModel):
    path: str
    resume: bool = True

class MigrateRequest(BaseModel):
    target_path: str = "F:/music production"
    skip_duplicates: bool = True
    test_mode: bool = False
    create_if_missing: bool = True

class AnalyzeRequest(BaseModel):
    use_migrated_paths: bool = True

# Progress tracking
progress_data = {
    'scan': {'status': 'idle', 'progress': 0, 'total': 0, 'message': ''},
    'duplicates': {'status': 'idle', 'progress': 0, 'total': 0, 'message': ''},
    'metadata': {'status': 'idle', 'progress': 0, 'total': 0, 'message': ''},
    'migrate': {'status': 'idle', 'progress': 0, 'total': 0, 'message': ''},
    'audio': {'status': 'idle', 'progress': 0, 'total': 0, 'message': ''},
    'classification': {'status': 'idle', 'progress': 0, 'total': 0, 'message': ''}
}

def update_progress(operation: str, data: Dict[str, Any]):
    """Update progress data for WebSocket broadcasting"""
    progress_data[operation].update(data)
    progress_data[operation]['status'] = 'running'

# Scanning endpoints
@router.post("/scan")
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """Start directory scanning"""
    if progress_data['scan']['status'] == 'running':
        raise HTTPException(status_code=400, detail="Scan already in progress")
    
    def run_scan():
        try:
            logger.info(f"=== STARTING SCAN PHASE ===")
            logger.info(f"Scanning directory: {request.path} (resume={request.resume})")
            progress_data['scan']['status'] = 'running'
            file_indexer.set_progress_callback(lambda d: update_progress('scan', d))
            result = file_indexer.index_directory(request.path, request.resume)
            progress_data['scan']['status'] = 'completed'
            progress_data['scan']['result'] = result
            logger.info(f"Scan complete: {result.get('files_added', 0)} added, {result.get('files_skipped', 0)} skipped, {result.get('errors', 0)} errors")
            logger.info(f"=== SCAN PHASE COMPLETE ===")
        except Exception as e:
            logger.error(f"Scan error: {e}")
            progress_data['scan']['status'] = 'error'
            progress_data['scan']['error'] = str(e)
    
    background_tasks.add_task(run_scan)
    return {"message": "Scan started", "path": request.path}

@router.get("/scan/status")
async def get_scan_status():
    """Get current scan status"""
    return progress_data['scan']

@router.post("/scan/stop")
async def stop_scan():
    """Stop current scan"""
    file_indexer.stop()
    return {"message": "Scan stop requested"}

# Analysis endpoints
@router.post("/analyze")
async def start_analysis(background_tasks: BackgroundTasks):
    """Start metadata extraction, duplicate detection, and classification"""
    if progress_data['metadata']['status'] == 'running':
        raise HTTPException(status_code=400, detail="Analysis already in progress")
    
    def run_analysis():
        try:
            # Extract metadata
            logger.info("=== STARTING ANALYSIS PHASE ===")
            logger.info("Step 1/3: Extracting metadata from all files...")
            progress_data['metadata']['status'] = 'running'
            metadata_extractor.set_progress_callback(lambda d: update_progress('metadata', d))
            metadata_result = metadata_extractor.extract_all_metadata()
            progress_data['metadata']['status'] = 'completed'
            progress_data['metadata']['result'] = metadata_result
            logger.info(f"Metadata extraction complete: {metadata_result.get('extracted', 0)} extracted, {metadata_result.get('failed', 0)} failed")
            
            # Find duplicates (now for ALL files)
            logger.info("Step 2/3: Finding duplicate files...")
            progress_data['duplicates']['status'] = 'running'
            duplicate_detector.set_progress_callback(lambda d: update_progress('duplicates', d))
            duplicate_result = duplicate_detector.find_duplicates()
            progress_data['duplicates']['status'] = 'completed'
            progress_data['duplicates']['result'] = duplicate_result
            logger.info(f"Duplicate detection complete: {duplicate_result.get('total_groups', 0)} groups found")
            
            # Classify files as songs or samples
            logger.info("Step 3/3: Classifying files as songs or samples...")
            progress_data['classification']['status'] = 'running'
            audio_classifier.set_progress_callback(lambda d: update_progress('classification', d))
            classification_result = audio_classifier.classify_library(use_primary_only=True)
            progress_data['classification']['status'] = 'completed'
            progress_data['classification']['result'] = classification_result
            logger.info(f"Classification complete: {classification_result.get('songs', 0)} songs, {classification_result.get('samples', 0)} samples, {classification_result.get('unknown', 0)} unknown")
            
            logger.info("=== ANALYSIS PHASE COMPLETE ===")
            
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            progress_data['metadata']['status'] = 'error'
            progress_data['metadata']['error'] = str(e)
    
    background_tasks.add_task(run_analysis)
    return {"message": "Analysis started"}

@router.get("/analyze/status")
async def get_analysis_status():
    """Get analysis status"""
    return {
        'metadata': progress_data['metadata'],
        'duplicates': progress_data['duplicates'],
        'classification': progress_data['classification']
    }

# Duplicate management
@router.get("/duplicates")
async def get_duplicates(limit: int = 100):
    """Get duplicate groups"""
    try:
        duplicates = duplicate_detector.get_duplicate_groups(limit)
        return {"duplicates": duplicates, "count": len(duplicates)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Classification endpoints
@router.get("/classifications")
async def get_classifications(file_type: Optional[str] = None, limit: int = 100):
    """Get classified files"""
    try:
        classifications = audio_classifier.get_classifications(file_type, limit)
        return {"classifications": classifications, "count": len(classifications)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/classifications/stats")
async def get_classification_stats():
    """Get classification statistics"""
    try:
        stats = audio_classifier.get_classification_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Migration endpoints
@router.post("/migrate")
async def start_migration(request: MigrateRequest, background_tasks: BackgroundTasks):
    """Start file migration"""
    if progress_data['migrate']['status'] == 'running':
        raise HTTPException(status_code=400, detail="Migration already in progress")
    
    # Set target path if provided
    if request.target_path:
        file_migrator.target_base = Path(request.target_path)
        
    # Create directory if requested and doesn't exist
    if request.create_if_missing and not file_migrator.target_base.exists():
        file_migrator.target_base.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created target directory: {file_migrator.target_base}")
    
    if request.test_mode:
        # Run test migration synchronously
        try:
            mappings = file_migrator.test_migration()
            return {"test_mode": True, "mappings": mappings[:100]}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    def run_migration():
        try:
            progress_data['migrate']['status'] = 'running'
            file_migrator.set_progress_callback(lambda d: update_progress('migrate', d))
            result = file_migrator.migrate_library(request.skip_duplicates)
            progress_data['migrate']['status'] = 'completed'
            progress_data['migrate']['result'] = result
        except Exception as e:
            logger.error(f"Migration error: {e}")
            progress_data['migrate']['status'] = 'error'
            progress_data['migrate']['error'] = str(e)
    
    background_tasks.add_task(run_migration)
    return {"message": "Migration started"}

@router.get("/migrate/status")
async def get_migration_status():
    """Get migration status"""
    status = progress_data['migrate'].copy()
    
    # Add database status
    db_status = file_migrator.get_migration_status()
    status.update(db_status)
    
    return status

@router.post("/migrate/stop")
async def stop_migration():
    """Stop current migration"""
    file_migrator.stop()
    return {"message": "Migration stop requested"}

# Audio analysis endpoints
@router.post("/audio-analyze")
async def start_audio_analysis(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """Start audio analysis (BPM, key detection)"""
    if progress_data['audio']['status'] == 'running':
        raise HTTPException(status_code=400, detail="Audio analysis already in progress")
    
    def run_audio_analysis():
        try:
            progress_data['audio']['status'] = 'running'
            audio_analyzer.set_progress_callback(lambda d: update_progress('audio', d))
            result = audio_analyzer.analyze_library(request.use_migrated_paths)
            progress_data['audio']['status'] = 'completed'
            progress_data['audio']['result'] = result
        except Exception as e:
            logger.error(f"Audio analysis error: {e}")
            progress_data['audio']['status'] = 'error'
            progress_data['audio']['error'] = str(e)
    
    background_tasks.add_task(run_audio_analysis)
    return {"message": "Audio analysis started"}

@router.get("/audio-analyze/status")
async def get_audio_analysis_status():
    """Get audio analysis status"""
    return progress_data['audio']

@router.post("/audio-analyze/stop")
async def stop_audio_analysis():
    """Stop audio analysis"""
    audio_analyzer.stop()
    return {"message": "Audio analysis stop requested"}

# Statistics and reporting
@router.get("/stats")
async def get_statistics():
    """Get library statistics"""
    try:
        stats = {
            'indexing': file_indexer.get_statistics(),
            'audio_analysis': audio_analyzer.get_analysis_statistics(),
            'migration': file_migrator.get_migration_status()
        }
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/files")
async def get_files(limit: int = 100, offset: int = 0, file_type: Optional[str] = None):
    """Get list of indexed files with optional classification filter"""
    try:
        from database.models import File, Metadata, Classification
        
        with db_manager.get_session() as session:
            query = session.query(File)
            
            # Apply classification filter if specified
            if file_type and file_type in ['song', 'sample', 'stem', 'unknown']:
                query = query.join(Classification).filter(Classification.file_type == file_type)
            
            files = query.limit(limit).offset(offset).all()
            
            file_list = []
            for file in files:
                metadata = session.query(Metadata).filter_by(file_id=file.id).first()
                classification = session.query(Classification).filter_by(file_id=file.id).first()
                
                file_list.append({
                    'id': file.id,
                    'path': file.source_path,
                    'size': file.file_size,
                    'status': file.status,
                    'classification': {
                        'type': classification.file_type if classification else 'unclassified',
                        'confidence': classification.confidence if classification else 0
                    },
                    'metadata': {
                        'artist': metadata.artist if metadata else None,
                        'title': metadata.title if metadata else None,
                        'album': metadata.album if metadata else None
                    } if metadata else None
                })
            
            total = session.query(File).count()
            
            return {
                'files': file_list,
                'total': total,
                'limit': limit,
                'offset': offset
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# File system browsing
@router.post("/create-directory")
async def create_directory(request: Dict[str, Any]):
    """Create a new directory"""
    try:
        path = request.get('path', '').strip()
        if not path:
            raise HTTPException(status_code=400, detail="Path is required")
        
        target_dir = Path(path)
        
        # Check if directory already exists
        if target_dir.exists():
            return {"created": False, "exists": True, "path": str(target_dir)}
        
        # Create the directory with all parent directories
        target_dir.mkdir(parents=True, exist_ok=True)
        
        return {"created": True, "exists": False, "path": str(target_dir)}
    
    except Exception as e:
        logger.error(f"Error creating directory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/browse")
async def browse_directory(path: str = ""):
    """Browse local file system directories"""
    try:
        if not path:
            # Return available drives on Windows
            drives = []
            for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    drives.append({
                        'name': drive,
                        'path': drive,
                        'type': 'drive'
                    })
            return {'items': drives, 'current_path': ''}
        
        path_obj = Path(path)
        if not path_obj.exists():
            raise HTTPException(status_code=404, detail="Path not found")
        
        items = []
        try:
            for item in path_obj.iterdir():
                if item.is_dir():
                    items.append({
                        'name': item.name,
                        'path': str(item),
                        'type': 'directory'
                    })
        except PermissionError:
            pass  # Skip directories we can't access
        
        # Sort directories
        items.sort(key=lambda x: x['name'].lower())
        
        return {
            'items': items,
            'current_path': str(path_obj),
            'parent_path': str(path_obj.parent) if path_obj.parent != path_obj else None
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Database management
@router.delete("/reset")
async def reset_database():
    """Reset the database (delete all data)"""
    try:
        db_manager.reset_database()
        
        # Reset progress data
        for key in progress_data:
            progress_data[key] = {'status': 'idle', 'progress': 0, 'total': 0, 'message': ''}
        
        return {"message": "Database reset successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))