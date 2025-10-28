#!/bin/bash
# USB Defender Kiosk - Kiosk Mode Configuration
# This script configures Ubuntu Desktop to run in kiosk mode

set -e

echo "=========================================="
echo "USB Defender Kiosk - Kiosk Mode Setup"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

KIOSK_USER="usb-kiosk"
APP_PATH="/opt/usb-defender-kiosk"

# Verify kiosk user exists
if ! id -u $KIOSK_USER > /dev/null 2>&1; then
    echo "ERROR: Kiosk user '$KIOSK_USER' does not exist. Run system_setup.sh first."
    exit 1
fi

# Verify application exists
if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: Application directory not found: $APP_PATH"
    exit 1
fi

# Verify venv exists
if [ ! -f "$APP_PATH/venv/bin/python" ]; then
    echo "ERROR: Python virtual environment not found at $APP_PATH/venv"
    echo "Please run system_setup.sh first."
    exit 1
fi

echo "Kiosk user: $KIOSK_USER"
echo "Application path: $APP_PATH"
echo ""

echo "[1/8] Configuring auto-login..."

# Configure LightDM for auto-login (Ubuntu default display manager)
if [ -f /etc/lightdm/lightdm.conf ]; then
    # Backup original config
    cp /etc/lightdm/lightdm.conf /etc/lightdm/lightdm.conf.backup
fi

cat > /etc/lightdm/lightdm.conf << EOF
[Seat:*]
autologin-user=$KIOSK_USER
autologin-user-timeout=0
user-session=ubuntu
greeter-show-manual-login=false
greeter-hide-users=true
allow-guest=false
EOF

# Configure GDM3 if present (alternative display manager)
if [ -f /etc/gdm3/custom.conf ]; then
    cat > /etc/gdm3/custom.conf << EOF
[daemon]
AutomaticLoginEnable=true
AutomaticLogin=$KIOSK_USER
EOF
fi

echo "[2/8] Creating kiosk autostart configuration..."

# Create .config directories for kiosk user
sudo -u $KIOSK_USER mkdir -p /home/$KIOSK_USER/.config/autostart
sudo -u $KIOSK_USER mkdir -p /home/$KIOSK_USER/.config/openbox

# Create autostart desktop entry
cat > /home/$KIOSK_USER/.config/autostart/usb-defender.desktop << EOF
[Desktop Entry]
Type=Application
Name=USB Defender Kiosk
Exec=$APP_PATH/venv/bin/python $APP_PATH/src/main.py
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Terminal=false
EOF

chown $KIOSK_USER:$KIOSK_USER /home/$KIOSK_USER/.config/autostart/usb-defender.desktop

echo "[3/8] Disabling screen saver and power management..."

# Function to apply gsettings with feedback
apply_gsetting() {
    local schema=$1
    local key=$2
    local value=$3
    
    if sudo -u $KIOSK_USER dbus-launch gsettings set "$schema" "$key" "$value" 2>/dev/null; then
        echo "  ✓ $schema.$key"
        return 0
    else
        echo "  ⊗ $schema.$key (not available - may not apply to this desktop environment)"
        return 1
    fi
}

# Disable screen blanking and power management for kiosk user
apply_gsetting org.gnome.desktop.screensaver idle-activation-enabled false
apply_gsetting org.gnome.desktop.screensaver lock-enabled false
apply_gsetting org.gnome.desktop.session idle-delay 0
apply_gsetting org.gnome.settings-daemon.plugins.power idle-dim false
apply_gsetting org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'
apply_gsetting org.gnome.settings-daemon.plugins.power sleep-inactive-battery-type 'nothing'

echo ""
echo "[4/8] Hiding GNOME panels and desktop..."

# Hide top panel and dock
apply_gsetting org.gnome.shell enabled-extensions "[]"
apply_gsetting org.gnome.desktop.background show-desktop-icons false

# Disable Ubuntu dock
apply_gsetting org.gnome.shell.extensions.dash-to-dock autohide false
apply_gsetting org.gnome.shell.extensions.dash-to-dock dock-fixed false
apply_gsetting org.gnome.shell.extensions.dash-to-dock intellihide false

echo ""
echo "[5/8] Disabling keyboard shortcuts..."

# Disable common keyboard shortcuts that could exit kiosk mode
apply_gsetting org.gnome.desktop.wm.keybindings close "[]"
apply_gsetting org.gnome.desktop.wm.keybindings minimize "[]"
apply_gsetting org.gnome.desktop.wm.keybindings maximize "[]"
apply_gsetting org.gnome.desktop.wm.keybindings toggle-fullscreen "[]"
apply_gsetting org.gnome.settings-daemon.plugins.media-keys logout "[]"
apply_gsetting org.gnome.settings-daemon.plugins.media-keys screensaver "[]"

echo ""

echo "[6/8] Configuring window manager..."

# Create custom Openbox config (if using Openbox)
cat > /home/$KIOSK_USER/.config/openbox/rc.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <applications>
    <application name="usb-defender-kiosk">
      <decor>no</decor>
      <fullscreen>yes</fullscreen>
      <maximized>yes</maximized>
      <focus>yes</focus>
    </application>
  </applications>
  <keyboard>
    <!-- Disable Alt+F4 -->
    <keybind key="A-F4">
      <action name="Execute">
        <execute>true</execute>
      </action>
    </keybind>
  </keyboard>
</openbox_config>
EOF

chown $KIOSK_USER:$KIOSK_USER /home/$KIOSK_USER/.config/openbox/rc.xml

echo "[7/8] Restricting kiosk user permissions..."

# Add kiosk user to necessary groups
usermod -a -G plugdev,video,audio $KIOSK_USER
echo "  ✓ Added to groups: plugdev, video, audio"

# Create sudoers file for limited sudo access (for mounting only)
# More restrictive - specific mount options and paths only
cat > /etc/sudoers.d/usb-kiosk << 'EOF'
# USB Defender Kiosk - Limited sudo permissions for USB mounting
# Allow kiosk user to mount/unmount USB devices with strict options

# Mount USB devices as read-only with security options
# Only allows mounting /dev/sd[a-z][0-9] to /media/usb-defender/*
usb-kiosk ALL=(ALL) NOPASSWD: /usr/bin/mount -o ro\,noexec\,nodev\,nosuid /dev/sd[a-z][0-9] /media/usb-defender/*
usb-kiosk ALL=(ALL) NOPASSWD: /usr/bin/mount -o ro\,noexec\,nodev\,nosuid /dev/sd[a-z][0-9][0-9] /media/usb-defender/*

# Unmount from usb-defender directory only
usb-kiosk ALL=(ALL) NOPASSWD: /usr/bin/umount /media/usb-defender/*

# Allow udisksctl for device management (more restrictive)
usb-kiosk ALL=(ALL) NOPASSWD: /usr/bin/udisksctl mount --block-device /dev/sd[a-z][0-9]*
usb-kiosk ALL=(ALL) NOPASSWD: /usr/bin/udisksctl unmount --block-device /dev/sd[a-z][0-9]*
usb-kiosk ALL=(ALL) NOPASSWD: /usr/bin/udisksctl power-off --block-device /dev/sd[a-z][0-9]*
EOF

chmod 440 /etc/sudoers.d/usb-kiosk

# Validate sudoers file
if visudo -c -f /etc/sudoers.d/usb-kiosk > /dev/null 2>&1; then
    echo "  ✓ Sudoers configuration validated"
else
    echo "  ✗ ERROR: Sudoers configuration has errors"
    rm /etc/sudoers.d/usb-kiosk
    exit 1
fi

echo "[8/8] Creating session management scripts..."

# Create improved watchdog script with locking and restart limits
cat > /usr/local/bin/usb-defender-watchdog << 'WATCHDOG_EOF'
#!/bin/bash
# USB Defender Kiosk Watchdog
# Monitors and restarts the application if it crashes
# Includes restart limiting to prevent infinite restart loops

LOCK_FILE="/var/run/usb-defender-watchdog.pid"
LOG_FILE="/var/log/usb-defender/watchdog.log"
APP_PATH="/opt/usb-defender-kiosk"
KIOSK_USER="usb-kiosk"
MAX_RESTARTS=5
RESTART_WINDOW=300  # 5 minutes
CHECK_INTERVAL=10

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Create PID file to prevent multiple instances
if [ -f "$LOCK_FILE" ]; then
    OLD_PID=$(cat "$LOCK_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Watchdog already running (PID: $OLD_PID)"
        exit 1
    fi
fi
echo $$ > "$LOCK_FILE"

# Cleanup on exit
cleanup() {
    rm -f "$LOCK_FILE"
    exit 0
}
trap cleanup EXIT INT TERM

# Track restart attempts
declare -a RESTART_TIMES=()

log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

can_restart() {
    local current_time=$(date +%s)
    local cutoff_time=$((current_time - RESTART_WINDOW))
    
    # Remove old restart times
    local new_times=()
    for time in "${RESTART_TIMES[@]}"; do
        if [ "$time" -gt "$cutoff_time" ]; then
            new_times+=("$time")
        fi
    done
    RESTART_TIMES=("${new_times[@]}")
    
    # Check if we're under the limit
    if [ ${#RESTART_TIMES[@]} -ge $MAX_RESTARTS ]; then
        return 1
    fi
    return 0
}

log_message "Watchdog started (PID: $$)"

while true; do
    sleep $CHECK_INTERVAL
    
    # Check if the main application is running
    if ! pgrep -f "$APP_PATH/venv/bin/python.*main.py" > /dev/null; then
        if can_restart; then
            log_message "Application not running, attempting restart..."
            RESTART_TIMES+=($(date +%s))
            
            # Restart the application
            sudo -u $KIOSK_USER DISPLAY=:0 XAUTHORITY=/home/$KIOSK_USER/.Xauthority \
                $APP_PATH/venv/bin/python $APP_PATH/src/main.py >> "$LOG_FILE" 2>&1 &
            
            sleep 3
            
            # Verify it started
            if pgrep -f "$APP_PATH/venv/bin/python.*main.py" > /dev/null; then
                log_message "Application restarted successfully"
            else
                log_message "ERROR: Failed to restart application"
            fi
        else
            log_message "ERROR: Maximum restart limit reached ($MAX_RESTARTS in $RESTART_WINDOW seconds)"
            log_message "Manual intervention required. Watchdog will continue monitoring."
            # Clear restart times and wait longer before next attempt
            RESTART_TIMES=()
            sleep 60
        fi
    fi
done
WATCHDOG_EOF

chmod +x /usr/local/bin/usb-defender-watchdog
echo "  ✓ Watchdog script created"

# Create systemd service for watchdog
cat > /etc/systemd/system/usb-defender-watchdog.service << EOF
[Unit]
Description=USB Defender Kiosk Watchdog
After=graphical.target
After=usb-defender.service

[Service]
Type=simple
ExecStart=/usr/local/bin/usb-defender-watchdog
Restart=always
RestartSec=10
StandardOutput=append:/var/log/usb-defender/watchdog.log
StandardError=append:/var/log/usb-defender/watchdog.log

[Install]
WantedBy=graphical.target
EOF

systemctl daemon-reload
systemctl enable usb-defender-watchdog.service
echo "  ✓ Watchdog service enabled"

echo ""
echo "=========================================="
echo "Kiosk mode configuration completed!"
echo "=========================================="
echo ""
echo "Configuration summary:"
echo "- Auto-login: $KIOSK_USER"
echo "- Application: $APP_PATH/src/main.py"
echo "- Watchdog: Enabled"
echo ""
echo "Please reboot the system to activate kiosk mode:"
echo "  sudo reboot"
echo ""

