#!/usr/bin/env python3
"""
Production server for G2-Service
"""

import argparse
import uvicorn
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.app import create_app

def main():
    parser = argparse.ArgumentParser(description="G2-Service Production Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    parser.add_argument("--config", help="Path to configuration file")
    
    args = parser.parse_args()
    
    app = create_app(config_path=args.config)
    
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        workers=args.workers,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    main()
