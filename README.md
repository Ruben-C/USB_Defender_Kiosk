# USB Defender Kiosk

A secure Linux kiosk application for safely receiving and sanitizing files from untrusted USB devices.

## Overview

USB Defender Kiosk provides a simple, user-friendly interface for non-technical users to transfer files from USB drives while protecting against malware and malicious content. The system:

- Mounts all USB devices as read-only (never modifies customer data)
- Scans files with ClamAV antivirus
- Converts documents to images to remove potential threats
- Transfers sanitized files to configured destinations
- Runs in full-screen kiosk mode with restricted system access

## Features

- **Read-Only USB Access**: All USB devices are automatically mounted read-only
- **Selective File Transfer**: Users select only the files they need, not entire drives
- **Antivirus Scanning**: ClamAV integration for malware detection
- **Document Sanitization**: Converts documents (PDF, DOC, XLS, PPT) to PNG/JPEG images
- **Flexible Output**: Supports local directory, network shares, or cloud storage
- **Audit Logging**: Complete audit trail of all operations
- **Support Dashboard**: Admin interface for monitoring and maintenance
- **Kiosk Mode**: Full-screen, locked-down interface

## Requirements

- Ubuntu Desktop 20.04 LTS or newer (fresh installation recommended)
- Minimum 4GB RAM
- 20GB free disk space
- Python 3.8 or newer (automatically detected)
- Internet connection for initial setup and ClamAV updates

## Installation

### Fresh Ubuntu Desktop Installation

1. Clone this repository:
```bash
cd ~
git clone <repository-url> usb-defender-kiosk
cd usb-defender-kiosk
```

2. Run the installation script with sudo:
```bash
sudo ./install/install.sh
```

The installation script will:
- Install system dependencies
- Configure USB security (read-only, no autorun)
- Set up ClamAV with automatic updates
- Create a restricted kiosk user account
- Install Python dependencies
- Configure kiosk mode
- Set up systemd service for auto-start

3. Reboot the system:
```bash
sudo reboot
```

After reboot, the system will automatically log in as the kiosk user and launch the USB Defender application in full-screen mode.

## Configuration

Edit `/etc/usb-defender/app_config.yaml` to configure:

### Transfer Method

```yaml
transfer:
  method: local  # Options: local, network, cloud
  
  # Local transfer settings
  local:
    output_directory: /var/usb-defender/transfers
  
  # Network share settings
  network:
    server: "//server.local/share"
    username: "transfer_user"
    password: "encrypted_password"
    domain: "WORKGROUP"
  
  # Cloud storage settings
  cloud:
    type: s3  # S3-compatible storage
    endpoint: "https://s3.amazonaws.com"
    bucket: "usb-transfers"
    access_key: "your_access_key"
    secret_key: "your_secret_key"
```

### File Limits and Types

```yaml
files:
  max_size_mb: 100
  allowed_extensions:
    - pdf
    - doc
    - docx
    - xls
    - xlsx
    - ppt
    - pptx
    - jpg
    - jpeg
    - png
    - gif
    - txt
```

### ClamAV Settings

```yaml
clamav:
  socket: /var/run/clamav/clamd.ctl
  timeout: 300
  update_on_startup: true
```

## Usage

### For End Users

1. **Insert USB Drive**: Plug in the USB device. The system will detect it automatically.

2. **Browse Files**: Use the file browser to navigate and select the files you need.

3. **Start Transfer**: Click the "Transfer Files" button.

4. **Wait for Processing**: The system will:
   - Scan files for malware
   - Convert documents to images
   - Transfer sanitized files

5. **Remove USB**: When complete, safely remove your USB drive.

### For Support Staff

Access the admin dashboard:
1. Press `Ctrl+Shift+D` while the kiosk is running
2. Enter the admin password
3. Access logs, statistics, and system health

## Security Features

### System Hardening

- USB devices forced to read-only mode via udev rules
- Automount disabled for USB storage
- Execution permissions blocked on USB mount points
- AppArmor profiles for USB access control
- Kiosk user runs with minimal permissions

### Application Security

- All file operations are read-only on source USB
- ClamAV scans before processing
- File type validation using magic numbers
- Document conversion strips embedded content
- Audit logging of all operations

### Kiosk Lockdown

- Full-screen mode with no window decorations
- Keyboard shortcuts disabled (Alt+F4, Ctrl+Alt+T, etc.)
- System panels and desktop hidden
- Auto-login with restricted user
- Application auto-starts on boot

## Troubleshooting

### USB Device Not Detected

- Check `dmesg | grep usb` to verify USB is recognized
- Ensure udisks2 is running: `systemctl status udisks2`
- Check logs: `sudo tail -f /var/log/usb-defender/app.log`

### ClamAV Not Scanning

- Verify ClamAV is running: `systemctl status clamav-daemon`
- Update signatures: `sudo freshclam`
- Check socket exists: `ls -l /var/run/clamav/clamd.ctl`

### Files Not Converting

- Check LibreOffice is installed: `which soffice`
- Verify ImageMagick: `which convert`
- Check conversion logs in `/var/log/usb-defender/conversion.log`

### Transfer Failures

**Local Transfer:**
- Verify directory exists: `ls -la /var/usb-defender/transfers`
- Check permissions: `sudo chown -R usb-kiosk:usb-kiosk /var/usb-defender/transfers`

**Network Share:**
- Test connection: `smbclient //server/share -U username`
- Verify credentials in config file

**Cloud Storage:**
- Test credentials with AWS CLI
- Verify bucket permissions

### Exit Kiosk Mode

To exit kiosk mode for maintenance:
1. Press `Ctrl+Shift+D` and enter admin password
2. Click "Exit Kiosk Mode"
3. Or switch to TTY: `Ctrl+Alt+F2`

## File Structure

```
usb-defender-kiosk/
├── src/
│   ├── main.py                    # Application entry point
│   ├── ui/
│   │   ├── main_window.py         # Main kiosk interface
│   │   └── styles.py              # UI styling
│   ├── usb/
│   │   ├── device_monitor.py      # USB detection and mounting
│   │   └── file_browser.py        # File selection UI
│   ├── scanner/
│   │   ├── clamav_scanner.py      # Antivirus integration
│   │   └── file_validator.py     # File type validation
│   ├── converter/
│   │   ├── document_to_image.py   # Document conversion
│   │   └── converter_manager.py   # Conversion coordinator
│   ├── transfer/
│   │   ├── transfer_manager.py    # Abstract transfer interface
│   │   ├── local_transfer.py      # Local filesystem transfer
│   │   ├── network_transfer.py    # SMB/CIFS transfer
│   │   └── cloud_transfer.py      # S3 cloud transfer
│   ├── dashboard/
│   │   ├── dashboard.py           # Admin interface
│   │   └── auth.py                # Authentication
│   └── utils/
│       ├── logger.py              # Logging utilities
│       └── config.py              # Configuration management
├── install/
│   ├── install.sh                 # Master installation script
│   ├── system_setup.sh            # System hardening
│   ├── kiosk_mode.sh              # Kiosk configuration
│   ├── requirements.txt           # Python dependencies
│   └── udev_rules/
│       └── 99-usb-readonly.rules  # USB read-only rules
├── config/
│   └── app_config.yaml            # Application configuration
├── systemd/
│   └── usb-defender.service       # Systemd service
└── README.md
```

## License

[Specify your license here]

## Support

For issues or questions, contact your system administrator.

