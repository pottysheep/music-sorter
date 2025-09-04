# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Music Library Migrator - A web application for organizing and migrating messy music libraries from HDDs to clean, organized SSD structures with intelligent deduplication and metadata recovery.

## Commands

### Development
```bash
# Install dependencies
uv sync

# Run the application
uv run python app.py

# Access the application
# Web UI: http://localhost:8000
# API docs: http://localhost:8000/docs
```

### Python Package Management
This project uses `uv` as the package manager. Always use:
- `uv add <package>` to add new dependencies
- `uv sync` to install dependencies
- `uv run python <script>` to run Python scripts

## Architecture

### Core Modules (`modules/`)
- **indexer.py**: File discovery with I/O optimization for HDDs, checkpoint/resume support
- **deduplicator.py**: Multi-level duplicate detection using MD5 hashing
- **metadata.py**: ID3 tag extraction and filename pattern parsing for metadata recovery
- **migrator.py**: Organized file migration to Artist/Album structure
- **audio_analysis.py**: BPM detection, key signature analysis using librosa

### API Layer (`api/`)
- **routes.py**: FastAPI REST endpoints for all operations
- **websocket.py**: Real-time progress updates via WebSocket

### Database (`database/`)
- **models.py**: SQLAlchemy models for files, metadata, duplicates
- **db.py**: Database session management
- SQLite database stored in `music_library.db`

### Frontend (`static/`)
- Vanilla HTML/JS/CSS - no frameworks
- Single-page application with real-time WebSocket updates
- Clean, simple interface for non-technical users

## Configuration

Main configuration in `config.yaml`:
- **source.io_threads**: Keep at 1 for HDDs to avoid seek thrashing
- **target.io_threads**: Can increase for SSDs (parallel writes)
- **checkpoint.interval**: Auto-save progress every N files
- **deduplication**: Size thresholds for songs vs samples

## Key Implementation Patterns

### I/O Optimization
- Batch processing to minimize HDD seeks
- Sequential reads with configurable batch sizes
- Checkpoint system for resume capability

### Error Handling
- Robust error recovery for corrupted files
- Detailed logging to `music_sorter.log`
- Progress persistence in database

### WebSocket Communication
- Real-time progress updates to frontend
- Broadcast pattern for multiple clients
- Automatic reconnection handling

## Database Schema

Primary tables:
- `files`: Indexed audio files with paths and hashes
- `metadata`: Extracted/parsed metadata
- `duplicates`: Duplicate file groups
- `migration_queue`: Files pending migration
- `checkpoints`: Operation resume points

## Testing & Quality

Currently no automated tests. When implementing tests:
- Use pytest for testing
- Mock file I/O operations for unit tests
- Test checkpoint/resume functionality
- Verify duplicate detection accuracy

## Common Tasks

### Reset Database
```bash
# Delete database to start fresh
rm music_library.db

# Or use API endpoint
curl -X POST http://localhost:8000/api/reset
```

### Monitor Progress
- Check `music_sorter.log` for backend operations
- Browser console for frontend/WebSocket issues
- Database queries for detailed state inspection