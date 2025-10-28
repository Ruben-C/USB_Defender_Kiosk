# Install Scripts - Issues and Improvements

## Critical Issues

### 1. Security Concerns

#### install.sh
- **Line 154**: Default password displayed in plain text in terminal output
- **Risk**: Password visible in terminal history, over-the-shoulder viewing
- **Fix**: Remind to change password but don't display it

#### kiosk_mode.sh
- **Line 140**: Sudoers wildcards allow mounting any /dev/sd* device
- **Risk**: Could mount unintended devices or partitions
- **Fix**: More restrictive mount permissions with validation

### 2. Non-Interactive Mode Failures

#### install.sh
- **Line 37, 56**: Uses `read -p` which blocks in automated/CI environments
- **Risk**: Hangs during automated installations
- **Fix**: Add `-t` timeout and `--assume-yes` flag option

### 3. Missing Pre-flight Checks

#### All Scripts
- No verification of minimum system requirements (RAM, disk space, CPU)
- No check for conflicting software
- No validation that dependencies are available in apt repositories
- **Fix**: Add comprehensive pre-flight validation function

### 4. Error Recovery

#### install.sh
- **Lines 75, 82**: If sub-scripts fail, no rollback
- No cleanup of partially installed components
- **Fix**: Add trap handlers and rollback functions

## Medium Priority Issues

### 5. Race Conditions

#### kiosk_mode.sh
- **Line 155-161**: Watchdog can start multiple instances
- No PID file or lock mechanism
- **Fix**: Add proper locking mechanism

### 6. Silent Failures

#### kiosk_mode.sh
- **Lines 77-103**: Many gsettings commands use `|| true`
- Failures are hidden; user doesn't know what worked
- **Fix**: Capture and report which settings succeeded/failed

### 7. Missing Validation

#### install.sh
- **Lines 67-68**: Makes scripts executable without checking they exist
- No verification that venv was created successfully
- **Fix**: Validate file existence before operations

#### kiosk_mode.sh
- **Line 65**: Uses venv/bin/python without checking if venv exists
- **Fix**: Verify venv and required packages before creating configs

### 8. Idempotency Issues

#### install.sh
- **Line 59-64**: Copy operation not idempotent
- Overwrites existing installation without warning
- **Fix**: Check if already installed, offer upgrade option

#### kiosk_mode.sh
- **Line 32**: Overwrites config without checking if backup exists
- Could lose custom configurations
- **Fix**: Better backup strategy with timestamps

## Low Priority Issues

### 9. User Experience

#### All Scripts
- Limited progress feedback during long operations
- No estimated time remaining
- **Fix**: Add progress indicators for long operations

### 10. Documentation

#### install.sh
- **Lines 160-171**: Post-install instructions could be in a file
- Hard to reference later
- **Fix**: Generate post-install.txt with instructions

### 11. Logging

#### All Scripts
- No detailed installation logs
- Hard to debug failed installations
- **Fix**: Add comprehensive logging to /var/log/usb-defender/install.log

### 12. Dependencies

#### requirements.txt
- Some packages may have newer versions with security fixes
- No hash verification for supply chain security
- **Fix**: Add version update check and pip hash-checking mode

## Suggested Improvements

### A. Add Pre-flight Check Script

Create `install/preflight_check.sh`:
- Check Ubuntu version compatibility
- Verify minimum 4GB RAM, 20GB disk space
- Check for required repositories
- Verify internet connectivity (for package downloads)
- Check if display manager is installed
- Validate user has sudo privileges

### B. Add Installation Log

All scripts should log to `/var/log/usb-defender/install.log`:
- Timestamp each operation
- Record success/failure of each step
- Include system information
- Make troubleshooting easier

### C. Add Rollback Capability

Implement `install/rollback.sh`:
- Remove installed packages (if not present before)
- Restore backed-up configuration files
- Remove created users and directories
- Restore original system state

### D. Improve Error Messages

Current: "ERROR: This script must be run as root"
Better: "ERROR: This script requires root privileges.
        Please run: sudo ./install.sh"

### E. Add Non-Interactive Mode

Support `--assume-yes` or `-y` flag:
- Skip confirmation prompts
- Use defaults for all questions
- Essential for automated deployments

### F. Add Verification Step

After installation, verify:
- All packages installed correctly
- Services are running
- Configuration files are valid
- Permissions are correct
- Application can start

### G. Improve Watchdog

#### kiosk_mode.sh watchdog:
- Add PID file locking
- Better process detection (check actual binary path)
- Limit restart attempts (avoid infinite restart loops)
- Add cooldown period between restarts
- Log restart events with details

### H. Add Update Script

Create `install/update.sh`:
- Check for application updates
- Preserve custom configurations
- Migrate data if schema changes
- Update Python dependencies
- Update virus definitions

## Implementation Priority

1. **High Priority** (Security & Reliability):
   - Fix security issues (#1)
   - Add pre-flight checks (#3)
   - Implement error recovery (#4)
   - Fix race conditions (#5)

2. **Medium Priority** (Robustness):
   - Improve error reporting (#6)
   - Add missing validation (#7)
   - Fix idempotency (#8)
   - Add logging (#11)

3. **Low Priority** (UX & Maintenance):
   - Improve user experience (#9)
   - Better documentation (#10)
   - Add update mechanism (H)
   - Add rollback capability (C)

## Testing Recommendations

1. Test installation on fresh Ubuntu 22.04 LTS
2. Test installation on Ubuntu 24.04 LTS
3. Test with existing installations (upgrade scenario)
4. Test in minimal VM (low resources)
5. Test without internet connection (for airgapped mode)
6. Test interrupted installation (power failure simulation)
7. Test with non-English locale
8. Test rollback procedures

## Next Steps

Would you like me to:
1. Implement the high-priority security fixes?
2. Create the pre-flight check script?
3. Add comprehensive logging throughout?
4. Create a rollback script?
5. All of the above?

