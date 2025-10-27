"""
USB Defender Kiosk - Secure USB Transfer
Two-USB workflow for airgapped systems
"""

import shutil
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import subprocess

from src.transfer.transfer_manager import TransferManager, TransferResult
from src.usb.secure_usb_manager import SecureUSBManager
from src.usb.device_monitor import USBDevice
from src.utils.logger import KioskLogger


logger = KioskLogger.get_logger('transfer')


class SecureUSBTransferManager(TransferManager):
    """Transfers files to registered secure USB devices"""
    
    def __init__(self, config: dict):
        """
        Initialize secure USB transfer manager
        
        Args:
            config: Secure USB transfer configuration
        """
        super().__init__(config)
        
        db_path = config.get('database_path', '/etc/usb-defender/secure_usb.db')
        self.usb_manager = SecureUSBManager(db_path)
        self.create_session_folders = config.get('create_session_folders', True)
        
        logger.info("Secure USB transfer manager initialized (airgapped mode)")
    
    def verify_secure_usb(self, device: USBDevice) -> tuple[bool, str]:
        """
        Verify that USB device is registered as secure
        
        Args:
            device: USB device to verify
            
        Returns:
            Tuple of (is_registered, message)
        """
        # Get device information
        serial = self._get_device_serial(device.device_node)
        vendor_id = self._get_device_vendor_id(device.device_node)
        product_id = self._get_device_product_id(device.device_node)
        
        if not serial:
            return False, "Unable to read USB device serial number"
        
        # Check if registered
        is_registered = self.usb_manager.is_registered(serial, vendor_id, product_id)
        
        if is_registered:
            registered_device = self.usb_manager.get_registered_device(serial)
            if registered_device:
                message = f"Verified secure USB: {registered_device.label}"
                logger.info(message)
                return True, message
            else:
                return True, f"Verified secure USB: {serial}"
        else:
            message = f"USB device not registered: {serial}"
            logger.warning(message)
            KioskLogger.audit("UNREGISTERED_USB_BLOCKED", 
                            serial=serial,
                            vendor_id=vendor_id,
                            product_id=product_id)
            return False, message
    
    def _get_device_serial(self, device_node: str) -> Optional[str]:
        """
        Get USB device serial number
        
        Args:
            device_node: Device node (e.g., /dev/sdb1)
            
        Returns:
            Serial number or None
        """
        try:
            # Get parent device (remove partition number)
            parent_device = device_node.rstrip('0123456789')
            
            # Use udevadm to get serial
            result = subprocess.run(
                ['udevadm', 'info', '--query=all', '--name=' + parent_device],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'ID_SERIAL_SHORT=' in line:
                        serial = line.split('=')[1].strip()
                        return serial
                    elif 'ID_SERIAL=' in line and 'ID_SERIAL_SHORT' not in line:
                        serial = line.split('=')[1].strip()
                        return serial
        
        except Exception as e:
            logger.error(f"Error getting device serial: {e}")
        
        return None
    
    def _get_device_vendor_id(self, device_node: str) -> Optional[str]:
        """Get USB vendor ID"""
        try:
            parent_device = device_node.rstrip('0123456789')
            result = subprocess.run(
                ['udevadm', 'info', '--query=all', '--name=' + parent_device],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'ID_VENDOR_ID=' in line:
                        return line.split('=')[1].strip()
        
        except Exception as e:
            logger.error(f"Error getting vendor ID: {e}")
        
        return None
    
    def _get_device_product_id(self, device_node: str) -> Optional[str]:
        """Get USB product ID"""
        try:
            parent_device = device_node.rstrip('0123456789')
            result = subprocess.run(
                ['udevadm', 'info', '--query=all', '--name=' + parent_device],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'ID_MODEL_ID=' in line:
                        return line.split('=')[1].strip()
        
        except Exception as e:
            logger.error(f"Error getting product ID: {e}")
        
        return None
    
    def transfer_files(self, file_paths: List[Path], session_id: str, 
                      secure_device: Optional[USBDevice] = None) -> Dict[str, TransferResult]:
        """
        Transfer files to secure USB device
        
        Args:
            file_paths: List of file paths to transfer
            session_id: Session identifier
            secure_device: Secure USB device (must be verified first)
            
        Returns:
            Dictionary mapping source paths to TransferResult objects
        """
        if not secure_device or not secure_device.mount_point:
            logger.error("No secure USB device provided")
            results = {}
            for file_path in file_paths:
                result = TransferResult(file_path)
                result.error_message = "No secure USB device available"
                results[str(file_path)] = result
            return results
        
        # Verify device is registered
        is_registered, message = self.verify_secure_usb(secure_device)
        if not is_registered:
            logger.error(f"Secure USB verification failed: {message}")
            results = {}
            for file_path in file_paths:
                result = TransferResult(file_path)
                result.error_message = f"USB not registered: {message}"
                results[str(file_path)] = result
            return results
        
        logger.info(f"Transferring {len(file_paths)} files to secure USB")
        
        # Determine destination directory
        dest_base = secure_device.mount_point
        
        if self.create_session_folders:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            dest_dir = dest_base / f"{session_id}_{timestamp}"
        else:
            dest_dir = dest_base / session_id
        
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        results = {}
        
        for file_path in file_paths:
            result = TransferResult(file_path)
            
            try:
                # Preserve directory structure
                parts = file_path.parts
                if session_id in parts:
                    session_idx = parts.index(session_id)
                    relative_parts = parts[session_idx + 1:]
                    relative_path = Path(*relative_parts) if relative_parts else file_path.name
                else:
                    relative_path = file_path.name
                
                dest_path = dest_dir / relative_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file
                shutil.copy2(file_path, dest_path)
                
                result.destination = str(dest_path)
                result.success = True
                
                self._log_transfer(file_path, str(dest_path), True)
            
            except Exception as e:
                result.error_message = str(e)
                self._log_transfer(file_path, str(dest_dir), False, str(e))
            
            results[str(file_path)] = result
        
        # Log usage
        successful_count = sum(1 for r in results.values() if r.success)
        if successful_count > 0:
            serial = self._get_device_serial(secure_device.device_node)
            if serial:
                self.usb_manager.log_usage(serial, session_id, successful_count)
        
        # Summary
        logger.info(f"Secure USB transfer complete: {successful_count}/{len(file_paths)} successful")
        logger.info(f"Files transferred to: {dest_dir}")
        
        return results
    
    def test_connection(self) -> bool:
        """
        Test if any secure USB is available
        
        Returns:
            True if at least one device is registered
        """
        device_count = self.usb_manager.get_device_count()
        
        if device_count > 0:
            logger.info(f"Secure USB system ready: {device_count} device(s) registered")
            return True
        else:
            logger.warning("No secure USB devices registered")
            return False
    
    def get_destination_info(self) -> str:
        """
        Get destination information
        
        Returns:
            Destination description
        """
        device_count = self.usb_manager.get_device_count()
        return f"Secure USB (airgapped): {device_count} device(s) registered"
    
    def get_device_info_for_registration(self, device: USBDevice) -> Dict[str, str]:
        """
        Get device information for registration purposes
        
        Args:
            device: USB device
            
        Returns:
            Dictionary with device information
        """
        serial = self._get_device_serial(device.device_node)
        vendor_id = self._get_device_vendor_id(device.device_node)
        product_id = self._get_device_product_id(device.device_node)
        
        return {
            'serial': serial or 'UNKNOWN',
            'vendor_id': vendor_id or 'UNKNOWN',
            'product_id': product_id or 'UNKNOWN',
            'device_node': device.device_node,
            'label': device.label or '',
            'size': device.size or ''
        }

