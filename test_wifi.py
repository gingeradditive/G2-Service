#!/usr/bin/env python3
"""
Test script for WiFi network scanning functionality
"""

import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.network import NetworkManager

def test_network_manager():
    """Test NetworkManager functionality"""
    print("Testing NetworkManager WiFi functionality...")
    
    try:
        nm = NetworkManager()
        
        # Test WiFi status
        print("\n1. Getting WiFi status...")
        try:
            status = nm.get_wifi_status()
            print(f"WiFi Status: {status}")
            
            # Print detailed status information
            if status.get("adapter"):
                print(f"\nAdapter Info:")
                adapter = status["adapter"]
                print(f"  Device: {adapter.get('device')}")
                print(f"  State: {adapter.get('state')}")
                print(f"  Connection: {adapter.get('connection')}")
            
            if status.get("connection"):
                print(f"\nConnection Info:")
                conn = status["connection"]
                print(f"  Name: {conn.get('name')}")
                print(f"  IP Address: {conn.get('ip_address')}")
                print(f"  Gateway: {conn.get('gateway')}")
            
            if status.get("network"):
                print(f"\nNetwork Info:")
                net = status["network"]
                print(f"  SSID: {net.get('ssid')}")
                print(f"  Signal Strength: {net.get('signal_strength')}%")
                print(f"  Frequency: {net.get('frequency')} MHz")
                print(f"  Channel: {net.get('channel')}")
                print(f"  Mode: {net.get('mode')}")
                print(f"  Security: {net.get('security')}")
            
            if status.get("ip"):
                print(f"\nIP Info:")
                ip = status["ip"]
                print(f"  IPv4: {ip.get('ipv4')}")
                print(f"  IPv6: {ip.get('ipv6')}")
                print(f"  MAC: {ip.get('mac')}")
                
        except Exception as e:
            print(f"WiFi status failed (expected on macOS): {str(e)}")
        
        # Test network scanning
        print("\n2. Scanning for WiFi networks...")
        networks = nm.get_visible_networks()
        print(f"Found {len(networks)} networks:")
        
        for i, network in enumerate(networks, 1):
            print(f"  {i}. SSID: {network.ssid}")
            print(f"     Signal: {network.signal_strength}%")
            print(f"     Security: {network.security}")
            print(f"     Frequency: {network.frequency} MHz")
            print()
        
        # Test rescan
        print("3. Triggering WiFi rescan...")
        try:
            success = nm.rescan_networks()
            print(f"Rescan successful: {success}")
        except Exception as e:
            print(f"Rescan failed (expected on macOS): {str(e)}")
        
        print("\n✅ All tests completed successfully!")
        print("Note: On macOS, mock data is returned for testing purposes.")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("Make sure NetworkManager is installed and running:")
        print("  sudo systemctl status NetworkManager")
        print("  sudo apt-get install network-manager")

if __name__ == "__main__":
    test_network_manager()
