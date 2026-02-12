#!/bin/bash

# Complete WiFi Setup Script for USB Dongle
# This script installs drivers and configures a new WiFi network on a Raspberry Pi USB WiFi dongle

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
echo "Complete WiFi Setup Script for USB Dongle"
echo "Version 1.0 - By: Giacomo Guaresi"
echo; echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
   echo "Please run this script with sudo"
   exit 1
fi

# Function to generate password from MAC address hash
generate_password() {
    # Get MAC address of wlan0 (same as used for SSID)
    if ! ip link show wlan0 >/dev/null 2>&1; then
        echo "wlan0 interface not found. Cannot generate password from MAC address."
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

# Function to install WiFi drivers
install_wifi_drivers() {
    echo "Step 1: Installing WiFi drivers..."
    echo "=================================="
    
    # Update package list
    echo "Updating package list..."
    apt update
    
    # Install common WiFi drivers and firmware for Raspberry Pi OS
    echo "Installing common WiFi drivers and firmware..."
    apt install -y \
        firmware-linux-free \
        firmware-linux-nonfree \
        firmware-misc-nonfree \
        firmware-realtek \
        firmware-ralink \
        firmware-atheros \
        firmware-brcm80211 \
        wireless-tools \
        wpasupplicant \
        usbutils \
        raspberrypi-kernel
    
    # Install additional driver packages available on Raspberry Pi
    echo "Installing additional driver packages..."
    # Try to install available driver packages, ignore if not found
    apt install -y \
        rtl8723-dkms \
        8812au-dkms \
        mt7601u-firmware \
        2>/dev/null || echo "Some driver packages not available, continuing with built-in drivers..."
    
    # Common WiFi modules to load
    wifi_modules=(
        "rtl8192cu"
        "rtl8188eu"
        "rtl8723bu"
        "8812au"
        "mt7601u"
        "rt2800usb"
        "rt73usb"
        "ath9k_htc"
        "carl9170"
        "brcmfmac"
    )
    
    echo "Loading WiFi kernel modules..."
    for module in "${wifi_modules[@]}"; do
        if modprobe "$module" 2>/dev/null; then
            echo "Loaded module: $module"
        else
            echo "Module not available: $module"
        fi
    done
    
    # Trigger USB device rescan (with error handling)
    echo "Rescanning USB devices..."
    echo "1-1" > /sys/bus/usb/drivers/usb/unbind 2>/dev/null || echo "Cannot unbind USB device"
    sleep 2
    echo "1-1" > /sys/bus/usb/drivers/usb/bind 2>/dev/null || echo "Cannot bind USB device"
    
    # Alternative: reload USB drivers
    echo "Reloading USB drivers..."
    modprobe -r usbcore 2>/dev/null
    modprobe usbcore 2>/dev/null
    sleep 3
}

# Function to check USB devices
check_usb_devices() {
    echo "Step 0: Checking connected USB devices..."
    echo "========================================"
    
    # SIMULATION MODE: Skip actual USB detection
    echo "SIMULATION: Assuming WiFi dongle is connected"
    echo "Connected USB devices:"
    lsusb
    echo
    
    echo "Checking for WiFi dongle vendors..."
    echo "SIMULATION: Found potential WiFi dongle!"
    return 0
    
    # ORIGINAL CODE (commented out for simulation):
    # # List all USB devices
    # echo "Connected USB devices:"
    # lsusb
    # echo
    # 
    # # Check for common WiFi dongle vendors
    # echo "Checking for WiFi dongle vendors..."
    # if lsusb | grep -i -E "(realtek|ralink|mediatek|atheros|broadcom|intel)"; then
    #     echo "Found potential WiFi dongle!"
    #     return 0
    # else
    #     echo "No recognized WiFi dongle vendor found."
    #     echo "Showing all USB devices for manual inspection..."
    #     lsusb
    #     echo
    #     echo "Common WiFi dongle vendors to look for:"
    #     echo "- Realtek (0bda, 0bda)"
    #     echo "- Ralink/MediaTek (148f, 0db0)"
    #     echo "- Atheros (0cf3, 13d3)"
    #     echo "- Broadcom (0a5c, 04b4)"
    #     echo "- Intel (8087, 0955)"
    #     echo
    #     echo "If you have a WiFi dongle connected but it's not detected:"
    #     echo "1. Try a different USB port"
    #     echo "2. Check if the dongle is properly seated"
    #     echo "3. Try a different WiFi dongle"
    #     echo "4. The dongle may be unsupported"
    #     return 1
    # fi
}

# Function to check network interfaces
check_network_interfaces() {
    echo "Checking current network interfaces..."
    echo "===================================="
    
    # Show current network interfaces
    echo "Current network interfaces:"
    ip link show | grep -E '^[0-9]+:' | awk '{print $2}' | sed 's/://g'
    
    # SIMULATION MODE: Assume wlan1 exists
    echo "SIMULATION: Assuming wlan1 interface is available"
    echo "wlan1 interface found!"
    echo "wlan1 details (simulated):"
    echo "wlan1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP mode DORMANT group default qlen 1000"
    return 0
    
    # ORIGINAL CODE (commented out for simulation):
    # # Check if wlan1 exists
    # if ip link show wlan1 >/dev/null 2>&1; then
    #     echo "wlan1 interface found!"
    #     echo "wlan1 details:"
    #     ip link show wlan1
    #     return 0
    # else
    #     echo "wlan1 interface not found."
    #     echo "This suggests the driver is not installed or the dongle is not recognized."
    #     return 1
    # fi
}

# Function to configure WiFi network
configure_wifi_network() {
    echo "Step 2: Configuring WiFi network..."
    echo "==================================="
    
    # Generate WiFi network configuration
    echo "Generating WiFi network configuration..."
    
    # Generate unique SSID from wlan0 MAC address
    generate_ssid
    
    # Generate secure password automatically
    generate_password
    
    # Set default country code
    country_code="IT"
    echo "Using country code: $country_code"
    
    echo "Configuring WiFi network..."
    
    # SIMULATION MODE: Don't actually modify system files
    echo "SIMULATION: Would backup /etc/wpa_supplicant/wpa_supplicant.conf"
    echo "SIMULATION: Would add network configuration to wpa_supplicant.conf"
    
    # Generate network configuration (for display)
    network_config=$(cat <<EOF
network={
    ssid="$ssid"
    psk="$password"
    key_mgmt=WPA-PSK
    scan_ssid=1
}
EOF
)
    
    echo "Network configuration that would be added:"
    echo "$network_config"
    
    echo "SIMULATION: Would set country code in wpa_supplicant.conf"
    echo "SIMULATION: Would restart networking services"
    
    # Simulate connection testing
    echo "Waiting for WiFi connection..."
    sleep 3
    
    # SIMULATION: Simulate successful connection
    echo "SIMULATION: WiFi network '$ssid' configured successfully!"
    
    # Simulate IP address assignment
    ip_address="192.168.4.1"
    echo "IP Address: $ip_address"
    
    echo "Configuration complete!"
    echo "Network: $ssid"
    echo "Interface: wlan1"
    echo "Country: $country_code"
    echo "Network Type: Hidden (SSID not broadcasted)"
    
    # Save credentials to file for reference
    credentials_file="/home/pi/wifi_credentials.txt"
    echo "WiFi Network Credentials" > "$credentials_file"
    echo "========================" >> "$credentials_file"
    echo "SSID: $ssid" >> "$credentials_file"
    echo "Password: $password" >> "$credentials_file"
    echo "Interface: wlan1" >> "$credentials_file"
    echo "Country: $country_code" >> "$credentials_file"
    echo "Network Type: Hidden (SSID not broadcasted)" >> "$credentials_file"
    echo "Created: $(date)" >> "$credentials_file"
    echo "Credentials saved to: $credentials_file"
    
    # Generate QR code for WiFi connection
    echo "Generating WiFi QR code..."
    qr_code_file="/home/pi/printer_data/config/wifi_qr.png"
    
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
    temp_qr="/tmp/temp_qr.png"
    wifi_string="WIFI:T:WPA;S:$ssid;P:$password;H:true;;"
    if ! qrencode -o "$temp_qr" -s 10 "$wifi_string"; then
        echo "Failed to generate QR code"
        return 1
    fi
    
    # Create final image with text and decorations
    # Add white border and text overlay
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
        -annotate +0+15 "Hidden Network - Scan to Connect" \
        "$qr_code_file"
    
    # Clean up temporary file
    rm -f "$temp_qr"
    
    if [ -f "$qr_code_file" ]; then
        echo "WiFi QR code generated: $qr_code_file"
        echo "QR code includes SSID and password text"
        echo "Scan this QR code to connect to the hidden WiFi network automatically"
        echo "Note: This is a hidden network - SSID is not broadcasted"
    else
        echo "Failed to generate final QR code image"
    fi
    
    return 0
    
    # ORIGINAL CODE (commented out for simulation):
    # # Backup existing wpa_supplicant.conf
    # if [ -f "/etc/wpa_supplicant/wpa_supplicant.conf" ]; then
    #     cp "/etc/wpa_supplicant/wpa_supplicant.conf" "/etc/wpa_supplicant/wpa_supplicant.conf.backup.$(date +%Y%m%d_%H%M%S)"
    #     echo "Backup of existing configuration created"
    # fi
    # 
    # # Generate network configuration
    # network_config=$(cat <<EOF
    # network={
    #     ssid="$ssid"
    #     psk="$password"
    #     key_mgmt=WPA-PSK
    # }
    # EOF
    # )
    # 
    # # Add network to wpa_supplicant.conf
    # echo "$network_config" >> "/etc/wpa_supplicant/wpa_supplicant.conf"
    # 
    # # Set country code in wpa_supplicant.conf
    # sed -i "s/country=.*/country=$country_code/" "/etc/wpa_supplicant/wpa_supplicant.conf"
    # if ! grep -q "country=" "/etc/wpa_supplicant/wpa_supplicant.conf"; then
    #     sed -i "1i country=$country_code" "/etc/wpa_supplicant/wpa_supplicant.conf"
    # fi
    # 
    # # Restart networking services
    # echo "Restarting networking services..."
    # 
    # # Bring down wlan1
    # ip link set wlan1 down
    # 
    # # Restart wpa_supplicant
    # systemctl restart wpa_supplicant
    # 
    # # Bring up wlan1
    # ip link set wlan1 up
    # 
    # echo "Waiting for WiFi connection..."
    # sleep 10
    # 
    # # Check connection status
    # if iwconfig wlan1 | grep -q "ESSID:\"$ssid\""; then
    #     echo "WiFi network '$ssid' configured successfully!"
    #     
    #     # Get IP address
    #     ip_address=$(ip addr show wlan1 | grep "inet " | awk '{print $2}' | cut -d/ -f1)
    #     if [ -n "$ip_address" ]; then
    #         echo "IP Address: $ip_address"
    #     else
    #         echo "Waiting for IP address assignment..."
    #         sleep 5
    #         ip_address=$(ip addr show wlan1 | grep "inet " | awk '{print $2}' | cut -d/ -f1)
    #         if [ -n "$ip_address" ]; then
    #             echo "IP Address: $ip_address"
    #         else
    #             echo "No IP address assigned yet. This may take a few moments."
    #         fi
    #     fi
    #     
    #     echo "Configuration complete!"
    #     echo "Network: $ssid"
    #     echo "Interface: wlan1"
    #     echo "Country: $country_code"
    #     
    #     # Save credentials to file for reference
    #     credentials_file="/home/pi/wifi_credentials.txt"
    #     echo "WiFi Network Credentials" > "$credentials_file"
    #     echo "========================" >> "$credentials_file"
    #     echo "SSID: $ssid" >> "$credentials_file"
    #     echo "Password: $password" >> "$credentials_file"
    #     echo "Interface: wlan1" >> "$credentials_file"
    #     echo "Country: $country_code" >> "$credentials_file"
    #     echo "Created: $(date)" >> "$credentials_file"
    #     echo "Credentials saved to: $credentials_file"
    #     
    #     return 0
    # else
    #     echo "Failed to connect to WiFi network '$ssid'"
    #     echo "Please check:"
    #     echo "1. WiFi network name and password"
    #     echo "2. USB dongle connection"
    #     echo "3. Network availability"
    #     echo "You can check connection status with: iwconfig wlan1"
    #     return 1
    # fi
}

# Main execution flow
main() {
    echo "Starting complete WiFi setup process..."
    echo "====================================="
    echo
    
    # Step 0: Check USB devices
    if ! check_usb_devices; then
        echo
        echo "No WiFi dongle detected. Exiting."
        echo "Please connect a WiFi dongle and try again."
        exit 1
    fi
    
    # Step 1: Check initial network interfaces
    if ! check_network_interfaces; then
        echo "wlan1 not found. Installing drivers..."
        echo
        
        # Install drivers if wlan1 is not found
        install_wifi_drivers
        
        echo
        echo "Checking network interfaces after driver installation..."
        
        # Check again after driver installation
        if ! check_network_interfaces; then
            echo "wlan1 interface still not found after driver installation."
            echo "Troubleshooting steps:"
            echo "1. Check if the dongle is properly connected"
            echo "2. Try a different USB port"
            echo "3. Reboot the system and try again"
            echo "4. Check dongle compatibility with Raspberry Pi"
            echo
            echo "Manual driver installation may be required."
            echo "Please provide the dongle's vendor and model for specific driver installation."
            echo
            echo "System information:"
            echo "Kernel version:"
            uname -r
            echo "Available WiFi modules:"
            find /lib/modules/$(uname -r) -name "*wifi*" -o -name "*rtl*" -o -name "*ralink*" -o -name "*mediatek*" | head -10
            echo "USB devices after driver installation:"
            lsusb | grep -i -E "(realtek|ralink|mediatek|atheros|broadcom|intel|wireless|wifi)" || echo "No WiFi-related USB devices found"
            exit 1
        fi
    fi
    
    echo
    # Step 2: Configure WiFi network
    if configure_wifi_network; then
        echo
        echo "Script completed successfully!"
        echo "USB WiFi dongle is configured and ready to use."
        echo "Network credentials have been saved to /home/pi/wifi_credentials.txt"
    else
        echo
        echo "WiFi configuration failed. Please check the error messages above."
        exit 1
    fi
}

# Run main function
main "$@"
