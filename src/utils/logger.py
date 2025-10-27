"""
USB Defender Kiosk - Logging Utilities
Centralized logging configuration and utilities
"""

import logging
import logging.handlers
import os
from pathlib import Path
from datetime import datetime
from typing import Optional


class KioskLogger:
    """Centralized logger for the USB Defender Kiosk application"""
    
    _loggers = {}
    _configured = False
    
    @classmethod
    def configure(cls, config: dict):
        """
        Configure the logging system
        
        Args:
            config: Logging configuration dictionary
        """
        if cls._configured:
            return
            
        log_dir = Path(config.get('directory', '/var/log/usb-defender'))
        log_dir.mkdir(parents=True, exist_ok=True)
        
        level_str = config.get('level', 'INFO')
        level = getattr(logging, level_str.upper(), logging.INFO)
        
        max_bytes = config.get('max_size_mb', 10) * 1024 * 1024
        backup_count = config.get('backup_count', 5)
        console_output = config.get('console', False)
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        
        # Add console handler if requested
        if console_output:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(detailed_formatter)
            console_handler.setLevel(level)
            root_logger.addHandler(console_handler)
        
        # Add main application log file
        app_log_file = log_dir / 'app.log'
        app_handler = logging.handlers.RotatingFileHandler(
            app_log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        app_handler.setFormatter(detailed_formatter)
        app_handler.setLevel(level)
        root_logger.addHandler(app_handler)
        
        # Create separate audit log (always INFO level, never rotates)
        audit_log_file = log_dir / 'audit.log'
        audit_handler = logging.FileHandler(audit_log_file)
        audit_handler.setFormatter(simple_formatter)
        audit_handler.setLevel(logging.INFO)
        
        audit_logger = logging.getLogger('audit')
        audit_logger.addHandler(audit_handler)
        audit_logger.setLevel(logging.INFO)
        audit_logger.propagate = False
        
        # Create separate conversion log
        conversion_log_file = log_dir / 'conversion.log'
        conversion_handler = logging.handlers.RotatingFileHandler(
            conversion_log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        conversion_handler.setFormatter(detailed_formatter)
        conversion_logger = logging.getLogger('conversion')
        conversion_logger.addHandler(conversion_handler)
        conversion_logger.setLevel(level)
        conversion_logger.propagate = False
        
        # Create separate transfer log
        transfer_log_file = log_dir / 'transfer.log'
        transfer_handler = logging.handlers.RotatingFileHandler(
            transfer_log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        transfer_handler.setFormatter(detailed_formatter)
        transfer_logger = logging.getLogger('transfer')
        transfer_logger.addHandler(transfer_handler)
        transfer_logger.setLevel(level)
        transfer_logger.propagate = False
        
        cls._configured = True
        
        # Log configuration complete
        logger = logging.getLogger(__name__)
        logger.info("Logging system configured")
        logger.info(f"Log directory: {log_dir}")
        logger.info(f"Log level: {level_str}")
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Get or create a logger with the given name
        
        Args:
            name: Logger name (typically __name__)
            
        Returns:
            Logger instance
        """
        if name not in cls._loggers:
            cls._loggers[name] = logging.getLogger(name)
        return cls._loggers[name]
    
    @classmethod
    def audit(cls, message: str, **kwargs):
        """
        Write an audit log entry
        
        Args:
            message: Audit message
            **kwargs: Additional context to log
        """
        audit_logger = logging.getLogger('audit')
        
        if kwargs:
            context = ' | '.join(f"{k}={v}" for k, v in kwargs.items())
            audit_logger.info(f"{message} | {context}")
        else:
            audit_logger.info(message)
    
    @classmethod
    def audit_usb_insert(cls, device_path: str, device_name: str, device_size: str):
        """Log USB device insertion"""
        cls.audit(
            "USB_INSERTED",
            device=device_path,
            name=device_name,
            size=device_size
        )
    
    @classmethod
    def audit_usb_remove(cls, device_path: str):
        """Log USB device removal"""
        cls.audit("USB_REMOVED", device=device_path)
    
    @classmethod
    def audit_file_scan(cls, file_path: str, result: str, details: str = ""):
        """Log file scan result"""
        cls.audit(
            "FILE_SCANNED",
            file=file_path,
            result=result,
            details=details
        )
    
    @classmethod
    def audit_file_conversion(cls, source: str, destination: str, status: str):
        """Log file conversion"""
        cls.audit(
            "FILE_CONVERTED",
            source=source,
            destination=destination,
            status=status
        )
    
    @classmethod
    def audit_file_transfer(cls, file_path: str, destination: str, status: str):
        """Log file transfer"""
        cls.audit(
            "FILE_TRANSFERRED",
            file=file_path,
            destination=destination,
            status=status
        )
    
    @classmethod
    def audit_session_start(cls, session_id: str):
        """Log transfer session start"""
        cls.audit("SESSION_STARTED", session_id=session_id)
    
    @classmethod
    def audit_session_end(cls, session_id: str, file_count: int, status: str):
        """Log transfer session end"""
        cls.audit(
            "SESSION_ENDED",
            session_id=session_id,
            files=file_count,
            status=status
        )

