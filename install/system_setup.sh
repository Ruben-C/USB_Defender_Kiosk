#!/bin/bash
# USB Defender Kiosk - System Hardening Script
# This script configures Ubuntu Desktop for secure USB handling

set -e  # Exit on error

echo "=========================================="
echo "USB Defender Kiosk - System Hardening"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

# Update system
echo "[1/10] Updating system packages..."
apt-get update
apt-get upgrade -y

# Install system dependencies
echo "[2/10] Installing system dependencies..."

# Detect Python version
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '(?<=Python )\d+\.\d+')
echo "Detected Python version: $PYTHON_VERSION"

apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    clamav \
    clamav-daemon \
    clamav-freshclam \
    libreoffice \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    imagemagick \
    udev \
    udisks2 \
    libmagic1 \
    libmagic-dev \
    samba-common \
    cifs-utils \
    dbus-x11 \
    build-essential

# Stop ClamAV services for configuration
echo "[3/10] Configuring ClamAV..."
systemctl stop clamav-freshclam || true
systemctl stop clamav-daemon || true

# Update ClamAV virus definitions
echo "Updating virus definitions (this may take a few minutes)..."
freshclam || true

# Configure ClamAV daemon
cat > /etc/clamav/clamd.conf << 'EOF'
LocalSocket /var/run/clamav/clamd.ctl
FixStaleSocket true
LocalSocketGroup clamav
LocalSocketMode 666
User clamav
ScanMail true
ScanArchive true
ArchiveBlockEncrypted false
MaxDirectoryRecursion 15
FollowDirectorySymlinks false
FollowFileSymlinks false
ReadTimeout 180
MaxThreads 12
MaxConnectionQueueLength 15
LogSyslog false
LogFacility LOG_LOCAL6
LogClean false
LogVerbose false
PreludeEnable no
PreludeAnalyzerName ClamAV
DatabaseDirectory /var/lib/clamav
OfficialDatabaseOnly false
SelfCheck 3600
Foreground false
Debug false
ScanPE true
MaxEmbeddedPE 10M
ScanOLE2 true
ScanPDF true
ScanHTML true
MaxHTMLNormalize 10M
MaxHTMLNoTags 2M
MaxScriptNormalize 5M
MaxZipTypeRcg 1M
ScanSWF true
ExitOnOOM false
LeaveTemporaryFiles false
AlgorithmicDetection true
ScanELF true
IdleTimeout 30
CrossFilesystems true
PhishingSignatures true
PhishingScanURLs true
PhishingAlwaysBlockSSLMismatch false
PhishingAlwaysBlockCloak false
PartitionIntersection false
DetectPUA false
ScanPartialMessages false
HeuristicScanPrecedence false
StructuredDataDetection false
CommandReadTimeout 30
SendBufTimeout 200
MaxQueue 100
ExtendedDetectionInfo true
OLE2BlockMacros false
ScanOnAccess false
AllowAllMatchScan true
ForceToDisk false
DisableCertCheck false
DisableCache false
MaxScanTime 120000
MaxScanSize 100M
MaxFileSize 25M
MaxRecursion 16
MaxFiles 10000
MaxPartitions 50
MaxIconsPE 100
PCREMatchLimit 10000
PCRERecMatchLimit 5000
PCREMaxFileSize 25M
ScanXMLDOCS true
ScanHWP3 true
MaxRecHWP3 16
StreamMaxLength 25M
LogFile /var/log/clamav/clamav.log
LogTime true
LogFileUnlock false
LogFileMaxSize 0
Bytecode true
BytecodeSecurity TrustSigned
BytecodeTimeout 60000
OnAccessMaxFileSize 5M
EOF

# Start ClamAV services
systemctl start clamav-daemon
systemctl enable clamav-daemon
systemctl start clamav-freshclam
systemctl enable clamav-freshclam

# Configure udev rules for USB read-only
echo "[4/10] Installing USB read-only udev rules..."
cp /opt/usb-defender-kiosk/install/udev_rules/99-usb-readonly.rules /etc/udev/rules.d/
udevadm control --reload-rules
udevadm trigger

# Disable USB automount via udisks2
echo "[5/10] Disabling USB automount..."
mkdir -p /etc/udisks2
cat > /etc/udisks2/mount_options.conf << 'EOF'
[defaults]
# Default mount options for all devices
defaults=ro,noexec,nodev,nosuid

[/dev/sd*]
# Force read-only for all SCSI/SATA/USB devices
ro,noexec,nodev,nosuid
EOF

# Disable automount in GNOME (if present)
if [ -d /usr/share/glib-2.0/schemas ]; then
    cat > /usr/share/glib-2.0/schemas/99-usb-defender.gschema.override << 'EOF'
[org.gnome.desktop.media-handling]
automount=false
automount-open=false
autorun-never=true
EOF
    glib-compile-schemas /usr/share/glib-2.0/schemas/ || true
fi

# Create kiosk user
echo "[6/10] Creating kiosk user account..."
if ! id -u usb-kiosk > /dev/null 2>&1; then
    useradd -m -s /bin/bash -G plugdev usb-kiosk
    echo "usb-kiosk:usb-defender-2024" | chpasswd
    echo "Kiosk user created with default password"
else
    echo "Kiosk user already exists"
fi

# Create necessary directories
echo "[7/10] Creating application directories..."
mkdir -p /etc/usb-defender
mkdir -p /var/log/usb-defender
mkdir -p /var/usb-defender/transfers
mkdir -p /var/usb-defender/temp
mkdir -p /media/usb-defender

# Set permissions
chown -R usb-kiosk:usb-kiosk /var/log/usb-defender
chown -R usb-kiosk:usb-kiosk /var/usb-defender
chown -R usb-kiosk:usb-kiosk /media/usb-defender
chmod 755 /var/log/usb-defender
chmod 755 /var/usb-defender
chmod 755 /media/usb-defender

# Copy configuration
echo "[8/10] Installing configuration..."
if [ ! -f /etc/usb-defender/app_config.yaml ]; then
    cp /opt/usb-defender-kiosk/config/app_config.yaml /etc/usb-defender/
    chown usb-kiosk:usb-kiosk /etc/usb-defender/app_config.yaml
    chmod 640 /etc/usb-defender/app_config.yaml
fi

# Configure AppArmor profile (basic)
echo "[9/10] Configuring AppArmor..."
if command -v aa-status > /dev/null 2>&1; then
    cat > /etc/apparmor.d/usr.bin.usb-defender << 'EOF'
#include <tunables/global>

/usr/bin/python3* {
  #include <abstractions/base>
  #include <abstractions/python>
  
  # Allow reading USB devices
  /sys/devices/** r,
  /dev/sd* r,
  /media/usb-defender/** r,
  
  # Allow application directories
  /opt/usb-defender-kiosk/** r,
  /var/usb-defender/** rw,
  /var/log/usb-defender/** w,
  /etc/usb-defender/** r,
  
  # Deny network except for specific services
  deny network inet,
  deny network inet6,
}
EOF
    # Note: This is a basic profile. In production, refine further.
fi

# Set up Python virtual environment
echo "[10/10] Setting up Python environment..."
if [ ! -d /opt/usb-defender-kiosk/venv ]; then
    python3 -m venv /opt/usb-defender-kiosk/venv
    /opt/usb-defender-kiosk/venv/bin/pip install --upgrade pip
    /opt/usb-defender-kiosk/venv/bin/pip install -r /opt/usb-defender-kiosk/install/requirements.txt
fi

echo ""
echo "=========================================="
echo "System hardening completed successfully!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Run ./install/kiosk_mode.sh to configure kiosk mode"
echo "2. Reboot the system"
echo ""

