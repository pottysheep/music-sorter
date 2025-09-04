"""Main FastAPI application for Music Sorter"""
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import asyncio
import uvicorn
import logging
from pathlib import Path

from api.routes import router as api_router
from api.search_routes import router as search_router
from api.websocket import websocket_endpoint, broadcast_progress_task
from config import config
from utils.logger import logger

# Background tasks
background_tasks = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting Music Sorter application...")
    
    # Start background tasks
    task = asyncio.create_task(broadcast_progress_task())
    background_tasks.add(task)
    
    yield
    
    # Shutdown
    logger.info("Shutting down Music Sorter application...")
    
    # Cancel background tasks
    for task in background_tasks:
        task.cancel()

# Create FastAPI application
app = FastAPI(
    title="Music Sorter",
    description="Organize and migrate your music library",
    version="1.0.0",
    lifespan=lifespan
)

# Include API routes
app.include_router(api_router)
app.include_router(search_router)

# WebSocket endpoint
app.add_api_websocket_route("/ws/progress", websocket_endpoint)

# Serve static files (CSS and JS)
static_dir = Path("static")
if static_dir.exists():
    # Mount static files at root level so they can be accessed directly
    @app.get("/style.css")
    async def get_css():
        return FileResponse(str(static_dir / "style.css"), media_type="text/css")
    
    @app.get("/app.js")
    async def get_js():
        return FileResponse(str(static_dir / "app.js"), media_type="application/javascript")
    
    @app.get("/library.css")
    async def get_library_css():
        return FileResponse(str(static_dir / "library.css"), media_type="text/css")
    
    @app.get("/library.js")
    async def get_library_js():
        return FileResponse(str(static_dir / "library.js"), media_type="application/javascript")

# Serve index.html
@app.get("/")
async def root():
    """Serve the main HTML page"""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    else:
        return {"message": "Music Sorter API", "docs": "/docs"}

# Serve library.html
@app.get("/library")
async def library():
    """Serve the library browser page"""
    library_file = static_dir / "library.html"
    if library_file.exists():
        return FileResponse(str(library_file))
    else:
        return {"message": "Library browser not found", "redirect": "/"}

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "application": "Music Sorter"}

if __name__ == "__main__":
    # Get configuration
    host = config.get('server.host', '0.0.0.0')
    port = config.get('server.port', 8000)
    
    # Run the application
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )