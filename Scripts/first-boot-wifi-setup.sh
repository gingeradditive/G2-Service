#!/bin/bash

# First Boot WiFi Setup Script for G2-Service
# This script runs only on first boot when network interfaces are available
# It configures the WiFi access point and then disables itself

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Check if first boot has already completed
if [ -f "/etc/g2-service/first-boot-completed" ]; then
    log "First boot setup already completed. Skipping WiFi setup."
    exit 0
fi

log "Starting G2-Service first boot WiFi setup..."

# Wait for network interfaces to be available
log "Waiting for network interfaces to be available..."
MAX_WAIT=60
WAIT_COUNT=0

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if ip link show wlan0 >/dev/null 2>&1; then
        log "wlan0 interface is available"
        break
    fi
    
    info "Waiting for wlan0 interface... ($((WAIT_COUNT + 1))/$MAX_WAIT)"
    sleep 2
    ((WAIT_COUNT++))
done

if [ $WAIT_COUNT -eq $MAX_WAIT ]; then
    error "wlan0 interface not available after $MAX_WAIT seconds"
    error "WiFi setup will be skipped. You can run it manually later:"
    error "sudo /home/pi/G2-Service/Scripts/setup_wifi_complete.sh"
    exit 1
fi

# Check if WiFi setup script exists
WIFI_SCRIPT="/home/pi/G2-Service/Scripts/setup_wifi_complete.sh"
if [ ! -f "$WIFI_SCRIPT" ]; then
    error "WiFi setup script not found: $WIFI_SCRIPT"
    exit 1
fi

# Make WiFi script executable
chmod +x "$WIFI_SCRIPT"

# Run WiFi setup
log "Running WiFi setup script..."
if "$WIFI_SCRIPT"; then
    log "WiFi setup completed successfully!"
    
    # Mark first boot as completed
    mkdir -p /etc/g2-service
    touch /etc/g2-service/first-boot-completed
    log "First boot setup marked as completed"
    
    # Display WiFi credentials
    CREDENTIALS_FILE="/home/pi/ap_credentials.txt"
    if [ -f "$CREDENTIALS_FILE" ]; then
        log ""
        log "🎉 WiFi Access Point is ready!"
        log "================================"
        cat "$CREDENTIALS_FILE"
        log ""
        log "📱 Connect your tablet/device to the WiFi network"
        log "📊 Then access: http://192.168.4.1:8000/docs"
        log ""
    fi
    
else
    error "WiFi setup failed!"
    error "You can run it manually later:"
    error "sudo $WIFI_SCRIPT"
    exit 1
fi

# Disable and remove the first-boot service
log "Disabling first-boot service..."
systemctl disable g2-service-first-boot.service 2>/dev/null || true
systemctl daemon-reload

log "First boot WiFi setup completed successfully!"
