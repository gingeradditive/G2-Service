#!/usr/bin/env python3
"""
Main entry point for G2-Service
"""

import uvicorn
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.app import create_app

def main():
    """Start the G2-Service API server"""
    app = create_app()
    
    uvicorn.run(
        app,
        host="localhost",
        port=8080,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()
