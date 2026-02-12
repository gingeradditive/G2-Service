# G2 Printer Configuration Backend API

RESTful API backend for managing G2 3D printer configuration, updates, and system operations.

## Overview

This backend service provides a comprehensive API for G2 printer management, including:
- Printer initialization and configuration
- System updates and maintenance
- Network configuration
- Factory reset operations
- Health monitoring

## Installation

```bash
# Install dependencies
pip3 install -r requirements.txt

# Start the backend server
./start_backend.sh
```

Or run directly:
```bash
python3 backend.py
```

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## API Endpoints

### Health
- `GET /health` - Health check endpoint

### Configuration
- `GET /timezones` - Get available timezones
- `PUT /hostname` - Set system hostname

### Printer Management
- `POST /init` - Initialize printer with serial and timezone

### System Management
- `POST /update` - Update system software
- `POST /check-update` - Check for available updates
- `POST /factory-reset` - Perform factory reset

### Testing
- `POST /test-icon` - Test icon menu states

## Request/Response Format

All endpoints return JSON responses with standardized format:

```json
{
  "status": "success|failed|redirect",
  "message": "Descriptive message",
  "data": {...}  // Optional additional data
}
```

## Error Handling

The API uses proper HTTP status codes:
- `200` - Success
- `400` - Bad Request
- `500` - Internal Server Error

## Development

The backend runs on port 8000 and provides automatic API documentation through FastAPI's built-in docs.

## Dependencies

- FastAPI - Modern web framework for building APIs
- Uvicorn - ASGI server
- Pydantic - Data validation and settings management
