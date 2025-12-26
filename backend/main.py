from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import routes, websocket
from pathlib import Path
import os

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

# Initialize services on startup
@app.on_event("startup")
async def startup_event():
    """Initialize services with data path"""
    # Path to filtered.json
    data_path = Path(__file__).parent.parent.parent / "clean" / "filtered.json"

    if not data_path.exists():
        print(f"Warning: Data file not found at {data_path}")
        print("Using mock data instead")
        data_path = None

    websocket.init_services(str(data_path) if data_path else None)
    print(f"Services initialized with data path: {data_path}")


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
