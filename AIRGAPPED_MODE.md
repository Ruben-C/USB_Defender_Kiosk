# USB Defender Kiosk - Airgapped Mode

## Overview

The USB Defender Kiosk supports **Airgapped Mode** for maximum security in isolated environments without network connectivity. In this mode, the system uses a **two-USB workflow** with registered secure USB devices.

## How It Works

### Traditional Mode vs. Airgapped Mode

**Traditional Mode** (network/cloud):
1. Customer inserts USB → Select files → Scan & Convert → Transfer to network/cloud → Complete

**Airgapped Mode** (secure USB):
1. Customer inserts USB → Select files → Scan & Convert
2. **Customer removes their USB**
3. **Support staff inserts REGISTERED secure USB**
4. System verifies USB is registered → Transfer to secure USB → Complete

## Key Features

- **Registered USB Devices**: Only pre-registered USB drives can receive converted files
- **USB Verification**: System checks serial number, vendor ID, and product ID
- **Two-USB Workflow**: Customer's untrusted USB never comes in contact with output
- **Air-gapped Security**: No network connectivity required
- **Audit Trail**: All USB registrations and transfers are logged

## Configuration

### Enable Airgapped Mode

Edit `/etc/usb-defender/app_config.yaml`:

```yaml
transfer:
  method: secure_usb  # Changed from 'local', 'network', or 'cloud'
  
  secure_usb:
    database_path: "/etc/usb-defender/secure_usb.db"
    create_session_folders: true
    session_folder_format: "%Y%m%d_%H%M%S"
```

## Registering Secure USB Devices

### Via Dashboard

1. **Open Admin Dashboard**:
   - Press `Ctrl+Shift+D` while kiosk is running
   - Enter admin password

2. **Insert USB to Register**:
   - Insert the USB device you want to register
   - System will detect and show device information

3. **Register Device**:
   - Click "Register Current USB"
   - Enter a friendly label (e.g., "Secure USB #1")
   - Add optional notes
   - Click OK

4. **Verify Registration**:
   - Device will appear in the registered devices table
   - Note the serial number for future reference

### Device Information

The system registers USB devices using:
- **Serial Number**: Unique identifier for the device
- **Vendor ID**: USB manufacturer identifier  
- **Product ID**: USB model identifier

All three must match for verification.

⚠️ **Warning**: Some USB devices may not have readable serial numbers. The system will warn you before registering such devices.

## User Workflow (Airgapped Mode)

### For End Users

1. **Insert Customer's USB Drive**
   - System detects and mounts read-only
   - Browse and select files

2. **Start Transfer**
   - Files are scanned with ClamAV
   - Files are converted to images
   - Infected files are automatically skipped

3. **Switch USB Devices**
   - Screen prompts: "Remove customer's USB"
   - Remove the customer's USB drive
   - Insert a **registered secure USB drive**

4. **Verification**
   - System verifies the USB is registered
   - If not registered: Error message, insert correct USB
   - If registered: Transfer proceeds automatically

5. **Complete**
   - Files transferred to secure USB
   - Remove secure USB and return to customer

### For Support Staff

**Daily Operations**:
- Keep registered secure USB devices accessible
- Verify USB labels match registration
- Monitor dashboard for unregistered USB attempts

**When Customer Arrives**:
1. Customer inserts their USB
2. Help customer select files if needed
3. Initiate transfer process
4. When prompted, swap customer USB for secure USB
5. After transfer, give secure USB to customer

## Managing Registered Devices

### View Registered Devices

Dashboard shows:
- Device label
- Serial number
- Vendor and Product IDs
- Registration date
- Last used date

### Unregister a Device

1. Select device in table
2. Click "Unregister Selected"
3. Confirm removal
4. Device will be blocked from receiving files

### View Usage History

1. Select device in table
2. Click "View Usage History"
3. See:
   - Transfer timestamps
   - Session IDs
   - Number of files transferred

### Export/Import Registrations

**Export** (for backup):
1. Click "Export"
2. Choose location
3. Saves JSON file with all registrations

**Import** (restore from backup):
1. Click "Import"
2. Select JSON file
3. Choose merge (add to existing) or replace (clear first)

## Security Considerations

### Why Two USBs?

The two-USB workflow ensures:
- Customer's untrusted USB never touches output files
- Output USB is pre-screened and registered
- Physical separation between untrusted and trusted devices
- Air-gap maintained (no network transfer)

### Physical Security

**Secure USB Storage**:
- Store registered USBs in secure location
- Label clearly for identification
- Maintain custody chain
- Regular inventory checks

**Registration Database**:
- Located at `/etc/usb-defender/secure_usb.db`
- SQLite database with device records
- Backup regularly
- Restrict file permissions

### Threat Model

**Protected Against**:
- Malware on customer USB spreading to output
- Unauthorized USB devices receiving files
- Network-based attacks (no network in airgapped mode)
- Execution of malicious files (read-only mount)

**Not Protected Against**:
- Physical theft of secure USB after transfer
- Malware in converted images (though significantly reduced)
- Social engineering to register malicious USB
- Physical access to registration database

## Troubleshooting

### USB Not Recognized as Secure

**Symptoms**: After inserting USB, message shows "USB device not registered"

**Solutions**:
1. Verify USB is actually registered (check dashboard)
2. Check serial number matches registration
3. Try removing and reinserting USB
4. Check USB device is functioning properly

### Cannot Register USB

**Symptoms**: Registration button disabled or error on registration

**Solutions**:
1. Check USB is properly inserted and mounted
2. Verify USB has readable serial number
3. Check database permissions: `/etc/usb-defender/secure_usb.db`
4. Review logs: `/var/log/usb-defender/app.log`

### Registered USB Not Detected

**Symptoms**: Insert registered USB but system doesn't recognize it

**Solutions**:
1. Wait a few seconds for USB detection
2. Check USB is mounted: `lsblk`
3. Verify udev rules: `udevadm info /dev/sdX`
4. Check USB device monitor logs

### Lost Registration Database

**Recovery**:
1. Check for backup exports (`.json` files)
2. Import backup via dashboard
3. If no backup, re-register all secure USB devices
4. Update documentation with new registrations

## Best Practices

### For Administrators

1. **Regular Backups**:
   - Export registrations weekly
   - Store backups securely off-site
   - Test restore procedure

2. **USB Management**:
   - Maintain inventory of secure USBs
   - Label with registration date and ID
   - Replace if damaged or suspected compromised

3. **Monitoring**:
   - Review audit logs regularly
   - Check for unauthorized USB attempts
   - Monitor database growth

4. **Documentation**:
   - Keep list of registered USBs
   - Document registration/unregistration
   - Maintain custody records

### For Users

1. **USB Handling**:
   - Do not force USB insertion
   - Wait for system prompts
   - Follow on-screen instructions
   - Report any errors to staff

2. **File Selection**:
   - Select only needed files
   - Verify file names before transfer
   - Note any infected file warnings

3. **Completion**:
   - Wait for completion message
   - Do not remove USB during transfer
   - Report any issues immediately

## Audit Log Entries

Airgapped mode adds these audit log entries:

```
SECURE_USB_REGISTERED | serial=ABC123 | label=Secure USB #1
SECURE_USB_UNREGISTERED | serial=ABC123
UNREGISTERED_USB_BLOCKED | serial=XYZ789 | vendor_id=1234 | product_id=5678
```

## Performance Considerations

- **Registration Lookup**: O(1) - SQLite indexed query
- **USB Detection**: 1-3 seconds typical
- **Verification**: < 1 second
- **Database Size**: ~1KB per registered device

## Comparison with Network Transfer

| Feature | Airgapped Mode | Network Transfer |
|---------|----------------|------------------|
| Network Required | No | Yes |
| Physical USB Swap | Yes | No |
| Speed | USB 2.0/3.0 | Network dependent |
| Security | Highest | High |
| Setup Complexity | Medium | Low-Medium |
| User Steps | More (USB swap) | Fewer |
| Suitable For | Classified environments | Standard environments |

## Migration

### From Network to Airgapped

1. Register secure USB devices
2. Update config: `method: secure_usb`
3. Train staff on two-USB workflow
4. Test with sample files
5. Deploy to production

### From Airgapped to Network

1. Configure network transfer settings
2. Update config: `method: network` or `cloud`
3. Test network connectivity
4. Deploy to production
5. Keep USB registrations for potential rollback

## Compliance

Airgapped mode supports compliance with:
- **NIST SP 800-53**: SC-7 (Boundary Protection)
- **PCI DSS**: Requirement 1.3 (Network segmentation)
- **HIPAA**: Administrative safeguards for PHI
- **Classified environments**: Air-gap requirements

Document your specific compliance requirements and map to USB Defender features.

## Support

For airgapped mode issues:
1. Check logs: `/var/log/usb-defender/audit.log`
2. Verify registrations: Dashboard → USB Registration
3. Test with known-good secure USB
4. Review this documentation
5. Contact system administrator

## Version History

- **v1.1.0**: Added airgapped mode with secure USB registration
- **v1.0.0**: Initial release with network/cloud transfer

