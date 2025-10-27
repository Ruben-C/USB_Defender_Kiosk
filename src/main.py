#!/usr/bin/env python3
"""
USB Defender Kiosk - Main Entry Point
Secure file transfer from untrusted USB devices
"""

import sys
import signal
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

from src.utils.logger import KioskLogger
from src.utils.config import ConfigManager
from src.ui.main_window import MainWindow


def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown"""
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        QApplication.quit()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def check_requirements():
    """
    Check if system requirements are met
    
    Returns:
        Tuple of (success, error_message)
    """
    errors = []
    
    # Check if running on Linux
    if sys.platform not in ['linux', 'linux2']:
        errors.append("This application is designed for Linux systems")
    
    # Check if required directories exist
    required_dirs = [
        '/var/log/usb-defender',
        '/var/usb-defender',
        '/media/usb-defender'
    ]
    
    for dir_path in required_dirs:
        path = Path(dir_path)
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                errors.append(f"Cannot create directory: {dir_path} (permission denied)")
    
    # Check if ClamAV socket exists
    clamav_socket = Path('/var/run/clamav/clamd.ctl')
    if not clamav_socket.exists():
        # This is a warning, not a hard error
        logger.warning("ClamAV socket not found - antivirus scanning will be disabled")
    
    if errors:
        return False, "\n".join(errors)
    
    return True, ""


def main():
    """Main application entry point"""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='USB Defender Kiosk')
    parser.add_argument(
        '--config',
        default='/etc/usb-defender/app_config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--no-fullscreen',
        action='store_true',
        help='Disable fullscreen mode (for testing)'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = ConfigManager(args.config)
    except FileNotFoundError as e:
        print(f"Error: Configuration file not found: {e}", file=sys.stderr)
        print("Please run the installation script first.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1
    
    # Override config with command line arguments
    if args.debug:
        config.set('logging.level', 'DEBUG')
        config.set('logging.console', True)
    
    if args.no_fullscreen:
        config.set('kiosk.fullscreen', False)
    
    # Configure logging
    KioskLogger.configure(config.get_logging_config())
    
    global logger
    logger = KioskLogger.get_logger(__name__)
    
    logger.info("=" * 60)
    logger.info("USB Defender Kiosk Starting")
    logger.info("=" * 60)
    logger.info(f"Configuration: {args.config}")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    
    # Check system requirements
    success, error_msg = check_requirements()
    if not success:
        logger.error(f"System requirements not met:\n{error_msg}")
        print(f"Error: {error_msg}", file=sys.stderr)
        return 1
    
    # Set up signal handlers
    setup_signal_handlers()
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("USB Defender Kiosk")
    app.setOrganizationName("USB Defender")
    
    # Set application-wide style
    app.setStyle('Fusion')
    
    # Disable screen blanking (if possible)
    if hasattr(Qt, 'AA_DisableWindowContextHelpButton'):
        app.setAttribute(Qt.ApplicationAttribute.AA_DisableWindowContextHelpButton)
    
    try:
        # Create and show main window
        window = MainWindow(config)
        window.show()
        
        logger.info("Application started successfully")
        
        # Run application
        exit_code = app.exec()
        
        logger.info(f"Application exiting with code {exit_code}")
        return exit_code
    
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        
        # Show error dialog
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Fatal Error")
        msg.setText("A fatal error occurred")
        msg.setInformativeText(str(e))
        msg.setDetailedText(f"See log file for details:\n/var/log/usb-defender/app.log")
        msg.exec()
        
        return 1


if __name__ == '__main__':
    sys.exit(main())

