#!/bin/bash
# USB Defender Kiosk - Master Installation Script
# This script installs and configures the complete USB Defender Kiosk system

set -e

# Enable logging
LOG_FILE="/var/log/usb-defender-install.log"
mkdir -p "$(dirname "$LOG_FILE")"
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

echo "=========================================="
echo "USB Defender Kiosk - Installation"
echo "=========================================="
echo "Installation started: $(date)"
echo ""
echo "This script will install and configure the USB Defender Kiosk system."
echo "It will:"
echo "  1. Run pre-flight system checks"
echo "  2. Install system dependencies"
echo "  3. Configure USB security (read-only, no autorun)"
echo "  4. Set up ClamAV antivirus"
echo "  5. Create kiosk user account"
echo "  6. Install Python application"
echo "  7. Configure kiosk mode"
echo "  8. Set up systemd services"
echo ""
echo "WARNING: This will modify system security settings."
echo "Only run this on a dedicated kiosk system."
echo ""
echo "Log file: $LOG_FILE"
echo ""

# Parse command line arguments
ASSUME_YES=false
SKIP_PREFLIGHT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -y|--yes|--assume-yes)
            ASSUME_YES=true
            shift
            ;;
        --skip-preflight)
            SKIP_PREFLIGHT=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [-y|--yes] [--skip-preflight]"
            exit 1
            ;;
    esac
done

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script requires root privileges."
    echo "Please run: sudo $0"
    exit 1
fi

# Cleanup function for error handling
cleanup_on_error() {
    echo ""
    echo "=========================================="
    echo "Installation Failed!"
    echo "=========================================="
    echo "An error occurred during installation."
    echo "Check the log file for details: $LOG_FILE"
    echo ""
    echo "To retry installation:"
    echo "  sudo $0"
    echo ""
    exit 1
}

trap cleanup_on_error ERR

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="/opt/usb-defender-kiosk"

# Run pre-flight checks
if [ "$SKIP_PREFLIGHT" = false ]; then
    echo "=========================================="
    echo "Step 0: Pre-flight System Checks"
    echo "=========================================="
    echo ""
    
    # Make preflight script executable
    chmod +x "$SCRIPT_DIR/preflight_check.sh" 2>/dev/null || true
    
    if [ -f "$SCRIPT_DIR/preflight_check.sh" ]; then
        if ! "$SCRIPT_DIR/preflight_check.sh"; then
            echo ""
            echo "Pre-flight checks failed. Installation cannot continue."
            echo "Please resolve the issues above and try again."
            exit 1
        fi
    else
        echo "WARNING: Pre-flight check script not found."
        echo "Continuing without system validation..."
    fi
    echo ""
fi

# Check Ubuntu version
if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [ "$ID" != "ubuntu" ]; then
        echo "WARNING: This script is designed for Ubuntu Desktop."
        echo "Current OS: $ID $VERSION_ID"
        
        if [ "$ASSUME_YES" = false ]; then
            read -t 30 -p "Continue anyway? (y/N): " -n 1 -r || true
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        else
            echo "Continuing in non-interactive mode..."
        fi
    fi
else
    echo "ERROR: Cannot determine OS version"
    exit 1
fi

echo "Installation directory: $INSTALL_DIR"
echo ""

if [ "$ASSUME_YES" = false ]; then
    read -t 30 -p "Press Enter to continue or Ctrl+C to cancel..." || echo ""
fi
echo ""

# Copy application to /opt if not already there
if [ "$APP_DIR" != "$INSTALL_DIR" ]; then
    echo "Copying application to $INSTALL_DIR..."
    
    # Backup existing installation if present
    if [ -d "$INSTALL_DIR" ]; then
        BACKUP_DIR="${INSTALL_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
        echo "Backing up existing installation to $BACKUP_DIR"
        mv "$INSTALL_DIR" "$BACKUP_DIR"
    fi
    
    mkdir -p /opt
    cp -r "$APP_DIR" "$INSTALL_DIR"
    
    if [ ! -d "$INSTALL_DIR" ]; then
        echo "ERROR: Failed to copy application to $INSTALL_DIR"
        exit 1
    fi
    
    cd "$INSTALL_DIR"
else
    cd "$INSTALL_DIR"
fi

# Verify required scripts exist
echo "Verifying installation scripts..."
REQUIRED_SCRIPTS=(
    "$INSTALL_DIR/install/system_setup.sh"
    "$INSTALL_DIR/install/kiosk_mode.sh"
)

for script in "${REQUIRED_SCRIPTS[@]}"; do
    if [ ! -f "$script" ]; then
        echo "ERROR: Required script not found: $script"
        exit 1
    fi
    echo "  ✓ Found: $(basename $script)"
done

# Make scripts executable
chmod +x "$INSTALL_DIR/install/system_setup.sh"
chmod +x "$INSTALL_DIR/install/kiosk_mode.sh"
chmod +x "$INSTALL_DIR/install/preflight_check.sh" 2>/dev/null || true

echo "Scripts verified successfully"
echo ""

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
echo "Installation finished: $(date)"
echo ""
echo "Summary:"
echo "--------"
echo "Installation directory: $INSTALL_DIR"
echo "Configuration file: /etc/usb-defender/app_config.yaml"
echo "Log directory: /var/log/usb-defender/"
echo "Transfer directory: /var/usb-defender/transfers/"
echo "Installation log: $LOG_FILE"
echo ""
echo "Kiosk User: usb-kiosk"
echo ""
echo "⚠ SECURITY NOTICE:"
echo "  A default password has been set for the kiosk user."
echo "  You MUST change it before deploying this system!"
echo ""
echo "Required Security Steps:"
echo "------------------------"
echo "1. Change kiosk user password:"
echo "   sudo passwd usb-kiosk"
echo ""
echo "2. Update admin dashboard credentials:"
echo "   sudo nano /etc/usb-defender/app_config.yaml"
echo "   (Edit the 'admin_password' field)"
echo ""
echo "3. Review and customize configuration:"
echo "   sudo nano /etc/usb-defender/app_config.yaml"
echo ""
echo "4. Reboot the system:"
echo "   sudo reboot"
echo ""
echo "After Reboot:"
echo "-------------"
echo "- System will auto-login as usb-kiosk"
echo "- USB Defender will start automatically in full-screen"
echo "- Press Ctrl+Shift+D to access admin dashboard"
echo ""
echo "Manual Testing (before reboot):"
echo "-------------------------------"
echo "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/src/main.py"
echo ""
echo "Documentation:"
echo "--------------"
echo "- Quick Start: $INSTALL_DIR/QUICKSTART.md"
echo "- Air-gapped Mode: $INSTALL_DIR/AIRGAPPED_MODE.md"
echo "- Development: $INSTALL_DIR/DEVELOPMENT.md"
echo ""

