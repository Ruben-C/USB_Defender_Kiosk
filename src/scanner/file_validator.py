"""
USB Defender Kiosk - File Validator
Validates file types and checks file properties
"""

import magic
from pathlib import Path
from typing import Tuple, Optional
from src.utils.logger import KioskLogger


logger = KioskLogger.get_logger(__name__)


class FileValidator:
    """Validates file types and properties"""
    
    # Known dangerous MIME types
    DANGEROUS_MIME_TYPES = {
        'application/x-executable',
        'application/x-sharedlib',
        'application/x-mach-binary',
        'application/x-dosexec',
        'application/x-msdownload',
        'application/x-ms-dos-executable',
        'application/x-sh',
        'application/x-shellscript',
        'application/x-javascript',
        'application/javascript',
        'text/x-shellscript',
        'text/x-python',
        'application/x-perl',
        'application/x-ruby',
    }
    
    def __init__(self, config: dict):
        """
        Initialize file validator
        
        Args:
            config: File configuration dictionary
        """
        self.config = config
        self.max_file_size = config.get('max_size_mb', 100) * 1024 * 1024
        self.allowed_extensions = set(ext.lower() for ext in config.get('allowed_extensions', []))
        self.blocked_extensions = set(ext.lower() for ext in config.get('blocked_extensions', []))
        
        # Initialize python-magic
        try:
            self.magic = magic.Magic(mime=True)
            logger.info("File validator initialized with python-magic")
        except Exception as e:
            logger.error(f"Failed to initialize python-magic: {e}")
            self.magic = None
    
    def validate_file(self, file_path: Path) -> Tuple[bool, str]:
        """
        Validate a file
        
        Args:
            file_path: Path to file to validate
            
        Returns:
            Tuple of (is_valid, reason)
        """
        if not file_path.exists():
            return False, "File does not exist"
        
        if not file_path.is_file():
            return False, "Not a regular file"
        
        # Check file size
        try:
            file_size = file_path.stat().st_size
            if file_size == 0:
                return False, "File is empty"
            
            if file_size > self.max_file_size:
                max_mb = self.max_file_size / (1024 * 1024)
                return False, f"File too large (max {max_mb:.0f} MB)"
        
        except Exception as e:
            logger.error(f"Error checking file size: {e}")
            return False, "Cannot read file"
        
        # Check extension
        extension = file_path.suffix.lower().lstrip('.')
        
        # Check if explicitly blocked
        if extension in self.blocked_extensions:
            logger.warning(f"Blocked file extension: {extension}")
            return False, f"File type not allowed: .{extension}"
        
        # Check if in allowed list
        if self.allowed_extensions and extension not in self.allowed_extensions:
            logger.warning(f"Extension not in allowed list: {extension}")
            return False, f"File type not allowed: .{extension}"
        
        # Validate MIME type using magic
        if self.magic:
            try:
                mime_type = self.magic.from_file(str(file_path))
                logger.debug(f"Detected MIME type for {file_path.name}: {mime_type}")
                
                # Check for dangerous MIME types
                if mime_type in self.DANGEROUS_MIME_TYPES:
                    logger.warning(f"Dangerous MIME type detected: {mime_type}")
                    return False, "Executable or script file not allowed"
                
                # Verify MIME type matches extension (basic check)
                expected_mime = self._get_expected_mime(extension)
                if expected_mime and not mime_type.startswith(expected_mime):
                    logger.warning(
                        f"MIME type mismatch: expected {expected_mime}, got {mime_type}"
                    )
                    # Don't reject, just log warning - some files have unexpected MIME types
            
            except Exception as e:
                logger.error(f"Error detecting MIME type: {e}")
                # Don't reject file on MIME detection error
        
        logger.info(f"File validation passed: {file_path.name}")
        return True, "Valid"
    
    def _get_expected_mime(self, extension: str) -> Optional[str]:
        """
        Get expected MIME type prefix for extension
        
        Args:
            extension: File extension (without dot)
            
        Returns:
            Expected MIME type prefix or None
        """
        mime_map = {
            'pdf': 'application/pdf',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats',
            'ppt': 'application/vnd.ms-powerpoint',
            'pptx': 'application/vnd.openxmlformats',
            'odt': 'application/vnd.oasis',
            'ods': 'application/vnd.oasis',
            'odp': 'application/vnd.oasis',
            'txt': 'text/',
            'rtf': 'application/rtf',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'bmp': 'image/bmp',
            'tiff': 'image/tiff',
        }
        
        return mime_map.get(extension.lower())
    
    def validate_multiple_files(self, file_paths: list) -> dict:
        """
        Validate multiple files
        
        Args:
            file_paths: List of file paths to validate
            
        Returns:
            Dictionary mapping file paths to (is_valid, reason) tuples
        """
        results = {}
        
        for file_path in file_paths:
            is_valid, reason = self.validate_file(Path(file_path))
            results[str(file_path)] = (is_valid, reason)
        
        return results
    
    def check_total_size(self, file_paths: list) -> Tuple[bool, int]:
        """
        Check if total size of files is within limit
        
        Args:
            file_paths: List of file paths
            
        Returns:
            Tuple of (is_within_limit, total_size_bytes)
        """
        max_total = self.config.get('max_total_size_mb', 500) * 1024 * 1024
        
        total_size = 0
        for file_path in file_paths:
            try:
                total_size += Path(file_path).stat().st_size
            except Exception as e:
                logger.error(f"Error getting file size for {file_path}: {e}")
        
        is_within_limit = total_size <= max_total
        
        if not is_within_limit:
            logger.warning(f"Total size {total_size} exceeds limit {max_total}")
        
        return is_within_limit, total_size
    
    def get_file_info(self, file_path: Path) -> dict:
        """
        Get file information
        
        Args:
            file_path: Path to file
            
        Returns:
            Dictionary with file information
        """
        info = {
            'name': file_path.name,
            'extension': file_path.suffix.lower().lstrip('.'),
            'size': 0,
            'size_human': '0 B',
            'mime_type': 'unknown',
        }
        
        try:
            stat = file_path.stat()
            info['size'] = stat.st_size
            info['size_human'] = self._format_size(stat.st_size)
            
            if self.magic:
                info['mime_type'] = self.magic.from_file(str(file_path))
        
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
        
        return info
    
    def _format_size(self, size_bytes: int) -> str:
        """
        Format size in human-readable format
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Formatted size string
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

