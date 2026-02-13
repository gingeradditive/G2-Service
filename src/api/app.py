"""
FastAPI application factory for G2-Service
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .network import NetworkManager, WiFiNetwork, WiFiConnectionRequest, WiFiConnectionResult
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

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
    
    return app
