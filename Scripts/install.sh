#!/bin/bash

# Install script for G2-Service FastAPI client on Raspberry Pi
# This script installs the FastAPI client in production mode,
# installs first-boot WiFi setup service, and creates the Configs symbolic link
# WiFi setup runs automatically on first boot when interfaces are available

set -e  # Exit on any error

echo "Starting G2-Service installation on Raspberry Pi..."

# Update system packages
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python and pip if not already installed
echo "Installing Python and pip..."
sudo apt install -y python3 python3-pip python3-venv

# Install Python dependencies in project directory
echo "Installing Python dependencies in project directory..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install fastapi uvicorn python-multipart
pip install -r requirements.txt

# Create systemd service file for production
echo "Creating systemd service..."
sudo tee /etc/systemd/system/g2-service.service > /dev/null <<EOF
[Unit]
Description=G2-Service FastAPI Client
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
ExecStart=$(pwd)/venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
echo "Enabling and starting G2-Service..."
sudo systemctl daemon-reload
sudo systemctl enable g2-service
sudo systemctl start g2-service

# Install first-boot service for WiFi setup
echo "Installing first-boot WiFi setup service..."
sudo cp Scripts/g2-service-first-boot.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/g2-service-first-boot.service
sudo systemctl daemon-reload
sudo systemctl enable g2-service-first-boot.service
echo "First-boot WiFi service installed - will run on next boot when interfaces are available"

# WiFi setup will be handled by first-boot service
echo "WiFi setup will be configured at first boot when interfaces are available"

# Create printer_data config directory if it doesn't exist
echo "Creating printer_data config directory..."
mkdir -p ~/printer_data/config

# Create symbolic link for Configs
echo "Creating symbolic link for Configs..."
if [ -d "Configs" ]; then
    ln -sf "$(pwd)/Configs" ~/printer_data/config/G2-Configs
    echo "Symbolic link created: ~/printer_data/config/G2-Configs -> $(pwd)/Configs"
else
    echo "Warning: Configs directory not found in project root"
fi

# Set permissions
echo "Setting permissions..."
chmod +x Scripts/deploy.sh

echo "Installation completed successfully!"
echo "G2-Service is running on http://localhost:8000"
echo "Service status: sudo systemctl status g2-service"
echo "Service logs: sudo journalctl -u g2-service -f"
