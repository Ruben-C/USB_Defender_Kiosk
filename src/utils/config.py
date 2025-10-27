"""
USB Defender Kiosk - Configuration Management
Handles loading and managing application configuration
"""

import yaml
from pathlib import Path
from typing import Any, Optional
from cryptography.fernet import Fernet
import base64
import hashlib


class ConfigManager:
    """Manages application configuration"""
    
    def __init__(self, config_path: str = "/etc/usb-defender/app_config.yaml"):
        """
        Initialize configuration manager
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = Path(config_path)
        self._config = {}
        self._encryption_key = None
        self.load()
    
    def load(self):
        """Load configuration from file"""
        if not self.config_path.exists():
            # Try alternative path in development
            alt_path = Path(__file__).parent.parent.parent / "config" / "app_config.yaml"
            if alt_path.exists():
                self.config_path = alt_path
            else:
                raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            self._config = yaml.safe_load(f)
        
        # Initialize encryption key for sensitive data
        self._init_encryption_key()
    
    def save(self):
        """Save configuration to file"""
        with open(self.config_path, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        
        Args:
            key: Configuration key (e.g., 'transfer.method')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """
        Set configuration value using dot notation
        
        Args:
            key: Configuration key (e.g., 'transfer.method')
            value: Value to set
        """
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def _init_encryption_key(self):
        """Initialize encryption key for sensitive data"""
        # Generate key from machine-specific data
        # In production, this should use a more secure key management system
        key_material = f"{self.config_path}".encode()
        key_hash = hashlib.sha256(key_material).digest()
        self._encryption_key = base64.urlsafe_b64encode(key_hash)
    
    def encrypt_value(self, value: str) -> str:
        """
        Encrypt a sensitive value
        
        Args:
            value: Plain text value
            
        Returns:
            Encrypted value (base64 encoded)
        """
        if not value:
            return ""
        
        f = Fernet(self._encryption_key)
        encrypted = f.encrypt(value.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt_value(self, encrypted_value: str) -> str:
        """
        Decrypt a sensitive value
        
        Args:
            encrypted_value: Encrypted value (base64 encoded)
            
        Returns:
            Decrypted plain text value
        """
        if not encrypted_value:
            return ""
        
        try:
            f = Fernet(self._encryption_key)
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_value.encode())
            decrypted = f.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception:
            # Value might not be encrypted, return as-is
            return encrypted_value
    
    def get_transfer_config(self) -> dict:
        """Get transfer configuration"""
        return self.get('transfer', {})
    
    def get_file_config(self) -> dict:
        """Get file processing configuration"""
        return self.get('files', {})
    
    def get_conversion_config(self) -> dict:
        """Get conversion configuration"""
        return self.get('conversion', {})
    
    def get_clamav_config(self) -> dict:
        """Get ClamAV configuration"""
        return self.get('clamav', {})
    
    def get_ui_config(self) -> dict:
        """Get UI configuration"""
        return self.get('ui', {})
    
    def get_logging_config(self) -> dict:
        """Get logging configuration"""
        return self.get('logging', {})
    
    def get_dashboard_config(self) -> dict:
        """Get dashboard configuration"""
        return self.get('dashboard', {})
    
    def get_kiosk_config(self) -> dict:
        """Get kiosk mode configuration"""
        return self.get('kiosk', {})
    
    def get_usb_config(self) -> dict:
        """Get USB configuration"""
        return self.get('usb', {})
    
    def is_extension_allowed(self, extension: str) -> bool:
        """
        Check if file extension is allowed
        
        Args:
            extension: File extension (without dot)
            
        Returns:
            True if allowed, False otherwise
        """
        extension = extension.lower().lstrip('.')
        
        # Check if explicitly blocked
        blocked = self.get('files.blocked_extensions', [])
        if extension in blocked:
            return False
        
        # Check if in allowed list
        allowed = self.get('files.allowed_extensions', [])
        return extension in allowed
    
    def get_max_file_size(self) -> int:
        """
        Get maximum file size in bytes
        
        Returns:
            Maximum file size in bytes
        """
        max_mb = self.get('files.max_size_mb', 100)
        return max_mb * 1024 * 1024
    
    def get_max_total_size(self) -> int:
        """
        Get maximum total transfer size in bytes
        
        Returns:
            Maximum total size in bytes
        """
        max_mb = self.get('files.max_total_size_mb', 500)
        return max_mb * 1024 * 1024

