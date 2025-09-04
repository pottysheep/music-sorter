"""WebSocket support for real-time progress updates"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import Set
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.progress_data = {}
    
    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific connection"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connections"""
        if not self.active_connections:
            return
        
        message_str = json.dumps(message)
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.error(f"Error broadcasting: {e}")
                disconnected.add(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def send_progress(self, operation: str, data: dict):
        """Send progress update"""
        message = {
            'type': 'progress',
            'operation': operation,
            'data': data
        }
        await self.broadcast(message)
    
    async def send_complete(self, operation: str, result: dict):
        """Send completion notification"""
        message = {
            'type': 'complete',
            'operation': operation,
            'result': result
        }
        await self.broadcast(message)
    
    async def send_error(self, operation: str, error: str):
        """Send error notification"""
        message = {
            'type': 'error',
            'operation': operation,
            'error': error
        }
        await self.broadcast(message)

# Global connection manager
manager = ConnectionManager()

async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            
            # Handle ping/pong for connection keepalive
            if data == "ping":
                await manager.send_personal_message("pong", websocket)
            else:
                # Echo back any other message (for testing)
                await manager.send_personal_message(f"Echo: {data}", websocket)
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# Progress broadcasting task
async def broadcast_progress_task():
    """Background task to broadcast progress updates"""
    from api.routes import progress_data
    
    last_progress = {}
    
    while True:
        try:
            # Check for progress updates
            for operation, data in progress_data.items():
                if data != last_progress.get(operation):
                    # Progress changed, broadcast update
                    await manager.send_progress(operation, data)
                    last_progress[operation] = data.copy()
            
            await asyncio.sleep(0.5)  # Update every 500ms
        
        except Exception as e:
            logger.error(f"Error in broadcast task: {e}")
            await asyncio.sleep(1)