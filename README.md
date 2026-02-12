# G2-Service

G2-Service is a project by Ginger for configuring the G2 3D printer. This guide will help you install and update all necessary components to ensure your 3D printer operates at its best.

## Installation Guide

### Requirements
- G2 3D Printer
- Access to the printer's local network
- An SSH client (such as PuTTY)
- A GitHub account

### Instructions

1. **Find the correct printer IP address**
   - Use the Mainsail software to find the IP address of your G2 printer.
   - Access Mainsail through your browser by entering the printer's IP address.

2. **Log in to the machine page**
   - Once logged into Mainsail, go to the machine page to manage the printer's settings and updates.

3. **Update all components**
   - On the machine page, locate the refresh button in the update manager and click the "Refresh" button to ensure all components are updated to the latest version.

4. **Log in with SSH**
   - Use an SSH client like PuTTY to log in to your printer. You will need the printer's IP address and login credentials.

5. **Clone the G2-Service project**
   - After logging in via SSH, run the following commands to clone the G2-Service project and start the installation script:
     ```sh
     cd ~
     git clone https://github.com/gingeradditive/G2-Service.git
     sh ./G2-Service/Scripts/install.sh 2>&1 | tee output.txt
     ```

### Notes
- **Backup:** It is always a good idea to back up your current configurations before performing updates or changes.
- **Support:** If you encounter any issues during the installation, contact Ginger's technical support.

## Additional Scripts

### Complete WiFi Setup for USB Dongle
Complete automated pipeline script that installs drivers and configures WiFi network for USB dongles:

```sh
sudo ./G2-Service/Scripts/setup_wifi_complete.sh
```

This script will:
- **Check connected USB devices** and identify WiFi dongles
- **Install WiFi drivers and firmware** automatically if needed
- **Load appropriate kernel modules** for common chipsets
- **Generate unique SSID** using format "G2TabletNetwork-######" (last 6 chars of wlan0 MAC)
- **Generate deterministic password** from SHA256 hash of wlan0 MAC address (format: G2 + 16 hash chars)
- **Configure hidden WiFi network** (SSID not broadcasted for security)
- **Configure network settings** and test connection
- **Save credentials** to `/home/pi/wifi_credentials.txt`
- **Generate WiFi QR code** at `~/printer_data/config/wifi_qr.png` with text overlay and decorations
- **Display IP address** and connection status

**Smart Features:**
- **Automatic driver detection** - Only installs drivers if wlan1 is not found
- **Comprehensive chipset support** - Realtek, Ralink, MediaTek, Atheros, Broadcom
- **Error recovery** - Provides troubleshooting steps if setup fails
- **Zero-interaction** - Fully automated pipeline script

**Requirements:**
- USB WiFi dongle connected to the Raspberry Pi
- wlan0 interface available for MAC address generation
- sudo privileges to modify network configuration

**Note:** This single script replaces both the dongle setup and WiFi configuration scripts.

**Generated Files:**
- `/home/pi/wifi_credentials.txt` - Contains SSID, password, and network details (including hidden network info)
- `~/printer_data/config/wifi_qr.png` - Enhanced QR code with text overlay showing SSID, password, and styling (overwritten each run)

**Enhanced QR Code Features:**
- **Text Overlay** - Displays SSID and password directly on the image
- **White Border** - 50px white space around QR code for better visibility
- **Decorative Elements** - Professional styling with headers and footers
- **Hidden Network Indicator** - "Hidden Network - Scan to Connect" text
- **High Quality** - Larger QR code size (10px per module) for better scanning
- **Professional Layout** - Clean design with proper typography and spacing

**Deterministic Password Generation:**
- **MAC-based hash** - Password generated from SHA256 hash of wlan0 MAC address
- **Format**: G2XXXXXXXXXXXXXXXX (G2 + first 16 characters of SHA256 hash)
- **Secure** - Hash provides cryptographic security while remaining deterministic
- **Deterministic** - Same MAC always generates same password hash
- **Unique per device** - Different MAC addresses produce different hash values
- **Non-reversible** - MAC address cannot be determined from the password

**Hidden Network Features:**
- **SSID not broadcasted** - Network won't appear in WiFi scans for enhanced security
- **scan_ssid=1** - Configured to actively probe for the hidden network
- **QR code includes H:true** - Indicates hidden network in QR code format
- **Manual connection required** - Devices must know exact SSID to connect

## License
This project is released under the MIT license. For more details, see the LICENSE file.

## Contact
For more information, visit our [website](https://gingeradditive.com) or contact us via email at support@gingeradditive.com.

---

We hope you find this guide helpful. Happy printing!
