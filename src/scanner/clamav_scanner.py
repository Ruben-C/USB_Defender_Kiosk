"""
USB Defender Kiosk - ClamAV Scanner
Integrates ClamAV antivirus for file scanning
"""

import clamd
from pathlib import Path
from typing import Tuple, Optional
from enum import Enum
from src.utils.logger import KioskLogger


logger = KioskLogger.get_logger(__name__)


class ScanResult(Enum):
    """Scan result enumeration"""
    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"
    TIMEOUT = "timeout"


class ClamAVScanner:
    """ClamAV antivirus scanner"""
    
    def __init__(self, config: dict):
        """
        Initialize ClamAV scanner
        
        Args:
            config: ClamAV configuration dictionary
        """
        self.config = config
        self.socket_path = config.get('socket', '/var/run/clamav/clamd.ctl')
        self.timeout = config.get('timeout', 300)
        self.cd: Optional[clamd.ClamdUnixSocket] = None
        
        self._connect()
    
    def _connect(self):
        """Connect to ClamAV daemon"""
        try:
            self.cd = clamd.ClamdUnixSocket(path=self.socket_path)
            
            # Test connection
            self.cd.ping()
            logger.info(f"Connected to ClamAV daemon at {self.socket_path}")
            
            # Log ClamAV version
            version = self.cd.version()
            logger.info(f"ClamAV version: {version}")
            
        except Exception as e:
            logger.error(f"Failed to connect to ClamAV daemon: {e}")
            logger.error(f"Make sure ClamAV is running: systemctl status clamav-daemon")
            self.cd = None
    
    def is_available(self) -> bool:
        """
        Check if ClamAV is available
        
        Returns:
            True if ClamAV daemon is available
        """
        if not self.cd:
            return False
        
        try:
            self.cd.ping()
            return True
        except Exception:
            return False
    
    def scan_file(self, file_path: Path) -> Tuple[ScanResult, str]:
        """
        Scan a single file
        
        Args:
            file_path: Path to file to scan
            
        Returns:
            Tuple of (ScanResult, details_message)
        """
        if not self.cd:
            logger.error("ClamAV not available")
            return ScanResult.ERROR, "ClamAV not available"
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return ScanResult.ERROR, "File not found"
        
        try:
            logger.info(f"Scanning file: {file_path}")
            
            # Scan the file
            result = self.cd.scan(str(file_path))
            
            # Parse result
            if result is None:
                # No threats found
                logger.info(f"File is clean: {file_path}")
                KioskLogger.audit_file_scan(str(file_path), "CLEAN")
                return ScanResult.CLEAN, "No threats detected"
            
            # result is a dict: {filename: ('FOUND', 'threat_name')}
            file_key = str(file_path)
            if file_key in result:
                status, threat_name = result[file_key]
                
                if status == 'FOUND':
                    logger.warning(f"Threat detected in {file_path}: {threat_name}")
                    KioskLogger.audit_file_scan(
                        str(file_path),
                        "INFECTED",
                        threat_name
                    )
                    return ScanResult.INFECTED, f"Threat detected: {threat_name}"
                elif status == 'ERROR':
                    logger.error(f"Error scanning {file_path}")
                    KioskLogger.audit_file_scan(str(file_path), "ERROR")
                    return ScanResult.ERROR, "Scan error"
            
            # Shouldn't reach here, but treat as clean
            return ScanResult.CLEAN, "No threats detected"
        
        except clamd.BufferTooLongError:
            logger.error(f"File too large to scan: {file_path}")
            return ScanResult.ERROR, "File too large for scanning"
        
        except clamd.ConnectionError:
            logger.error("Lost connection to ClamAV daemon")
            self._connect()  # Try to reconnect
            return ScanResult.ERROR, "Connection to antivirus lost"
        
        except Exception as e:
            logger.error(f"Error scanning file: {e}", exc_info=True)
            return ScanResult.ERROR, f"Scan error: {str(e)}"
    
    def scan_multiple_files(self, file_paths: list) -> dict:
        """
        Scan multiple files
        
        Args:
            file_paths: List of file paths to scan
            
        Returns:
            Dictionary mapping file paths to (ScanResult, details) tuples
        """
        results = {}
        
        for file_path in file_paths:
            result, details = self.scan_file(Path(file_path))
            results[str(file_path)] = (result, details)
        
        return results
    
    def update_signatures(self) -> bool:
        """
        Update virus signatures
        Note: This requires freshclam to be running
        
        Returns:
            True if update was triggered
        """
        try:
            logger.info("Triggering virus signature update")
            # Note: We can't directly update via clamd
            # This should be handled by freshclam service
            # We just log the request
            import subprocess
            result = subprocess.run(
                ['systemctl', 'restart', 'clamav-freshclam'],
                capture_output=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info("Freshclam update triggered")
                return True
            else:
                logger.error(f"Failed to trigger update: {result.stderr}")
                return False
        
        except Exception as e:
            logger.error(f"Error triggering signature update: {e}")
            return False
    
    def get_signature_info(self) -> Optional[str]:
        """
        Get virus signature database information
        
        Returns:
            Signature info string or None
        """
        if not self.cd:
            return None
        
        try:
            stats = self.cd.stats()
            return stats
        except Exception as e:
            logger.error(f"Error getting signature info: {e}")
            return None

