"""
FastAPI application factory for G2-Service
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def create_app(config_path: str = None) -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title="G2-Service API",
        description="Backend API per Stampante G2",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/")
    async def root():
        return {"message": "G2-Service API", "version": "1.0.0"}
    
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "G2-Service"}
    
    return app
