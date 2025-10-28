#!/bin/bash
# USB Defender Kiosk - Pre-flight System Check
# Validates system requirements before installation

set -e

echo "=========================================="
echo "USB Defender Kiosk - Pre-flight Check"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# Function to print check result
print_check() {
    local status=$1
    local message=$2
    local detail=$3
    
    if [ "$status" = "PASS" ]; then
        echo -e "${GREEN}✓${NC} $message"
        [ -n "$detail" ] && echo "  $detail"
    elif [ "$status" = "FAIL" ]; then
        echo -e "${RED}✗${NC} $message"
        [ -n "$detail" ] && echo "  $detail"
        ((ERRORS++))
    elif [ "$status" = "WARN" ]; then
        echo -e "${YELLOW}⚠${NC} $message"
        [ -n "$detail" ] && echo "  $detail"
        ((WARNINGS++))
    fi
}

echo "System Requirements Check:"
echo "--------------------------"

# Check 1: Root privileges
if [ "$EUID" -eq 0 ]; then
    print_check "PASS" "Root privileges"
else
    print_check "FAIL" "Root privileges" "This script must be run with sudo"
fi

# Check 2: OS Detection
if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [ "$ID" = "ubuntu" ]; then
        VERSION_NUM=$(echo $VERSION_ID | cut -d. -f1)
        if [ "$VERSION_NUM" -ge 20 ]; then
            print_check "PASS" "Operating System: Ubuntu $VERSION_ID"
        else
            print_check "WARN" "Operating System: Ubuntu $VERSION_ID" "Ubuntu 20.04 or newer recommended"
        fi
    else
        print_check "WARN" "Operating System: $ID $VERSION_ID" "Designed for Ubuntu, may not work correctly"
    fi
else
    print_check "FAIL" "Operating System" "Cannot detect OS version"
fi

# Check 3: System Architecture
ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
    print_check "PASS" "Architecture: $ARCH"
else
    print_check "WARN" "Architecture: $ARCH" "x86_64 recommended, other architectures may have issues"
fi

# Check 4: Memory
TOTAL_MEM=$(free -m | awk '/^Mem:/{print $2}')
if [ "$TOTAL_MEM" -ge 4096 ]; then
    print_check "PASS" "Memory: ${TOTAL_MEM}MB"
elif [ "$TOTAL_MEM" -ge 2048 ]; then
    print_check "WARN" "Memory: ${TOTAL_MEM}MB" "4GB or more recommended for optimal performance"
else
    print_check "FAIL" "Memory: ${TOTAL_MEM}MB" "Minimum 2GB RAM required, 4GB recommended"
fi

# Check 5: Disk Space
AVAILABLE_SPACE=$(df -BM /opt 2>/dev/null | awk 'NR==2 {print $4}' | sed 's/M//')
if [ -z "$AVAILABLE_SPACE" ]; then
    AVAILABLE_SPACE=$(df -BM / | awk 'NR==2 {print $4}' | sed 's/M//')
fi

if [ "$AVAILABLE_SPACE" -ge 20480 ]; then
    print_check "PASS" "Disk Space: ${AVAILABLE_SPACE}MB available"
elif [ "$AVAILABLE_SPACE" -ge 10240 ]; then
    print_check "WARN" "Disk Space: ${AVAILABLE_SPACE}MB available" "20GB or more recommended"
else
    print_check "FAIL" "Disk Space: ${AVAILABLE_SPACE}MB available" "Minimum 10GB required, 20GB recommended"
fi

# Check 6: Python 3
echo ""
echo "Software Dependencies Check:"
echo "----------------------------"

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '(?<=Python )\d+\.\d+')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
        print_check "PASS" "Python: $PYTHON_VERSION"
    else
        print_check "WARN" "Python: $PYTHON_VERSION" "Python 3.8+ recommended"
    fi
else
    print_check "WARN" "Python 3" "Will be installed during setup"
fi

# Check 7: Display Server
if [ -n "$DISPLAY" ] || systemctl is-active --quiet gdm || systemctl is-active --quiet lightdm; then
    print_check "PASS" "Display server detected"
else
    print_check "WARN" "Display server" "No active display server detected - required for kiosk mode"
fi

# Check 8: Internet connectivity (optional for airgapped)
if ping -c 1 -W 2 8.8.8.8 &> /dev/null; then
    print_check "PASS" "Internet connectivity"
else
    print_check "WARN" "Internet connectivity" "Required for initial package downloads (unless airgapped mode)"
fi

# Check 9: Package manager
if command -v apt-get &> /dev/null; then
    print_check "PASS" "Package manager: apt-get"
else
    print_check "FAIL" "Package manager" "apt-get not found - Ubuntu required"
fi

# Check 10: Systemd
if command -v systemctl &> /dev/null; then
    print_check "PASS" "Init system: systemd"
else
    print_check "FAIL" "Init system" "systemd required for service management"
fi

# Check 11: Existing installation
echo ""
echo "Installation Status Check:"
echo "--------------------------"

if [ -d "/opt/usb-defender-kiosk" ]; then
    print_check "WARN" "Existing installation detected at /opt/usb-defender-kiosk" "Will be overwritten during installation"
fi

if id -u usb-kiosk &> /dev/null; then
    print_check "WARN" "Kiosk user 'usb-kiosk' already exists" "Existing user will be used"
fi

if systemctl is-active --quiet usb-defender.service 2>/dev/null; then
    print_check "WARN" "USB Defender service is running" "Will be stopped during installation"
fi

# Check 12: Conflicting services
echo ""
echo "Conflict Check:"
echo "---------------"

if systemctl is-active --quiet usbguard &> /dev/null; then
    print_check "WARN" "USBGuard service detected" "May conflict with USB Defender"
fi

# Summary
echo ""
echo "=========================================="
echo "Pre-flight Check Summary"
echo "=========================================="
echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo "System is ready for USB Defender Kiosk installation."
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ $WARNINGS warning(s) found${NC}"
    echo "Installation can proceed but some features may not work optimally."
    echo ""
    read -p "Continue with installation? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    else
        exit 1
    fi
else
    echo -e "${RED}✗ $ERRORS critical error(s) found${NC}"
    echo -e "${YELLOW}⚠ $WARNINGS warning(s) found${NC}"
    echo ""
    echo "Please fix the errors above before installing."
    exit 1
fi

