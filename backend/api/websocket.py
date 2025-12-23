from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from services.comment_stream import CommentStreamService
from services.kafka_consumer import KafkaConsumerService
from services.eaos_analyzer import EAOSAnalyzerService
from services.mongodb_repository import MongoDBRepository
from typing import List, Optional
import json
import asyncio
from pathlib import Path

router = APIRouter()

# Global instances
comment_service = None
kafka_consumer: Optional[KafkaConsumerService] = None
mongodb_repo: Optional[MongoDBRepository] = None
analyzer = EAOSAnalyzerService()
active_connections: List[WebSocket] = []


async def init_services(data_path: str, use_kafka: bool = True, use_mongodb: bool = True):
    """
    Initialize services with data path

    Args:
        data_path: Path to filtered.json data file
        use_kafka: Whether to use Kafka consumer (True) or direct file stream (False)
        use_mongodb: Whether to enable MongoDB storage (True) or not (False)
    """
    global comment_service, kafka_consumer, mongodb_repo

    # Always initialize comment service as fallback
    comment_service = CommentStreamService(data_path)

    # Initialize Kafka consumer if enabled
    if use_kafka:
        kafka_consumer = KafkaConsumerService()
        print("[WebSocket] Kafka consumer initialized")

    # Initialize MongoDB repository if enabled
    if use_mongodb:
        try:
            mongodb_repo = MongoDBRepository()
            await mongodb_repo.connect()
            print("[WebSocket] MongoDB repository initialized")
        except Exception as e:
            print(f"[WebSocket] Failed to initialize MongoDB: {e}")
            print("[WebSocket] Continuing without MongoDB storage")


@router.websocket("/ws/comments")
async def websocket_comments(websocket: WebSocket):
    """WebSocket endpoint for streaming comments (with Kafka support)"""
    await websocket.accept()
    active_connections.append(websocket)

    # Start Kafka consumer if available
    consumer_started = False
    if kafka_consumer:
        try:
            await kafka_consumer.start()
            consumer_started = True
            print(f"[WebSocket] Kafka consumer started for client")
        except Exception as e:
            print(f"[WebSocket] Failed to start Kafka consumer: {e}")
            print("[WebSocket] Falling back to file-based streaming")

    try:
        if consumer_started and kafka_consumer:
            # Stream from Kafka
            print("[WebSocket] Streaming comments from Kafka")
            async for comment in kafka_consumer.consume_comments():
                # Add to analyzer
                analyzer.add_comment(comment)

                # Save to MongoDB if available
                if mongodb_repo and mongodb_repo.is_connected:
                    asyncio.create_task(mongodb_repo.save_comment(comment))

                # Send to client
                await websocket.send_json({
                    "type": "comment",
                    "data": comment.model_dump(mode='json'),
                    "source": "kafka"
                })
        else:
            # Fallback: Stream from file directly
            print("[WebSocket] Streaming comments from file")
            async for comment in comment_service.stream_comments(interval=2.0):
                # Add to analyzer
                analyzer.add_comment(comment)

                # Save to MongoDB if available
                if mongodb_repo and mongodb_repo.is_connected:
                    asyncio.create_task(mongodb_repo.save_comment(comment))

                # Send to client
                await websocket.send_json({
                    "type": "comment",
                    "data": comment.model_dump(mode='json'),
                    "source": "file"
                })

    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print("[WebSocket] Client disconnected")
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)
    finally:
        # Stop Kafka consumer when client disconnects
        if consumer_started and kafka_consumer:
            await kafka_consumer.stop()


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
