"""
USB Defender Kiosk - Local Transfer
Transfers files to local filesystem directory
"""

import shutil
from pathlib import Path
from typing import List, Dict
from datetime import datetime
from src.transfer.transfer_manager import TransferManager, TransferResult
from src.utils.logger import KioskLogger


logger = KioskLogger.get_logger('transfer')


class LocalTransferManager(TransferManager):
    """Transfers files to local directory"""
    
    def __init__(self, config: dict):
        """
        Initialize local transfer manager
        
        Args:
            config: Local transfer configuration
        """
        super().__init__(config)
        
        self.output_directory = Path(config.get('output_directory', '/var/usb-defender/transfers'))
        self.create_session_folders = config.get('create_session_folders', True)
        self.session_folder_format = config.get('session_folder_format', '%Y%m%d_%H%M%S')
        
        # Create base directory if it doesn't exist
        self.output_directory.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Local transfer manager initialized: {self.output_directory}")
    
    def transfer_files(self, file_paths: List[Path], session_id: str) -> Dict[str, TransferResult]:
        """
        Transfer files to local directory
        
        Args:
            file_paths: List of file paths to transfer
            session_id: Session identifier
            
        Returns:
            Dictionary mapping source paths to TransferResult objects
        """
        logger.info(f"Transferring {len(file_paths)} files to local directory")
        
        # Determine destination directory
        if self.create_session_folders:
            timestamp = datetime.now().strftime(self.session_folder_format)
            dest_dir = self.output_directory / f"{session_id}_{timestamp}"
        else:
            dest_dir = self.output_directory
        
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        results = {}
        
        for file_path in file_paths:
            result = TransferResult(file_path)
            
            try:
                # Preserve directory structure relative to session
                # If file is /tmp/session123/file1/page1.png
                # We want to copy to dest_dir/file1/page1.png
                
                # Find the relative path from the session directory
                # Assume files are structured as: base/session_id/file_name/image.png
                parts = file_path.parts
                
                # Find session_id in path
                if session_id in parts:
                    session_idx = parts.index(session_id)
                    relative_parts = parts[session_idx + 1:]  # Everything after session_id
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
        
        # Summary
        successful = sum(1 for r in results.values() if r.success)
        logger.info(f"Local transfer complete: {successful}/{len(file_paths)} successful")
        logger.info(f"Files transferred to: {dest_dir}")
        
        return results
    
    def test_connection(self) -> bool:
        """
        Test if destination directory is writable
        
        Returns:
            True if directory is accessible and writable
        """
        try:
            # Try to create a test file
            test_file = self.output_directory / '.test_write'
            test_file.write_text('test')
            test_file.unlink()
            
            logger.info("Local transfer destination is accessible")
            return True
        
        except Exception as e:
            logger.error(f"Local transfer destination not accessible: {e}")
            return False
    
    def get_destination_info(self) -> str:
        """
        Get destination information
        
        Returns:
            Destination description
        """
        return f"Local directory: {self.output_directory}"

