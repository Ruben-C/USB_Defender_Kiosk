"""
USB Defender Kiosk - Network Transfer
Transfers files to SMB/CIFS network share
"""

from pathlib import Path
from typing import List, Dict
from datetime import datetime
import tempfile
from smb.SMBConnection import SMBConnection
from src.transfer.transfer_manager import TransferManager, TransferResult
from src.utils.logger import KioskLogger


logger = KioskLogger.get_logger('transfer')


class NetworkTransferManager(TransferManager):
    """Transfers files to network share via SMB/CIFS"""
    
    def __init__(self, config: dict):
        """
        Initialize network transfer manager
        
        Args:
            config: Network transfer configuration
        """
        super().__init__(config)
        
        # Parse server and share from UNC path or separate config
        server_path = config.get('server', '//server/share')
        if server_path.startswith('//'):
            parts = server_path.lstrip('/').split('/', 1)
            self.server = parts[0]
            self.share_name = parts[1] if len(parts) > 1 else config.get('share_path', 'share')
        else:
            self.server = server_path
            self.share_name = config.get('share_path', 'share')
        
        self.username = config.get('username', '')
        self.password = config.get('password', '')
        self.domain = config.get('domain', 'WORKGROUP')
        self.timeout = config.get('timeout', 30)
        
        self.client_name = 'USB-DEFENDER-KIOSK'
        self.server_name = self.server.split('.')[0].upper()  # NetBIOS name
        
        logger.info(f"Network transfer manager initialized: //{self.server}/{self.share_name}")
    
    def _connect(self) -> SMBConnection:
        """
        Create SMB connection
        
        Returns:
            SMBConnection instance
            
        Raises:
            Exception if connection fails
        """
        conn = SMBConnection(
            self.username,
            self.password,
            self.client_name,
            self.server_name,
            domain=self.domain,
            use_ntlm_v2=True,
            is_direct_tcp=True
        )
        
        # Connect to server
        if not conn.connect(self.server, 445, timeout=self.timeout):
            raise ConnectionError(f"Failed to connect to {self.server}")
        
        return conn
    
    def transfer_files(self, file_paths: List[Path], session_id: str) -> Dict[str, TransferResult]:
        """
        Transfer files to network share
        
        Args:
            file_paths: List of file paths to transfer
            session_id: Session identifier
            
        Returns:
            Dictionary mapping source paths to TransferResult objects
        """
        logger.info(f"Transferring {len(file_paths)} files to network share")
        
        results = {}
        
        try:
            # Connect to share
            conn = self._connect()
            
            # Create session folder on share
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            remote_base = f"{session_id}_{timestamp}"
            
            # Transfer each file
            for file_path in file_paths:
                result = TransferResult(file_path)
                
                try:
                    # Determine remote path
                    # Preserve directory structure
                    parts = file_path.parts
                    if session_id in parts:
                        session_idx = parts.index(session_id)
                        relative_parts = parts[session_idx + 1:]
                        relative_path = '/'.join(relative_parts) if relative_parts else file_path.name
                    else:
                        relative_path = file_path.name
                    
                    remote_path = f"{remote_base}/{relative_path}".replace('\\', '/')
                    
                    # Create directory structure if needed
                    remote_dir = '/'.join(remote_path.split('/')[:-1])
                    if remote_dir:
                        self._create_remote_directory(conn, self.share_name, remote_dir)
                    
                    # Upload file
                    with open(file_path, 'rb') as f:
                        conn.storeFile(self.share_name, remote_path, f, timeout=self.timeout)
                    
                    result.destination = f"//{self.server}/{self.share_name}/{remote_path}"
                    result.success = True
                    
                    self._log_transfer(file_path, result.destination, True)
                
                except Exception as e:
                    result.error_message = str(e)
                    self._log_transfer(
                        file_path,
                        f"//{self.server}/{self.share_name}",
                        False,
                        str(e)
                    )
                
                results[str(file_path)] = result
            
            # Close connection
            conn.close()
        
        except Exception as e:
            logger.error(f"Network transfer failed: {e}", exc_info=True)
            
            # Mark all remaining files as failed
            for file_path in file_paths:
                if str(file_path) not in results:
                    result = TransferResult(file_path)
                    result.error_message = f"Connection failed: {str(e)}"
                    results[str(file_path)] = result
        
        # Summary
        successful = sum(1 for r in results.values() if r.success)
        logger.info(f"Network transfer complete: {successful}/{len(file_paths)} successful")
        
        return results
    
    def _create_remote_directory(self, conn: SMBConnection, share: str, path: str):
        """
        Create remote directory structure
        
        Args:
            conn: SMB connection
            share: Share name
            path: Directory path to create
        """
        # Split path and create each level
        parts = path.split('/')
        current_path = ''
        
        for part in parts:
            if not part:
                continue
            
            current_path = f"{current_path}/{part}" if current_path else part
            
            try:
                # Try to create directory (will fail if exists, which is fine)
                conn.createDirectory(share, current_path)
                logger.debug(f"Created remote directory: {current_path}")
            except Exception:
                # Directory probably exists
                pass
    
    def test_connection(self) -> bool:
        """
        Test network share connection
        
        Returns:
            True if connection successful
        """
        try:
            conn = self._connect()
            
            # Try to list files in share root
            conn.listPath(self.share_name, '/')
            
            conn.close()
            
            logger.info("Network share connection test successful")
            return True
        
        except Exception as e:
            logger.error(f"Network share connection test failed: {e}")
            return False
    
    def get_destination_info(self) -> str:
        """
        Get destination information
        
        Returns:
            Destination description
        """
        return f"Network share: //{self.server}/{self.share_name}"

