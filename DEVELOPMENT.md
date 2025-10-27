# USB Defender Kiosk - Development Guide

## Development Setup

### Prerequisites

- Ubuntu Desktop 22.04 or newer (or similar Linux distribution)
- Python 3.11 or newer
- Git

### Quick Start for Development

1. Clone the repository:
```bash
git clone <repository-url>
cd usb-defender-kiosk
```

2. Make the development script executable:
```bash
chmod +x run-dev.sh
```

3. Run in development mode:
```bash
./run-dev.sh
```

The development script will:
- Create a virtual environment if needed
- Install dependencies
- Create necessary directories
- Run the application without fullscreen mode
- Enable console logging for debugging

### Manual Development Setup

If you prefer manual setup:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r install/requirements.txt

# Create directories
mkdir -p var/log/usb-defender
mkdir -p var/usb-defender/transfers
mkdir -p media/usb-defender

# Run application
PYTHONPATH=. python3 src/main.py --config config/app_config.yaml --no-fullscreen --debug
```

## Project Structure

```
usb-defender-kiosk/
├── src/                          # Source code
│   ├── main.py                   # Application entry point
│   ├── ui/                       # User interface
│   │   └── main_window.py        # Main kiosk window
│   ├── usb/                      # USB device handling
│   │   ├── device_monitor.py     # USB detection/mounting
│   │   └── file_browser.py       # File selection UI
│   ├── scanner/                  # File scanning
│   │   ├── clamav_scanner.py     # Antivirus scanning
│   │   └── file_validator.py    # File validation
│   ├── converter/                # Document conversion
│   │   ├── document_to_image.py  # Conversion logic
│   │   └── converter_manager.py  # Conversion coordinator
│   ├── transfer/                 # File transfer
│   │   ├── transfer_manager.py   # Base transfer class
│   │   ├── local_transfer.py     # Local filesystem
│   │   ├── network_transfer.py   # SMB/CIFS shares
│   │   └── cloud_transfer.py     # S3 cloud storage
│   ├── dashboard/                # Admin interface
│   │   ├── dashboard.py          # Dashboard UI
│   │   └── auth.py               # Authentication
│   └── utils/                    # Utilities
│       ├── logger.py             # Logging system
│       └── config.py             # Configuration manager
├── config/                       # Configuration files
│   └── app_config.yaml           # Main configuration
├── install/                      # Installation scripts
│   ├── install.sh                # Master installer
│   ├── system_setup.sh           # System hardening
│   ├── kiosk_mode.sh             # Kiosk configuration
│   ├── requirements.txt          # Python dependencies
│   └── udev_rules/               # USB security rules
├── systemd/                      # Systemd services
│   └── usb-defender.service      # Application service
├── README.md                     # User documentation
├── DEVELOPMENT.md                # This file
└── run-dev.sh                    # Development launcher
```

## Development Workflow

### Testing Without USB Device

For development without a physical USB device:

1. Create a test directory:
```bash
mkdir -p /tmp/test-usb
echo "Test content" > /tmp/test-usb/test.txt
```

2. Modify the code to use this directory for testing (in `src/ui/main_window.py`):
```python
# Temporary: Load test directory instead of USB
test_device = USBDevice("/dev/null", "/sys/devices/test")
test_device.mount_point = Path("/tmp/test-usb")
test_device.label = "Test USB"
test_device.size = "1GB"
self.on_usb_added(test_device)
```

### Testing ClamAV Integration

ClamAV may not be running in development:

1. Check ClamAV status:
```bash
systemctl status clamav-daemon
```

2. If not running, the application will log warnings but continue without virus scanning

3. To install ClamAV for testing:
```bash
sudo apt-get install clamav clamav-daemon
sudo freshclam
sudo systemctl start clamav-daemon
```

### Testing File Conversion

The file conversion requires LibreOffice and ImageMagick:

```bash
# Install conversion tools
sudo apt-get install libreoffice imagemagick

# Test LibreOffice headless conversion
soffice --headless --convert-to pdf test.docx --outdir /tmp/

# Test ImageMagick PDF to image
convert -density 150 test.pdf test.png
```

### Configuration Changes

Edit `config/app_config.yaml` to customize behavior:

- Change transfer method (local/network/cloud)
- Adjust file size limits
- Modify allowed file types
- Configure conversion settings

Changes take effect on next application start.

### Logging

Logs are written to:
- `var/log/usb-defender/app.log` - Application log
- `var/log/usb-defender/audit.log` - Audit trail
- `var/log/usb-defender/transfer.log` - Transfer log
- `var/log/usb-defender/conversion.log` - Conversion log

In development mode (--debug), logs also appear in console.

## Testing

### Unit Testing

Create test files in a `tests/` directory:

```python
# tests/test_file_validator.py
import unittest
from pathlib import Path
from src.scanner.file_validator import FileValidator

class TestFileValidator(unittest.TestCase):
    def setUp(self):
        self.config = {
            'max_size_mb': 100,
            'allowed_extensions': ['txt', 'pdf'],
            'blocked_extensions': ['exe']
        }
        self.validator = FileValidator(self.config)
    
    def test_validate_allowed_extension(self):
        # Test implementation
        pass
```

Run tests:
```bash
python -m unittest discover tests/
```

### Integration Testing

Test the full workflow:

1. Insert USB device (or use test directory)
2. Select files
3. Start transfer
4. Verify files are:
   - Validated correctly
   - Scanned (if ClamAV available)
   - Converted to images
   - Transferred to destination

### Performance Testing

Test with large files and many files:

```bash
# Create test files
for i in {1..100}; do
    dd if=/dev/urandom of=/tmp/test-usb/file$i.bin bs=1M count=10
done
```

## Debugging

### Enable Debug Logging

Run with debug flag:
```bash
python3 src/main.py --debug
```

### Common Issues

**Issue: USB device not detected**
- Check udev rules are loaded: `sudo udevadm control --reload-rules`
- Monitor udev events: `udevadm monitor`
- Check USB is recognized: `lsusb` and `dmesg | grep usb`

**Issue: Files not converting**
- Check LibreOffice: `soffice --version`
- Check ImageMagick: `convert -version`
- Check conversion logs: `cat var/log/usb-defender/conversion.log`

**Issue: ClamAV not working**
- Check daemon: `systemctl status clamav-daemon`
- Check socket: `ls -l /var/run/clamav/clamd.ctl`
- Test connection: `clamdscan --version`

**Issue: Permission denied errors**
- In development, you may need to run with sudo for USB mounting
- Or add your user to plugdev group: `sudo usermod -a -G plugdev $USER`

## Code Style

Follow PEP 8 Python style guidelines:

```bash
# Install style checkers
pip install flake8 black

# Check code style
flake8 src/

# Auto-format code
black src/
```

## Security Considerations

### Development vs Production

**Never in production:**
- Debug mode enabled
- Default passwords
- Permissive file permissions
- Disabled security features

**Development testing:**
- Test with malicious files (in isolated VM)
- Test file type validation
- Test conversion edge cases
- Test transfer failures

### Test Files

Create test files for validation:

```bash
# Suspicious file (executable with .txt extension)
cp /bin/ls test-files/fake.txt

# Large file
dd if=/dev/zero of=test-files/large.bin bs=1M count=500

# Infected test file (use EICAR test file)
echo 'X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*' > test-files/eicar.txt
```

## Deployment

### From Development to Production

1. Test thoroughly in development
2. Run full installation on production system:
```bash
sudo ./install/install.sh
```

3. Configure production settings in `/etc/usb-defender/app_config.yaml`

4. Change default passwords:
```bash
sudo passwd usb-kiosk
# Edit /etc/usb-defender/app_config.yaml dashboard password
```

5. Reboot system

### Updates

To update an existing installation:

```bash
# Stop service
sudo systemctl stop usb-defender

# Backup configuration
sudo cp /etc/usb-defender/app_config.yaml /etc/usb-defender/app_config.yaml.bak

# Update code
cd /opt/usb-defender-kiosk
sudo git pull

# Update dependencies
sudo /opt/usb-defender-kiosk/venv/bin/pip install -r install/requirements.txt

# Restore configuration if needed
# sudo cp /etc/usb-defender/app_config.yaml.bak /etc/usb-defender/app_config.yaml

# Restart service
sudo systemctl start usb-defender
```

## Contributing

### Adding New Features

1. Create feature branch
2. Implement feature with tests
3. Update documentation
4. Test in development mode
5. Test on fresh Ubuntu installation
6. Submit pull request

### Code Review Checklist

- [ ] Code follows PEP 8 style
- [ ] New features have tests
- [ ] Documentation updated
- [ ] No hardcoded credentials
- [ ] Error handling implemented
- [ ] Logging added
- [ ] Security implications considered

## Support

For issues or questions:
- Check logs in `var/log/usb-defender/`
- Review this guide
- Check README.md for user documentation
- Contact system administrator

