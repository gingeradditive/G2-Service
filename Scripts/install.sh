#!/bin/bash

# G2 FastAPI Service Installation Script for Raspberry Pi
# This script installs and configures the FastAPI service to run on startup

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="g2-api"
SERVICE_USER="g2service"
SERVICE_DIR="/opt/g2-service"
PYTHON_VERSION="3.9"
VENV_PATH="$SERVICE_DIR/venv"
REPO_URL="https://github.com/your-org/G2-Service.git"  # Update with actual repo URL

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
    fi
}

# Check if this is a Raspberry Pi
check_raspberry_pi() {
    if ! grep -q "Raspberry Pi" /proc/cpuinfo && ! grep -q "BCM" /proc/cpuinfo; then
        warning "This doesn't appear to be a Raspberry Pi. Continue anyway? (y/N)"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Update system packages
update_system() {
    log "Updating system packages..."
    apt update && apt upgrade -y
    success "System updated"
}

# Install system dependencies
install_dependencies() {
    log "Installing system dependencies..."
    
    # Basic dependencies
    apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        git \
        curl \
        wget \
        build-essential \
        libffi-dev \
        libssl-dev \
        nginx \
        supervisor
    
    # Install uvicorn with system dependencies
    apt install -y \
        python3-certifi \
        python3-chardet \
        python3-idna \
        python3-urllib3 \
        python3-requests
    
    success "System dependencies installed"
}

# Create service user
create_service_user() {
    log "Creating service user: $SERVICE_USER"
    
    if ! id "$SERVICE_USER" &>/dev/null; then
        useradd -r -s /bin/false -d "$SERVICE_DIR" "$SERVICE_USER"
        success "Service user created"
    else
        warning "Service user already exists"
    fi
}

# Create service directory
create_service_directory() {
    log "Creating service directory: $SERVICE_DIR"
    
    mkdir -p "$SERVICE_DIR"
    chown -R "$SERVICE_USER:$SERVICE_USER" "$SERVICE_DIR"
    chmod 755 "$SERVICE_DIR"
    
    success "Service directory created"
}

# Clone or update repository
setup_repository() {
    log "Setting up service repository..."
    
    if [[ -d "$SERVICE_DIR/.git" ]]; then
        log "Repository exists, updating..."
        cd "$SERVICE_DIR"
        sudo -u "$SERVICE_USER" git pull origin main
    else
        log "Cloning repository..."
        cd "$SERVICE_DIR"
        sudo -u "$SERVICE_USER" git clone "$REPO_URL" .
    fi
    
    success "Repository setup complete"
}

# Create Python virtual environment
create_venv() {
    log "Creating Python virtual environment..."
    
    cd "$SERVICE_DIR"
    
    # Remove existing venv if present
    if [[ -d "$VENV_PATH" ]]; then
        rm -rf "$VENV_PATH"
    fi
    
    # Create new virtual environment
    python3 -m venv "$VENV_PATH"
    chown -R "$SERVICE_USER:$SERVICE_USER" "$VENV_PATH"
    
    success "Virtual environment created"
}

# Install Python dependencies
install_python_deps() {
    log "Installing Python dependencies..."
    
    cd "$SERVICE_DIR"
    
    # Activate virtual environment and install dependencies
    sudo -u "$SERVICE_USER" "$VENV_PATH/bin/pip" install --upgrade pip
    sudo -u "$SERVICE_USER" "$VENV_PATH/bin/pip" install -r Backend/requirements.txt
    
    # Install additional dependencies for production
    sudo -u "$SERVICE_USER" "$VENV_PATH/bin/pip" install \
        gunicorn \
        python-multipart
    
    success "Python dependencies installed"
}

# Create systemd service
create_systemd_service() {
    log "Creating systemd service..."
    
    cat > "/etc/systemd/system/$SERVICE_NAME.service" << EOF
[Unit]
Description=G2 FastAPI Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$SERVICE_DIR/Backend
Environment="PATH=$VENV_PATH/bin"
ExecStart=$VENV_PATH/bin/gunicorn server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$SERVICE_DIR

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    
    success "Systemd service created and enabled"
}

# Configure nginx reverse proxy (optional)
configure_nginx() {
    log "Configuring nginx reverse proxy..."
    
    cat > "/etc/nginx/sites-available/$SERVICE_NAME" << EOF
server {
    listen 80;
    server_name _;
    
    # API routes
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Static files (if any)
    location /static/ {
        alias $SERVICE_DIR/Backend/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
EOF

    # Enable site
    ln -sf "/etc/nginx/sites-available/$SERVICE_NAME" "/etc/nginx/sites-enabled/"
    rm -f "/etc/nginx/sites-enabled/default"
    
    # Test and restart nginx
    nginx -t && systemctl restart nginx
    systemctl enable nginx
    
    success "Nginx configured"
}

# Set up log rotation
setup_log_rotation() {
    log "Setting up log rotation..."
    
    cat > "/etc/logrotate.d/$SERVICE_NAME" << EOF
/var/log/$SERVICE_NAME/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 $SERVICE_USER $SERVICE_USER
    postrotate
        systemctl reload $SERVICE_NAME
    endscript
}
EOF

    success "Log rotation configured"
}

# Create startup script
create_startup_script() {
    log "Creating startup script..."
    
    cat > "$SERVICE_DIR/start.sh" << EOF
#!/bin/bash
# G2 Service startup script

SERVICE_DIR="$SERVICE_DIR"
VENV_PATH="$VENV_PATH"
SERVICE_NAME="$SERVICE_NAME"

cd "\$SERVICE_DIR/Backend"

# Check if virtual environment exists
if [[ ! -d "\$VENV_PATH" ]]; then
    echo "Virtual environment not found. Please run install script again."
    exit 1
fi

# Activate virtual environment
source "\$VENV_PATH/bin/activate"

# Start the service
exec gunicorn server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
EOF

    chmod +x "$SERVICE_DIR/start.sh"
    chown "$SERVICE_USER:$SERVICE_USER" "$SERVICE_DIR/start.sh"
    
    success "Startup script created"
}

# Start the service
start_service() {
    log "Starting $SERVICE_NAME service..."
    
    systemctl start "$SERVICE_NAME"
    
    # Wait a moment and check status
    sleep 3
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        success "Service started successfully"
        log "Service status: $(systemctl is-active "$SERVICE_NAME")"
    else
        error "Service failed to start. Check logs with: journalctl -u $SERVICE_NAME"
    fi
}

# Display installation summary
show_summary() {
    log "Installation Summary:"
    echo "=================================="
    echo "Service Name: $SERVICE_NAME"
    echo "Service User: $SERVICE_USER"
    echo "Service Directory: $SERVICE_DIR"
    echo "Virtual Environment: $VENV_PATH"
    echo "API Endpoint: http://$(hostname -I | awk '{print $1}'):8000"
    echo "API Documentation: http://$(hostname -I | awk '{print $1}'):8000/docs"
    echo ""
    echo "Service Management Commands:"
    echo "  Start:   sudo systemctl start $SERVICE_NAME"
    echo "  Stop:    sudo systemctl stop $SERVICE_NAME"
    echo "  Restart: sudo systemctl restart $SERVICE_NAME"
    echo "  Status:  sudo systemctl status $SERVICE_NAME"
    echo "  Logs:    sudo journalctl -u $SERVICE_NAME -f"
    echo "=================================="
}

# Main installation function
main() {
    log "Starting G2 FastAPI Service Installation..."
    
    check_root
    check_raspberry_pi
    update_system
    install_dependencies
    create_service_user
    create_service_directory
    setup_repository
    create_venv
    install_python_deps
    create_systemd_service
    configure_nginx
    setup_log_rotation
    create_startup_script
    start_service
    show_summary
    
    success "Installation completed successfully!"
}

# Handle script arguments
case "${1:-}" in
    "update")
        log "Updating G2 FastAPI Service..."
        update_system
        setup_repository
        install_python_deps
        systemctl restart "$SERVICE_NAME"
        success "Service updated and restarted"
        ;;
    "uninstall")
        log "Uninstalling G2 FastAPI Service..."
        systemctl stop "$SERVICE_NAME" || true
        systemctl disable "$SERVICE_NAME" || true
        rm -f "/etc/systemd/system/$SERVICE_NAME.service"
        systemctl daemon-reload
        rm -f "/etc/nginx/sites-available/$SERVICE_NAME"
        rm -f "/etc/nginx/sites-enabled/$SERVICE_NAME"
        systemctl restart nginx || true
        userdel -r "$SERVICE_USER" || true
        rm -rf "$SERVICE_DIR"
        success "Service uninstalled"
        ;;
    "status")
        systemctl status "$SERVICE_NAME"
        ;;
    "logs")
        journalctl -u "$SERVICE_NAME" -f
        ;;
    "help"|"-h"|"--help")
        echo "G2 FastAPI Service Installation Script"
        echo ""
        echo "Usage: $0 [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  (no args)  Full installation"
        echo "  update     Update existing installation"
        echo "  uninstall  Remove service and files"
        echo "  status     Show service status"
        echo "  logs       Show service logs"
        echo "  help       Show this help"
        ;;
    "")
        main
        ;;
    *)
        error "Unknown command: $1. Use 'help' for usage information."
        ;;
esac
