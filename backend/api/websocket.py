from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from services.comment_stream import CommentStreamService
from services.eaos_analyzer import EAOSAnalyzerService
from services.pyspark_client import get_pyspark_client
from typing import List
import json
import asyncio
from pathlib import Path

router = APIRouter()

# Global instances
comment_service = None
analyzer = EAOSAnalyzerService()
pyspark_client = None
active_connections: List[WebSocket] = []


def init_services(data_path: str):
    """
    Initialize services with data path

    Connects to PySpark service for predictions instead of loading model directly
    """
    global comment_service, pyspark_client
    comment_service = CommentStreamService(data_path)

    # Initialize PySpark client
    try:
        pyspark_client = get_pyspark_client()
        if pyspark_client:
            print("✅ Connected to PySpark service for predictions")
        else:
            print("⚠️  Warning: PySpark service not available")
            print("   Comments will be streamed without EAOS predictions")
    except Exception as e:
        print(f"⚠️  Warning: Failed to connect to PySpark service: {e}")
        print("   Comments will be streamed without EAOS predictions")
        pyspark_client = None


@router.websocket("/ws/comments")
async def websocket_comments(websocket: WebSocket):
    """
    WebSocket endpoint for streaming comments with EAOS predictions

    Flow: Backend → PySpark Service (HTTP) → Model → Predictions
    """
    await websocket.accept()
    active_connections.append(websocket)

    try:
        # Stream comments to this client
        async for comment in comment_service.stream_comments(interval=2.0):
            # Predict EAOS labels via PySpark service
            if pyspark_client is not None:
                try:
                    # Call PySpark service for prediction
                    predicted_labels = pyspark_client.predict(
                        comment.text,
                        confidence_threshold=0.3
                    )
                    comment.labels = predicted_labels
                except Exception as e:
                    print(f"Prediction error (PySpark service): {e}")
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
