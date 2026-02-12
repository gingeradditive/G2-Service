"""
G1 Printer Configuration Backend API

RESTful API backend for managing G1 3D printer configuration, updates, and system operations.
Migrated from Flask to FastAPI for better performance and automatic API documentation.
"""

from fastapi import FastAPI, HTTPException, status, Query, Form
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import threading
import time
import socket
import platform
import json
import os
import subprocess
import re

from utils.mainsail_menu import UpdateMainsailMenu
import scripts.init_script as init_script
import scripts.update_script as update_script
import scripts.sethostname_script as sethostname_script
import scripts.checkforupdate_script as checkforupdate_script
import scripts.factoryreset_script as factoryreset_script

app = FastAPI(
    title="G1 Printer Configuration API",
    description="RESTful API for managing G1 3D printer configuration, updates, and system operations",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

menu = UpdateMainsailMenu()

# Pydantic models for response bodies
class APIResponse(BaseModel):
    """Standard API response model"""
    status: str = Field(..., description="Operation status (success/failed)")
    message: str = Field(..., description="Descriptive message about the operation")
    data: Optional[dict] = Field(None, description="Additional response data")

class TimezoneResponse(BaseModel):
    """Response model for timezone data"""
    timezones: List[str] = Field(..., description="List of available timezones")

class WiFiNetwork(BaseModel):
    """WiFi network information model"""
    ssid: str = Field(..., description="Network SSID")
    bssid: Optional[str] = Field(None, description="Network BSSID")
    signal_strength: Optional[int] = Field(None, description="Signal strength in dBm")
    security: Optional[str] = Field(None, description="Security type (e.g., WPA2, WEP, Open)")
    frequency: Optional[str] = Field(None, description="Frequency band (e.g., 2.4GHz, 5GHz)")

class NetworkListResponse(BaseModel):
    """Response model for network list"""
    networks: List[WiFiNetwork] = Field(..., description="List of available WiFi networks")

class CurrentNetworkInfo(BaseModel):
    """Current network connection information"""
    ssid: Optional[str] = Field(None, description="Currently connected SSID")
    ip_address: Optional[str] = Field(None, description="Current IP address")
    gateway: Optional[str] = Field(None, description="Gateway address")
    dns: Optional[List[str]] = Field(None, description="DNS servers")
    signal_strength: Optional[int] = Field(None, description="Current signal strength")
    connection_type: Optional[str] = Field(None, description="Connection type (WiFi/Ethernet)")

class NetworkConnectRequest(BaseModel):
    """Request model for network connection"""
    ssid: str = Field(..., description="Network SSID to connect to")
    password: Optional[str] = Field(None, description="Network password (if required)")

def get_base_url():
    """Get the base URL for the system"""
    system_name = platform.system()

    if system_name == "Windows":
        return "http://127.0.0.1"
    else:  # Linux (quindi anche Raspberry)
        hostname = socket.gethostname()

        if not hostname.endswith(".local"):
            hostname += ".local"

        return f"http://{hostname}"

def run_check_update(url):
    """Run update check and update menu status"""
    update_status = checkforupdate_script.run()
    if (update_status == "update available"):
        menu.set_to_update_available(url)
    elif (update_status == "system not initialized"):
        menu.set_to_initialize_printer(url)
    else:
        menu.set_to_system_ok(url)

# ---------- HEALTH CHECK ----------
@app.get(
    "/health",
    response_model=APIResponse,
    summary="Health Check",
    description="Check if the API server is running and responsive",
    tags=["Health"],
    responses={
        200: {"description": "Server is healthy"},
        503: {"description": "Server is unhealthy"}
    }
)
async def health_check():
    """Health check endpoint to verify server status"""
    return APIResponse(
        status="success",
        message="API server is running",
        data={"timestamp": time.time()}
    )

# ---------- TIMEZONES ----------
@app.get(
    "/timezones",
    response_model=TimezoneResponse,
    summary="Get Available Timezones",
    description="Retrieve list of all available timezones for system configuration",
    tags=["Configuration"],
    responses={
        200: {"description": "Timezones retrieved successfully"},
        500: {"description": "Failed to read timezone data"}
    }
)
async def get_timezones():
    """Get available system timezones"""
    try:
        with open("static/data/timezones.json") as f:
            timezones = json.load(f)
        return TimezoneResponse(timezones=timezones)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load timezones: {str(e)}"
        )

# ---------- INIT ----------
@app.post(
    "/init",
    response_model=APIResponse,
    summary="Initialize Printer",
    description="Initialize the G1 printer with serial number and timezone configuration",
    tags=["Printer Management"],
    responses={
        200: {"description": "Printer initialized successfully"},
        400: {"description": "Invalid request data"},
        500: {"description": "Initialization failed"}
    }
)
async def initialize_printer(
    serial: str = Query(..., description="Printer serial number (e.g., G1-0000-00)", min_length=1, max_length=50),
    timezone: str = Query(..., description="System timezone (e.g., Europe/London)", min_length=1, max_length=50)
):
    """Initialize printer with provided serial number and timezone"""
    try:
        init_script.run(serial, timezone)
        run_check_update(get_base_url())
        return APIResponse(
            status="success",
            message="Printer initialized successfully",
            data={"serial": serial, "timezone": timezone}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Initialization failed: {str(e)}"
        )

# ---------- UPDATE ----------
@app.post(
    "/update",
    response_model=APIResponse,
    summary="Update Printer System",
    description="Perform system update for the G1 printer",
    tags=["System Management"],
    responses={
        200: {"description": "Update completed successfully"},
        302: {"description": "Redirect required to configuration"},
        500: {"description": "Update failed"}
    }
)
async def update_system():
    """Update the printer system software"""
    try:
        update_result = update_script.run()
        if update_result is True:
            menu.set_to_system_ok(get_base_url())
            return APIResponse(
                status="success",
                message="System update completed successfully"
            )
        elif update_result == "redirect":
            menu.set_to_system_ok(get_base_url())
            return APIResponse(
                status="redirect",
                message="Configuration update required - redirect to config page",
                data={"redirect_url": f"{get_base_url()}/config"}
            )
        else:
            menu.set_to_update_available(get_base_url())
            return APIResponse(
                status="failed",
                message="System update failed"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Update failed: {str(e)}"
        )

# ---------- CHECK FOR UPDATE ----------
@app.post(
    "/check-update",
    response_model=APIResponse,
    summary="Check for Updates",
    description="Check if system updates are available for the printer",
    tags=["System Management"],
    responses={
        200: {"description": "Update check completed"},
        500: {"description": "Update check failed"}
    }
)
async def check_for_updates():
    """Check for available system updates"""
    try:
        run_check_update(get_base_url())
        return APIResponse(
            status="success",
            message="Update check completed successfully"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Update check failed: {str(e)}"
        )

# ---------- HOSTNAME ----------
@app.put(
    "/hostname",
    response_model=APIResponse,
    summary="Set System Hostname",
    description="Update the system hostname for network identification",
    tags=["Configuration"],
    responses={
        200: {"description": "Hostname updated successfully"},
        400: {"description": "Invalid hostname format"},
        500: {"description": "Hostname update failed"}
    }
)
async def set_hostname(
    hostname: str = Query(..., description="System hostname (e.g., g1os.local)", min_length=1, max_length=63)
):
    """Set system hostname"""
    try:
        sethostname_script.run(hostname)
        menu.set_to_system_ok(get_base_url())
        return APIResponse(
            status="success",
            message="Hostname updated successfully",
            data={"hostname": hostname}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hostname update failed: {str(e)}"
        )

# ---------- FACTORY RESET ----------
@app.post(
    "/factory-reset",
    response_model=APIResponse,
    summary="Factory Reset",
    description="Perform factory reset to restore default system settings",
    tags=["System Management"],
    responses={
        200: {"description": "Factory reset completed successfully"},
        500: {"description": "Factory reset failed"}
    }
)
async def factory_reset():
    """Perform factory reset of the system"""
    try:
        reset_complete = factoryreset_script.run()
        if reset_complete:
            run_check_update(get_base_url())
            return APIResponse(
                status="success",
                message="Factory reset completed successfully"
            )
        else:
            return APIResponse(
                status="failed",
                message="Factory reset failed"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Factory reset failed: {str(e)}"
        )

# ---------- TEST ICON ----------
@app.post(
    "/test-icon",
    response_model=APIResponse,
    summary="Test Icon Menu State",
    description="Set the icon menu to a specific state for testing purposes",
    tags=["Testing"],
    responses={
        200: {"description": "Icon menu state set successfully"},
        400: {"description": "Invalid action specified"},
        500: {"description": "Failed to set icon menu state"}
    }
)
async def test_icon_menu(
    action: str = Query(..., description="Menu state to set", 
                       enum=["update_available", "initialize_printer", "system_ok", "factory_reset"])
):
    """Test icon menu by setting it to a specific state"""
    try:
        base_url = get_base_url()

        if action == "update_available":
            menu.set_to_update_available(base_url)
        elif action == "initialize_printer":
            menu.set_to_initialize_printer(base_url)
        elif action == "system_ok":
            menu.set_to_system_ok(base_url)
        elif action == "factory_reset":
            menu.set_to_system_ok(base_url)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action: {action}"
            )

        return APIResponse(
            status="success",
            message=f"Icon menu set to: {action}",
            data={"action": action}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set icon menu state: {str(e)}"
        )

# ---------- WIFI MANAGEMENT ----------
def run_command(command: str) -> Dict[str, Any]:
    """Execute shell command and return result"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Command timed out",
            "returncode": -1
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1
        }

def parse_wifi_scan(output: str) -> List[WiFiNetwork]:
    """Parse wifi scan output into WiFiNetwork objects"""
    networks = []
    lines = output.split('\n')
    
    for line in lines:
        if line.strip() and not line.startswith('bssid') and ':' in line:
            # Parse line format: bssid / frequency / signal level / flags / ssid
            parts = line.split('\t')
            if len(parts) >= 5:
                bssid = parts[0].strip()
                frequency = parts[1].strip()
                signal_str = parts[2].strip().replace('signal:', '').replace('dBm', '')
                flags = parts[3].strip()
                ssid = parts[4].strip()
                
                if ssid:  # Only include networks with SSID
                    try:
                        signal_strength = int(signal_str)
                    except ValueError:
                        signal_strength = None
                    
                    # Determine security type from flags
                    security = "Open"
                    if "WPA2" in flags:
                        security = "WPA2"
                    elif "WPA" in flags:
                        security = "WPA"
                    elif "WEP" in flags:
                        security = "WEP"
                    
                    # Determine frequency band
                    freq_band = "2.4GHz" if "2412" in frequency or "2437" in frequency else "5GHz"
                    
                    networks.append(WiFiNetwork(
                        ssid=ssid,
                        bssid=bssid,
                        signal_strength=signal_strength,
                        security=security,
                        frequency=freq_band
                    ))
    
    return networks

def get_current_connection_info() -> CurrentNetworkInfo:
    """Get current network connection information"""
    try:
        # Get current SSID
        ssid_result = run_command("iwgetid -r")
        ssid = ssid_result["stdout"] if ssid_result["success"] and ssid_result["stdout"] else None
        
        # Get IP address
        ip_result = run_command("hostname -I | awk '{print $1}'")
        ip_address = ip_result["stdout"] if ip_result["success"] and ip_result["stdout"] else None
        
        # Get gateway
        gateway_result = run_command("ip route | grep default | awk '{print $3}'")
        gateway = gateway_result["stdout"] if gateway_result["success"] and gateway_result["stdout"] else None
        
        # Get DNS servers
        dns_result = run_command("cat /etc/resolv.conf | grep nameserver | awk '{print $2}'")
        dns = dns_result["stdout"].split('\n') if dns_result["success"] and dns_result["stdout"] else []
        
        # Get signal strength if connected to WiFi
        signal_strength = None
        if ssid:
            signal_result = run_command("iwconfig wlan0 | grep 'Signal level'")
            if signal_result["success"]:
                match = re.search(r'Signal level=(-?\d+) dBm', signal_result["stdout"])
                if match:
                    signal_strength = int(match.group(1))
        
        # Determine connection type
        connection_type = "WiFi" if ssid else "Ethernet" if ip_address else None
        
        return CurrentNetworkInfo(
            ssid=ssid,
            ip_address=ip_address,
            gateway=gateway,
            dns=dns if dns else None,
            signal_strength=signal_strength,
            connection_type=connection_type
        )
    except Exception as e:
        return CurrentNetworkInfo()

@app.get(
    "/wifi/networks",
    response_model=NetworkListResponse,
    summary="Get Available WiFi Networks",
    description="Scan and retrieve list of available WiFi networks",
    tags=["WiFi Management"],
    responses={
        200: {"description": "Network list retrieved successfully"},
        500: {"description": "Failed to scan networks"}
    }
)
async def get_wifi_networks():
    """Get list of available WiFi networks"""
    try:
        # Scan for networks
        scan_result = run_command("sudo iwlist wlan0 scan | grep -E 'bssid|frequency|signal|flags|ssid'")
        
        if not scan_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to scan WiFi networks"
            )
        
        networks = parse_wifi_scan(scan_result["stdout"])
        
        # Sort by signal strength (strongest first)
        networks.sort(key=lambda x: x.signal_strength or -100, reverse=True)
        
        return NetworkListResponse(networks=networks)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get WiFi networks: {str(e)}"
        )

@app.get(
    "/wifi/status",
    response_model=CurrentNetworkInfo,
    summary="Get Current Network Status",
    description="Get current network connection information",
    tags=["WiFi Management"],
    responses={
        200: {"description": "Network status retrieved successfully"},
        500: {"description": "Failed to get network status"}
    }
)
async def get_network_status():
    """Get current network connection status"""
    try:
        return get_current_connection_info()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get network status: {str(e)}"
        )

@app.post(
    "/wifi/connect",
    response_model=APIResponse,
    summary="Connect to WiFi Network",
    description="Connect to a WiFi network using SSID and optional password",
    tags=["WiFi Management"],
    responses={
        200: {"description": "Connection initiated successfully"},
        400: {"description": "Invalid network credentials"},
        500: {"description": "Failed to connect to network"}
    }
)
async def connect_to_wifi(
    ssid: str = Query(..., description="Network SSID to connect to"),
    password: Optional[str] = Query(None, description="Network password (if required)")
):
    """Connect to WiFi network"""
    try:
        # Check if already connected to this network
        current_info = get_current_connection_info()
        if current_info.ssid == ssid:
            return APIResponse(
                status="success",
                message="Already connected to this network",
                data={"ssid": ssid}
            )
        
        # Generate network configuration
        if password:
            # For secured networks
            config = f'''
network={{
    ssid="{ssid}"
    psk="{password}"
    key_mgmt=WPA-PSK
}}
'''
        else:
            # For open networks
            config = f'''
network={{
    ssid="{ssid}"
    key_mgmt=NONE
}}
'''
        
        # Write to wpa_supplicant.conf
        with open('/tmp/wpa_config.conf', 'w') as f:
            f.write(config)
        
        # Backup current config and apply new one
        run_command("sudo cp /etc/wpa_supplicant/wpa_supplicant.conf /etc/wpa_supplicant/wpa_supplicant.conf.bak")
        run_command("sudo cp /tmp/wpa_config.conf /etc/wpa_supplicant/wpa_supplicant.conf")
        
        # Restart WiFi interface
        run_command("sudo wpa_cli -i wlan0 reconfigure")
        run_command("sudo systemctl restart networking")
        
        # Wait a bit for connection
        time.sleep(5)
        
        # Verify connection
        new_info = get_current_connection_info()
        if new_info.ssid == ssid:
            return APIResponse(
                status="success",
                message="Successfully connected to WiFi network",
                data={"ssid": ssid, "ip_address": new_info.ip_address}
            )
        else:
            # Restore backup if connection failed
            run_command("sudo cp /etc/wpa_supplicant/wpa_supplicant.conf.bak /etc/wpa_supplicant/wpa_supplicant.conf")
            run_command("sudo wpa_cli -i wlan0 reconfigure")
            
            return APIResponse(
                status="failed",
                message="Failed to connect to WiFi network. Check credentials and try again.",
                data={"ssid": ssid}
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect to WiFi: {str(e)}"
        )

@app.post(
    "/wifi/disconnect",
    response_model=APIResponse,
    summary="Disconnect from WiFi Network",
    description="Disconnect from current WiFi network",
    tags=["WiFi Management"],
    responses={
        200: {"description": "Disconnected successfully"},
        500: {"description": "Failed to disconnect"}
    }
)
async def disconnect_wifi():
    """Disconnect from current WiFi network"""
    try:
        current_info = get_current_connection_info()
        
        if not current_info.ssid:
            return APIResponse(
                status="success",
                message="Not connected to any WiFi network"
            )
        
        # Disconnect by removing all network configurations
        run_command("sudo wpa_cli -i wlan0 remove_all_networks")
        run_command("sudo wpa_cli -i wlan0 save_config")
        run_command("sudo wpa_cli -i wlan0 reconfigure")
        
        # Wait for disconnection
        time.sleep(3)
        
        # Verify disconnection
        new_info = get_current_connection_info()
        if not new_info.ssid:
            return APIResponse(
                status="success",
                message="Successfully disconnected from WiFi network",
                data={"previous_ssid": current_info.ssid}
            )
        else:
            return APIResponse(
                status="failed",
                message="Failed to disconnect from WiFi network",
                data={"ssid": new_info.ssid}
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect from WiFi: {str(e)}"
        )

@app.post(
    "/wifi/forget",
    response_model=APIResponse,
    summary="Forget WiFi Network",
    description="Remove saved WiFi network configuration",
    tags=["WiFi Management"],
    responses={
        200: {"description": "Network forgotten successfully"},
        404: {"description": "Network not found in saved configurations"},
        500: {"description": "Failed to forget network"}
    }
)
async def forget_wifi_network(
    ssid: str = Query(..., description="Network SSID to forget")
):
    """Remove saved WiFi network configuration"""
    try:
        # Get list of configured networks
        list_result = run_command("wpa_cli -i wlan0 list_networks")
        if not list_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list saved networks"
            )
        
        # Find network ID by SSID
        network_id = None
        for line in list_result["stdout"].split('\n'):
            if ssid in line:
                parts = line.split('\t')
                if len(parts) > 0 and parts[0].isdigit():
                    network_id = parts[0]
                    break
        
        if not network_id:
            return APIResponse(
                status="failed",
                message="Network not found in saved configurations",
                data={"ssid": ssid}
            )
        
        # Remove network
        remove_result = run_command(f"sudo wpa_cli -i wlan0 remove_network {network_id}")
        run_command("sudo wpa_cli -i wlan0 save_config")
        run_command("sudo wpa_cli -i wlan0 reconfigure")
        
        if remove_result["success"]:
            return APIResponse(
                status="success",
                message="Network forgotten successfully",
                data={"ssid": ssid, "network_id": network_id}
            )
        else:
            return APIResponse(
                status="failed",
                message="Failed to forget network",
                data={"ssid": ssid}
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to forget WiFi network: {str(e)}"
        )

@app.get(
    "/wifi/saved",
    response_model=List[str],
    summary="Get Saved WiFi Networks",
    description="Get list of saved WiFi network configurations",
    tags=["WiFi Management"],
    responses={
        200: {"description": "Saved networks retrieved successfully"},
        500: {"description": "Failed to get saved networks"}
    }
)
async def get_saved_networks():
    """Get list of saved WiFi networks"""
    try:
        list_result = run_command("wpa_cli -i wlan0 list_networks")
        if not list_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list saved networks"
            )
        
        saved_networks = []
        for line in list_result["stdout"].split('\n'):
            if '\t' in line and not line.startswith('network'):
                parts = line.split('\t')
                if len(parts) > 1 and parts[1].strip():
                    saved_networks.append(parts[1].strip())
        
        return saved_networks
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get saved networks: {str(e)}"
        )

@app.post(
    "/wifi/enable",
    response_model=APIResponse,
    summary="Enable WiFi Interface",
    description="Enable the WiFi interface (wlan0)",
    tags=["WiFi Management"],
    responses={
        200: {"description": "WiFi enabled successfully"},
        500: {"description": "Failed to enable WiFi"}
    }
)
async def enable_wifi():
    """Enable WiFi interface"""
    try:
        # Bring up the interface
        run_command("sudo ifconfig wlan0 up")
        
        # Enable WiFi via wpa_supplicant
        run_command("sudo wpa_cli -i wlan0 enable")
        
        # Wait for interface to be ready
        time.sleep(2)
        
        return APIResponse(
            status="success",
            message="WiFi interface enabled successfully"
        )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable WiFi: {str(e)}"
        )

@app.post(
    "/wifi/disable",
    response_model=APIResponse,
    summary="Disable WiFi Interface",
    description="Disable the WiFi interface (wlan0)",
    tags=["WiFi Management"],
    responses={
        200: {"description": "WiFi disabled successfully"},
        500: {"description": "Failed to disable WiFi"}
    }
)
async def disable_wifi():
    """Disable WiFi interface"""
    try:
        current_info = get_current_connection_info()
        
        # Disable WiFi via wpa_supplicant
        run_command("sudo wpa_cli -i wlan0 disable")
        
        # Bring down the interface
        run_command("sudo ifconfig wlan0 down")
        
        return APIResponse(
            status="success",
            message="WiFi interface disabled successfully",
            data={"was_connected": current_info.ssid is not None}
        )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable WiFi: {str(e)}"
        )

@app.get(
    "/network/interfaces",
    response_model=Dict[str, Any],
    summary="Get Network Interfaces",
    description="Get information about all network interfaces",
    tags=["Network Configuration"],
    responses={
        200: {"description": "Network interfaces retrieved successfully"},
        500: {"description": "Failed to get network interfaces"}
    }
)
async def get_network_interfaces():
    """Get information about all network interfaces"""
    try:
        # Get interface information
        ifconfig_result = run_command("ifconfig")
        ip_result = run_command("ip addr show")
        
        interfaces = {}
        
        # Parse ifconfig output
        current_interface = None
        for line in ifconfig_result["stdout"].split('\n'):
            if line and not line.startswith(' '):
                # Interface name line
                if ':' in line:
                    interface_name = line.split(':')[0].strip()
                    current_interface = interface_name
                    interfaces[interface_name] = {
                        "name": interface_name,
                        "status": "UP" if "UP" in line else "DOWN",
                        "ipv4": None,
                        "ipv6": None,
                        "mac": None,
                        "netmask": None,
                        "broadcast": None
                    }
            elif current_interface and line.strip():
                # Interface details
                if "inet " in line:
                    parts = line.strip().split()
                    for i, part in enumerate(parts):
                        if part == "inet" and i + 1 < len(parts):
                            ip_info = parts[i + 1].split(':')
                            if len(ip_info) > 1:
                                interfaces[current_interface]["ipv4"] = ip_info[1]
                                interfaces[current_interface]["netmask"] = parts[i + 3] if i + 3 < len(parts) else None
                                interfaces[current_interface]["broadcast"] = parts[i + 5] if i + 5 < len(parts) else None
                            break
                elif "ether " in line:
                    parts = line.strip().split()
                    for i, part in enumerate(parts):
                        if part == "ether" and i + 1 < len(parts):
                            interfaces[current_interface]["mac"] = parts[i + 1]
                            break
        
        return interfaces
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get network interfaces: {str(e)}"
        )

@app.post(
    "/network/restart",
    response_model=APIResponse,
    summary="Restart Network Service",
    description="Restart the network service to apply configuration changes",
    tags=["Network Configuration"],
    responses={
        200: {"description": "Network service restarted successfully"},
        500: {"description": "Failed to restart network service"}
    }
)
async def restart_network():
    """Restart network service"""
    try:
        # Restart networking service
        restart_result = run_command("sudo systemctl restart networking")
        
        if restart_result["success"]:
            # Wait for service to be fully restarted
            time.sleep(5)
            
            return APIResponse(
                status="success",
                message="Network service restarted successfully"
            )
        else:
            return APIResponse(
                status="failed",
                message="Failed to restart network service",
                data={"error": restart_result["stderr"]}
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart network service: {str(e)}"
        )

@app.get(
    "/network/dhcp-lease",
    response_model=Dict[str, Any],
    summary="Get DHCP Lease Information",
    description="Get current DHCP lease information",
    tags=["Network Configuration"],
    responses={
        200: {"description": "DHCP lease information retrieved successfully"},
        404: {"description": "No DHCP lease found"},
        500: {"description": "Failed to get DHCP lease"}
    }
)
async def get_dhcp_lease():
    """Get DHCP lease information"""
    try:
        # Try to read DHCP lease file
        lease_files = [
            "/var/lib/dhcp/dhcpd.leases",
            "/var/lib/dhcp/dhclient.leases",
            "/var/lib/dhcp/dhclient.wlan0.leases"
        ]
        
        lease_info = {}
        
        for lease_file in lease_files:
            if os.path.exists(lease_file):
                with open(lease_file, 'r') as f:
                    content = f.read()
                    lease_info["file"] = lease_file
                    lease_info["content"] = content[-1000:]  # Last 1000 chars
                    break
        
        if not lease_info:
            # Try to get lease info from command
            lease_result = run_command("dhclient -r && dhclient wlan0")
            if lease_result["success"]:
                lease_info["status"] = "DHCP client restarted"
            else:
                lease_info["status"] = "No DHCP lease found"
        
        return lease_info
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get DHCP lease: {str(e)}"
        )

def periodic_check():
    """Background thread for periodic update checks"""
    while True:
        run_check_update(get_base_url())
        # time.sleep(10)  # ogni 10 secondi
        time.sleep(3600)  # <-- in produzione, ogni 1 ora

def is_internet_available(host="8.8.8.8", port=53, timeout=3):
    """
    Check internet connectivity by attempting to connect to a public DNS server.
    More reliable than ping.
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except OSError:
        return False

if __name__ == "__main__":
    import uvicorn
    
    print("Controllo disponibilità rete...")
    timeout_limit = 120  # secondi
    retry_interval = 5   # secondi
    # ripeti finché non c'è connessione
    while not is_internet_available():        
        if retry_interval > timeout_limit:
            retry_interval = timeout_limit
        else:
            retry_interval += 5
        print(f"Nessuna connessione. Riprovo tra {retry_interval} secondi...")
        time.sleep(retry_interval)

    print("Connessione rilevata! Procedo con l'avvio del Backend...")

    # ora puoi lanciare il resto del tuo codice
    print("Avvio controllo iniziale...")
    run_check_update(get_base_url())

    print("Avvio thread periodic_check...")
    threading.Thread(target=periodic_check, daemon=True).start()

    print("Avvio Backend API su http://0.0.0.0:8000")
    if os.name == "nt":
        uvicorn.run(app, host="127.0.0.1", port=8000, debug=True)
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)
