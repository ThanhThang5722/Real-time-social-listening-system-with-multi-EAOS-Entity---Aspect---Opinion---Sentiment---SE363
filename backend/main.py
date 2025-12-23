from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import routes, websocket
from services.kafka_producer import KafkaProducerService
from pathlib import Path
import os
import asyncio

# Initialize FastAPI app
app = FastAPI(
    title="EAOS Dashboard API",
    description="Real-time comment analysis dashboard with multi-EAOS (Entity-Aspect-Opinion-Sentiment) detection",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(routes.router, prefix="/api", tags=["api"])
app.include_router(websocket.router, prefix="/api", tags=["websocket"])

# Global Kafka producer instance and background task
kafka_producer = None
producer_task = None

# Initialize services on startup
@app.on_event("startup")
async def startup_event():
    """Initialize services with data path and start Kafka producer"""
    global kafka_producer, producer_task

    # Path to filtered.json
    data_path = Path(__file__).parent.parent.parent / "clean" / "filtered.json"

    if not data_path.exists():
        print(f"Warning: Data file not found at {data_path}")
        print("Using mock data instead")
        data_path = None

    # Initialize WebSocket services with Kafka and MongoDB enabled
    await websocket.init_services(
        str(data_path) if data_path else None,
        use_kafka=True,
        use_mongodb=True
    )
    print(f"Services initialized with data path: {data_path}")

    # Start Kafka Producer in background
    if data_path:
        try:
            kafka_producer = KafkaProducerService(str(data_path))
            await kafka_producer.start()

            # Run producer streaming in background task
            producer_task = asyncio.create_task(kafka_producer.stream_to_kafka())
            print("[Main] Kafka producer started and streaming in background")
        except Exception as e:
            print(f"[Main] Failed to start Kafka producer: {e}")
            print("[Main] Application will use file-based streaming")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global kafka_producer, producer_task

    # Stop Kafka producer
    if producer_task:
        producer_task.cancel()
        try:
            await producer_task
        except asyncio.CancelledError:
            pass

    if kafka_producer:
        await kafka_producer.stop()
        print("[Main] Kafka producer stopped")

    # Disconnect MongoDB
    if websocket.mongodb_repo:
        await websocket.mongodb_repo.disconnect()
        print("[Main] MongoDB disconnected")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "EAOS Dashboard API",
        "version": "1.0.0",
        "docs": "/docs",
        "websocket_endpoints": {
            "comments": "/api/ws/comments",
            "analytics": "/api/ws/analytics"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
