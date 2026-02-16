#!/bin/bash

# Complete WiFi Setup Script for Access Point Mode
# This script configures wlan0 as a WiFi Access Point (hotspot)

# Banner
echo "                                                        
                 5@?                                                            
    :~!7!~:  :^. ~!^ .^^  ^!77!:        .^!77!^  :^:     :~!77!^.    ^^..!7~.   
 .?B&#GPPG#BJB@7 P@J 7@#JBBPPPB&G!    !G&#GPPGB#YP@5   7B&BGPPB##5^  #@B#BGY    
~#@5^     .!B@@7 P@J 7@@#!.    !@@~ :G@G~.    .~P@@5 :B@5:     .!#@? #@@!       
&@J         .#@7 P@J 7@&:       P@Y 5@P          P@5 G@&YJYYYYYJJP@@~B@Y        
@@!          B@7 P@J 7@#        5@5 P@Y          5@5 #@P7????????777^B@7        
7@&7       :P@@7 P@J 7@#        5@5 ^&@J.      .J@@5 ?@#:        !5~ #@7     :: 
 ^5&#PYJY5G#P#@7 G@J ?@#.       5@5  .J##G5JJ5G#GB@5  7#@P7~^^!JB@P^ #@?    G@@G
^~:.~7JJJ?~.:&@^ ?P! ~PY        7P7 :~^.^7JJJ?!. B@7    !YGGBBGP?^   YP~    ?GG?
~B@P!:. ..^J&&7                     :P@G7:.  .^7B@Y                             
  !P#######GJ:                        ~5B######BY^                              "
echo
echo "Complete WiFi Setup Script for Access Point Mode"
echo "Version 1.0 - By: Giacomo Guaresi"
echo; echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
   echo "Please run this script with sudo"
   exit 1
fi

# Function to generate password from MAC address hash
generate_password() {
    # Get MAC address of wlan0
    if ! ip link show wlan0 >/dev/null 2>&1; then
        echo "wlan0 interface not found. Cannot generate password from MAC address."
        echo "Please ensure wlan0 is available before running this script."
        exit 1
    fi
    
    mac_address=$(ip link show wlan0 | grep -o -E '([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}' | head -1)
    if [ -z "$mac_address" ]; then
        echo "Could not retrieve MAC address from wlan0"
        exit 1
    fi
    
    # Remove colons and convert to lowercase
    mac_clean=$(echo "$mac_address" | tr -d ':' | tr '[:upper:]' '[:lower:]')
    
    # Generate SHA256 hash of MAC address
    mac_hash=$(echo -n "$mac_clean" | sha256sum | cut -d' ' -f1)
    
    # Take first 16 characters of hash and add G2 prefix
    password="G2${mac_hash:0:16}"
    
    echo "Generated password from MAC hash: $password"
    echo "Based on wlan0 MAC: $mac_address"
}

# Function to generate unique SSID from wlan0 MAC address
generate_ssid() {
    # Check if wlan0 exists
    if ! ip link show wlan0 >/dev/null 2>&1; then
        echo "wlan0 interface not found. Cannot generate unique SSID."
        echo "Available interfaces:"
        ip link show | grep -E '^[0-9]+:' | awk '{print $2}' | sed 's/://g'
        exit 1
    fi
    
    # Get MAC address of wlan0 and extract last 6 characters
    mac_address=$(ip link show wlan0 | grep -o -E '([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}' | head -1)
    if [ -z "$mac_address" ]; then
        echo "Could not retrieve MAC address from wlan0"
        exit 1
    fi
    
    # Remove colons and get last 6 characters
    mac_clean=$(echo "$mac_address" | tr -d ':')
    last_six=${mac_clean: -6}
    
    # Generate SSID
    ssid="G2TabletNetwork-$last_six"
    echo "Generated unique SSID: $ssid"
    echo "Based on wlan0 MAC: $mac_address"
}

# Function to install AP requirements
install_ap_requirements() {
    echo "Step 1: Installing Access Point requirements..."
    echo "==========================================="
    
    # Update package list
    echo "Updating package list..."
    apt update
    
    # Install AP software
    echo "Installing hostapd, dnsmasq, and net-tools..."
    apt install -y \
        hostapd \
        dnsmasq \
        net-tools \
        iptables \
        wireless-tools \
        wpasupplicant \
        raspberrypi-kernel
    
    # Enable IP forwarding
    echo "Enabling IP forwarding..."
    sed -i 's/#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/' /etc/sysctl.conf
    sysctl -p
    
    echo "AP requirements installed successfully!"
}

# Function to check wlan0 interface
check_wlan0_interface() {
    echo "Step 0: Checking wlan0 interface..."
    echo "==================================="
    
    # Show current network interfaces
    echo "Current network interfaces:"
    ip link show | grep -E '^[0-9]+:' | awk '{print $2}' | sed 's/://g'
    
    # Check if wlan0 exists
    if ip link show wlan0 >/dev/null 2>&1; then
        echo "wlan0 interface found!"
        echo "wlan0 details:"
        ip link show wlan0
        return 0
    else
        echo "wlan0 interface not found."
        echo "This suggests the WiFi adapter is not available."
        echo "Please check:"
        echo "1. WiFi adapter is properly connected"
        echo "2. WiFi drivers are installed"
        echo "3. The adapter is not disabled"
        return 1
    fi
}

# Function to configure Access Point
configure_access_point() {
    echo "Step 2: Configuring Access Point on wlan0..."
    echo "============================================"
    
    # Generate WiFi network configuration
    echo "Generating Access Point configuration..."
    
    # Generate unique SSID from wlan0 MAC address
    generate_ssid
    
    # Generate secure password automatically
    generate_password
    
    # Set default country code
    country_code="IT"
    echo "Using country code: $country_code"
    
    # Configure static IP for wlan0 using NetworkManager
    echo "Configuring static IP for wlan0..."
    
    # Stop NetworkManager management of wlan0 temporarily
    nmcli device set wlan0 managed no
    
    # Configure static IP using ip command
    ip addr add 192.168.4.1/24 dev wlan0 2>/dev/null || echo "IP already configured or interface not ready"
    
    # Bring up wlan0 interface
    ip link set wlan0 up
    
    echo "Static IP configured: 192.168.4.1/24"
    
    # Configure dnsmasq for DHCP
    echo "Configuring dnsmasq for DHCP..."
    
    # Backup original dnsmasq.conf
    if [ -f "/etc/dnsmasq.conf" ]; then
        cp "/etc/dnsmasq.conf" "/etc/dnsmasq.conf.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Create dnsmasq configuration
    cat > /etc/dnsmasq.conf <<EOF
# DHCP configuration for wlan0 Access Point
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
domain=local
dhcp-option=option:dns-server,192.168.4.1
EOF
    
    echo "DHCP server configured for range 192.168.4.2-192.168.4.20"
    
    # Configure hostapd for Access Point
    echo "Configuring hostapd for Access Point..."
    
    # Create hostapd configuration
    cat > /etc/hostapd/hostapd.conf <<EOF
# Access Point configuration
interface=wlan0
driver=nl80211
ssid=$ssid
hw_mode=g
channel=6
ieee80211n=1
wmm_enabled=1
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=$password
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
country_code=$country_code
EOF
    
    echo "Access Point configuration created"
    echo "SSID: $ssid"
    echo "Password: $password"
    echo "Channel: 6 (2.4GHz)"
    
    # Update hostapd default configuration
    sed -i 's/#DAEMON_CONF=""/DAEMON_CONF="\/etc\/hostapd\/hostapd.conf"/' /etc/default/hostapd
    
    # Enable services
    echo "Enabling and starting services..."
    systemctl unmask hostapd
    systemctl enable hostapd
    systemctl enable dnsmasq
    
    # Restart networking services
    echo "Restarting networking services..."
    # Don't restart dhcpcd as it's not available, just ensure interface is up
    systemctl restart NetworkManager 2>/dev/null || echo "NetworkManager restart not needed"
    sleep 3
    
    # Start AP services
    echo "Starting Access Point services..."
    
    # Kill any existing hostapd processes
    pkill -f hostapd 2>/dev/null || true
    sleep 2
    
    # Start hostapd manually first to test
    echo "Testing hostapd configuration..."
    if hostapd -dd /etc/hostapd/hostapd.conf > /tmp/hostapd_debug.log 2>&1 & then
        sleep 5
        if pgrep -f hostapd > /dev/null; then
            echo "Hostapd started successfully in debug mode"
            kill $(pgrep -f hostapd) 2>/dev/null || true
            sleep 2
        else
            echo "Hostapd failed to start, checking debug log..."
            tail -20 /tmp/hostapd_debug.log
            echo "Continuing with systemd service..."
        fi
    fi
    
    # Start services via systemd
    systemctl start hostapd
    systemctl start dnsmasq
    
    echo "Waiting for Access Point to start..."
    sleep 15
    
    # Check if AP is running
    if systemctl is-active --quiet hostapd && pgrep -f hostapd > /dev/null; then
        echo "Access Point started successfully!"
        echo "Network: $ssid"
        echo "Password: $password"
        echo "IP Address: 192.168.4.1"
        echo "Interface: wlan0"
        echo "Country: $country_code"
        echo "Network Type: Hidden (SSID not broadcasted)"
        
        # Save credentials to file for reference
        credentials_file="/home/pi/ap_credentials.txt"
        echo "Access Point Credentials" > "$credentials_file"
        echo "======================" >> "$credentials_file"
        echo "SSID: $ssid" >> "$credentials_file"
        echo "Password: $password" >> "$credentials_file"
        echo "IP Address: 192.168.4.1" >> "$credentials_file"
        echo "Interface: wlan0" >> "$credentials_file"
        echo "Country: $country_code" >> "$credentials_file"
        echo "Network Type: Hidden (SSID not broadcasted)" >> "$credentials_file"
        echo "Created: $(date)" >> "$credentials_file"
        echo "Credentials saved to: $credentials_file"
        
        # Generate QR code for WiFi connection
        echo "Generating WiFi QR code..."
        qr_code_file="/home/pi/printer_data/config/ap_qr.png"
        
        # Create directory if it doesn't exist
        mkdir -p "$(dirname "$qr_code_file")"
        
        # Install required packages if not available
        if ! command -v qrencode >/dev/null 2>&1; then
            echo "Installing qrencode for QR code generation..."
            apt update && apt install -y qrencode
        fi
        
        if ! command -v convert >/dev/null 2>&1; then
            echo "Installing ImageMagick for image processing..."
            apt update && apt install -y imagemagick
        fi
        
        # Generate initial QR code (larger size for better quality)
        temp_qr="/tmp/temp_ap_qr.png"
        wifi_string="WIFI:T:WPA;S:$ssid;P:$password;H:true;;"
        if ! qrencode -o "$temp_qr" -s 10 "$wifi_string"; then
            echo "Failed to generate QR code"
            return 1
        fi
        
        # Create final image with text and decorations
        convert "$temp_qr" \
            -bordercolor white -border 50 \
            -gravity north \
            -background white \
            -splice 0x80 \
            -font DejaVu-Sans-Bold \
            -pointsize 24 \
            -fill black \
            -annotate +0+20 "SSID: $ssid" \
            -font DejaVu-Sans \
            -pointsize 18 \
            -fill "#333333" \
            -annotate +0+50 "Password: $password" \
            -gravity south \
            -background white \
            -splice 0x40 \
            -font DejaVu-Sans \
            -pointsize 14 \
            -fill "#666666" \
            -annotate +0+15 "Access Point - Scan to Connect" \
            "$qr_code_file"
        
        # Clean up temporary file
        rm -f "$temp_qr"
        
        if [ -f "$qr_code_file" ]; then
            echo "Access Point QR code generated: $qr_code_file"
            echo "QR code includes SSID and password text"
            echo "Scan this QR code to connect to the Access Point automatically"
            echo "Note: This is a hidden network - SSID is not broadcasted"
        else
            echo "Failed to generate final QR code image"
        fi
        
        return 0
    else
        echo "Failed to start Access Point"
        echo "Please check the hostapd service status:"
        systemctl status hostapd
        echo ""
        echo "Checking hostapd configuration:"
        echo "Interface: $(grep '^interface=' /etc/hostapd/hostapd.conf)"
        echo "Driver: $(grep '^driver=' /etc/hostapd/hostapd.conf)"
        echo "SSID: $(grep '^ssid=' /etc/hostapd/hostapd.conf)"
        echo "Channel: $(grep '^channel=' /etc/hostapd/hostapd.conf)"
        echo "HW Mode: $(grep '^hw_mode=' /etc/hostapd/hostapd.conf)"
        echo ""
        echo "Checking wlan0 interface status:"
        ip link show wlan0
        echo ""
        echo "Checking if wlan0 is up:"
        ip addr show wlan0
        echo ""
        echo "Debug log (last 20 lines):"
        tail -20 /tmp/hostapd_debug.log 2>/dev/null || echo "No debug log found"
        return 1
    fi
}

# Function to configure WiFi network (legacy - not used in AP mode)
configure_wifi_network() {
    echo "This function is deprecated in AP mode. Use configure_access_point() instead."
    return 0
}

# Main execution flow
main() {
    echo "Starting Access Point setup process..."
    echo "======================================"
    echo
    
    # Step 0: Check wlan0 interface
    if ! check_wlan0_interface; then
        echo
        echo "wlan0 interface not available. Exiting."
        echo "Please ensure wlan0 is available before running this script."
        exit 1
    fi
    
    # Step 1: Install AP requirements
    install_ap_requirements
    
    echo
    # Step 2: Configure Access Point
    if configure_access_point; then
        echo
        echo "Access Point setup completed successfully!"
        echo "wlan0 is now configured as an Access Point (hotspot)."
        echo "Network credentials have been saved to /home/pi/ap_credentials.txt"
        echo
        echo "To test the Access Point:"
        echo "1. Connect a device to the network '$ssid'"
        echo "2. Use the password: $password"
        echo "3. You should get an IP address in the range 192.168.4.2-192.168.4.20"
        echo "4. Test connectivity by pinging 192.168.4.1"
    else
        echo
        echo "Access Point configuration failed. Please check the error messages above."
        exit 1
    fi
}

# Run main function
main "$@"
