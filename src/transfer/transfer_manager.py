"""
USB Defender Kiosk - Transfer Manager
Abstract base for file transfer implementations
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict
from src.utils.logger import KioskLogger


logger = KioskLogger.get_logger('transfer')


class TransferResult:
    """Result of file transfer operation"""
    
    def __init__(self, source_path: Path, destination: str = ""):
        """
        Initialize transfer result
        
        Args:
            source_path: Source file path
            destination: Destination path/URL
        """
        self.source_path = source_path
        self.destination = destination
        self.success = False
        self.error_message = ""
    
    def __repr__(self):
        status = "SUCCESS" if self.success else "FAILED"
        return f"TransferResult({self.source_path.name}, {status})"


class TransferManager(ABC):
    """Abstract base class for transfer implementations"""
    
    def __init__(self, config: dict):
        """
        Initialize transfer manager
        
        Args:
            config: Transfer configuration
        """
        self.config = config
    
    @abstractmethod
    def transfer_files(self, file_paths: List[Path], session_id: str) -> Dict[str, TransferResult]:
        """
        Transfer files to destination
        
        Args:
            file_paths: List of file paths to transfer
            session_id: Session identifier
            
        Returns:
            Dictionary mapping source paths to TransferResult objects
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test if destination is accessible
        
        Returns:
            True if connection successful
        """
        pass
    
    @abstractmethod
    def get_destination_info(self) -> str:
        """
        Get human-readable destination information
        
        Returns:
            Destination description
        """
        pass
    
    def _log_transfer(self, source: Path, destination: str, success: bool, error: str = ""):
        """
        Log transfer operation
        
        Args:
            source: Source file path
            destination: Destination path
            success: Whether transfer was successful
            error: Error message if failed
        """
        status = "SUCCESS" if success else f"FAILED: {error}"
        KioskLogger.audit_file_transfer(str(source), destination, status)
        
        if success:
            logger.info(f"Transferred {source.name} to {destination}")
        else:
            logger.error(f"Failed to transfer {source.name}: {error}")


def create_transfer_manager(config: dict) -> TransferManager:
    """
    Factory function to create appropriate transfer manager
    
    Args:
        config: Full application configuration
        
    Returns:
        TransferManager instance
    """
    from src.transfer.local_transfer import LocalTransferManager
    from src.transfer.network_transfer import NetworkTransferManager
    from src.transfer.cloud_transfer import CloudTransferManager
    from src.transfer.secure_usb_transfer import SecureUSBTransferManager
    
    transfer_config = config.get('transfer', {})
    method = transfer_config.get('method', 'local').lower()
    
    if method == 'local':
        return LocalTransferManager(transfer_config.get('local', {}))
    elif method == 'network':
        return NetworkTransferManager(transfer_config.get('network', {}))
    elif method == 'cloud':
        return CloudTransferManager(transfer_config.get('cloud', {}))
    elif method == 'secure_usb':
        return SecureUSBTransferManager(transfer_config.get('secure_usb', {}))
    else:
        logger.warning(f"Unknown transfer method '{method}', defaulting to secure USB (airgapped)")
        return SecureUSBTransferManager(transfer_config.get('secure_usb', {}))

