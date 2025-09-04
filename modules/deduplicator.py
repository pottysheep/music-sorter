"""Duplicate detection module with multi-level detection"""
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict
import logging

from database.db import db_manager
from database.models import File, Duplicate, Metadata
from config import config

logger = logging.getLogger(__name__)

class DuplicateDetector:
    def __init__(self):
        self.min_song_size = config.get('deduplication.min_song_size_mb', 2) * 1024 * 1024
        self.max_sample_size = config.get('deduplication.max_sample_size_mb', 0.5) * 1024 * 1024
        self.progress_callback = None
    
    def set_progress_callback(self, callback):
        """Set callback for progress updates"""
        self.progress_callback = callback
    
    def find_duplicates(self) -> Dict[str, Any]:
        """
        Find duplicate files using multi-level detection
        
        Returns:
            Dictionary with duplicate detection results
        """
        logger.info("Starting duplicate detection...")
        
        # Level 1: Group by file size and hash
        hash_groups = self._group_by_hash()
        
        # Level 2: Analyze groups and score quality
        duplicate_groups = self._analyze_duplicate_groups(hash_groups)
        
        # Save results to database
        self._save_duplicate_groups(duplicate_groups)
        
        stats = {
            'total_groups': len(duplicate_groups),
            'total_duplicates': sum(len(group['files']) for group in duplicate_groups.values()),
            'space_savings': self._calculate_space_savings(duplicate_groups)
        }
        
        logger.info(f"Found {stats['total_groups']} duplicate groups with {stats['total_duplicates']} files")
        logger.info(f"Potential space savings: {stats['space_savings'] / 1024 / 1024 / 1024:.2f} GB")
        
        return stats
    
    def _group_by_hash(self) -> Dict[str, List[File]]:
        """Group files by their hash"""
        hash_groups = defaultdict(list)
        
        try:
            with db_manager.get_session() as session:
                # Get all indexed files
                files = session.query(File).filter(
                    File.file_hash.isnot(None),
                    File.file_size >= self.min_song_size  # Only consider files likely to be songs
                ).all()
                
                total_files = len(files)
                
                for i, file in enumerate(files):
                    hash_groups[file.file_hash].append(file)
                    
                    if self.progress_callback and i % 100 == 0:
                        self.progress_callback({
                            'operation': 'duplicate_detection',
                            'progress': i,
                            'total': total_files,
                            'message': f"Grouping files by hash: {i}/{total_files}"
                        })
        
        except Exception as e:
            logger.error(f"Error grouping files by hash: {e}")
        
        # Filter out non-duplicates
        return {h: files for h, files in hash_groups.items() if len(files) > 1}
    
    def _analyze_duplicate_groups(self, hash_groups: Dict[str, List[File]]) -> Dict[str, Dict[str, Any]]:
        """Analyze duplicate groups and score quality"""
        duplicate_groups = {}
        
        for hash_value, files in hash_groups.items():
            group_id = str(uuid.uuid4())
            
            # Score each file in the group
            scored_files = []
            for file in files:
                score = self._calculate_quality_score(file)
                scored_files.append({
                    'file': file,
                    'score': score
                })
            
            # Sort by quality score (highest first)
            scored_files.sort(key=lambda x: x['score'], reverse=True)
            
            duplicate_groups[group_id] = {
                'files': scored_files,
                'primary': scored_files[0]['file'],  # Best quality file
                'hash': hash_value
            }
        
        return duplicate_groups
    
    def _calculate_quality_score(self, file: File) -> int:
        """
        Calculate quality score for a file
        Higher score = better quality
        """
        score = 0
        
        try:
            with db_manager.get_session() as session:
                # Get metadata if available
                metadata = session.query(Metadata).filter_by(file_id=file.id).first()
                
                if metadata:
                    # Bitrate score (higher is better)
                    if metadata.bitrate:
                        if metadata.bitrate >= 320:
                            score += 100
                        elif metadata.bitrate >= 256:
                            score += 80
                        elif metadata.bitrate >= 192:
                            score += 60
                        elif metadata.bitrate >= 128:
                            score += 40
                        else:
                            score += 20
                    
                    # Format score
                    if metadata.format:
                        format_scores = {
                            'flac': 150,
                            'wav': 140,
                            'm4a': 90,
                            'mp3': 70,
                            'aac': 60,
                            'ogg': 50,
                            'wma': 30
                        }
                        score += format_scores.get(metadata.format.lower(), 0)
                    
                    # Metadata completeness score
                    if metadata.artist:
                        score += 20
                    if metadata.album:
                        score += 20
                    if metadata.title:
                        score += 20
                    if metadata.year:
                        score += 10
                
                # File path score (prefer organized paths)
                path = Path(file.source_path)
                if any(part in path.parts for part in ['Music', 'music', 'Audio']):
                    score += 10
                if 'backup' in path.parts or 'Backup' in path.parts:
                    score -= 20  # Penalize backup copies
        
        except Exception as e:
            logger.error(f"Error calculating quality score for {file.source_path}: {e}")
        
        return score
    
    def _save_duplicate_groups(self, duplicate_groups: Dict[str, Dict[str, Any]]):
        """Save duplicate groups to database"""
        try:
            with db_manager.get_session() as session:
                # Clear existing duplicate records
                session.query(Duplicate).delete()
                
                for group_id, group_data in duplicate_groups.items():
                    for item in group_data['files']:
                        file = item['file']
                        is_primary = (file.id == group_data['primary'].id)
                        
                        duplicate = Duplicate(
                            group_id=group_id,
                            file_id=file.id,
                            is_primary=is_primary,
                            quality_score=item['score']
                        )
                        session.add(duplicate)
                
                session.commit()
                logger.info(f"Saved {len(duplicate_groups)} duplicate groups to database")
        
        except Exception as e:
            logger.error(f"Error saving duplicate groups: {e}")
    
    def _calculate_space_savings(self, duplicate_groups: Dict[str, Dict[str, Any]]) -> int:
        """Calculate potential space savings from removing duplicates"""
        total_savings = 0
        
        for group_data in duplicate_groups.values():
            # Sum size of all non-primary files
            for item in group_data['files'][1:]:  # Skip primary file
                total_savings += item['file'].file_size
        
        return total_savings
    
    def get_duplicate_groups(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get duplicate groups from database
        
        Args:
            limit: Maximum number of groups to return
        
        Returns:
            List of duplicate groups with file information
        """
        groups = []
        
        try:
            with db_manager.get_session() as session:
                # Get unique group IDs
                group_ids = session.query(Duplicate.group_id).distinct().limit(limit).all()
                
                for (group_id,) in group_ids:
                    # Get all files in this group
                    duplicates = session.query(Duplicate).filter_by(group_id=group_id).all()
                    
                    group_files = []
                    primary_file = None
                    
                    for dup in duplicates:
                        file = session.query(File).get(dup.file_id)
                        metadata = session.query(Metadata).filter_by(file_id=dup.file_id).first()
                        
                        file_info = {
                            'id': file.id,
                            'path': file.source_path,
                            'size': file.file_size,
                            'is_primary': dup.is_primary,
                            'quality_score': dup.quality_score,
                            'metadata': {
                                'artist': metadata.artist if metadata else None,
                                'title': metadata.title if metadata else None,
                                'bitrate': metadata.bitrate if metadata else None,
                                'format': metadata.format if metadata else None
                            }
                        }
                        
                        group_files.append(file_info)
                        if dup.is_primary:
                            primary_file = file_info
                    
                    groups.append({
                        'group_id': group_id,
                        'files': group_files,
                        'primary': primary_file,
                        'count': len(group_files)
                    })
        
        except Exception as e:
            logger.error(f"Error getting duplicate groups: {e}")
        
        return groups