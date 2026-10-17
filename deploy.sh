#!/bin/bash
set -e

echo "========================================="
echo " SkyRewind Production Deployment Script"
echo "========================================="
echo

# Configuration
INSTALL_DIR="/opt/skyrewind"
SERVICE_USER="skyrewind"
VENV_PATH="${INSTALL_DIR}/venv"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

# Check if rtl_adsb is available
if ! command -v rtl_adsb &> /dev/null; then
    echo "WARNING: rtl_adsb command not found"
    echo "Install rtl-sdr package (rtl_adsb) before running SkyRewind"
    echo
fi

# Create service user if it doesn't exist
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "Creating service user: $SERVICE_USER"
    useradd --system --no-create-home --shell /bin/false "$SERVICE_USER"
fi

# Add skyrewind user to plugdev group (needed for RTL-SDR access)
echo "Adding $SERVICE_USER to plugdev group..."
usermod -a -G plugdev "$SERVICE_USER"

# Stop and disable dump1090-mutability (bridge replaces it)
if systemctl list-unit-files | grep -q dump1090-mutability; then
    echo "Stopping and disabling dump1090-mutability..."
    systemctl stop dump1090-mutability.service || true
    systemctl disable dump1090-mutability.service || true
fi

# Create installation directory
echo "Setting up installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# Copy files excluding .git, __pycache__, and database files
echo "Copying application files..."
rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='data/*.db' --exclude='data/*.sqlite*' --exclude='.pytest_cache' \
    ./ "$INSTALL_DIR/"

chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# Create Python virtual environment
echo "Creating Python virtual environment..."
cd "$INSTALL_DIR"
sudo -u "$SERVICE_USER" python3 -m venv "$VENV_PATH"

# Install Python dependencies
echo "Installing Python dependencies..."
sudo -u "$SERVICE_USER" "$VENV_PATH/bin/pip" install --upgrade pip
sudo -u "$SERVICE_USER" "$VENV_PATH/bin/pip" install -r requirements.txt gunicorn

# Initialize database
echo "Initializing database..."
sudo -u "$SERVICE_USER" "$VENV_PATH/bin/python3" -c "from backend.database import init_db; init_db()"

# Install systemd service files
echo "Installing systemd service files..."
cp systemd/skyrewind-adsb-bridge.service /etc/systemd/system/
cp systemd/skyrewind-logger.service /etc/systemd/system/
cp systemd/skyrewind-web.service /etc/systemd/system/
cp systemd/skyrewind-dashboard.service /etc/systemd/system/
chmod 644 /etc/systemd/system/skyrewind-*.service

# Install tmpfiles.d config for /var/run/dump1090-mutability
echo "Installing tmpfiles.d configuration..."
cp systemd/tmpfiles.d/skyrewind.conf /etc/tmpfiles.d/
chmod 644 /etc/tmpfiles.d/skyrewind.conf

# Create the directory now (tmpfiles also creates on boot)
systemd-tmpfiles --create /etc/tmpfiles.d/skyrewind.conf

# Reload systemd
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable and restart services
echo "Enabling and restarting services..."
systemctl enable skyrewind-adsb-bridge.service
systemctl enable skyrewind-logger.service
systemctl enable skyrewind-web.service
systemctl enable skyrewind-dashboard.service
systemctl restart skyrewind-adsb-bridge.service
systemctl restart skyrewind-logger.service
systemctl restart skyrewind-web.service
systemctl restart skyrewind-dashboard.service

# Wait a moment for services to start
sleep 2

# Check service status
echo
echo "========================================="
echo " Service Status"
echo "========================================="
systemctl status skyrewind-adsb-bridge.service --no-pager -l || true
echo
systemctl status skyrewind-logger.service --no-pager -l || true
echo
systemctl status skyrewind-web.service --no-pager -l || true
echo
systemctl status skyrewind-dashboard.service --no-pager -l || true

# Get server IP address
SERVER_IP=$(hostname -I | awk '{print $1}')

echo
echo "========================================="
echo " Deployment Complete!"
echo "========================================="
echo
echo "SkyRewind is now running:"
echo "  - ADS-B Bridge: systemctl status skyrewind-adsb-bridge"
echo "  - Logger:       systemctl status skyrewind-logger"
echo "  - Web:          systemctl status skyrewind-web"
echo "  - Dashboard:    systemctl status skyrewind-dashboard"
echo
echo "Access the application at:"
echo "  http://localhost:5000"
echo "  http://${SERVER_IP}:5000"
echo
echo "Useful commands:"
echo "  sudo systemctl restart skyrewind-adsb-bridge"
echo "  sudo systemctl restart skyrewind-logger"
echo "  sudo systemctl restart skyrewind-web"
echo "  sudo systemctl restart skyrewind-dashboard"
echo "  sudo journalctl -u skyrewind-adsb-bridge -f"
echo "  sudo journalctl -u skyrewind-logger -f"
echo "  sudo journalctl -u skyrewind-web -f"
echo "  sudo journalctl -u skyrewind-dashboard -f"
echo
