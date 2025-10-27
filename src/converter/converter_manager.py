"""
USB Defender Kiosk - Converter Manager
Coordinates the conversion of multiple files
"""

from pathlib import Path
from typing import List, Dict, Callable, Optional
import json
from datetime import datetime
from src.converter.document_to_image import DocumentConverter
from src.utils.logger import KioskLogger


logger = KioskLogger.get_logger(__name__)


class ConversionResult:
    """Result of file conversion"""
    
    def __init__(self, source_path: Path):
        """
        Initialize conversion result
        
        Args:
            source_path: Path to source file
        """
        self.source_path = source_path
        self.output_paths: List[Path] = []
        self.success = False
        self.error_message = ""
    
    def __repr__(self):
        status = "SUCCESS" if self.success else "FAILED"
        return f"ConversionResult({self.source_path.name}, {status}, {len(self.output_paths)} files)"


class ConverterManager:
    """Manages conversion of multiple files"""
    
    def __init__(self, config: dict, output_base_dir: Path):
        """
        Initialize converter manager
        
        Args:
            config: Conversion configuration
            output_base_dir: Base directory for output files
        """
        self.config = config
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)
        
        self.converter = DocumentConverter(config)
        
        self.progress_callback: Optional[Callable[[int, int, str], None]] = None
        
        logger.info(f"Converter manager initialized, output dir: {output_base_dir}")
    
    def convert_files(self, file_paths: List[Path], session_id: str) -> Dict[str, ConversionResult]:
        """
        Convert multiple files
        
        Args:
            file_paths: List of file paths to convert
            session_id: Session identifier for organizing output
            
        Returns:
            Dictionary mapping source paths to ConversionResult objects
        """
        logger.info(f"Converting {len(file_paths)} files for session {session_id}")
        
        # Create session output directory
        session_dir = self.output_base_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        results = {}
        total_files = len(file_paths)
        
        for idx, file_path in enumerate(file_paths, 1):
            # Update progress
            if self.progress_callback:
                self.progress_callback(idx, total_files, file_path.name)
            
            logger.info(f"Converting file {idx}/{total_files}: {file_path.name}")
            
            result = ConversionResult(file_path)
            
            try:
                # Create subdirectory for this file's output
                file_output_dir = session_dir / file_path.stem
                file_output_dir.mkdir(parents=True, exist_ok=True)
                
                # Convert file
                output_paths = self.converter.convert_file(file_path, file_output_dir)
                
                if output_paths:
                    result.output_paths = output_paths
                    result.success = True
                    logger.info(f"Successfully converted {file_path.name} to {len(output_paths)} image(s)")
                    
                    # Audit log
                    for output_path in output_paths:
                        KioskLogger.audit_file_conversion(
                            str(file_path),
                            str(output_path),
                            "SUCCESS"
                        )
                else:
                    result.error_message = "Conversion produced no output"
                    logger.error(f"Conversion failed for {file_path.name}: no output")
                    
                    KioskLogger.audit_file_conversion(
                        str(file_path),
                        "",
                        "FAILED: No output"
                    )
            
            except Exception as e:
                result.error_message = str(e)
                logger.error(f"Error converting {file_path.name}: {e}", exc_info=True)
                
                KioskLogger.audit_file_conversion(
                    str(file_path),
                    "",
                    f"FAILED: {str(e)}"
                )
            
            results[str(file_path)] = result
        
        # Generate manifest if configured
        if self.config.get('create_manifest', True):
            self._create_manifest(results, session_dir)
        
        # Summary
        successful = sum(1 for r in results.values() if r.success)
        logger.info(f"Conversion complete: {successful}/{total_files} successful")
        
        return results
    
    def _create_manifest(self, results: Dict[str, ConversionResult], session_dir: Path):
        """
        Create manifest file documenting conversions
        
        Args:
            results: Conversion results
            session_dir: Session output directory
        """
        try:
            manifest = {
                'session_id': session_dir.name,
                'timestamp': datetime.now().isoformat(),
                'total_files': len(results),
                'successful': sum(1 for r in results.values() if r.success),
                'failed': sum(1 for r in results.values() if not r.success),
                'conversions': []
            }
            
            for source_path_str, result in results.items():
                source_path = Path(source_path_str)
                
                conversion_entry = {
                    'source_file': source_path.name,
                    'source_path': str(source_path),
                    'success': result.success,
                    'output_files': [p.name for p in result.output_paths],
                    'output_paths': [str(p) for p in result.output_paths],
                }
                
                if not result.success:
                    conversion_entry['error'] = result.error_message
                
                manifest['conversions'].append(conversion_entry)
            
            # Write manifest
            manifest_path = session_dir / 'manifest.json'
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            logger.info(f"Manifest created: {manifest_path}")
        
        except Exception as e:
            logger.error(f"Error creating manifest: {e}", exc_info=True)
    
    def set_progress_callback(self, callback: Callable[[int, int, str], None]):
        """
        Set progress callback function
        
        Args:
            callback: Function taking (current, total, filename)
        """
        self.progress_callback = callback
    
    def get_conversion_summary(self, results: Dict[str, ConversionResult]) -> dict:
        """
        Get summary of conversion results
        
        Args:
            results: Conversion results
            
        Returns:
            Summary dictionary
        """
        total = len(results)
        successful = sum(1 for r in results.values() if r.success)
        failed = total - successful
        
        total_images = sum(len(r.output_paths) for r in results.values() if r.success)
        
        failed_files = [
            {
                'filename': Path(path).name,
                'error': result.error_message
            }
            for path, result in results.items()
            if not result.success
        ]
        
        return {
            'total_files': total,
            'successful': successful,
            'failed': failed,
            'total_images_generated': total_images,
            'failed_files': failed_files
        }

