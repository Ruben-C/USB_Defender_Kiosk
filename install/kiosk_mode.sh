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

# Disable screen blanking and power management for kiosk user
sudo -u $KIOSK_USER dbus-launch gsettings set org.gnome.desktop.screensaver idle-activation-enabled false 2>/dev/null || true
sudo -u $KIOSK_USER dbus-launch gsettings set org.gnome.desktop.screensaver lock-enabled false 2>/dev/null || true
sudo -u $KIOSK_USER dbus-launch gsettings set org.gnome.desktop.session idle-delay 0 2>/dev/null || true
sudo -u $KIOSK_USER dbus-launch gsettings set org.gnome.settings-daemon.plugins.power idle-dim false 2>/dev/null || true
sudo -u $KIOSK_USER dbus-launch gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing' 2>/dev/null || true
sudo -u $KIOSK_USER dbus-launch gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-battery-type 'nothing' 2>/dev/null || true

echo "[4/8] Hiding GNOME panels and desktop..."

# Hide top panel and dock
sudo -u $KIOSK_USER dbus-launch gsettings set org.gnome.shell enabled-extensions "[]" 2>/dev/null || true
sudo -u $KIOSK_USER dbus-launch gsettings set org.gnome.desktop.background show-desktop-icons false 2>/dev/null || true

# Disable Ubuntu dock
sudo -u $KIOSK_USER dbus-launch gsettings set org.gnome.shell.extensions.dash-to-dock autohide false 2>/dev/null || true
sudo -u $KIOSK_USER dbus-launch gsettings set org.gnome.shell.extensions.dash-to-dock dock-fixed false 2>/dev/null || true
sudo -u $KIOSK_USER dbus-launch gsettings set org.gnome.shell.extensions.dash-to-dock intellihide false 2>/dev/null || true

echo "[5/8] Disabling keyboard shortcuts..."

# Disable common keyboard shortcuts that could exit kiosk mode
sudo -u $KIOSK_USER dbus-launch gsettings set org.gnome.desktop.wm.keybindings close "[]" 2>/dev/null || true
sudo -u $KIOSK_USER dbus-launch gsettings set org.gnome.desktop.wm.keybindings minimize "[]" 2>/dev/null || true
sudo -u $KIOSK_USER dbus-launch gsettings set org.gnome.desktop.wm.keybindings maximize "[]" 2>/dev/null || true
sudo -u $KIOSK_USER dbus-launch gsettings set org.gnome.desktop.wm.keybindings toggle-fullscreen "[]" 2>/dev/null || true
sudo -u $KIOSK_USER dbus-launch gsettings set org.gnome.settings-daemon.plugins.media-keys logout "[]" 2>/dev/null || true
sudo -u $KIOSK_USER dbus-launch gsettings set org.gnome.settings-daemon.plugins.media-keys screensaver "[]" 2>/dev/null || true

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

# Create sudoers file for limited sudo access (for mounting only)
cat > /etc/sudoers.d/usb-kiosk << 'EOF'
# Allow kiosk user to mount/unmount USB devices only
usb-kiosk ALL=(ALL) NOPASSWD: /usr/bin/mount -o ro\,noexec\,nodev\,nosuid /dev/sd* /media/usb-defender/*
usb-kiosk ALL=(ALL) NOPASSWD: /usr/bin/umount /media/usb-defender/*
usb-kiosk ALL=(ALL) NOPASSWD: /usr/bin/udisksctl mount *
usb-kiosk ALL=(ALL) NOPASSWD: /usr/bin/udisksctl unmount *
EOF

chmod 440 /etc/sudoers.d/usb-kiosk

echo "[8/8] Creating session management scripts..."

# Create script to reset kiosk session if it crashes
cat > /usr/local/bin/usb-defender-watchdog << EOF
#!/bin/bash
# Watchdog script to restart the application if it crashes

while true; do
    sleep 10
    if ! pgrep -f "python.*main.py" > /dev/null; then
        echo "\$(date): USB Defender crashed, restarting..." >> /var/log/usb-defender/watchdog.log
        sudo -u $KIOSK_USER DISPLAY=:0 $APP_PATH/venv/bin/python $APP_PATH/src/main.py &
    fi
done
EOF

chmod +x /usr/local/bin/usb-defender-watchdog

# Create systemd service for watchdog
cat > /etc/systemd/system/usb-defender-watchdog.service << EOF
[Unit]
Description=USB Defender Kiosk Watchdog
After=graphical.target

[Service]
Type=simple
ExecStart=/usr/local/bin/usb-defender-watchdog
Restart=always
RestartSec=10

[Install]
WantedBy=graphical.target
EOF

systemctl daemon-reload
systemctl enable usb-defender-watchdog.service

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

