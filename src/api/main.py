"""FastAPI application entry point"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime
import structlog

from src.config import settings
from src.api.routes import chat, eaos, trends, health
from src.storage.redis_client_v2 import redis_client_v2
from src.storage.clickhouse_client_v2 import clickhouse_client_v2
from src.storage.elasticsearch_client_v2 import elasticsearch_client_v2
from src.agent.orchestrator import orchestrator

# Setup logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer() if settings.log_format == "json" else structlog.dev.ConsoleRenderer()
    ]
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for startup and shutdown"""
    # Startup
    logger.info("Starting TV Producer Analytics API")

    try:
        # Initialize database connections
        await redis_client_v2.connect()
        clickhouse_client_v2.connect()
        await elasticsearch_client_v2.connect()

        # Initialize agent orchestrator
        await orchestrator.initialize_connections()

        logger.info("All services initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize services", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("Shutting down TV Producer Analytics API")

    try:
        await redis_client_v2.disconnect()
        clickhouse_client_v2.disconnect()
        await elasticsearch_client_v2.disconnect()
        await orchestrator.close()

        logger.info("All services closed successfully")
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))


# Create FastAPI app
app = FastAPI(
    title="TV Producer Analytics API",
    description="""
    Real-time analytics API for TV producers with AI Agent capabilities.

    **Features:**
    - Chat with AI Agent for insights
    - Query EAOS scores and timelines
    - Get trending topics
    - Health monitoring

    **Powered by:**
    - LangGraph + Vertex AI Gemini Pro
    - Redis, ClickHouse, Elasticsearch
    - FastAPI + Python 3.11
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc)
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.api_debug else "An unexpected error occurred",
            "timestamp": datetime.now().isoformat()
        }
    )


# Include routers
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(eaos.router)
app.include_router(trends.router)


# Root endpoint
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "TV Producer Analytics API",
        "version": "1.0.0",
        "status": "operational",
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        },
        "endpoints": {
            "health": "/api/v1/health",
            "chat": "POST /api/v1/chat",
            "eaos_current": "GET /api/v1/eaos/current/{program_id}",
            "eaos_timeline": "GET /api/v1/eaos/timeline/{program_id}",
            "trends": "GET /api/v1/trends"
        }
    }


# Main entry point
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower()
    )
