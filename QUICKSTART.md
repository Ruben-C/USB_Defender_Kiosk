# USB Defender Kiosk - Quick Start Guide

## For End Users

### Using the Kiosk

1. **Insert your USB drive** into the kiosk computer
   - Wait for the device to be detected (a few seconds)

2. **Select the files you need**
   - Navigate through folders if needed
   - Check the boxes next to files you want to transfer
   - You can select individual files - no need to transfer everything

3. **Click "Transfer Selected Files"**
   - The system will:
     - Check files for viruses
     - Convert documents to safe image format
     - Transfer to secure location
   - This may take several minutes depending on file size

4. **Wait for completion**
   - DO NOT remove your USB drive while processing
   - You'll see a success or error message when done

5. **Remove your USB drive**
   - Click "Done" when you see the completion message
   - Your USB drive is safe to remove
   - All files on your USB remain unchanged

### Important Notes

- **Your files are never deleted or modified** - the kiosk only reads from your USB
- **Infected files are skipped** - if malware is detected, those files won't be transferred
- **Documents become images** - Word, PDF, Excel files are converted to PNG/JPEG for security
- **Maximum file size** - Check with staff for current limits (typically 100MB per file)

### What File Types Are Supported?

Supported:
- Documents: PDF, Word (DOC/DOCX), Excel (XLS/XLSX), PowerPoint (PPT/PPTX)
- Images: JPG, PNG, GIF, BMP, TIFF
- Text: TXT, RTF

Not Allowed:
- Executable files (.exe, .bat, .sh, etc.)
- Scripts (.js, .vbs, .ps1, etc.)
- Compressed archives may have restrictions

### Troubleshooting

**USB not detected:**
- Make sure it's fully inserted
- Try removing and reinserting
- Ask staff if the problem persists

**Files won't transfer:**
- Check file types are supported
- Verify files aren't too large
- Infected files will be automatically skipped

**Process is slow:**
- Large files take longer to scan and convert
- Multiple files take time to process
- This is normal security scanning

## For System Administrators

### Quick Installation (Fresh Ubuntu Desktop)

```bash
# 1. Clone or copy the application
cd /opt
sudo git clone <repository-url> usb-defender-kiosk
cd usb-defender-kiosk

# 2. Run installation (this takes 10-15 minutes)
sudo ./install/install.sh

# 3. Configure settings
sudo nano /etc/usb-defender/app_config.yaml

# 4. Change default passwords
sudo passwd usb-kiosk
sudo nano /etc/usb-defender/app_config.yaml
# Change dashboard password in config

# 5. Reboot
sudo reboot
```

After reboot, the kiosk will start automatically.

### Quick Configuration

Edit `/etc/usb-defender/app_config.yaml`:

**Transfer to Network Share:**
```yaml
transfer:
  method: network
  network:
    server: "//server.local/share"
    username: "your_username"
    password: "your_password"
```

**Transfer to Cloud (S3):**
```yaml
transfer:
  method: cloud
  cloud:
    bucket: "your-bucket-name"
    access_key: "your_access_key"
    secret_key: "your_secret_key"
```

**Adjust File Limits:**
```yaml
files:
  max_size_mb: 100
  max_total_size_mb: 500
```

### Access Admin Dashboard

While kiosk is running:
1. Press `Ctrl+Shift+D`
2. Enter admin password (default: "admin" - CHANGE THIS!)
3. View logs, statistics, and system status

### Common Admin Tasks

**View Logs:**
```bash
sudo tail -f /var/log/usb-defender/app.log
sudo tail -f /var/log/usb-defender/audit.log
```

**Check Service Status:**
```bash
sudo systemctl status usb-defender
sudo systemctl status clamav-daemon
```

**Update Virus Signatures:**
```bash
sudo freshclam
sudo systemctl restart clamav-daemon
```

**Restart Kiosk:**
```bash
sudo systemctl restart usb-defender
```

**View Transferred Files:**
```bash
ls -lah /var/usb-defender/transfers/
```

**Check Disk Space:**
```bash
df -h /var/usb-defender
```

### Emergency Access

If you need to exit kiosk mode:

1. Switch to TTY: `Ctrl+Alt+F2`
2. Login as administrator
3. Stop service: `sudo systemctl stop usb-defender`
4. Return to desktop: `Ctrl+Alt+F1` or `Ctrl+Alt+F7`

### Monitoring

**Key metrics to monitor:**
- Disk space in `/var/usb-defender/transfers/`
- ClamAV signature update date
- System logs for errors
- Failed transfer attempts

**Set up log rotation:**
Logs automatically rotate (5 backups, 10MB max per file)

**Set up alerts:**
Consider monitoring:
- Disk space > 80% usage
- ClamAV daemon stopped
- Multiple failed scans (potential malware)

### Backup

**What to backup:**
- Configuration: `/etc/usb-defender/app_config.yaml`
- Logs: `/var/log/usb-defender/` (if needed for compliance)
- Transferred files: `/var/usb-defender/transfers/`

**Automated backup script:**
```bash
#!/bin/bash
BACKUP_DIR="/backup/usb-defender/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"
cp /etc/usb-defender/app_config.yaml "$BACKUP_DIR/"
cp -r /var/usb-defender/transfers/ "$BACKUP_DIR/"
```

### Security Checklist

- [ ] Changed default kiosk user password
- [ ] Changed default dashboard password
- [ ] Configured proper transfer destination
- [ ] Verified USB devices mount read-only
- [ ] Confirmed ClamAV is updating signatures
- [ ] Set up log monitoring
- [ ] Tested with known malware sample (EICAR)
- [ ] Documented admin procedures
- [ ] Restricted physical access to kiosk

### Support Contacts

- Application Logs: `/var/log/usb-defender/`
- Configuration: `/etc/usb-defender/app_config.yaml`
- Installation: `/opt/usb-defender-kiosk/`
- Documentation: `/opt/usb-defender-kiosk/README.md`

## For Developers

### Quick Development Setup

```bash
git clone <repository-url>
cd usb-defender-kiosk
./run-dev.sh
```

See `DEVELOPMENT.md` for detailed development guide.

### Testing

```bash
# Run in development mode
./run-dev.sh

# Run with debug logging
python3 src/main.py --debug --no-fullscreen

# Test specific component
python3 -m pytest tests/
```

## FAQ

### For Users

**Q: Will my files be deleted?**
A: No, the kiosk only reads your files. Your USB drive is mounted read-only.

**Q: How long does it take?**
A: Depends on file size and count. Usually 1-5 minutes for typical documents.

**Q: What if a file is infected?**
A: Infected files are skipped and not transferred. You'll be notified.

**Q: Can I transfer folders?**
A: Select individual files within folders. All folder structure is preserved.

### For Administrators

**Q: How do I change where files are transferred?**
A: Edit `/etc/usb-defender/app_config.yaml` and change the `transfer` section.

**Q: How do I add allowed file types?**
A: Edit `files.allowed_extensions` in the config file.

**Q: Can users access the system?**
A: No, kiosk mode restricts access. Only admin can access via dashboard or TTY.

**Q: How do I uninstall?**
A: Stop service, remove kiosk user, delete `/opt/usb-defender-kiosk/` and `/etc/usb-defender/`.

## Version Information

- Version: 1.1.0
- Python: 3.8+ (automatically detected during installation)
- Platform: Ubuntu Desktop 20.04 LTS or newer
- License: MIT License

## Getting Help

1. Check logs: `/var/log/usb-defender/app.log`
2. Review README.md for detailed documentation
3. Check DEVELOPMENT.md for technical details
4. Contact system administrator

