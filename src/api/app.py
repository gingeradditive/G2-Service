"""
FastAPI application factory for G2-Service
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from .network import NetworkManager, WiFiNetwork, WiFiConnectionRequest, WiFiConnectionResult
import logging
import os
import re

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def get_ap_credentials() -> dict:
    """Read Access Point credentials from file"""
    credentials_file = "/home/pi/ap_credentials.txt"
    
    if not os.path.exists(credentials_file):
        return None
    
    try:
        with open(credentials_file, 'r') as f:
            content = f.read()
        
        credentials = {}
        for line in content.split('\n'):
            if ':' in line and not line.startswith('='):
                key, value = line.split(':', 1)
                credentials[key.strip().lower()] = value.strip()
        
        return credentials
    except Exception as e:
        logging.error(f"Failed to read AP credentials: {str(e)}")
        return None

def get_ap_testing_info() -> dict:
    """Generate Access Point testing information"""
    credentials = get_ap_credentials()
    
    if not credentials:
        return {
            "available": False,
            "message": "Access Point credentials not found. Please run setup_wifi_complete.sh first."
        }
    
    ssid = credentials.get('ssid', 'Unknown')
    password = credentials.get('password', 'Unknown')
    ip_address = credentials.get('ip address', '192.168.4.1')
    
    return {
        "available": True,
        "access_point": {
            "ssid": ssid,
            "password": password,
            "ip_address": ip_address,
            "interface": credentials.get('interface', 'wlan0'),
            "country": credentials.get('country', 'IT'),
            "network_type": credentials.get('network type', 'Hidden'),
            "ip_range": "192.168.4.2-192.168.4.20"
        },
        "testing_steps": [
            f"1. Connect a device to the network '{ssid}'",
            f"2. Use the password: {password}",
            "3. You should get an IP address in the range 192.168.4.2-192.168.4.20",
            f"4. Test connectivity by pinging {ip_address}"
        ],
        "notes": [
            "This is a hidden network - SSID is not broadcasted",
            "You may need to manually add the network on your device",
            "The Access Point runs on wlan0 interface",
            "Client connections are managed via wlan1 interface"
        ]
    }

def create_app(config_path: str = None) -> FastAPI:
    """Create and configure FastAPI application"""
    
    # Create static directory for offline assets
    static_dir = os.path.join(os.path.dirname(__file__), '..', 'static')
    os.makedirs(static_dir, exist_ok=True)
    
    app = FastAPI(
        title="G2-Service API",
        description="Backend API per Stampante G2 - Offline Mode",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        swagger_ui_parameters={"deepLinking": False, "displayRequestDuration": True},
        swagger_ui_oauth2_redirect_url=None,
    )
    
    # Mount static files for offline Swagger assets
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/docs-offline", response_class=HTMLResponse)
    async def get_offline_docs():
        """
        Get offline API documentation (works without internet)
        
        Returns:
            HTML page with complete API documentation
        """
        static_dir = os.path.join(os.path.dirname(__file__), '..', 'static')
        docs_file = os.path.join(static_dir, 'api-docs.html')
        
        if os.path.exists(docs_file):
            with open(docs_file, 'r') as f:
                return HTMLResponse(content=f.read())
        else:
            # Fallback to simple HTML if file doesn't exist
            return HTMLResponse(content="""
            <!DOCTYPE html>
            <html>
            <head><title>G2-Service API</title></head>
            <body>
                <h1>G2-Service API</h1>
                <p>Offline documentation not available. Use regular /docs endpoint.</p>
                <p><a href="/docs">Go to Swagger UI</a></p>
            </body>
            </html>
            """)
    
    @app.get("/")
    async def root():
        return {"message": "G2-Service API", "version": "1.0.0"}
    
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "G2-Service"}
    
    # WiFi Network endpoints
    network_manager = NetworkManager()
    
    @app.get("/api/wifi/networks", response_model=list[WiFiNetwork])
    async def get_wifi_networks():
        """
        Get list of visible WiFi networks
        
        Returns:
            List of available WiFi networks with signal strength and security info
        """
        try:
            networks = network_manager.get_visible_networks()
            return networks
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to scan WiFi networks: {str(e)}")
    
    @app.get("/api/wifi/status")
    async def get_wifi_status():
        """
        Get WiFi adapter status
        
        Returns:
            WiFi adapter status information
        """
        try:
            status = network_manager.get_wifi_status()
            return status
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get WiFi status: {str(e)}")
    
    @app.post("/api/wifi/rescan")
    async def rescan_wifi_networks():
        """
        Trigger WiFi network rescan
        
        Returns:
            Success status of rescan operation
        """
        try:
            success = network_manager.rescan_networks()
            return {"success": success, "message": "WiFi rescan triggered"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to trigger WiFi rescan: {str(e)}")
    
    @app.post("/api/wifi/connect", response_model=WiFiConnectionResult)
    async def connect_to_wifi_network(request: WiFiConnectionRequest):
        """
        Connect to a WiFi network
        
        Args:
            request: WiFi connection request with SSID and optional password
            
        Returns:
            Connection result with status and details
        """
        try:
            result = network_manager.connect_to_network(request.ssid, request.password)
            return WiFiConnectionResult(**result)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to connect to WiFi network: {str(e)}")
    
    @app.post("/api/wifi/disconnect", response_model=WiFiConnectionResult)
    async def disconnect_from_wifi_network():
        """
        Disconnect from current WiFi network
        
        Returns:
            Disconnection result with status and details
        """
        try:
            result = network_manager.disconnect_network()
            return WiFiConnectionResult(**result)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to disconnect from WiFi network: {str(e)}")
    
    @app.get("/api/wifi/saved-networks")
    async def get_saved_wifi_networks():
        """
        Get list of saved/configured WiFi networks
        
        Returns:
            List of saved network configurations
        """
        try:
            networks = network_manager.get_saved_networks()
            return {"saved_networks": networks}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get saved networks: {str(e)}")
    
    @app.delete("/api/wifi/saved-networks/{ssid:path}")
    async def delete_saved_wifi_network(ssid: str):
        """
        Delete a saved WiFi network configuration
        
        Args:
            ssid: Network name to delete (supports path parameters for special characters)
            
        Returns:
            Deletion result with status and details
        """
        try:
            result = network_manager.delete_saved_network(ssid)
            return WiFiConnectionResult(**result)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete saved network: {str(e)}")
    
    @app.post("/api/wifi/forget-network")
    async def forget_wifi_network(request: WiFiConnectionRequest):
        """
        Forget a WiFi network (remove password and saved configuration)
        
        Args:
            request: WiFi network to forget
            
        Returns:
            Forget result with status and details
        """
        try:
            result = network_manager.forget_network(request.ssid)
            return WiFiConnectionResult(**result)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to forget network: {str(e)}")
    
    @app.get("/api/access-point/info")
    async def get_access_point_info():
        """
        Get Access Point testing information and status
        
        Returns:
            Access Point configuration, testing steps, and current status
        """
        try:
            info = get_ap_testing_info()
            
            # Add real-time AP status check
            try:
                ap_status = network_manager.get_wlan0_ap_status()
                info["ap_status"] = ap_status
                
                # Update available status based on real AP status
                if ap_status.get("status") == "working":
                    info["available"] = True
                    info["status_message"] = "Access Point is working correctly"
                elif ap_status.get("status") == "active":
                    info["available"] = True
                    info["status_message"] = "Access Point is active"
                elif ap_status.get("status") == "inactive":
                    info["available"] = False
                    info["status_message"] = "Access Point is inactive"
                else:
                    info["available"] = False
                    info["status_message"] = f"Access Point status: {ap_status.get('status', 'unknown')}"
                    
            except Exception as e:
                info["ap_status"] = {
                    "status": "error",
                    "message": f"Failed to check AP status: {str(e)}"
                }
                info["status_message"] = "Could not determine AP status"
            
            return info
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get Access Point info: {str(e)}")
    
    return app
