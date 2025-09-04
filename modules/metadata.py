"""Metadata extraction and enhancement module"""
import re
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from mutagen import File as MutagenFile
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, TRCK
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis

from database.db import db_manager
from database.models import File, Metadata
from config import config

logger = logging.getLogger(__name__)

class MetadataExtractor:
    def __init__(self):
        self.progress_callback = None
        self.filename_patterns = [
            # Artist - Title
            re.compile(r'^(?P<artist>[^-]+?)\s*-\s*(?P<title>[^\.]+)'),
            # Artist - Album - Track - Title
            re.compile(r'^(?P<artist>[^-]+?)\s*-\s*(?P<album>[^-]+?)\s*-\s*(?P<track>\d+)\s*-\s*(?P<title>[^\.]+)'),
            # Track. Artist - Title
            re.compile(r'^(?P<track>\d+)\.?\s*(?P<artist>[^-]+?)\s*-\s*(?P<title>[^\.]+)'),
            # Track - Title
            re.compile(r'^(?P<track>\d+)\s*-\s*(?P<title>[^\.]+)')
        ]
    
    def set_progress_callback(self, callback):
        """Set callback for progress updates"""
        self.progress_callback = callback
    
    def extract_all_metadata(self) -> Dict[str, Any]:
        """
        Extract metadata for all indexed files
        
        Returns:
            Dictionary with extraction results
        """
        logger.info("Starting metadata extraction...")
        
        extracted = 0
        failed = 0
        errors = []
        
        try:
            with db_manager.get_session() as session:
                # Get all files without metadata
                files = session.query(File).outerjoin(Metadata).filter(
                    Metadata.file_id.is_(None),
                    File.status == 'indexed'
                ).all()
                
                total_files = len(files)
                logger.info(f"Extracting metadata for {total_files} files")
                
                for i, file in enumerate(files):
                    try:
                        metadata = self.extract_metadata(file.source_path)
                        if metadata:
                            self._save_metadata(file.id, metadata)
                            extracted += 1
                        else:
                            failed += 1
                    
                    except Exception as e:
                        logger.error(f"Error extracting metadata for {file.source_path}: {e}")
                        errors.append(file.source_path)
                        failed += 1
                    
                    # Update progress for each file
                    if self.progress_callback:
                        self.progress_callback({
                            'operation': 'metadata_extraction',
                            'progress': i + 1,
                            'total': total_files,
                            'message': f"Extracting metadata: {i + 1}/{total_files}"
                        })
        
        except Exception as e:
            logger.error(f"Fatal error during metadata extraction: {e}")
            raise
        
        return {
            'extracted': extracted,
            'failed': failed,
            'errors': len(errors),
            'error_files': errors[:10]
        }
    
    def extract_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from a single file
        
        Args:
            file_path: Path to audio file
        
        Returns:
            Dictionary with metadata or None if extraction fails
        """
        path = Path(file_path)
        
        if not path.exists():
            return None
        
        # Try to extract from file tags
        metadata = self._extract_from_tags(path)
        
        # If tags are incomplete, try filename parsing
        if not metadata or not all([metadata.get('artist'), metadata.get('title')]):
            filename_metadata = self._extract_from_filename(path)
            if filename_metadata:
                # Merge with existing metadata (filename has lower priority)
                for key, value in filename_metadata.items():
                    if not metadata.get(key):
                        metadata[key] = value
        
        return metadata
    
    def _extract_from_tags(self, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from file tags using mutagen"""
        metadata = {}
        
        try:
            audio_file = MutagenFile(str(file_path))
            
            if audio_file is None:
                return metadata
            
            # Get format
            if isinstance(audio_file, MP3):
                metadata['format'] = 'mp3'
            elif isinstance(audio_file, FLAC):
                metadata['format'] = 'flac'
            elif isinstance(audio_file, MP4):
                metadata['format'] = 'm4a'
            elif isinstance(audio_file, OggVorbis):
                metadata['format'] = 'ogg'
            else:
                metadata['format'] = file_path.suffix.lower()[1:]
            
            # Get audio properties
            if hasattr(audio_file.info, 'bitrate'):
                metadata['bitrate'] = audio_file.info.bitrate
            if hasattr(audio_file.info, 'sample_rate'):
                metadata['sample_rate'] = audio_file.info.sample_rate
            if hasattr(audio_file.info, 'length'):
                metadata['duration_seconds'] = audio_file.info.length
            
            # Extract tags based on format
            if isinstance(audio_file, MP3):
                if audio_file.tags:
                    metadata.update(self._extract_id3_tags(audio_file.tags))
            
            elif isinstance(audio_file, FLAC) or isinstance(audio_file, OggVorbis):
                if audio_file.tags:
                    metadata['artist'] = audio_file.tags.get('artist', [None])[0]
                    metadata['album'] = audio_file.tags.get('album', [None])[0]
                    metadata['title'] = audio_file.tags.get('title', [None])[0]
                    metadata['genre'] = audio_file.tags.get('genre', [None])[0]
                    
                    # Year
                    year = audio_file.tags.get('date', [None])[0]
                    if year:
                        try:
                            metadata['year'] = int(str(year)[:4])
                        except:
                            pass
                    
                    # Track number
                    track = audio_file.tags.get('tracknumber', [None])[0]
                    if track:
                        try:
                            metadata['track_number'] = int(str(track).split('/')[0])
                        except:
                            pass
            
            elif isinstance(audio_file, MP4):
                if audio_file.tags:
                    metadata['artist'] = audio_file.tags.get('\xa9ART', [None])[0]
                    metadata['album'] = audio_file.tags.get('\xa9alb', [None])[0]
                    metadata['title'] = audio_file.tags.get('\xa9nam', [None])[0]
                    metadata['genre'] = audio_file.tags.get('\xa9gen', [None])[0]
                    
                    # Year
                    year = audio_file.tags.get('\xa9day', [None])[0]
                    if year:
                        try:
                            metadata['year'] = int(str(year)[:4])
                        except:
                            pass
                    
                    # Track number
                    track = audio_file.tags.get('trkn', [(None, None)])[0]
                    if track and track[0]:
                        metadata['track_number'] = track[0]
        
        except Exception as e:
            logger.debug(f"Error extracting tags from {file_path}: {e}")
        
        # Clean up None values
        return {k: v for k, v in metadata.items() if v is not None}
    
    def _extract_id3_tags(self, tags: ID3) -> Dict[str, Any]:
        """Extract metadata from ID3 tags"""
        metadata = {}
        
        # Title
        if 'TIT2' in tags:
            metadata['title'] = str(tags['TIT2'])
        
        # Artist
        if 'TPE1' in tags:
            metadata['artist'] = str(tags['TPE1'])
        
        # Album
        if 'TALB' in tags:
            metadata['album'] = str(tags['TALB'])
        
        # Year
        if 'TDRC' in tags:
            try:
                metadata['year'] = int(str(tags['TDRC'])[:4])
            except:
                pass
        
        # Genre
        if 'TCON' in tags:
            metadata['genre'] = str(tags['TCON'])
        
        # Track number
        if 'TRCK' in tags:
            try:
                track = str(tags['TRCK']).split('/')[0]
                metadata['track_number'] = int(track)
            except:
                pass
        
        return metadata
    
    def _extract_from_filename(self, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from filename using patterns"""
        metadata = {}
        filename = file_path.stem  # Filename without extension
        
        # Try each pattern
        for pattern in self.filename_patterns:
            match = pattern.match(filename)
            if match:
                groups = match.groupdict()
                
                if 'artist' in groups and groups['artist']:
                    metadata['artist'] = groups['artist'].strip()
                
                if 'title' in groups and groups['title']:
                    metadata['title'] = groups['title'].strip()
                
                if 'album' in groups and groups['album']:
                    metadata['album'] = groups['album'].strip()
                
                if 'track' in groups and groups['track']:
                    try:
                        metadata['track_number'] = int(groups['track'])
                    except:
                        pass
                
                break  # Use first matching pattern
        
        # If no pattern matched, use filename as title
        if not metadata:
            metadata['title'] = filename
        
        return metadata
    
    def _save_metadata(self, file_id: int, metadata: Dict[str, Any]):
        """Save metadata to database"""
        try:
            with db_manager.get_session() as session:
                # Check if metadata already exists
                existing = session.query(Metadata).filter_by(file_id=file_id).first()
                
                if existing:
                    # Update existing metadata
                    for key, value in metadata.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                else:
                    # Create new metadata record
                    metadata_record = Metadata(
                        file_id=file_id,
                        artist=metadata.get('artist'),
                        album=metadata.get('album'),
                        title=metadata.get('title'),
                        track_number=metadata.get('track_number'),
                        year=metadata.get('year'),
                        genre=metadata.get('genre'),
                        duration_seconds=metadata.get('duration_seconds'),
                        bitrate=metadata.get('bitrate'),
                        sample_rate=metadata.get('sample_rate'),
                        format=metadata.get('format')
                    )
                    session.add(metadata_record)
                
                # Update file status
                file = session.query(File).get(file_id)
                if file:
                    file.status = 'analyzed'
                
                session.commit()
        
        except Exception as e:
            logger.error(f"Error saving metadata for file {file_id}: {e}")