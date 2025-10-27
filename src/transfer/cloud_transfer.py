"""
USB Defender Kiosk - Cloud Transfer
Transfers files to S3-compatible cloud storage
"""

from pathlib import Path
from typing import List, Dict
from datetime import datetime
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from src.transfer.transfer_manager import TransferManager, TransferResult
from src.utils.logger import KioskLogger


logger = KioskLogger.get_logger('transfer')


class CloudTransferManager(TransferManager):
    """Transfers files to S3-compatible cloud storage"""
    
    def __init__(self, config: dict):
        """
        Initialize cloud transfer manager
        
        Args:
            config: Cloud transfer configuration
        """
        super().__init__(config)
        
        self.storage_type = config.get('type', 's3')
        self.endpoint = config.get('endpoint', 'https://s3.amazonaws.com')
        self.bucket = config.get('bucket', '')
        self.region = config.get('region', 'us-east-1')
        self.access_key = config.get('access_key', '')
        self.secret_key = config.get('secret_key', '')
        self.prefix = config.get('prefix', 'transfers/')
        
        # Ensure prefix ends with /
        if self.prefix and not self.prefix.endswith('/'):
            self.prefix += '/'
        
        self.s3_client = None
        
        if self.access_key and self.secret_key:
            self._init_client()
        else:
            logger.warning("Cloud storage credentials not configured")
        
        logger.info(f"Cloud transfer manager initialized: {self.bucket}")
    
    def _init_client(self):
        """Initialize S3 client"""
        try:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
            
            logger.info("S3 client initialized")
        
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            self.s3_client = None
    
    def transfer_files(self, file_paths: List[Path], session_id: str) -> Dict[str, TransferResult]:
        """
        Transfer files to cloud storage
        
        Args:
            file_paths: List of file paths to transfer
            session_id: Session identifier
            
        Returns:
            Dictionary mapping source paths to TransferResult objects
        """
        logger.info(f"Transferring {len(file_paths)} files to cloud storage")
        
        if not self.s3_client:
            logger.error("S3 client not initialized")
            
            # Mark all as failed
            results = {}
            for file_path in file_paths:
                result = TransferResult(file_path)
                result.error_message = "Cloud storage not configured"
                results[str(file_path)] = result
            
            return results
        
        # Create session prefix
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        session_prefix = f"{self.prefix}{session_id}_{timestamp}/"
        
        results = {}
        
        for file_path in file_paths:
            result = TransferResult(file_path)
            
            try:
                # Determine S3 key
                # Preserve directory structure
                parts = file_path.parts
                if session_id in parts:
                    session_idx = parts.index(session_id)
                    relative_parts = parts[session_idx + 1:]
                    relative_path = '/'.join(relative_parts) if relative_parts else file_path.name
                else:
                    relative_path = file_path.name
                
                s3_key = f"{session_prefix}{relative_path}"
                
                # Upload file
                self.s3_client.upload_file(
                    str(file_path),
                    self.bucket,
                    s3_key
                )
                
                result.destination = f"s3://{self.bucket}/{s3_key}"
                result.success = True
                
                self._log_transfer(file_path, result.destination, True)
            
            except (ClientError, BotoCoreError) as e:
                result.error_message = str(e)
                self._log_transfer(
                    file_path,
                    f"s3://{self.bucket}",
                    False,
                    str(e)
                )
            
            except Exception as e:
                result.error_message = str(e)
                logger.error(f"Unexpected error uploading {file_path.name}: {e}", exc_info=True)
            
            results[str(file_path)] = result
        
        # Summary
        successful = sum(1 for r in results.values() if r.success)
        logger.info(f"Cloud transfer complete: {successful}/{len(file_paths)} successful")
        
        return results
    
    def test_connection(self) -> bool:
        """
        Test cloud storage connection
        
        Returns:
            True if connection successful
        """
        if not self.s3_client:
            return False
        
        try:
            # Try to head bucket
            self.s3_client.head_bucket(Bucket=self.bucket)
            
            logger.info("Cloud storage connection test successful")
            return True
        
        except ClientError as e:
            logger.error(f"Cloud storage connection test failed: {e}")
            return False
        
        except Exception as e:
            logger.error(f"Unexpected error testing cloud connection: {e}")
            return False
    
    def get_destination_info(self) -> str:
        """
        Get destination information
        
        Returns:
            Destination description
        """
        return f"Cloud storage: s3://{self.bucket}/{self.prefix}"

