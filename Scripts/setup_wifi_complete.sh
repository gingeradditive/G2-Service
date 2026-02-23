#!/bin/bash

# Complete WiFi Setup Script for Access Point Mode - Refactored Version
# This script configures wlan0 as a WiFi Access Point (hotspot) with proper local services access

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
echo "Complete WiFi Setup Script for Access Point Mode - REFACTORED"
echo "Version 2.0 - By: Giacomo Guaresi"
echo "Fixed: Local services access, proper routing, DNS resolution"
echo; echo

# Global variables
LOG_FILE="/var/log/wifi_setup.log"
CREDENTIALS_FILE="/home/pi/ap_credentials.txt"
AP_INTERFACE="wlan0"
AP_IP="192.168.4.1"
AP_NETMASK="255.255.255.0"
AP_NETWORK="192.168.4.0/24"

# Set to "true" to hide the SSID (not broadcasted), "false" to make it visible
AP_HIDDEN="false"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Error handling function
error_exit() {
    log "ERROR: $1"
    exit 1
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
   echo "Please run this script with sudo"
   exit 1
fi

# Function to generate password from MAC address hash
generate_password() {
    log "Generating password from MAC address..."
    
    if ! ip link show "$AP_INTERFACE" >/dev/null 2>&1; then
        error_exit "$AP_INTERFACE interface not found. Cannot generate password from MAC address."
    fi
    
    mac_address=$(ip link show "$AP_INTERFACE" | grep -o -E '([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}' | head -1)
    if [ -z "$mac_address" ]; then
        error_exit "Could not retrieve MAC address from $AP_INTERFACE"
    fi
    
    mac_clean=$(echo "$mac_address" | tr -d ':' | tr '[:upper:]' '[:lower:]')
    mac_hash=$(echo -n "$mac_clean" | sha256sum | cut -d' ' -f1)
    password="G2${mac_hash:0:16}"
    
    log "Generated password: $password"
    log "Based on $AP_INTERFACE MAC: $mac_address"
    # Return password without echoing it
    echo "$password"
}

# Function to generate unique SSID from wlan0 MAC address
generate_ssid() {
    log "Generating unique SSID from MAC address..."
    
    if ! ip link show "$AP_INTERFACE" >/dev/null 2>&1; then
        error_exit "$AP_INTERFACE interface not found. Cannot generate unique SSID."
    fi
    
    mac_address=$(ip link show "$AP_INTERFACE" | grep -o -E '([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}' | head -1)
    if [ -z "$mac_address" ]; then
        error_exit "Could not retrieve MAC address from $AP_INTERFACE"
    fi
    
    mac_clean=$(echo "$mac_address" | tr -d ':')
    last_six=${mac_clean: -6}
    ssid="G2TabletNetwork-$last_six"
    
    log "Generated SSID: $ssid"
    log "Based on $AP_INTERFACE MAC: $mac_address"
    # Return SSID without echoing it
    echo "$ssid"
}

# Function to install AP requirements
install_ap_requirements() {
    log "Step 1: Installing Access Point requirements..."
    
    # Update package list
    log "Updating package list..."
    apt update || error_exit "Failed to update package list"
    
    # Install AP software
    log "Installing required packages..."
    
    # Install core packages first
    DEBIAN_FRONTEND=noninteractive apt install -y \
        hostapd \
        dnsmasq \
        net-tools \
        iptables \
        iptables-persistent \
        netfilter-persistent \
        wireless-tools \
        wpasupplicant || error_exit "Failed to install core packages"
    
    # Install optional packages that might not be available
    log "Installing optional packages..."
    apt install -y haveged 2>/dev/null || log "haveged not available, skipping"
    
    # Verify core packages are installed
    for package in hostapd dnsmasq net-tools iptables iptables-persistent; do
        if ! dpkg -l | grep -q "^ii.*$package "; then
            error_exit "Required package $package not installed"
        fi
    done
    
    log "✓ All required packages installed successfully"
    
    # Enable IP forwarding
    log "Enabling IP forwarding..."
    sed -i 's/#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/' /etc/sysctl.conf
    sysctl -p || error_exit "Failed to enable IP forwarding"
    
    # Configure nginx for gzip compression (if available)
    if command -v nginx >/dev/null 2>&1; then
        log "Configuring nginx for gzip compression..."
        cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup
        
        # Enable gzip compression
        sed -i 's/# gzip_vary on;/gzip_vary on;/' /etc/nginx/nginx.conf
        sed -i 's/# gzip_proxied any;/gzip_proxied any;/' /etc/nginx/nginx.conf
        sed -i 's/# gzip_comp_level 6;/gzip_comp_level 9;/' /etc/nginx/nginx.conf
        sed -i 's/# gzip_buffers 16 8k;/gzip_buffers 16 8k;/' /etc/nginx/nginx.conf
        sed -i 's/# gzip_http_version 1.1;/gzip_http_version 1.1;/' /etc/nginx/nginx.conf
        sed -i 's/# gzip_types text\/plain text\/css application\/json application\/javascript text\/xml application\/xml application\/xml\+rss text\/javascript;/gzip_types text\/plain text\/css application\/json application\/javascript text\/xml application\/xml application\/xml\+rss text\/javascript;/' /etc/nginx/nginx.conf
        
        if nginx -t; then
            systemctl reload nginx
            log "✓ nginx gzip compression enabled"
        else
            log "❌ nginx configuration error, restoring backup"
            cp /etc/nginx/nginx.conf.backup /etc/nginx/nginx.conf
        fi
    else
        log "nginx not found, skipping gzip configuration"
    fi
    
    log "✓ AP requirements installed successfully!"
}

# Function to check and prepare wlan0 interface
prepare_wlan0_interface() {
    log "Step 0: Preparing $AP_INTERFACE interface..."
    
    # Show current network interfaces
    log "Current network interfaces:"
    ip link show | grep -E '^[0-9]+:' | awk '{print $2}' | sed 's/://g' | tee -a "$LOG_FILE"
    
    if ! ip link show "$AP_INTERFACE" >/dev/null 2>&1; then
        error_exit "$AP_INTERFACE interface not found. Please check WiFi adapter connection and drivers."
    fi
    
    log "$AP_INTERFACE interface found!"
    log "$AP_INTERFACE details:"
    ip link show "$AP_INTERFACE" | tee -a "$LOG_FILE"
    
    # Stop and disable conflicting services
    log "Stopping conflicting services..."
    systemctl stop wpa_supplicant 2>/dev/null || true
    systemctl stop hostapd 2>/dev/null || true
    systemctl stop dnsmasq 2>/dev/null || true
    
    # Kill any remaining processes
    pkill -f wpa_supplicant 2>/dev/null || true
    pkill -f hostapd 2>/dev/null || true
    pkill -f dnsmasq 2>/dev/null || true
    
    # Remove NetworkManager management of wlan0 permanently
    if command -v nmcli >/dev/null 2>&1; then
        log "Removing NetworkManager management of $AP_INTERFACE..."
        nmcli device set "$AP_INTERFACE" managed no 2>/dev/null || true
    fi
    
    # Write persistent NM unmanaged config so wlan0 is never re-claimed after reboot
    mkdir -p /etc/NetworkManager/conf.d
    cat > /etc/NetworkManager/conf.d/unmanaged-wlan0.conf <<EOF
[keyfile]
unmanaged-devices=interface-name:$AP_INTERFACE
EOF
    log "✓ NetworkManager will not manage $AP_INTERFACE (persistent)"
    
    # Wait for processes to stop
    sleep 3
    
    log "✓ $AP_INTERFACE interface prepared"
}

# Function to configure network interface
configure_network_interface() {
    log "Step 2: Configuring network interface..."
    
    # Flush existing IP addresses
    log "Flushing existing IP addresses from $AP_INTERFACE..."
    ip addr flush dev "$AP_INTERFACE" 2>/dev/null || true
    
    # Set interface up
    log "Bringing $AP_INTERFACE up..."
    ip link set "$AP_INTERFACE" up || error_exit "Failed to bring $AP_INTERFACE up"
    
    # Configure static IP persistently via dhcpcd.conf (survives reboots)
    log "Writing persistent static IP config to /etc/dhcpcd.conf..."
    # Remove any existing wlan0 static block first
    sed -i '/^# G2-AP static/,/^$/d' /etc/dhcpcd.conf 2>/dev/null || true
    cat >> /etc/dhcpcd.conf <<EOF

# G2-AP static
interface $AP_INTERFACE
static ip_address=$AP_IP/24
nohook wpa_supplicant
EOF
    log "✓ dhcpcd static IP written"
    
    # Also write a systemd-networkd config as fallback (if networkd is active)
    mkdir -p /etc/systemd/network
    cat > /etc/systemd/network/10-${AP_INTERFACE}-ap.network <<EOF
[Match]
Name=$AP_INTERFACE

[Network]
Address=$AP_IP/24
ConfigureWithoutCarrier=yes
EOF
    
    # Apply IP now (runtime)
    log "Configuring static IP: $AP_IP/$AP_NETMASK"
    ip addr add "$AP_IP/$AP_NETMASK" dev "$AP_INTERFACE" 2>/dev/null || true
    
    # Optimize network interface for performance
    log "Optimizing network interface performance..."
    
    # Disable IPv6 on AP interface to reduce overhead
    sysctl -w net.ipv6.conf."$AP_INTERFACE".disable_ipv6=1 2>/dev/null || true
    
    # Optimize TCP settings for local network
    sysctl -w net.core.rmem_max=16777216 2>/dev/null || true
    sysctl -w net.core.wmem_max=16777216 2>/dev/null || true
    sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216" 2>/dev/null || true
    sysctl -w net.ipv4.tcp_wmem="4096 65536 16777216" 2>/dev/null || true
    
    # Verify IP configuration
    if ip addr show "$AP_INTERFACE" | grep -q "$AP_IP"; then
        log "✓ Static IP configured successfully: $AP_IP"
    else
        error_exit "Failed to verify static IP configuration"
    fi
    
    # Wait for interface to stabilize
    sleep 2
}

# Function to configure dnsmasq
configure_dnsmasq() {
    log "Step 3: Configuring dnsmasq for DHCP and DNS..."
    
    # Backup original configuration
    if [ -f "/etc/dnsmasq.conf" ]; then
        cp "/etc/dnsmasq.conf" "/etc/dnsmasq.conf.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Create optimized dnsmasq configuration
    cat > /etc/dnsmasq.conf <<EOF
# DHCP and DNS configuration for $AP_INTERFACE Access Point
interface=$AP_INTERFACE
domain=local
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,12h
dhcp-option=6,$AP_IP
dhcp-option=3,$AP_IP
dhcp-option=1,$AP_NETMASK
dhcp-option=28,192.168.4.255
dhcp-leasefile=/var/lib/misc/dnsmasq.leases
dhcp-authoritative
listen-address=$AP_IP
bind-interfaces
no-resolv
cache-size=1000
log-queries
log-dhcp

# Local DNS entries for services (priority resolution)
address=/mainsail.local/$AP_IP
address=/api.local/$AP_IP
address=/klipper.local/$AP_IP
address=/printer.local/$AP_IP
address=/g2.local/$AP_IP
EOF
    
    # Create leases directory
    mkdir -p /var/lib/misc
    touch /var/lib/misc/dnsmasq.leases
    chmod 644 /var/lib/misc/dnsmasq.leases
    
    log "✓ dnsmasq configuration created"
    log "DHCP range: 192.168.4.2-192.168.4.20"
    log "DNS server: $AP_IP"
}

# Function to configure hostapd
configure_hostapd() {
    log "Step 4: Configuring hostapd for Access Point..."
    
    # Generate SSID and password (capture output without logs)
    log "Generating network credentials..."
    ssid=$(generate_ssid | tail -1)
    password=$(generate_password | tail -1)
    country_code="IT"
    
    log "Generated credentials - SSID: $ssid, Password: [HIDDEN]"
    
    # Create hostapd configuration
    cat > /etc/hostapd/hostapd.conf <<EOF
# Access Point configuration for $AP_INTERFACE
interface=$AP_INTERFACE
driver=nl80211
ssid=$ssid
hw_mode=g
channel=6
ieee80211n=1
ieee80211ax=0
wmm_enabled=1
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=$([ "$AP_HIDDEN" = "true" ] && echo 1 || echo 0)
wpa=2
wpa_passphrase=$password
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
country_code=$country_code
ieee80211h=0
ieee80211d=1

# Performance optimizations
beacon_int=100
dtim_period=1
max_num_sta=8
rts_threshold=2347
fragm_threshold=2346

# Logging
logger_syslog=-1
logger_syslog_level=2
EOF
    
    # Update hostapd default configuration
    sed -i 's/#DAEMON_CONF=""/DAEMON_CONF="\/etc\/hostapd\/hostapd.conf"/' /etc/default/hostapd
    
    log "✓ hostapd configuration created"
    log "SSID: $ssid"
    log "Password: $password"
    log "Channel: 6 (2.4GHz)"
    log "Country: $country_code"
    
    # Save credentials
    save_credentials "$ssid" "$password"
}

# Function to save credentials
save_credentials() {
    local ssid="$1"
    local password="$2"
    
    log "Saving credentials to $CREDENTIALS_FILE..."
    mkdir -p "$(dirname "$CREDENTIALS_FILE")"
    
    cat > "$CREDENTIALS_FILE" <<EOF
Access Point Credentials
======================
SSID: $ssid
Password: $password
IP Address: $AP_IP
Interface: $AP_INTERFACE
Country: IT
Network Type: $([ "$AP_HIDDEN" = "true" ] && echo "Hidden (SSID not broadcasted)" || echo "Visible (SSID broadcasted)")
Created: $(date)

Local Services (via nginx on port 80):
- Mainsail:            http://$AP_IP/
- Swagger UI:          http://$AP_IP/docs
- G2-Service API:      http://$AP_IP/g2/
- Moonraker API:       http://$AP_IP/api
- Moonraker WebSocket: ws://$AP_IP/websocket

Direct ports (also accessible):
- G2-Service FastAPI:  http://$AP_IP:8080
- Moonraker:           http://$AP_IP:7125

DNS Names: mainsail.local, api.local, g2.local
EOF
    
    log "✓ Credentials saved to: $CREDENTIALS_FILE"
}

# Function to configure nginx as reverse proxy on the AP interface
configure_nginx_ap() {
    log "Configuring nginx reverse proxy on $AP_IP..."
    
    if ! command -v nginx >/dev/null 2>&1; then
        log "nginx not installed, installing..."
        apt install -y nginx || error_exit "Failed to install nginx"
    fi
    
    # Write dedicated AP virtual host
    cat > /etc/nginx/sites-available/g2-ap <<EOF
# G2-Service AP reverse proxy - serves all local services on 192.168.4.1
server {
    listen $AP_IP:80;
    server_name $AP_IP mainsail.local api.local g2.local klipper.local printer.local;

    # Mainsail static files
    location / {
        root /var/www/mainsail;
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }

    # G2-Service FastAPI - /g2/ prefix
    location /g2/ {
        proxy_pass http://127.0.0.1:8080/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_connect_timeout 5;
        proxy_read_timeout 30;
        proxy_buffering off;
    }

    # G2-Service FastAPI docs shortcut
    location /docs {
        proxy_pass http://127.0.0.1:8080/docs;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_buffering off;
    }

    # Moonraker API
    location /printer {
        proxy_pass http://127.0.0.1:7125;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_connect_timeout 5;
        proxy_read_timeout 30;
        proxy_buffering off;
    }

    location /api {
        proxy_pass http://127.0.0.1:7125;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_connect_timeout 5;
        proxy_read_timeout 30;
        proxy_buffering off;
    }

    # Moonraker WebSocket
    location /websocket {
        proxy_pass http://127.0.0.1:7125/websocket;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 86400;
        proxy_buffering off;
    }

    access_log /var/log/nginx/g2-ap_access.log;
    error_log  /var/log/nginx/g2-ap_error.log;
}
EOF
    
    # Enable the site
    ln -sf /etc/nginx/sites-available/g2-ap /etc/nginx/sites-enabled/g2-ap
    
    # Test and reload nginx
    if nginx -t; then
        systemctl enable nginx
        systemctl reload nginx 2>/dev/null || systemctl start nginx
        log "✓ nginx AP reverse proxy configured on http://$AP_IP"
        log "  http://$AP_IP        → Mainsail"
        log "  http://$AP_IP/g2/   → G2-Service FastAPI"
        log "  http://$AP_IP/docs  → Swagger UI"
        log "  http://$AP_IP/api   → Moonraker API"
    else
        log "❌ nginx configuration error - check /etc/nginx/sites-available/g2-ap"
    fi
}

# Function to optimize DNS configuration
optimize_dns_resolution() {
    log "Optimizing DNS resolution for local services..."
    
    # Configure system to use local DNS first
    log "Configuring system DNS to use local server..."
    
    # Backup original resolv.conf
    cp /etc/resolv.conf /etc/resolv.conf.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
    
    # Create optimized resolv.conf for local services
    cat > /etc/resolv.conf <<EOF
# Local DNS configuration for Access Point
nameserver $AP_IP
nameserver 127.0.0.1
# Fallback DNS (only if local fails)
nameserver 8.8.8.8
nameserver 8.8.4.4
options timeout:2 attempts:2 rotate
EOF
    
    # Prevent NetworkManager from overwriting resolv.conf
    log "Protecting DNS configuration from NetworkManager..."
    
    # Create NetworkManager configuration to preserve our DNS
    mkdir -p /etc/NetworkManager/conf.d
    cat > /etc/NetworkManager/conf.d/dns.conf <<EOF
[main]
dns=none
EOF
    
    # Restart NetworkManager to apply DNS settings
    systemctl restart NetworkManager 2>/dev/null || true
    
    # Add local entries to /etc/hosts for instant resolution
    log "Adding local service entries to hosts file..."
    cp /etc/hosts /etc/hosts.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
    
    # Add local entries to hosts file (bypass DNS completely)
    cat >> /etc/hosts <<EOF

# Local Access Point services - instant resolution
$AP_IP mainsail.local api.local g2.local klipper.local printer.local
$AP_IP mainsail api g2 klipper printer
127.0.0.1 localhost
EOF
    
    log "✓ DNS optimization completed"
    log "Local services will now resolve instantly"
}

# Function to configure firewall for local services
configure_firewall() {
    log "Step 5: Configuring firewall for local services access..."
    
    # Get the main network interface (if exists)
    MAIN_INTERFACE=$(ip route | grep default | awk '{print $5}' | head -1)
    log "Main network interface: ${MAIN_INTERFACE:-'None'}"
    
    # Clear existing rules
    log "Clearing existing firewall rules..."
    iptables -t nat -F 2>/dev/null || true
    iptables -t nat -X 2>/dev/null || true
    iptables -F 2>/dev/null || true
    iptables -X 2>/dev/null || true
    
    # Set default policies
    iptables -P INPUT ACCEPT
    iptables -P FORWARD ACCEPT
    iptables -P OUTPUT ACCEPT
    
    # Allow loopback traffic
    iptables -A INPUT -i lo -j ACCEPT
    iptables -A OUTPUT -o lo -j ACCEPT
    
    # Allow established and related connections
    iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
    iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT
    
    # Allow ALL traffic from/to AP interface (critical for local services)
    iptables -A INPUT -i "$AP_INTERFACE" -j ACCEPT
    iptables -A OUTPUT -o "$AP_INTERFACE" -j ACCEPT
    iptables -A FORWARD -i "$AP_INTERFACE" -j ACCEPT
    iptables -A FORWARD -o "$AP_INTERFACE" -j ACCEPT
    
    # Allow specific local services (redundant but explicit)
    iptables -A INPUT -i "$AP_INTERFACE" -p tcp --dport 22 -j ACCEPT   # SSH
    iptables -A INPUT -i "$AP_INTERFACE" -p tcp --dport 53 -j ACCEPT   # DNS
    iptables -A INPUT -i "$AP_INTERFACE" -p udp --dport 53 -j ACCEPT   # DNS
    iptables -A INPUT -i "$AP_INTERFACE" -p tcp --dport 67 -j ACCEPT   # DHCP
    iptables -A INPUT -i "$AP_INTERFACE" -p udp --dport 67 -j ACCEPT   # DHCP
    iptables -A INPUT -i "$AP_INTERFACE" -p tcp --dport 80 -j ACCEPT   # HTTP / nginx (Mainsail)
    iptables -A INPUT -i "$AP_INTERFACE" -p tcp --dport 443 -j ACCEPT  # HTTPS
    iptables -A INPUT -i "$AP_INTERFACE" -p tcp --dport 8080 -j ACCEPT # FastAPI/Swagger/Main Service
    iptables -A INPUT -i "$AP_INTERFACE" -p tcp --dport 7125 -j ACCEPT # Moonraker (direct)
    
    # DNAT: redirect AP clients hitting 192.168.4.1:7125 to Moonraker on 127.0.0.1:7125
    # Required because Moonraker binds only on 127.0.0.1 by default
    log "Adding DNAT rules for localhost-bound services..."
    iptables -t nat -A PREROUTING -i "$AP_INTERFACE" -p tcp --dport 7125 \
        -j DNAT --to-destination 127.0.0.1:7125
    
    # MASQUERADE on loopback so the Pi's services see traffic as coming from 127.0.0.1
    iptables -t nat -A POSTROUTING -o lo -j MASQUERADE
    
    # Allow forwarding to loopback for DNAT'd traffic
    iptables -A FORWARD -i "$AP_INTERFACE" -o lo -j ACCEPT
    iptables -A FORWARD -i lo -o "$AP_INTERFACE" -j ACCEPT
    
    # Block internet access from AP (if main interface exists)
    if [ -n "$MAIN_INTERFACE" ] && [ "$MAIN_INTERFACE" != "$AP_INTERFACE" ]; then
        log "Blocking internet access from $AP_INTERFACE..."
        iptables -A FORWARD -i "$AP_INTERFACE" -o "$MAIN_INTERFACE" -j REJECT --reject-with icmp-port-unreachable
        iptables -A FORWARD -i "$MAIN_INTERFACE" -o "$AP_INTERFACE" -j REJECT --reject-with icmp-port-unreachable
    fi
    
    # Save firewall rules persistently (survives reboots via iptables-persistent)
    mkdir -p /etc/iptables
    iptables-save > /etc/iptables/rules.v4
    ip6tables-save > /etc/iptables/rules.v6 2>/dev/null || true
    log "✓ Firewall rules saved persistently to /etc/iptables/rules.v4"
    
    # Enable netfilter-persistent to restore rules on boot
    systemctl enable netfilter-persistent 2>/dev/null || true
    
    log "✓ Firewall configured - Local services bridged, internet blocked"
}

# Function to start services
start_services() {
    log "Step 6: Starting Access Point services..."
    
    # Enable services
    log "Enabling services..."
    systemctl unmask hostapd
    systemctl enable hostapd
    systemctl enable dnsmasq
    
    # Check if dnsmasq configuration is valid before starting
    log "Validating dnsmasq configuration..."
    if ! dnsmasq --test --conf-file=/etc/dnsmasq.conf; then
        log "❌ dnsmasq configuration is invalid"
        log "Configuration file content:"
        cat /etc/dnsmasq.conf | tee -a "$LOG_FILE"
        error_exit "dnsmasq configuration validation failed"
    fi
    
    # Check if port 53 is already in use
    log "Checking if DNS port 53 is available..."
    if netstat -tulnp | grep :53 > /dev/null; then
        log "⚠ Port 53 is already in use, stopping conflicting services..."
        systemctl stop systemd-resolved 2>/dev/null || true
        pkill -f systemd-resolved 2>/dev/null || true
        sleep 2
    fi
    
    # Start dnsmasq first
    log "Starting dnsmasq..."
    
    # Try to start dnsmasq with detailed error reporting
    if systemctl start dnsmasq; then
        log "✓ dnsmasq service started"
    else
        log "❌ dnsmasq service failed to start"
        log "Getting detailed error information..."
        systemctl status dnsmasq.service | tee -a "$LOG_FILE"
        journalctl -xeu dnsmasq.service --no-pager | tail -20 | tee -a "$LOG_FILE"
        
        # Try manual start for debugging
        log "Trying manual dnsmasq start for debugging..."
        pkill -f dnsmasq 2>/dev/null || true
        if dnsmasq -C /etc/dnsmasq.conf --log-queries --log-dhcp > /tmp/dnsmasq_manual.log 2>&1 & then
            sleep 3
            if pgrep -f dnsmasq > /dev/null; then
                log "✓ dnsmasq started manually"
                log "Manual start log:"
                cat /tmp/dnsmasq_manual.log | tee -a "$LOG_FILE"
            else
                log "❌ dnsmasq failed to start manually"
                cat /tmp/dnsmasq_manual.log | tee -a "$LOG_FILE"
                error_exit "dnsmasq failed to start both via systemd and manually"
            fi
        else
            log "❌ Manual dnsmasq start command failed"
            error_exit "dnsmasq failed to start"
        fi
    fi
    
    # Wait for dnsmasq to start
    sleep 3
    
    # Verify dnsmasq is running
    if pgrep -f dnsmasq > /dev/null; then
        log "✓ dnsmasq is running"
        log "dnsmasq processes:"
        ps aux | grep dnsmasq | grep -v grep | tee -a "$LOG_FILE"
    else
        log "❌ dnsmasq process is NOT running"
        error_exit "dnsmasq failed to start"
    fi
    
    # Test hostapd configuration
    log "Testing hostapd configuration..."
    if timeout 10 hostapd -dd /etc/hostapd/hostapd.conf > /tmp/hostapd_debug.log 2>&1; then
        log "✓ hostapd configuration test passed"
    else
        log "⚠ hostapd configuration test failed, checking logs..."
        tail -10 /tmp/hostapd_debug.log | tee -a "$LOG_FILE"
    fi
    
    # Start hostapd
    log "Starting hostapd..."
    systemctl start hostapd || error_exit "Failed to start hostapd"
    
    # Wait for hostapd to start
    sleep 5
    
    # Verify hostapd is running
    if pgrep -f hostapd > /dev/null; then
        log "✓ hostapd is running"
    else
        log "❌ hostapd process is NOT running"
        systemctl status hostapd.service | tee -a "$LOG_FILE"
        error_exit "hostapd failed to start"
    fi
    
    log "✓ All services started successfully"
}

# Function to start G2-Service
start_g2_service() {
    log "Starting G2-Service for verification..."
    
    # Check if G2-Service is already running
    if pgrep -f "python.*src/main.py" > /dev/null; then
        log "✓ G2-Service is already running"
        return 0
    fi
    
    # Check if the service exists
    if systemctl list-unit-files | grep -q "g2-service.service"; then
        log "Starting G2-Service via systemctl..."
        systemctl start g2-service
        
        # Wait for service to start
        sleep 3
        
        if systemctl is-active --quiet g2-service; then
            log "✓ G2-Service started successfully via systemctl"
            return 0
        else
            log "⚠ G2-Service systemctl failed, trying manual start..."
        fi
    fi
    
    # Try to start manually
    if [ -f "/home/pi/G2-Service/src/main.py" ]; then
        log "Starting G2-Service manually..."
        
        # Check if virtual environment exists
        if [ -d "/home/pi/G2-Service/venv" ]; then
            cd /home/pi/G2-Service
            nohup venv/bin/python src/main.py > /dev/null 2>&1 &
        else
            cd /home/pi/G2-Service
            nohup python3 src/main.py > /dev/null 2>&1 &
        fi
        
        # Wait for service to start
        sleep 5
        
        if pgrep -f "python.*src/main.py" > /dev/null; then
            log "✓ G2-Service started successfully manually"
            return 0
        else
            log "❌ Failed to start G2-Service"
            return 1
        fi
    else
        log "❌ G2-Service main.py not found at /home/pi/G2-Service/src/main.py"
        return 1
    fi
}

# Function to verify setup
verify_setup() {
    log "Step 7: Verifying Access Point setup..."
    
    local errors=0
    
    # Check interface IP
    if ip addr show "$AP_INTERFACE" | grep -q "$AP_IP"; then
        log "✓ $AP_INTERFACE has correct IP ($AP_IP)"
    else
        log "❌ $AP_INTERFACE does NOT have correct IP"
        ((errors++))
    fi
    
    # Check hostapd process
    if pgrep -f hostapd > /dev/null; then
        log "✓ hostapd process is running"
    else
        log "❌ hostapd process is NOT running"
        ((errors++))
    fi
    
    # Check dnsmasq process
    if pgrep -f dnsmasq > /dev/null; then
        log "✓ dnsmasq process is running"
    else
        log "❌ dnsmasq process is NOT running"
        ((errors++))
    fi
    
    # Check DHCP server
    if netstat -ulnp | grep :67 > /dev/null; then
        log "✓ DHCP server is listening on port 67"
    else
        log "❌ DHCP server is NOT listening"
        ((errors++))
    fi
    
    # Check DNS server
    if netstat -ulnp | grep :53 > /dev/null; then
        log "✓ DNS server is listening on port 53"
    else
        log "❌ DNS server is NOT listening"
        ((errors++))
    fi
    
    # Test local service access
    log "Testing local service access..."
    
    # Test HTTP service (main page)
    if timeout 5 curl -s http://"$AP_IP" > /dev/null; then
        log "✓ HTTP service accessible"
    else
        log "❌ HTTP service NOT accessible"
        ((errors++))
    fi
    
    # Test FastAPI service (correct port 8080)
    if timeout 5 curl -s http://"$AP_IP":8080 > /dev/null; then
        log "✓ FastAPI service accessible"
    else
        log "❌ FastAPI service NOT accessible"
        ((errors++))
    fi
    
    # Test FastAPI docs specifically
    if timeout 5 curl -s http://"$AP_IP":8080/docs > /dev/null; then
        log "✓ Swagger API docs accessible"
    else
        log "❌ Swagger API docs NOT accessible"
        ((errors++))
    fi
    
    # Test DNS resolution (non-blocking)
    log "Testing DNS resolution..."
    dns_working=false
    
    # Test with nslookup first
    if timeout 5 nslookup mainsail.local "$AP_IP" > /dev/null 2>&1; then
        log "✓ DNS resolution working with nslookup"
        dns_working=true
    else
        log "⚠ nslookup failed, trying alternative methods..."
        # Try with host
        if timeout 5 host mainsail.local "$AP_IP" > /dev/null 2>&1; then
            log "✓ DNS resolution working with host"
            dns_working=true
        else
            log "⚠ DNS resolution issues detected"
            log "  Services will still be accessible via IP address"
            log "  Checking DNS server basic functionality..."
            
            # Check if DNS server responds to basic queries
            if timeout 3 telnet "$AP_IP" 53 </dev/null 2>/dev/null | grep -q "Connected"; then
                log "✓ DNS server port is responsive"
            else
                log "⚠ DNS server port may have issues"
            fi
            
            # Don't fail the entire setup for DNS issues, just warn
            log "⚠ DNS resolution has issues - services accessible via IP only"
            dns_working=false
        fi
    fi
    
    # Check for DHCP clients (optional)
    if [ -f "/var/lib/misc/dnsmasq.leases" ] && [ -s "/var/lib/misc/dnsmasq.leases" ]; then
        local client_count=$(wc -l < /var/lib/misc/dnsmasq.leases)
        log "✓ DHCP has served $client_count client(s)"
    else
        log "ℹ No DHCP clients yet (normal for new setup)"
    fi
    
    # Final assessment - DNS issues don't fail the setup
    if [ $errors -eq 0 ]; then
        log "✓ All critical verification checks passed"
        if [ "$dns_working" = true ]; then
            log "✓ DNS resolution working perfectly"
        else
            log "⚠ DNS has issues but services accessible via IP"
        fi
        return 0
    else
        log "❌ $errors critical verification checks failed"
        return 1
    fi
}

# Function to generate QR code
generate_qr_code() {
    log "Generating WiFi QR code..."
    
    local qr_code_file="/home/pi/printer_data/config/ap_qr.png"
    local ssid=$(grep "^SSID:" "$CREDENTIALS_FILE" | cut -d' ' -f2)
    local password=$(grep "^Password:" "$CREDENTIALS_FILE" | cut -d' ' -f2)
    
    # Install required packages if needed
    if ! command -v qrencode >/dev/null 2>&1; then
        log "Installing qrencode for QR code generation..."
        apt update && apt install -y qrencode
    fi
    
    if ! command -v convert >/dev/null 2>&1; then
        log "Installing ImageMagick for image processing..."
        apt update && apt install -y imagemagick
    fi
    
    # Generate QR code
    local temp_qr="/tmp/temp_ap_qr.png"
    local wifi_string="WIFI:T:WPA;S:$ssid;P:$password;H:true;;"
    
    if qrencode -o "$temp_qr" -s 10 "$wifi_string"; then
        # Create final image with text
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
        
        rm -f "$temp_qr"
        
        if [ -f "$qr_code_file" ]; then
            log "✓ QR code generated: $qr_code_file"
        else
            log "❌ Failed to generate final QR code"
        fi
    else
        log "❌ Failed to generate QR code"
    fi
}

# Main execution function
main() {
    log "Starting Access Point setup process..."
    log "======================================"
    
    # Initialize log file
    mkdir -p "$(dirname "$LOG_FILE")"
    touch "$LOG_FILE"
    
    # Execute setup steps
    prepare_wlan0_interface || error_exit "Interface preparation failed"
    install_ap_requirements || error_exit "Package installation failed"
    configure_network_interface || error_exit "Network configuration failed"
    configure_dnsmasq || error_exit "dnsmasq configuration failed"
    configure_hostapd || error_exit "hostapd configuration failed"
    configure_firewall || error_exit "Firewall configuration failed"
    configure_nginx_ap || error_exit "nginx AP proxy configuration failed"
    optimize_dns_resolution || error_exit "DNS optimization failed"
    start_services || error_exit "Service startup failed"
    
    # Wait for services to stabilize
    log "Waiting for services to stabilize..."
    sleep 10
    
    # Start G2-Service for verification
    start_g2_service
    
    # Verify setup
    if verify_setup; then
        log ""
        log "🎉 Access Point setup completed successfully!"
        log "=========================================="
        
        # Final comprehensive test
        log "Running final connectivity test..."
        if timeout 5 curl -s http://"$AP_IP":8080/docs > /dev/null && \
           timeout 5 curl -s http://"$AP_IP":8080 > /dev/null; then
            log "✅ All services are accessible and working!"
        else
            log "⚠ Some services may need additional configuration"
        fi
        
        # Display connection info
        local ssid=$(grep "^SSID:" "$CREDENTIALS_FILE" | cut -d' ' -f2)
        local password=$(grep "^Password:" "$CREDENTIALS_FILE" | cut -d' ' -f2)
        
        log ""
        log "📱 Connection Information:"
        log "========================"
        log "📡 Network: $ssid"
        log "🔑 Password: $password"
        log "🌐 IP Address: $AP_IP"
        log "📡 Interface: $AP_INTERFACE"
        log "🌍 Country: IT"
        log "� Network Type: $([ "$AP_HIDDEN" = "true" ] && echo "Hidden (SSID not broadcasted)" || echo "Visible (SSID broadcasted)")"
        log ""
        log "📱 Local Services Access (via nginx port 80):"
        log "============================================="
        log "�️  Mainsail:            http://$AP_IP/"
        log "�📊 Swagger UI:          http://$AP_IP/docs"
        log "�️  G2-Service API:      http://$AP_IP/g2/"
        log "🔧 Moonraker API:       http://$AP_IP/api"
        log "🔌 Moonraker WebSocket: ws://$AP_IP/websocket"
        log ""
        log "Direct ports (also accessible):"
        log "🖥️  G2-Service FastAPI:  http://$AP_IP:8080"
        log "� Moonraker:           http://$AP_IP:7125"
        log "🔗 DNS Names: mainsail.local, api.local, g2.local"
        log ""
        log "🔒 Internet access is BLOCKED - Only local services available"
        log ""
        log "📋 Testing Steps:"
        log "=================="
        log "1. Connect a device to the network '$ssid'"
        log "2. Use the password: $password"
        log "3. You should get an IP address in the range 192.168.4.2-192.168.4.20"
        log "4. Test connectivity by accessing http://$AP_IP/"
        log ""
        log "📄 Credentials saved to: $CREDENTIALS_FILE"
        log "📝 Log file: $LOG_FILE"
        
        # Generate QR code
        generate_qr_code
        
        return 0
    else
        error_exit "Setup verification failed. Check $LOG_FILE for details."
    fi
}

# Run main function
main "$@"
