"""
USB Defender Kiosk - Secure USB Manager
Manages registration and verification of trusted USB devices for output
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from src.utils.logger import KioskLogger


logger = KioskLogger.get_logger(__name__)


class SecureUSBDevice:
    """Represents a registered secure USB device"""
    
    def __init__(self, serial: str, vendor_id: str, product_id: str, 
                 label: str = "", notes: str = "", registered_date: str = ""):
        """
        Initialize secure USB device
        
        Args:
            serial: USB device serial number
            vendor_id: USB vendor ID
            product_id: USB product ID
            label: User-friendly label
            notes: Additional notes
            registered_date: Registration timestamp
        """
        self.serial = serial
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.label = label or f"USB_{serial[:8]}"
        self.notes = notes
        self.registered_date = registered_date or datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'serial': self.serial,
            'vendor_id': self.vendor_id,
            'product_id': self.product_id,
            'label': self.label,
            'notes': self.notes,
            'registered_date': self.registered_date
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SecureUSBDevice':
        """Create from dictionary"""
        return cls(
            serial=data['serial'],
            vendor_id=data['vendor_id'],
            product_id=data['product_id'],
            label=data.get('label', ''),
            notes=data.get('notes', ''),
            registered_date=data.get('registered_date', '')
        )
    
    def __str__(self):
        return f"SecureUSB({self.label}, {self.serial})"


class SecureUSBManager:
    """Manages secure USB device registration and verification"""
    
    def __init__(self, db_path: str = "/etc/usb-defender/secure_usb.db"):
        """
        Initialize secure USB manager
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_database()
        
        logger.info(f"Secure USB manager initialized: {self.db_path}")
    
    def _init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS secure_usb_devices (
                serial TEXT PRIMARY KEY,
                vendor_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                label TEXT,
                notes TEXT,
                registered_date TEXT,
                last_used TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serial TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                session_id TEXT,
                file_count INTEGER,
                FOREIGN KEY (serial) REFERENCES secure_usb_devices(serial)
            )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("Secure USB database initialized")
    
    def register_usb(self, device: SecureUSBDevice) -> bool:
        """
        Register a secure USB device
        
        Args:
            device: SecureUSBDevice to register
            
        Returns:
            True if registered successfully
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO secure_usb_devices
                (serial, vendor_id, product_id, label, notes, registered_date, last_used)
                VALUES (?, ?, ?, ?, ?, ?, NULL)
            ''', (
                device.serial,
                device.vendor_id,
                device.product_id,
                device.label,
                device.notes,
                device.registered_date
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Registered secure USB: {device}")
            KioskLogger.audit("SECURE_USB_REGISTERED", 
                            serial=device.serial, 
                            label=device.label)
            
            return True
        
        except Exception as e:
            logger.error(f"Error registering USB device: {e}", exc_info=True)
            return False
    
    def unregister_usb(self, serial: str) -> bool:
        """
        Unregister a secure USB device
        
        Args:
            serial: USB device serial number
            
        Returns:
            True if unregistered successfully
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Delete usage log entries
            cursor.execute('DELETE FROM usage_log WHERE serial = ?', (serial,))
            
            # Delete device
            cursor.execute('DELETE FROM secure_usb_devices WHERE serial = ?', (serial,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Unregistered secure USB: {serial}")
            KioskLogger.audit("SECURE_USB_UNREGISTERED", serial=serial)
            
            return True
        
        except Exception as e:
            logger.error(f"Error unregistering USB device: {e}", exc_info=True)
            return False
    
    def is_registered(self, serial: str, vendor_id: str = None, 
                     product_id: str = None) -> bool:
        """
        Check if USB device is registered
        
        Args:
            serial: USB device serial number
            vendor_id: Optional vendor ID for additional verification
            product_id: Optional product ID for additional verification
            
        Returns:
            True if device is registered
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            if vendor_id and product_id:
                cursor.execute('''
                    SELECT COUNT(*) FROM secure_usb_devices
                    WHERE serial = ? AND vendor_id = ? AND product_id = ?
                ''', (serial, vendor_id, product_id))
            else:
                cursor.execute('''
                    SELECT COUNT(*) FROM secure_usb_devices
                    WHERE serial = ?
                ''', (serial,))
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count > 0
        
        except Exception as e:
            logger.error(f"Error checking USB registration: {e}", exc_info=True)
            return False
    
    def get_registered_device(self, serial: str) -> Optional[SecureUSBDevice]:
        """
        Get registered device by serial number
        
        Args:
            serial: USB device serial number
            
        Returns:
            SecureUSBDevice or None
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT serial, vendor_id, product_id, label, notes, registered_date
                FROM secure_usb_devices
                WHERE serial = ?
            ''', (serial,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return SecureUSBDevice(
                    serial=row[0],
                    vendor_id=row[1],
                    product_id=row[2],
                    label=row[3],
                    notes=row[4],
                    registered_date=row[5]
                )
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting registered device: {e}", exc_info=True)
            return None
    
    def get_all_registered(self) -> List[SecureUSBDevice]:
        """
        Get all registered USB devices
        
        Returns:
            List of SecureUSBDevice objects
        """
        devices = []
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT serial, vendor_id, product_id, label, notes, registered_date
                FROM secure_usb_devices
                ORDER BY registered_date DESC
            ''')
            
            for row in cursor.fetchall():
                devices.append(SecureUSBDevice(
                    serial=row[0],
                    vendor_id=row[1],
                    product_id=row[2],
                    label=row[3],
                    notes=row[4],
                    registered_date=row[5]
                ))
            
            conn.close()
        
        except Exception as e:
            logger.error(f"Error getting registered devices: {e}", exc_info=True)
        
        return devices
    
    def log_usage(self, serial: str, session_id: str, file_count: int):
        """
        Log usage of a secure USB device
        
        Args:
            serial: USB device serial number
            session_id: Transfer session ID
            file_count: Number of files transferred
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            timestamp = datetime.now().isoformat()
            
            # Add usage log entry
            cursor.execute('''
                INSERT INTO usage_log (serial, timestamp, session_id, file_count)
                VALUES (?, ?, ?, ?)
            ''', (serial, timestamp, session_id, file_count))
            
            # Update last_used timestamp
            cursor.execute('''
                UPDATE secure_usb_devices
                SET last_used = ?
                WHERE serial = ?
            ''', (timestamp, serial))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Logged usage for secure USB: {serial}, files: {file_count}")
        
        except Exception as e:
            logger.error(f"Error logging USB usage: {e}", exc_info=True)
    
    def get_usage_history(self, serial: str, limit: int = 50) -> List[Dict]:
        """
        Get usage history for a device
        
        Args:
            serial: USB device serial number
            limit: Maximum number of entries to return
            
        Returns:
            List of usage log entries
        """
        history = []
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT timestamp, session_id, file_count
                FROM usage_log
                WHERE serial = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (serial, limit))
            
            for row in cursor.fetchall():
                history.append({
                    'timestamp': row[0],
                    'session_id': row[1],
                    'file_count': row[2]
                })
            
            conn.close()
        
        except Exception as e:
            logger.error(f"Error getting usage history: {e}", exc_info=True)
        
        return history
    
    def export_registrations(self, export_path: Path) -> bool:
        """
        Export registered devices to JSON file
        
        Args:
            export_path: Path to export file
            
        Returns:
            True if exported successfully
        """
        try:
            devices = self.get_all_registered()
            
            export_data = {
                'export_date': datetime.now().isoformat(),
                'device_count': len(devices),
                'devices': [device.to_dict() for device in devices]
            }
            
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            logger.info(f"Exported {len(devices)} registered devices to {export_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error exporting registrations: {e}", exc_info=True)
            return False
    
    def import_registrations(self, import_path: Path, merge: bool = True) -> Tuple[int, int]:
        """
        Import registered devices from JSON file
        
        Args:
            import_path: Path to import file
            merge: If True, merge with existing; if False, replace existing
            
        Returns:
            Tuple of (successful_imports, failed_imports)
        """
        successful = 0
        failed = 0
        
        try:
            with open(import_path, 'r') as f:
                import_data = json.load(f)
            
            if not merge:
                # Clear existing registrations
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute('DELETE FROM usage_log')
                cursor.execute('DELETE FROM secure_usb_devices')
                conn.commit()
                conn.close()
                logger.info("Cleared existing registrations for import")
            
            for device_data in import_data.get('devices', []):
                try:
                    device = SecureUSBDevice.from_dict(device_data)
                    if self.register_usb(device):
                        successful += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"Error importing device: {e}")
                    failed += 1
            
            logger.info(f"Imported registrations: {successful} successful, {failed} failed")
            return successful, failed
        
        except Exception as e:
            logger.error(f"Error importing registrations: {e}", exc_info=True)
            return 0, 0
    
    def get_device_count(self) -> int:
        """
        Get count of registered devices
        
        Returns:
            Number of registered devices
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM secure_usb_devices')
            count = cursor.fetchone()[0]
            
            conn.close()
            return count
        
        except Exception as e:
            logger.error(f"Error getting device count: {e}", exc_info=True)
            return 0

