from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from services.comment_stream import CommentStreamService
from services.eaos_analyzer import EAOSAnalyzerService
from services.eaos_model_service import EAOSModelService
from typing import List
import json
import asyncio
from pathlib import Path

router = APIRouter()

# Global instances
comment_service = None
analyzer = EAOSAnalyzerService()
model_service = None
active_connections: List[WebSocket] = []


def init_services(data_path: str):
    """Initialize services with data path"""
    global comment_service, model_service
    comment_service = CommentStreamService(data_path)

    # Initialize EAOS model service
    try:
        model_service = EAOSModelService()
        print("✅ EAOS Model Service initialized successfully")
    except Exception as e:
        print(f"⚠️  Warning: Failed to load EAOS model: {e}")
        print("   Comments will be streamed without EAOS predictions")
        model_service = None


@router.websocket("/ws/comments")
async def websocket_comments(websocket: WebSocket):
    """WebSocket endpoint for streaming comments with EAOS predictions"""
    await websocket.accept()
    active_connections.append(websocket)

    try:
        # Stream comments to this client
        async for comment in comment_service.stream_comments(interval=2.0):
            # Predict EAOS labels if model is available
            if model_service is not None:
                try:
                    # Predict labels from comment text
                    predicted_labels = model_service.predict(
                        comment.text,
                        confidence_threshold=0.3
                    )
                    comment.labels = predicted_labels
                except Exception as e:
                    print(f"Prediction error: {e}")
                    comment.labels = []

            # Add to analyzer
            analyzer.add_comment(comment)

            # Send to client
            await websocket.send_json({
                "type": "comment",
                "data": comment.model_dump(mode='json')
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
