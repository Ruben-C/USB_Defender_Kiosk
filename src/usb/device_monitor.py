"""
USB Defender Kiosk - USB Device Monitor
Monitors USB insertion/removal and handles mounting
"""

import pyudev
import subprocess
import os
from pathlib import Path
from typing import Optional, List, Callable
import threading
import time
from src.utils.logger import KioskLogger


logger = KioskLogger.get_logger(__name__)


class USBDevice:
    """Represents a USB storage device"""
    
    def __init__(self, device_node: str, device_path: str):
        """
        Initialize USB device
        
        Args:
            device_node: Device node (e.g., /dev/sdb1)
            device_path: Sysfs device path
        """
        self.device_node = device_node
        self.device_path = device_path
        self.mount_point: Optional[Path] = None
        self.label = ""
        self.size = 0
        self.model = ""
        self._info_loaded = False
    
    def load_info(self):
        """Load device information"""
        if self._info_loaded:
            return
        
        try:
            # Get device label
            result = subprocess.run(
                ['lsblk', '-no', 'LABEL', self.device_node],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.label = result.stdout.strip()
            
            # Get device size
            result = subprocess.run(
                ['lsblk', '-no', 'SIZE', self.device_node],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.size = result.stdout.strip()
            
            # Get device model
            result = subprocess.run(
                ['lsblk', '-no', 'MODEL', self.device_node],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.model = result.stdout.strip()
            
            self._info_loaded = True
            logger.debug(f"Loaded info for {self.device_node}: {self.label} ({self.size})")
            
        except Exception as e:
            logger.error(f"Error loading device info: {e}")
    
    def get_display_name(self) -> str:
        """Get human-readable device name"""
        if self.label:
            return f"{self.label} ({self.size})"
        elif self.model:
            return f"{self.model} ({self.size})"
        else:
            return f"USB Drive ({self.size})"
    
    def __str__(self):
        return f"USBDevice({self.device_node}, {self.get_display_name()})"


class USBDeviceMonitor:
    """Monitors USB device insertion and removal"""
    
    def __init__(self, mount_base: str = "/media/usb-defender"):
        """
        Initialize USB device monitor
        
        Args:
            mount_base: Base directory for mounting USB devices
        """
        self.mount_base = Path(mount_base)
        self.mount_base.mkdir(parents=True, exist_ok=True)
        
        self.context = pyudev.Context()
        self.monitor = pyudev.Monitor.from_netlink(self.context)
        self.monitor.filter_by(subsystem='block', device_type='partition')
        
        self.devices: List[USBDevice] = []
        self.on_device_added: Optional[Callable[[USBDevice], None]] = None
        self.on_device_removed: Optional[Callable[[USBDevice], None]] = None
        
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        logger.info("USB device monitor initialized")
    
    def start(self):
        """Start monitoring for USB devices"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        # Scan for existing devices
        self.scan_existing_devices()
        
        logger.info("USB device monitoring started")
    
    def stop(self):
        """Stop monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
        logger.info("USB device monitoring stopped")
    
    def _monitor_loop(self):
        """Monitor loop running in separate thread"""
        observer = pyudev.MonitorObserver(self.monitor, callback=self._on_udev_event)
        observer.start()
        
        while self._monitoring:
            time.sleep(0.5)
        
        observer.stop()
    
    def _on_udev_event(self, action: str, device: pyudev.Device):
        """
        Handle udev device events
        
        Args:
            action: Event action ('add' or 'remove')
            device: udev device object
        """
        try:
            # Only handle USB storage devices
            if not self._is_usb_storage(device):
                return
            
            device_node = device.device_node
            if not device_node:
                return
            
            if action == 'add':
                logger.info(f"USB device added: {device_node}")
                usb_device = USBDevice(device_node, device.sys_path)
                usb_device.load_info()
                
                self.devices.append(usb_device)
                
                # Audit log
                KioskLogger.audit_usb_insert(
                    device_node,
                    usb_device.get_display_name(),
                    str(usb_device.size)
                )
                
                if self.on_device_added:
                    self.on_device_added(usb_device)
            
            elif action == 'remove':
                logger.info(f"USB device removed: {device_node}")
                
                # Find and remove device from list
                device_to_remove = None
                for dev in self.devices:
                    if dev.device_node == device_node:
                        device_to_remove = dev
                        break
                
                if device_to_remove:
                    self.devices.remove(device_to_remove)
                    
                    # Audit log
                    KioskLogger.audit_usb_remove(device_node)
                    
                    if self.on_device_removed:
                        self.on_device_removed(device_to_remove)
        
        except Exception as e:
            logger.error(f"Error handling udev event: {e}", exc_info=True)
    
    def _is_usb_storage(self, device: pyudev.Device) -> bool:
        """
        Check if device is a USB storage device
        
        Args:
            device: udev device
            
        Returns:
            True if USB storage device
        """
        # Check if device is on USB bus
        parent = device.find_parent('usb', 'usb_device')
        if not parent:
            return False
        
        # Check if it's a storage device
        if device.subsystem != 'block':
            return False
        
        return True
    
    def scan_existing_devices(self):
        """Scan for USB devices that are already connected"""
        logger.info("Scanning for existing USB devices...")
        
        for device in self.context.list_devices(subsystem='block', DEVTYPE='partition'):
            if self._is_usb_storage(device):
                device_node = device.device_node
                if device_node and not any(d.device_node == device_node for d in self.devices):
                    logger.info(f"Found existing USB device: {device_node}")
                    usb_device = USBDevice(device_node, device.sys_path)
                    usb_device.load_info()
                    self.devices.append(usb_device)
                    
                    if self.on_device_added:
                        self.on_device_added(usb_device)
    
    def mount_device(self, device: USBDevice) -> bool:
        """
        Mount USB device read-only
        
        Args:
            device: USB device to mount
            
        Returns:
            True if mounted successfully
        """
        if device.mount_point and device.mount_point.exists():
            logger.warning(f"Device {device.device_node} already mounted")
            return True
        
        try:
            # Create unique mount point
            mount_point = self.mount_base / f"usb_{device.device_node.split('/')[-1]}"
            mount_point.mkdir(parents=True, exist_ok=True)
            
            # Use udisksctl for mounting (respects udev rules)
            logger.info(f"Mounting {device.device_node} to {mount_point}")
            
            result = subprocess.run(
                ['udisksctl', 'mount', '-b', device.device_node, '--no-user-interaction'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # udisksctl outputs the mount point
                output = result.stdout.strip()
                if "Mounted" in output:
                    # Extract mount point from output
                    # Format: "Mounted /dev/sdb1 at /media/..."
                    parts = output.split(" at ")
                    if len(parts) == 2:
                        actual_mount = Path(parts[1].strip().rstrip('.'))
                        device.mount_point = actual_mount
                        logger.info(f"Device mounted at {device.mount_point}")
                        return True
                
                device.mount_point = mount_point
                logger.info(f"Device mounted successfully")
                return True
            else:
                logger.error(f"Failed to mount device: {result.stderr}")
                return False
        
        except subprocess.TimeoutExpired:
            logger.error("Mount operation timed out")
            return False
        except Exception as e:
            logger.error(f"Error mounting device: {e}", exc_info=True)
            return False
    
    def unmount_device(self, device: USBDevice) -> bool:
        """
        Unmount USB device
        
        Args:
            device: USB device to unmount
            
        Returns:
            True if unmounted successfully
        """
        if not device.mount_point:
            logger.warning(f"Device {device.device_node} not mounted")
            return True
        
        try:
            logger.info(f"Unmounting {device.device_node}")
            
            result = subprocess.run(
                ['udisksctl', 'unmount', '-b', device.device_node, '--no-user-interaction'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"Device unmounted successfully")
                device.mount_point = None
                return True
            else:
                logger.error(f"Failed to unmount device: {result.stderr}")
                return False
        
        except subprocess.TimeoutExpired:
            logger.error("Unmount operation timed out")
            return False
        except Exception as e:
            logger.error(f"Error unmounting device: {e}", exc_info=True)
            return False
    
    def get_devices(self) -> List[USBDevice]:
        """
        Get list of connected USB devices
        
        Returns:
            List of USB devices
        """
        return self.devices.copy()

