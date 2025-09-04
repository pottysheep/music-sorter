"""Enhanced search and filter API routes for browsing the music library"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from sqlalchemy import func, or_, and_, distinct
from sqlalchemy.orm import joinedload
import logging
from pathlib import Path

from database.db import db_manager
from database.models import File, Metadata, Duplicate, AudioAnalysis, Migration

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/library")

class SearchFilters(BaseModel):
    search_query: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    genre: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    bpm_min: Optional[float] = None
    bpm_max: Optional[float] = None
    key_signature: Optional[str] = None
    status: Optional[str] = None
    has_duplicates: Optional[bool] = None
    size_min_mb: Optional[float] = None
    size_max_mb: Optional[float] = None
    sort_by: str = "artist"
    sort_order: str = "asc"
    limit: int = 50
    offset: int = 0

@router.post("/search")
async def search_library(filters: SearchFilters):
    """Advanced search with multiple filters"""
    try:
        with db_manager.get_session() as session:
            query = session.query(File).options(
                joinedload(File.file_metadata),
                joinedload(File.audio_analysis),
                joinedload(File.migration)
            )
            
            # Metadata is already loaded via joinedload, no need for explicit join for sorting
            # Only join if we need to filter
            metadata_joined = False
            if any([filters.search_query, filters.artist, filters.album, 
                   filters.genre, filters.year_from, filters.year_to]):
                query = query.join(Metadata, File.id == Metadata.file_id, isouter=True)
                metadata_joined = True
            
            # Join with audio analysis if needed
            if any([filters.bpm_min, filters.bpm_max, filters.key_signature]):
                query = query.join(AudioAnalysis, File.id == AudioAnalysis.file_id, isouter=True)
            
            # Global search across multiple fields
            if filters.search_query:
                search_term = f"%{filters.search_query}%"
                query = query.filter(
                    or_(
                        Metadata.artist.ilike(search_term),
                        Metadata.title.ilike(search_term),
                        Metadata.album.ilike(search_term),
                        File.source_path.ilike(search_term),
                        File.target_path.ilike(search_term)
                    )
                )
            
            # Specific field filters
            if filters.artist:
                query = query.filter(Metadata.artist.ilike(f"%{filters.artist}%"))
            if filters.album:
                query = query.filter(Metadata.album.ilike(f"%{filters.album}%"))
            if filters.genre:
                query = query.filter(Metadata.genre.ilike(f"%{filters.genre}%"))
            
            # Year range filter
            if filters.year_from:
                query = query.filter(Metadata.year >= filters.year_from)
            if filters.year_to:
                query = query.filter(Metadata.year <= filters.year_to)
            
            # BPM range filter
            if filters.bpm_min:
                query = query.filter(AudioAnalysis.bpm >= filters.bpm_min)
            if filters.bpm_max:
                query = query.filter(AudioAnalysis.bpm <= filters.bpm_max)
            
            # Key signature filter
            if filters.key_signature:
                query = query.filter(AudioAnalysis.key_signature == filters.key_signature)
            
            # Status filter
            if filters.status:
                query = query.filter(File.status == filters.status)
            
            # File size filter (convert MB to bytes)
            if filters.size_min_mb:
                query = query.filter(File.file_size >= filters.size_min_mb * 1024 * 1024)
            if filters.size_max_mb:
                query = query.filter(File.file_size <= filters.size_max_mb * 1024 * 1024)
            
            # Duplicate filter
            if filters.has_duplicates is not None:
                if filters.has_duplicates:
                    query = query.filter(File.file_hash.in_(
                        session.query(File.file_hash)
                        .group_by(File.file_hash)
                        .having(func.count(File.file_hash) > 1)
                    ))
                else:
                    query = query.filter(File.file_hash.in_(
                        session.query(File.file_hash)
                        .group_by(File.file_hash)
                        .having(func.count(File.file_hash) == 1)
                    ))
            
            # Get total count before pagination
            total_count = query.count()
            
            # Sorting - ensure metadata table is joined if sorting by metadata fields
            if filters.sort_by in ['artist', 'title', 'album'] and not metadata_joined:
                query = query.join(Metadata, File.id == Metadata.file_id, isouter=True)
            
            sort_column = {
                'artist': Metadata.artist,
                'title': Metadata.title,
                'album': Metadata.album,
                'size': File.file_size,
                'date_added': File.created_at,
                'bpm': AudioAnalysis.bpm,
                'path': File.source_path
            }.get(filters.sort_by, File.created_at)  # Default to created_at instead of artist
            
            if filters.sort_order == 'desc':
                query = query.order_by(sort_column.desc().nullslast())
            else:
                query = query.order_by(sort_column.asc().nullsfirst())
            
            # Pagination
            files = query.limit(filters.limit).offset(filters.offset).all()
            
            # Format response
            results = []
            for file in files:
                metadata = file.file_metadata
                audio = file.audio_analysis
                
                results.append({
                    'id': file.id,
                    'source_path': file.source_path,
                    'target_path': file.migration.target_path if file.migration else None,
                    'file_size': file.file_size,
                    'file_size_mb': round(file.file_size / (1024 * 1024), 2) if file.file_size else 0,
                    'status': file.status,
                    'indexed_at': file.created_at.isoformat() if file.created_at else None,
                    'migrated_at': file.migration.completed_at.isoformat() if file.migration and file.migration.completed_at else None,
                    'metadata': {
                        'artist': metadata.artist if metadata else None,
                        'title': metadata.title if metadata else None,
                        'album': metadata.album if metadata else None,
                        'genre': metadata.genre if metadata else None,
                        'year': metadata.year if metadata else None,
                        'track_number': metadata.track_number if metadata else None,
                        'duration': metadata.duration_seconds if metadata else None
                    },
                    'audio_analysis': {
                        'bpm': audio.bpm if audio else None,
                        'key_signature': audio.key_signature if audio else None,
                        'energy': audio.energy if audio else None
                    } if audio else None
                })
            
            return {
                'results': results,
                'total': total_count,
                'limit': filters.limit,
                'offset': filters.offset,
                'page': (filters.offset // filters.limit) + 1,
                'total_pages': (total_count + filters.limit - 1) // filters.limit
            }
    
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/artists")
async def get_artists():
    """Get list of unique artists with track counts"""
    try:
        with db_manager.get_session() as session:
            artists = session.query(
                Metadata.artist,
                func.count(Metadata.file_id).label('track_count')
            ).filter(
                Metadata.artist.isnot(None),
                Metadata.artist != ''
            ).group_by(
                Metadata.artist
            ).order_by(
                Metadata.artist.asc()
            ).all()
            
            return {
                'artists': [
                    {'name': artist, 'track_count': count}
                    for artist, count in artists
                ],
                'total': len(artists)
            }
    
    except Exception as e:
        logger.error(f"Error fetching artists: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/albums")
async def get_albums(artist: Optional[str] = None):
    """Get list of albums, optionally filtered by artist"""
    try:
        with db_manager.get_session() as session:
            query = session.query(
                Metadata.album,
                Metadata.artist,
                func.count(Metadata.file_id).label('track_count'),
                func.min(Metadata.year).label('year')
            ).filter(
                Metadata.album.isnot(None),
                Metadata.album != ''
            )
            
            if artist:
                query = query.filter(Metadata.artist.ilike(f"%{artist}%"))
            
            albums = query.group_by(
                Metadata.album,
                Metadata.artist
            ).order_by(
                Metadata.album.asc()
            ).all()
            
            return {
                'albums': [
                    {
                        'album': album,
                        'artist': artist,
                        'track_count': count,
                        'year': year
                    }
                    for album, artist, count, year in albums
                ],
                'total': len(albums)
            }
    
    except Exception as e:
        logger.error(f"Error fetching albums: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/genres")
async def get_genres():
    """Get list of unique genres with track counts"""
    try:
        with db_manager.get_session() as session:
            genres = session.query(
                Metadata.genre,
                func.count(Metadata.file_id).label('track_count')
            ).filter(
                Metadata.genre.isnot(None),
                Metadata.genre != ''
            ).group_by(
                Metadata.genre
            ).order_by(
                func.count(Metadata.file_id).desc()
            ).all()
            
            return {
                'genres': [
                    {'name': genre, 'track_count': count}
                    for genre, count in genres
                ],
                'total': len(genres)
            }
    
    except Exception as e:
        logger.error(f"Error fetching genres: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/statistics")
async def get_library_statistics():
    """Get comprehensive library statistics"""
    try:
        with db_manager.get_session() as session:
            # Basic file stats
            total_files = session.query(func.count(File.id)).scalar()
            total_size = session.query(func.sum(File.file_size)).scalar() or 0
            
            # Status breakdown
            status_counts = dict(
                session.query(File.status, func.count(File.id))
                .group_by(File.status)
                .all()
            )
            
            # Files with metadata
            files_with_metadata = session.query(func.count(distinct(Metadata.file_id))).scalar()
            
            # Files with audio analysis
            files_with_analysis = session.query(func.count(distinct(AudioAnalysis.file_id))).scalar()
            
            # Duplicate statistics
            duplicate_groups = session.query(func.count(distinct(Duplicate.group_id))).scalar()
            duplicate_files = session.query(
                func.count(File.id)
            ).filter(
                File.file_hash.in_(
                    session.query(File.file_hash)
                    .group_by(File.file_hash)
                    .having(func.count(File.file_hash) > 1)
                )
            ).scalar()
            
            # Space that could be saved by removing duplicates
            duplicate_space = session.query(
                func.sum(File.file_size)
            ).filter(
                File.file_hash.in_(
                    session.query(File.file_hash)
                    .group_by(File.file_hash)
                    .having(func.count(File.file_hash) > 1)
                )
            ).scalar() or 0
            
            # Get unique duplicate hashes and calculate potential savings
            unique_duplicate_sizes = session.query(
                File.file_hash,
                func.max(File.file_size).label('size'),
                func.count(File.id).label('count')
            ).group_by(
                File.file_hash
            ).having(
                func.count(File.id) > 1
            ).all()
            
            potential_savings = sum(
                size * (count - 1) for _, size, count in unique_duplicate_sizes
            )
            
            # Average BPM
            avg_bpm = session.query(func.avg(AudioAnalysis.bpm)).scalar()
            
            # Key signature distribution
            key_distribution = dict(
                session.query(
                    AudioAnalysis.key_signature,
                    func.count(AudioAnalysis.file_id)
                ).filter(
                    AudioAnalysis.key_signature.isnot(None)
                ).group_by(
                    AudioAnalysis.key_signature
                ).all()
            )
            
            # Top artists by track count
            top_artists = session.query(
                Metadata.artist,
                func.count(Metadata.file_id).label('count')
            ).filter(
                Metadata.artist.isnot(None),
                Metadata.artist != ''
            ).group_by(
                Metadata.artist
            ).order_by(
                func.count(Metadata.file_id).desc()
            ).limit(10).all()
            
            # File format distribution
            format_distribution = {}
            files = session.query(File.source_path).all()
            for (path,) in files:
                ext = Path(path).suffix.lower()
                format_distribution[ext] = format_distribution.get(ext, 0) + 1
            
            return {
                'total_files': total_files,
                'total_size_gb': round(total_size / (1024**3), 2),
                'status_breakdown': status_counts,
                'files_with_metadata': files_with_metadata,
                'metadata_coverage': round(files_with_metadata / total_files * 100, 2) if total_files > 0 else 0,
                'files_with_analysis': files_with_analysis,
                'analysis_coverage': round(files_with_analysis / total_files * 100, 2) if total_files > 0 else 0,
                'duplicates': {
                    'groups': duplicate_groups,
                    'total_files': duplicate_files,
                    'space_used_gb': round(duplicate_space / (1024**3), 2),
                    'potential_savings_gb': round(potential_savings / (1024**3), 2)
                },
                'audio_stats': {
                    'average_bpm': round(avg_bpm, 1) if avg_bpm else None,
                    'key_distribution': key_distribution
                },
                'top_artists': [
                    {'artist': artist, 'track_count': count}
                    for artist, count in top_artists
                ],
                'format_distribution': format_distribution
            }
    
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/folders")
async def get_folder_structure(base_path: Optional[str] = None):
    """Get folder structure of migrated files"""
    try:
        with db_manager.get_session() as session:
            query = session.query(Migration.target_path).join(
                File, Migration.file_id == File.id
            ).filter(
                Migration.target_path.isnot(None),
                Migration.status == 'completed'
            )
            
            if base_path:
                query = query.filter(Migration.target_path.like(f"{base_path}%"))
            
            paths = query.all()
            
            # Build folder structure
            folder_tree = {}
            for (path,) in paths:
                if not path:
                    continue
                    
                path_obj = Path(path)
                parts = path_obj.parts
                
                current = folder_tree
                for part in parts[:-1]:  # Exclude the file name
                    if part not in current:
                        current[part] = {}
                    current = current[part]
            
            # Convert to list format for frontend
            def build_tree_list(tree, parent_path=""):
                items = []
                for name, subtree in tree.items():
                    full_path = f"{parent_path}/{name}" if parent_path else name
                    item = {
                        'name': name,
                        'path': full_path,
                        'type': 'folder'
                    }
                    if subtree:
                        item['children'] = build_tree_list(subtree, full_path)
                    items.append(item)
                return sorted(items, key=lambda x: x['name'].lower())
            
            return {
                'folders': build_tree_list(folder_tree),
                'total_files': len(paths)
            }
    
    except Exception as e:
        logger.error(f"Error fetching folder structure: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recent")
async def get_recent_additions(limit: int = 50):
    """Get recently added or migrated files"""
    try:
        with db_manager.get_session() as session:
            # Recently indexed
            recently_indexed = session.query(File).options(
                joinedload(File.file_metadata)
            ).order_by(
                File.created_at.desc()
            ).limit(limit).all()
            
            # Recently migrated
            recently_migrated = session.query(File).options(
                joinedload(File.file_metadata),
                joinedload(File.migration)
            ).filter(
                File.migration.has()
            ).order_by(
                File.created_at.desc()
            ).limit(limit).all()
            
            def format_file(file):
                metadata = file.file_metadata
                return {
                    'id': file.id,
                    'path': (file.migration.target_path if file.migration else None) or file.source_path,
                    'artist': metadata.artist if metadata else None,
                    'title': metadata.title if metadata else None,
                    'album': metadata.album if metadata else None,
                    'timestamp': file.created_at.isoformat() if file.created_at else None
                }
            
            return {
                'recently_indexed': [format_file(f) for f in recently_indexed],
                'recently_migrated': [format_file(f) for f in recently_migrated]
            }
    
    except Exception as e:
        logger.error(f"Error fetching recent files: {e}")
        raise HTTPException(status_code=500, detail=str(e))