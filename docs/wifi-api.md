# WiFi Network API Endpoints

This document describes the WiFi network endpoints added to G2-Service for Raspberry Pi 4.

## Prerequisites

The server requires NetworkManager to be installed and running on the Raspberry Pi:

```bash
# Install NetworkManager (if not already installed)
sudo apt-get update
sudo apt-get install network-manager

# Enable and start NetworkManager
sudo systemctl enable NetworkManager
sudo systemctl start NetworkManager

# Check status
sudo systemctl status NetworkManager
```

## API Endpoints

### Get Visible WiFi Networks

**GET** `/api/wifi/networks`

Returns a list of all visible WiFi networks with their details.

**Response:**
```json
[
  {
    "ssid": "NetworkName",
    "signal_strength": 85,
    "security": "WPA2",
    "frequency": 2412,
    "is_hidden": false
  }
]
```

**Response Model:**
- `ssid`: Network name (string)
- `signal_strength`: Signal strength in percentage (integer, optional)
- `security`: Security type (string, optional)
- `frequency`: Frequency in MHz (integer, optional)
- `is_hidden`: Whether network is hidden (boolean)

### Get WiFi Status

**GET** `/api/wifi/status`

Returns the current status of the WiFi adapter.

**Response:**
```json
{
  "device": "wlan0",
  "type": "wifi",
  "state": "connected",
  "connection": "MyWiFiNetwork"
}
```

### Trigger WiFi Rescan

**POST** `/api/wifi/rescan`

Triggers a new scan for WiFi networks.

**Response:**
```json
{
  "success": true,
  "message": "WiFi rescan triggered"
}
```

## Usage Examples

### Using curl

```bash
# Get available networks
curl http://localhost:8080/api/wifi/networks

# Get WiFi status
curl http://localhost:8080/api/wifi/status

# Trigger rescan
curl -X POST http://localhost:8080/api/wifi/rescan
```

### Using Python requests

```python
import requests

# Get available networks
response = requests.get("http://localhost:8080/api/wifi/networks")
networks = response.json()

# Get WiFi status
status = requests.get("http://localhost:8080/api/wifi/status").json()

# Trigger rescan
rescan = requests.post("http://localhost:8080/api/wifi/rescan").json()
```

## Error Handling

The endpoints return HTTP 500 status codes when NetworkManager operations fail. Common issues include:

- NetworkManager not installed
- WiFi adapter not available
- Insufficient permissions (may need to run with appropriate user privileges)

## Testing

Run the test script to verify functionality:

```bash
python test_wifi.py
```

## Security Notes

- These endpoints only read network information and do not modify network configurations
- No passwords or sensitive information is exposed
- Consider adding authentication for production deployments
