#!/bin/bash
# USB Defender Kiosk - Development/Testing Script
# Run the application in development mode (no fullscreen, console logging)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "USB Defender Kiosk - Development Mode"
echo "======================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r install/requirements.txt
else
    source venv/bin/activate
fi

# Create necessary directories for testing
mkdir -p var/log/usb-defender
mkdir -p var/usb-defender/transfers
mkdir -p var/usb-defender/temp
mkdir -p media/usb-defender

echo "Starting application in development mode..."
echo "- No fullscreen"
echo "- Console logging enabled"
echo "- Using local config"
echo ""

# Run application with development flags
PYTHONPATH="$SCRIPT_DIR" python3 src/main.py \
    --config "$SCRIPT_DIR/config/app_config.yaml" \
    --no-fullscreen \
    --debug

echo ""
echo "Application exited"

