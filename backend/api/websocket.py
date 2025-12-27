from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from services.comment_stream import CommentStreamService
from services.eaos_analyzer import EAOSAnalyzerService
from pymongo import MongoClient
from typing import List
import json
import asyncio
from pathlib import Path
from datetime import datetime

router = APIRouter()

# Global instances
comment_service = None
analyzer = EAOSAnalyzerService()
mongo_client = None
active_connections: List[WebSocket] = []


def init_services(data_path: str):
    """
    Initialize services with data path

    Saves comments to MongoDB for batch processing by Airflow
    """
    global comment_service, mongo_client
    comment_service = CommentStreamService(data_path)

    # Initialize MongoDB client
    # Use environment variable or default to localhost (for local development)
    import os
    mongo_host = os.getenv('MONGO_HOST', 'localhost')
    mongo_url = f'mongodb://admin:admin123@{mongo_host}:27017/'

    try:
        mongo_client = MongoClient(mongo_url)
        # Test connection
        mongo_client.server_info()
        print(f"✅ Connected to MongoDB at {mongo_host}:27017")
    except Exception as e:
        print(f"⚠️  Warning: Failed to connect to MongoDB at {mongo_host}:27017: {e}")
        mongo_client = None


@router.websocket("/ws/comments")
async def websocket_comments(websocket: WebSocket):
    """
    WebSocket endpoint for streaming comments

    Flow: Backend → MongoDB (unlabeled) → Wait for Airflow batch processing
    """
    await websocket.accept()
    active_connections.append(websocket)

    try:
        # Stream comments to this client
        async for comment in comment_service.stream_comments(interval=2.0):
            # Save to MongoDB WITHOUT labels (to be processed by Airflow)
            if mongo_client is not None:
                try:
                    db = mongo_client['tv_analytics']
                    collection = db['comments']

                    collection.insert_one({
                        'text': comment.text,
                        'source': 'websocket',
                        'created_at': datetime.now(),
                        'labels': []  # Empty - will be filled by Airflow batch processing
                    })

                    print(f"💾 Saved to MongoDB: {comment.text[:50]}...")

                except Exception as e:
                    print(f"MongoDB save error: {e}")

            # Send to client WITHOUT predictions
            comment.labels = []  # No predictions - must wait for batch processing

            # Add to analyzer
            analyzer.add_comment(comment)

            # Send to client
            await websocket.send_json({
                "type": "comment",
                "data": comment.model_dump(mode='json'),
                "message": "Saved to MongoDB. Will be processed in next batch (every 15 min)."
            })

    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        active_connections.remove(websocket)


@router.websocket("/ws/analytics")
async def websocket_analytics(websocket: WebSocket):
    """WebSocket endpoint for streaming analytics updates"""
    await websocket.accept()

    try:
        while True:
            # Send analytics summary every 5 seconds
            summary = analyzer.get_analytics_summary()
            await websocket.send_json({
                "type": "analytics",
                "data": summary.model_dump(mode='json')
            })
            await asyncio.sleep(5)

    except WebSocketDisconnect:
        print("Analytics client disconnected")
    except Exception as e:
        print(f"Analytics WebSocket error: {e}")


async def broadcast_message(message: dict):
    """Broadcast message to all connected clients"""
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except:
            pass
