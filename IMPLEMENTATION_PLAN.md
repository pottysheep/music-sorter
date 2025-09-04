# Music Library Migration App - Complete Implementation Plan

## Application Overview
A robust, reusable web application for organizing and migrating music libraries from messy HDDs to clean SSD structures, with intelligent deduplication, metadata recovery, and audio analysis.

## Target Directory Structure
```
F:\music production\
└── [Artist Name]\
    ├── [Album Name]\
    │   └── [Track Number] - [Track Title].mp3
    └── Singles\
        └── [Track Title].mp3
```

## Architecture

### Backend (Python + FastAPI)
```
music_sorter/
├── app.py                  # FastAPI main application
├── config.py              # Configuration management
├── database/
│   ├── __init__.py
│   ├── models.py          # SQLAlchemy models
│   └── db.py             # Database connection
├── modules/
│   ├── indexer.py        # File discovery and indexing
│   ├── analyzer.py       # File classification
│   ├── deduplicator.py   # Duplicate detection
│   ├── metadata.py       # Metadata extraction/enhancement
│   ├── migrator.py       # File migration engine
│   ├── audio_analysis.py # BPM/key detection
│   └── fingerprint.py    # Audio fingerprinting
├── api/
│   ├── routes.py         # REST endpoints
│   └── websocket.py      # Real-time progress
├── utils/
│   ├── hashing.py        # File hashing utilities
│   ├── io_optimizer.py   # HDD I/O optimization
│   └── logger.py         # Logging setup
└── static/
    ├── index.html        # Single-page frontend
    ├── app.js           # Vanilla JavaScript
    └── style.css        # Simple styling
```

### Frontend (Dead Simple HTML/JS)
- Single `index.html` file
- Vanilla JavaScript - no frameworks
- Basic CSS for clean UI
- WebSocket for real-time progress
- Drag & drop folder selection

## Database Schema (SQLite)

```sql
-- Main file index
CREATE TABLE files (
    id INTEGER PRIMARY KEY,
    source_path TEXT UNIQUE NOT NULL,
    file_size INTEGER,
    modified_date TIMESTAMP,
    file_hash TEXT,
    audio_hash TEXT,
    status TEXT DEFAULT 'indexed',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Metadata information
CREATE TABLE metadata (
    file_id INTEGER PRIMARY KEY,
    artist TEXT,
    album TEXT,
    title TEXT,
    track_number INTEGER,
    year INTEGER,
    genre TEXT,
    duration_seconds FLOAT,
    bitrate INTEGER,
    sample_rate INTEGER,
    format TEXT,
    fingerprint_id TEXT,
    FOREIGN KEY (file_id) REFERENCES files(id)
);

-- Duplicate groups
CREATE TABLE duplicates (
    id INTEGER PRIMARY KEY,
    group_id TEXT,
    file_id INTEGER,
    is_primary BOOLEAN DEFAULT FALSE,
    quality_score INTEGER,
    FOREIGN KEY (file_id) REFERENCES files(id)
);

-- Migration tracking
CREATE TABLE migrations (
    id INTEGER PRIMARY KEY,
    source_path TEXT,
    target_path TEXT,
    status TEXT DEFAULT 'pending',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error TEXT,
    file_id INTEGER,
    FOREIGN KEY (file_id) REFERENCES files(id)
);

-- Audio analysis results
CREATE TABLE audio_analysis (
    file_id INTEGER PRIMARY KEY,
    bpm FLOAT,
    key_signature TEXT,
    energy FLOAT,
    danceability FLOAT,
    loudness_db FLOAT,
    dynamic_range FLOAT,
    analyzed_at TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES files(id)
);

-- Processing checkpoints
CREATE TABLE checkpoints (
    id INTEGER PRIMARY KEY,
    operation TEXT,
    state TEXT,
    progress INTEGER,
    total INTEGER,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);
```

## Core Modules

### 1. File Indexer (`indexer.py`)
- **Smart I/O optimization**: Sequential directory reads, batch processing
- **Checkpoint support**: Resume from interruption
- **Memory efficient**: Stream processing for large directories
- **Features**:
  ```python
  - index_directory(path, batch_size=100)
  - resume_from_checkpoint()
  - estimate_completion_time()
  - validate_accessibility()
  ```

### 2. Duplicate Detector (`deduplicator.py`)
- **Multi-level detection**:
  - Level 1: File size + name similarity
  - Level 2: MD5 hash of first 1MB
  - Level 3: Audio fingerprinting
- **Quality scoring**: Bitrate, format, completeness
- **Smart selection**: Keep highest quality version

### 3. Metadata Pipeline (`metadata.py`)
- **Primary**: Read ID3/Vorbis tags with mutagen
- **Secondary**: Audio fingerprinting via AcoustID
- **Tertiary**: Filename pattern matching
- **API Integration**: MusicBrainz, Last.fm, Spotify

### 4. Migration Engine (`migrator.py`)
- **I/O optimized**: Read HDD sequentially, write SSD in parallel
- **Resume capability**: Track each file's migration status
- **Verification**: Post-copy hash validation
- **Organization**:
  ```python
  - organize_by_artist()
  - handle_unknown_artist()
  - sanitize_filename()
  - create_folder_structure()
  ```

### 5. Audio Analysis (`audio_analysis.py`)
- **librosa integration**: BPM, key detection
- **Quality metrics**: Bitrate, dynamic range, loudness
- **Batch processing**: Analyze in background after migration
- **Caching**: Store results in database

## API Endpoints

```python
# Core Operations
POST   /api/scan          # Start directory scan
GET    /api/scan/status   # Check scan progress
POST   /api/analyze       # Start analysis
GET    /api/duplicates    # Get duplicate groups
POST   /api/migrate       # Start migration
GET    /api/migrate/status # Migration progress
POST   /api/audio-analyze # Start audio analysis

# Management
GET    /api/files         # List indexed files
GET    /api/stats         # Library statistics
POST   /api/checkpoint    # Save checkpoint
DELETE /api/reset         # Clear database

# WebSocket
WS     /ws/progress       # Real-time progress updates
```

## Frontend Interface

### HTML Structure
```html
<!DOCTYPE html>
<html>
<head>
    <title>Music Library Migrator</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div id="app">
        <header>
            <h1>🎵 Music Library Migrator</h1>
        </header>
        
        <main>
            <!-- Step 1: Source Selection -->
            <section id="source-section">
                <h2>1. Select Source Directory</h2>
                <input type="text" id="source-path" placeholder="D:\">
                <button onclick="startScan()">Scan Directory</button>
            </section>

            <!-- Step 2: Analysis Results -->
            <section id="analysis-section" class="hidden">
                <h2>2. Analysis Results</h2>
                <div id="stats"></div>
                <div id="duplicates"></div>
                <button onclick="testMigration()">Test Migration</button>
            </section>

            <!-- Step 3: Migration -->
            <section id="migration-section" class="hidden">
                <h2>3. Migration</h2>
                <input type="text" id="target-path" value="F:\music production">
                <div id="progress-bar"></div>
                <button onclick="startMigration()">Start Migration</button>
            </section>

            <!-- Step 4: Audio Analysis -->
            <section id="audio-analysis-section" class="hidden">
                <h2>4. Audio Analysis</h2>
                <button onclick="startAudioAnalysis()">Analyze Audio</button>
                <div id="analysis-results"></div>
            </section>
        </main>

        <!-- Progress Modal -->
        <div id="progress-modal" class="hidden">
            <div class="progress-content">
                <h3 id="progress-title"></h3>
                <div class="progress-bar">
                    <div id="progress-fill"></div>
                </div>
                <p id="progress-text"></p>
                <ul id="progress-log"></ul>
            </div>
        </div>
    </div>
    <script src="app.js"></script>
</body>
</html>
```

### JavaScript Core (Vanilla)
```javascript
// WebSocket connection for progress
let ws = null;

function connectWebSocket() {
    ws = new WebSocket('ws://localhost:8000/ws/progress');
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateProgress(data);
    };
}

// API calls
async function startScan() {
    const path = document.getElementById('source-path').value;
    const response = await fetch('/api/scan', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({path: path})
    });
    // Handle response
}

// Progress updates
function updateProgress(data) {
    document.getElementById('progress-fill').style.width = data.progress + '%';
    document.getElementById('progress-text').innerText = 
        `${data.current}/${data.total} - ${data.message}`;
}
```

## Key Features

### 1. Checkpointing System
- Save state every 100 files processed
- Resume from exact position after crash
- Track per-operation progress

### 2. Error Recovery
- Retry failed operations with exponential backoff
- Quarantine corrupted files
- Detailed error logging

### 3. Performance Optimizations
- **HDD**: Sequential reads, minimize seeks
- **SSD**: Parallel writes, batch operations
- **Memory**: Stream processing, no full directory loads
- **CPU**: Multi-threading for hash computation

### 4. Audio Service Integration
```python
SERVICES = {
    'acoustid': {
        'api_key': 'config',
        'endpoint': 'https://api.acoustid.org/v2/lookup'
    },
    'musicbrainz': {
        'endpoint': 'https://musicbrainz.org/ws/2/'
    },
    'spotify': {
        'features': ['audio-features', 'track-info']
    }
}
```

### 5. Configuration File
```yaml
# config.yaml
source:
  batch_size: 100
  io_threads: 1  # Keep at 1 for HDD
  
target:
  io_threads: 4  # Parallel for SSD
  
deduplication:
  min_song_size_mb: 2
  max_sample_size_mb: 0.5
  
audio_analysis:
  enabled: true
  bpm_detection: true
  key_detection: true
  
api_keys:
  acoustid: "your_key"
  lastfm: "your_key"
```

## Development Phases

### Phase 1: Core Infrastructure (Tasks 6-7)
- Set up FastAPI project
- Create database schema
- Basic API structure

### Phase 2: Indexing & Analysis (Tasks 8-11)
- File indexer with checkpointing
- Duplicate detection
- Metadata extraction

### Phase 3: Migration Engine (Task 12)
- Smart copy with resume
- Folder organization
- Verification

### Phase 4: Audio Features (Tasks 13)
- BPM/key detection
- Quality analysis
- API integration

### Phase 5: Frontend (Tasks 16-18)
- HTML interface
- JavaScript functionality
- Progress visualization

### Phase 6: Polish (Tasks 19-25)
- Error handling
- Testing
- Documentation
- Packaging

## Deployment
```bash
# Install
uv pip install -r requirements.txt

# Run
python app.py --host 0.0.0.0 --port 8000

# Access
http://localhost:8000
```

## Implementation Status
Implementation started: 2025-09-04
All components will be built following this plan with uv for dependency management.