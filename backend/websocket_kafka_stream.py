"""
FastAPI WebSocket endpoint for streaming Kafka data

This module provides WebSocket endpoints that stream real-time data from Kafka
to connected clients.

Usage in main FastAPI app:
    from websocket_kafka_stream import router as ws_kafka_router
    app.include_router(ws_kafka_router)

Or run standalone:
    uvicorn websocket_kafka_stream:app --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, APIRouter
from typing import Set
import asyncio
import json
import logging
from kafka_consumer import KafkaDataConsumer
from mongodb_service import get_mongo_service

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Router for integration with main app
router = APIRouter(prefix="/ws", tags=["websocket"])

# WebSocket connection manager
class ConnectionManager:
    """Manage WebSocket connections and broadcast messages"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """Accept WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        self.active_connections.discard(websocket)
        logger.info(f"Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        if not self.active_connections:
            return

        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send to client: {e}")
                disconnected.add(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def send_personal(self, message: dict, websocket: WebSocket):
        """Send message to specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send to client: {e}")
            self.disconnect(websocket)


# Global manager instance
manager = ConnectionManager()

# Kafka consumer background task
kafka_consumer_task = None
kafka_consumer = None


async def kafka_to_websocket_stream():
    """Background task: consume Kafka and broadcast to WebSocket clients"""
    global kafka_consumer

    try:
        # Initialize Kafka consumer
        kafka_consumer = KafkaDataConsumer(
            topic="tv-comments",
            bootstrap_servers="localhost:9092",
            group_id="websocket-stream",
            auto_offset_reset="latest"  # Only new messages
        )

        await kafka_consumer.start()
        logger.info("🚀 Kafka to WebSocket stream started")

        # Get MongoDB service for optional storage
        mongo = await get_mongo_service()

        # Consume messages
        async for msg in kafka_consumer.consumer:
            try:
                data = msg.value

                # Broadcast to WebSocket clients
                await manager.broadcast({
                    "type": "kafka_message",
                    "topic": msg.topic,
                    "data": data
                })

                # Optionally save to MongoDB
                try:
                    await mongo.save_comment(data)
                except Exception as e:
                    logger.error(f"Failed to save to MongoDB: {e}")

            except Exception as e:
                logger.error(f"Error processing Kafka message: {e}")
                continue

    except asyncio.CancelledError:
        logger.info("Kafka stream task cancelled")
    except Exception as e:
        logger.error(f"Kafka stream error: {e}", exc_info=True)
    finally:
        if kafka_consumer:
            await kafka_consumer.stop()


@router.on_event("startup")
async def startup_kafka_stream():
    """Start Kafka consumer background task on app startup"""
    global kafka_consumer_task

    kafka_consumer_task = asyncio.create_task(kafka_to_websocket_stream())
    logger.info("✅ Kafka WebSocket stream initialized")


@router.on_event("shutdown")
async def shutdown_kafka_stream():
    """Stop Kafka consumer background task on app shutdown"""
    global kafka_consumer_task

    if kafka_consumer_task:
        kafka_consumer_task.cancel()
        try:
            await kafka_consumer_task
        except asyncio.CancelledError:
            pass

    logger.info("🛑 Kafka WebSocket stream stopped")


@router.websocket("/kafka/stream")
async def websocket_kafka_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time Kafka data stream

    Connect from frontend:
        const ws = new WebSocket('ws://localhost:8000/ws/kafka/stream');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Received:', data);
        };
    """
    await manager.connect(websocket)

    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "message": "Connected to Kafka stream"
        })

        # Keep connection alive and handle client messages
        while True:
            try:
                # Receive messages from client (optional)
                data = await websocket.receive_text()

                # Echo back or handle client commands
                await websocket.send_json({
                    "type": "echo",
                    "message": f"Received: {data}"
                })

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break

    finally:
        manager.disconnect(websocket)


@router.websocket("/kafka/filtered")
async def websocket_kafka_filtered(websocket: WebSocket, video_id: str = None):
    """
    WebSocket endpoint with filtering support

    Connect from frontend:
        const ws = new WebSocket('ws://localhost:8000/ws/kafka/filtered?video_id=123');
    """
    await manager.connect(websocket)

    try:
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "filter": {"video_id": video_id} if video_id else None
        })

        # This is a simplified version - in production, you'd create a separate
        # consumer group for each filtered stream
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "echo", "message": data})

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)


# Standalone app for testing
app = FastAPI(title="Kafka WebSocket Stream")
app.include_router(router)


@app.get("/")
async def root():
    return {
        "message": "Kafka WebSocket Stream Server",
        "endpoints": {
            "stream": "ws://localhost:8000/ws/kafka/stream",
            "filtered": "ws://localhost:8000/ws/kafka/filtered?video_id=123"
        },
        "active_connections": len(manager.active_connections)
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "kafka_consumer": "running" if kafka_consumer and kafka_consumer.running else "stopped",
        "active_connections": len(manager.active_connections)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
