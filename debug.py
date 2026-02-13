#!/usr/bin/env python3
"""
Debug script for G2-Service
Run this to test the API in debug mode
"""

if __name__ == "__main__":
    print("=== G2-Service Debug Mode ===")
    print("Starting API server with auto-reload...")
    print("API will be available at: http://localhost:8080")
    print("Documentation at: http://localhost:8080/docs")
    print()
    
    import uvicorn
    
    uvicorn.run(
        "src.api.app:create_app",
        host="localhost",
        port=8080,
        reload=True,
        reload_dirs=["src"],
        factory=True,
        log_level="debug"
    )
