"""Audio file classifier - determines if files are songs or samples"""
import logging
import random
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
        # Load classification categories from config
        self.categories = config.get('classification.categories', ['song', 'sample', 'stem', 'unknown'])
        
        # For now, use random classification with weighted probabilities
        # This will be replaced with ML model later
        self.classification_weights = {
            'song': 0.5,    # 50% chance
            'sample': 0.25,  # 25% chance
            'stem': 0.2,     # 20% chance
            'unknown': 0.05  # 5% chance
        }
        
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
        
        # Initialize counters for all categories
        category_counts = {cat: 0 for cat in self.categories}
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
                        # Re-attach file to current session
                        file = session.merge(file)
                        
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
                        category_counts[classification['type']] = category_counts.get(classification['type'], 0) + 1
                        
                        # Log progress every 100 files
                        if i % 100 == 0 and i > 0:
                            counts_str = ', '.join([f"{cat.capitalize()}: {category_counts.get(cat, 0)}" for cat in self.categories])
                            logger.info(f"Classification progress: {i}/{total_files} - {counts_str}")
                            session.commit()
                        
                        # Update progress more frequently for UI
                        if self.progress_callback:
                            if i % 5 == 0 or i == total_files - 1:  # Every 5 files or last file
                                self.progress_callback({
                                    'operation': 'classification',
                                    'progress': i + 1,
                                    'total': total_files,
                                    'message': f"Classified {i + 1}/{total_files} files (Songs: {category_counts.get('song', 0)}, Samples: {category_counts.get('sample', 0)}, Stems: {category_counts.get('stem', 0)})"
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
                        'message': f"Classification complete: {category_counts.get('song', 0)} songs, {category_counts.get('sample', 0)} samples, {category_counts.get('stem', 0)} stems, {category_counts.get('unknown', 0)} unknown"
                    })
        
        except Exception as e:
            logger.error(f"Fatal error during classification: {e}")
            raise
        
        results = {
            'total_files': total_files,
            'songs': category_counts.get('song', 0),
            'samples': category_counts.get('sample', 0),
            'stems': category_counts.get('stem', 0),
            'unknown': category_counts.get('unknown', 0),
            'errors': len(errors),
            'error_files': errors[:10],
            'category_counts': category_counts
        }
        
        counts_str = ', '.join([f"{category_counts.get(cat, 0)} {cat}s" for cat in self.categories])
        logger.info(f"Classification complete: {counts_str}")
        
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
        Classify a single file as song, sample, stem, or unknown
        
        Currently uses random weighted classification as placeholder.
        Will be replaced with ML model that considers:
        - Audio features (duration, spectral characteristics, repetition)
        - Metadata (tags, embedded info)
        - Path and filename patterns
        - File format and encoding
        """
        # Get metadata if available
        metadata = session.query(Metadata).filter_by(file_id=file.id).first()
        
        # Random weighted classification (temporary - will be replaced with ML)
        # Using weighted random choice for realistic distribution
        categories = list(self.classification_weights.keys())
        weights = list(self.classification_weights.values())
        
        # Choose category based on weighted probabilities
        classification_type = random.choices(categories, weights=weights)[0]
        
        # Generate mock confidence based on type (temporary)
        confidence_ranges = {
            'song': (0.7, 0.95),
            'sample': (0.6, 0.85),
            'stem': (0.5, 0.8),
            'unknown': (0.1, 0.3)
        }
        
        min_conf, max_conf = confidence_ranges.get(classification_type, (0.1, 0.3))
        confidence = random.uniform(min_conf, max_conf)
        
        classification = {
            'type': classification_type,
            'confidence': round(confidence, 2),
            'method': 'random_weighted',  # Will be 'ml_model' in future
            'details': {
                'size_mb': file.file_size / 1024 / 1024,
                'path': str(Path(file.source_path).parent.name),
                'filename': Path(file.source_path).name,
                'reason': 'Temporary random classification - ML model pending'
            }
        }
        
        # Add metadata details if available
        if metadata:
            classification['details']['duration'] = metadata.duration_seconds
            classification['details']['format'] = metadata.format
            classification['details']['bitrate'] = metadata.bitrate
        
        return classification
    
    def get_classification_stats(self) -> Dict[str, Any]:
        """Get classification statistics from database"""
        try:
            with db_manager.get_session() as session:
                total = session.query(Classification).count()
                
                songs = session.query(Classification).filter_by(file_type='song').count()
                samples = session.query(Classification).filter_by(file_type='sample').count()
                stems = session.query(Classification).filter_by(file_type='stem').count()
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
                    'stems': stems,
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