"""
USB Defender Kiosk - Dashboard Authentication
Simple authentication for admin dashboard
"""

import hashlib
from typing import Optional
from src.utils.logger import KioskLogger


logger = KioskLogger.get_logger(__name__)


class DashboardAuth:
    """Simple authentication for dashboard access"""
    
    def __init__(self, config: dict):
        """
        Initialize dashboard authentication
        
        Args:
            config: Dashboard configuration
        """
        self.config = config
        self.password_hash = self._get_password_hash()
        self.session_timeout = config.get('session_timeout', 15) * 60  # Convert to seconds
    
    def _get_password_hash(self) -> str:
        """
        Get password hash from config
        
        Returns:
            Password hash
        """
        password = self.config.get('password', 'admin')
        
        # Check if it's already hashed (starts with hash marker)
        if password.startswith('$hash$'):
            return password[6:]  # Remove marker
        
        # Hash the password
        return self._hash_password(password)
    
    def _hash_password(self, password: str) -> str:
        """
        Hash password using SHA-256
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password: str) -> bool:
        """
        Verify password
        
        Args:
            password: Password to verify
            
        Returns:
            True if password is correct
        """
        password_hash = self._hash_password(password)
        
        is_valid = password_hash == self.password_hash
        
        if is_valid:
            logger.info("Dashboard authentication successful")
        else:
            logger.warning("Dashboard authentication failed")
        
        return is_valid
    
    def change_password(self, old_password: str, new_password: str) -> bool:
        """
        Change password
        
        Args:
            old_password: Current password
            new_password: New password
            
        Returns:
            True if password was changed
        """
        if not self.verify_password(old_password):
            return False
        
        self.password_hash = self._hash_password(new_password)
        
        # TODO: Update config file with new hashed password
        logger.info("Dashboard password changed")
        
        return True

