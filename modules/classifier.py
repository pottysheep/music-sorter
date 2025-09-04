"""Audio file classifier - determines if files are songs or samples"""
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from sqlalchemy import select
from database.db import db_manager
from database.models import File, Metadata, Duplicate, Classification
from config import config

logger = logging.getLogger(__name__)

class AudioClassifier:
    def __init__(self):
        # Size thresholds (will be part of more complex logic later)
        self.min_song_size = config.get('deduplication.min_song_size_mb', 2) * 1024 * 1024
        self.max_sample_size = config.get('deduplication.max_sample_size_mb', 0.5) * 1024 * 1024
        self.progress_callback = None
        self.should_stop = False
        
    def set_progress_callback(self, callback):
        """Set callback for progress updates"""
        self.progress_callback = callback
    
    def stop(self):
        """Signal to stop classification"""
        self.should_stop = True
    
    def classify_library(self, use_primary_only: bool = True) -> Dict[str, Any]:
        """
        Classify all audio files as songs or samples
        
        Args:
            use_primary_only: If True, only classify primary files from duplicate groups
        
        Returns:
            Dictionary with classification results
        """
        logger.info("Starting audio classification...")
        
        logger.info(f"Getting files to classify (use_primary_only={use_primary_only})...")
        files_to_classify = self._get_files_to_classify(use_primary_only)
        total_files = len(files_to_classify)
        
        logger.info(f"Found {total_files} files to classify")
        
        # Send initial progress
        if self.progress_callback:
            self.progress_callback({
                'operation': 'classification',
                'progress': 0,
                'total': total_files,
                'message': f"Starting classification of {total_files} files"
            })
        
        songs_count = 0
        samples_count = 0
        unknown_count = 0
        errors = []
        
        try:
            with db_manager.get_session() as session:
                # Clear existing classifications
                session.query(Classification).delete()
                session.commit()
                
                for i, file in enumerate(files_to_classify):
                    if self.should_stop:
                        logger.info("Classification stopped by user")
                        break
                    
                    try:
                        # Classify the file
                        classification = self._classify_file(file, session)
                        
                        # Save classification
                        class_record = Classification(
                            file_id=file.id,
                            file_type=classification['type'],
                            confidence=classification['confidence'],
                            classification_method=classification['method'],
                            classification_details=classification['details']
                        )
                        session.add(class_record)
                        
                        # Update counters
                        if classification['type'] == 'song':
                            songs_count += 1
                        elif classification['type'] == 'sample':
                            samples_count += 1
                        else:
                            unknown_count += 1
                        
                        # Log progress every 100 files
                        if i % 100 == 0 and i > 0:
                            logger.info(f"Classification progress: {i}/{total_files} - Songs: {songs_count}, Samples: {samples_count}, Unknown: {unknown_count}")
                            session.commit()
                        
                        # Update progress more frequently for UI
                        if self.progress_callback:
                            if i % 5 == 0 or i == total_files - 1:  # Every 5 files or last file
                                self.progress_callback({
                                    'operation': 'classification',
                                    'progress': i + 1,
                                    'total': total_files,
                                    'message': f"Classified {i + 1}/{total_files} files (Songs: {songs_count}, Samples: {samples_count})"
                                })
                    
                    except Exception as e:
                        logger.error(f"Error classifying file {file.source_path}: {e}")
                        errors.append(str(file.source_path))
                
                # Final commit
                session.commit()
                
                # Send final progress
                if self.progress_callback:
                    self.progress_callback({
                        'operation': 'classification',
                        'progress': total_files,
                        'total': total_files,
                        'message': f"Classification complete: {songs_count} songs, {samples_count} samples, {unknown_count} unknown"
                    })
        
        except Exception as e:
            logger.error(f"Fatal error during classification: {e}")
            raise
        
        results = {
            'total_files': total_files,
            'songs': songs_count,
            'samples': samples_count,
            'unknown': unknown_count,
            'errors': len(errors),
            'error_files': errors[:10]
        }
        
        logger.info(f"Classification complete: {songs_count} songs, {samples_count} samples, {unknown_count} unknown")
        
        return results
    
    def _get_files_to_classify(self, use_primary_only: bool) -> List[File]:
        """Get list of files to classify"""
        files = []
        
        try:
            with db_manager.get_session() as session:
                if use_primary_only:
                    # Get primary files from duplicate groups
                    primary_duplicates = session.query(Duplicate).filter(
                        Duplicate.is_primary == True
                    ).all()
                    
                    primary_file_ids = {d.file_id for d in primary_duplicates}
                    
                    # Get non-duplicate files
                    all_files = session.query(File).filter(
                        File.status.in_(['indexed', 'analyzed'])
                    ).all()
                    
                    non_dup_files = []
                    for file in all_files:
                        # Check if file is in any duplicate group
                        dup = session.query(Duplicate).filter_by(file_id=file.id).first()
                        if not dup:
                            non_dup_files.append(file)
                        elif file.id in primary_file_ids:
                            non_dup_files.append(file)
                    
                    files = non_dup_files
                else:
                    # Get all indexed/analyzed files
                    files = session.query(File).filter(
                        File.status.in_(['indexed', 'analyzed'])
                    ).all()
        
        except Exception as e:
            logger.error(f"Error getting files to classify: {e}")
        
        return files
    
    def _classify_file(self, file: File, session) -> Dict[str, Any]:
        """
        Classify a single file as song or sample
        
        Currently uses simple size-based classification.
        Will be enhanced with:
        - Duration analysis
        - Metadata patterns
        - Path analysis
        - Audio characteristics
        """
        classification = {
            'type': 'unknown',
            'confidence': 0.0,
            'method': 'size_threshold',
            'details': {}
        }
        
        # Get metadata if available
        metadata = session.query(Metadata).filter_by(file_id=file.id).first()
        
        # Simple size-based classification (to be enhanced)
        if file.file_size >= self.min_song_size:
            classification['type'] = 'song'
            classification['confidence'] = 0.8
            classification['details']['size_mb'] = file.file_size / 1024 / 1024
            classification['details']['reason'] = 'File size >= 2MB'
            
        elif file.file_size <= self.max_sample_size:
            classification['type'] = 'sample'
            classification['confidence'] = 0.8
            classification['details']['size_mb'] = file.file_size / 1024 / 1024
            classification['details']['reason'] = 'File size <= 0.5MB'
            
        else:
            # Files between 0.5MB and 2MB - need more analysis
            # For now, classify as unknown
            classification['type'] = 'unknown'
            classification['confidence'] = 0.3
            classification['details']['size_mb'] = file.file_size / 1024 / 1024
            classification['details']['reason'] = 'File size between 0.5MB and 2MB'
            
            # Future enhancements:
            # - Check duration (if available in metadata)
            # - Check path for keywords like 'samples', 'loops', 'one-shots'
            # - Check filename patterns
            # - Analyze audio characteristics
        
        return classification
    
    def get_classification_stats(self) -> Dict[str, Any]:
        """Get classification statistics from database"""
        try:
            with db_manager.get_session() as session:
                total = session.query(Classification).count()
                
                songs = session.query(Classification).filter_by(file_type='song').count()
                samples = session.query(Classification).filter_by(file_type='sample').count()
                unknown = session.query(Classification).filter_by(file_type='unknown').count()
                
                # Get confidence distribution
                high_confidence = session.query(Classification).filter(
                    Classification.confidence >= 0.8
                ).count()
                
                medium_confidence = session.query(Classification).filter(
                    Classification.confidence >= 0.5,
                    Classification.confidence < 0.8
                ).count()
                
                low_confidence = session.query(Classification).filter(
                    Classification.confidence < 0.5
                ).count()
                
                return {
                    'total_classified': total,
                    'songs': songs,
                    'samples': samples,
                    'unknown': unknown,
                    'confidence': {
                        'high': high_confidence,
                        'medium': medium_confidence,
                        'low': low_confidence
                    }
                }
        
        except Exception as e:
            logger.error(f"Error getting classification stats: {e}")
            return {}
    
    def get_classifications(self, file_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get classified files from database
        
        Args:
            file_type: Filter by type ('song', 'sample', 'unknown')
            limit: Maximum number of results
        
        Returns:
            List of classified files with details
        """
        classifications = []
        
        try:
            with db_manager.get_session() as session:
                query = session.query(Classification)
                
                if file_type:
                    query = query.filter_by(file_type=file_type)
                
                results = query.limit(limit).all()
                
                for classification in results:
                    file = session.query(File).get(classification.file_id)
                    metadata = session.query(Metadata).filter_by(file_id=classification.file_id).first()
                    
                    classifications.append({
                        'file_id': classification.file_id,
                        'path': file.source_path,
                        'size_mb': file.file_size / 1024 / 1024,
                        'type': classification.file_type,
                        'confidence': classification.confidence,
                        'method': classification.classification_method,
                        'details': classification.classification_details,
                        'metadata': {
                            'artist': metadata.artist if metadata else None,
                            'title': metadata.title if metadata else None,
                            'duration': metadata.duration if metadata else None
                        } if metadata else None
                    })
        
        except Exception as e:
            logger.error(f"Error getting classifications: {e}")
        
        return classifications