#!/bin/bash
# USB Defender Kiosk - Master Installation Script
# This script installs and configures the complete USB Defender Kiosk system

set -e

echo "=========================================="
echo "USB Defender Kiosk - Installation"
echo "=========================================="
echo ""
echo "This script will install and configure the USB Defender Kiosk system."
echo "It will:"
echo "  1. Install system dependencies"
echo "  2. Configure USB security (read-only, no autorun)"
echo "  3. Set up ClamAV antivirus"
echo "  4. Create kiosk user account"
echo "  5. Install Python application"
echo "  6. Configure kiosk mode"
echo "  7. Set up systemd services"
echo ""
echo "WARNING: This will modify system security settings."
echo "Only run this on a dedicated kiosk system."
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

# Check Ubuntu version
if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [ "$ID" != "ubuntu" ]; then
        echo "WARNING: This script is designed for Ubuntu Desktop."
        echo "Current OS: $ID $VERSION_ID"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
else
    echo "ERROR: Cannot determine OS version"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="/opt/usb-defender-kiosk"

echo "Installation directory: $INSTALL_DIR"
echo ""

read -p "Press Enter to continue or Ctrl+C to cancel..."

# Copy application to /opt if not already there
if [ "$APP_DIR" != "$INSTALL_DIR" ]; then
    echo "Copying application to $INSTALL_DIR..."
    mkdir -p /opt
    cp -r "$APP_DIR" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Make scripts executable
chmod +x "$INSTALL_DIR/install/system_setup.sh"
chmod +x "$INSTALL_DIR/install/kiosk_mode.sh"

# Run system hardening
echo ""
echo "=========================================="
echo "Step 1: System Hardening"
echo "=========================================="
"$INSTALL_DIR/install/system_setup.sh"

# Run kiosk mode configuration
echo ""
echo "=========================================="
echo "Step 2: Kiosk Mode Configuration"
echo "=========================================="
"$INSTALL_DIR/install/kiosk_mode.sh"

# Install systemd service
echo ""
echo "=========================================="
echo "Step 3: Installing systemd service"
echo "=========================================="

mkdir -p "$INSTALL_DIR/systemd"

cat > "$INSTALL_DIR/systemd/usb-defender.service" << EOF
[Unit]
Description=USB Defender Kiosk Application
After=graphical.target
Wants=clamav-daemon.service
After=clamav-daemon.service

[Service]
Type=simple
User=usb-kiosk
Group=usb-kiosk
WorkingDirectory=$INSTALL_DIR
Environment="DISPLAY=:0"
Environment="XAUTHORITY=/home/usb-kiosk/.Xauthority"
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/src/main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target
EOF

cp "$INSTALL_DIR/systemd/usb-defender.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable usb-defender.service

echo "Systemd service installed and enabled"

# Create desktop shortcut for admin access
echo ""
echo "Creating desktop shortcut for admin access..."

cat > /usr/share/applications/usb-defender-admin.desktop << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=USB Defender Admin
Comment=USB Defender Kiosk Administration
Exec=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/src/dashboard/dashboard.py
Icon=preferences-system
Terminal=false
Categories=System;Settings;
EOF

# Set proper ownership
chown -R usb-kiosk:usb-kiosk "$INSTALL_DIR"

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Summary:"
echo "--------"
echo "Installation directory: $INSTALL_DIR"
echo "Configuration file: /etc/usb-defender/app_config.yaml"
echo "Log directory: /var/log/usb-defender/"
echo "Transfer directory: /var/usb-defender/transfers/"
echo ""
echo "Kiosk User: usb-kiosk"
echo "Default password: usb-defender-2024"
echo ""
echo "IMPORTANT: Change the default password!"
echo "  sudo passwd usb-kiosk"
echo ""
echo "Next Steps:"
echo "1. Edit configuration: sudo nano /etc/usb-defender/app_config.yaml"
echo "2. Change kiosk user password: sudo passwd usb-kiosk"
echo "3. Change admin dashboard password in config file"
echo "4. Reboot the system: sudo reboot"
echo ""
echo "After reboot:"
echo "- System will auto-login as usb-kiosk"
echo "- USB Defender will start automatically in full-screen"
echo "- Press Ctrl+Shift+D to access admin dashboard"
echo ""
echo "For manual start (testing): $INSTALL_DIR/venv/bin/python $INSTALL_DIR/src/main.py"
echo ""

