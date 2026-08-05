#!/bin/bash

# LED Matrix Display Installation Script for Raspberry Pi
# This script enables SPI and installs all required dependencies

set -e

echo "=========================================="
echo "LED Matrix Display Installation"
echo "=========================================="

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ] || ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "⚠️  Warning: This script is designed for Raspberry Pi"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Enable SPI
echo "📡 Enabling SPI interface..."
if command -v raspi-config &> /dev/null; then
    sudo raspi-config nonint do_spi 0
    echo "✓ SPI enabled (reboot may be required)"
else
    echo "⚠️  raspi-config not found, please enable SPI manually"
fi

# Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt update
sudo apt install -y python3-full python3-pip python3-venv git

# Ask installation method
echo ""
echo "Choose installation method:"
echo "1) Virtual environment (recommended)"
echo "2) System-wide (with --break-system-packages)"
echo "3) Via apt packages"
read -p "Enter choice [1-3] (default: 1): " choice
choice=${choice:-1}

case $choice in
    1)
        echo "🔧 Creating virtual environment..."
        python3 -m venv venv
        source venv/bin/activate
        echo "✓ Virtual environment created"
        echo "📦 Installing Python packages..."
        pip install --upgrade pip
        pip install -r requirements.txt
        echo "✓ Packages installed in venv"
        echo ""
        echo "📝 To activate the virtual environment, run:"
        echo "   source venv/bin/activate"
        ;;
    2)
        echo "📦 Installing Python packages system-wide..."
        pip install --break-system-packages --upgrade pip
        pip install --break-system-packages -r requirements.txt
        echo "✓ Packages installed system-wide"
        ;;
    3)
        echo "📦 Installing Python packages via apt..."
        sudo apt install -y python3-luma.led-matrix python3-luma.core python3-spidev python3-rpi.gpio || {
            echo "⚠️  Some apt packages not available, falling back to pip"
            pip install --break-system-packages -r requirements.txt
        }
        echo "✓ Packages installed"
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

# Make script executable
echo "🔧 Making display script executable..."
chmod +x led_matrix_display.py
echo "✓ Script is now executable"

echo ""
echo "=========================================="
echo "✓ Installation complete!"
echo "=========================================="
echo ""
echo "Next steps:"
if [ "$choice" = "1" ]; then
    echo "  1. Activate virtual environment: source venv/bin/activate"
fi
echo "  2. Reboot if SPI was just enabled: sudo reboot"
echo "  3. Run the display script:"
echo "     ./led_matrix_display.py \"Hello World!\""
echo ""
