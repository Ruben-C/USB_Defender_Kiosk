"""
USB Defender Kiosk - Document to Image Converter
Converts documents to images to sanitize content
"""

import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional
from PIL import Image
import os
from src.utils.logger import KioskLogger


logger = KioskLogger.get_logger(__name__)
conversion_logger = KioskLogger.get_logger('conversion')


class DocumentConverter:
    """Converts documents to images for sanitization"""
    
    # Document types that need LibreOffice conversion
    OFFICE_EXTENSIONS = {
        'doc', 'docx', 'odt',
        'xls', 'xlsx', 'ods',
        'ppt', 'pptx', 'odp',
        'rtf'
    }
    
    # Image types that need re-encoding
    IMAGE_EXTENSIONS = {
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'tif'
    }
    
    # PDF needs special handling
    PDF_EXTENSION = 'pdf'
    
    def __init__(self, config: dict):
        """
        Initialize document converter
        
        Args:
            config: Conversion configuration dictionary
        """
        self.config = config
        self.output_format = config.get('output_format', 'png').lower()
        self.jpeg_quality = config.get('jpeg_quality', 95)
        self.png_compression = config.get('png_compression', 6)
        self.dpi = config.get('dpi', 150)
        self.max_dimension = config.get('max_dimension', 2400)
        
        # Check if required tools are available
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check if required conversion tools are available"""
        # Check for LibreOffice
        try:
            result = subprocess.run(
                ['soffice', '--version'],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info(f"LibreOffice available: {result.stdout.decode().strip()}")
            else:
                logger.warning("LibreOffice not found - office documents cannot be converted")
        except Exception as e:
            logger.warning(f"LibreOffice not available: {e}")
        
        # Check for ImageMagick (for PDF conversion)
        try:
            result = subprocess.run(
                ['convert', '-version'],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info("ImageMagick available")
            else:
                logger.warning("ImageMagick not found - PDF conversion may not work")
        except Exception as e:
            logger.warning(f"ImageMagick not available: {e}")
    
    def convert_file(self, input_path: Path, output_dir: Path) -> List[Path]:
        """
        Convert a file to image(s)
        
        Args:
            input_path: Path to input file
            output_dir: Directory to save output images
            
        Returns:
            List of paths to generated images
        """
        if not input_path.exists():
            conversion_logger.error(f"Input file not found: {input_path}")
            return []
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        extension = input_path.suffix.lower().lstrip('.')
        base_name = input_path.stem
        
        conversion_logger.info(f"Converting {input_path.name} (type: {extension})")
        
        try:
            if extension in self.OFFICE_EXTENSIONS:
                return self._convert_office_document(input_path, output_dir, base_name)
            elif extension == self.PDF_EXTENSION:
                return self._convert_pdf(input_path, output_dir, base_name)
            elif extension in self.IMAGE_EXTENSIONS:
                return self._convert_image(input_path, output_dir, base_name)
            elif extension == 'txt':
                return self._convert_text(input_path, output_dir, base_name)
            else:
                conversion_logger.warning(f"Unsupported file type: {extension}")
                return []
        
        except Exception as e:
            conversion_logger.error(f"Error converting {input_path.name}: {e}", exc_info=True)
            return []
    
    def _convert_office_document(self, input_path: Path, output_dir: Path, base_name: str) -> List[Path]:
        """
        Convert office document using LibreOffice
        
        Args:
            input_path: Input document path
            output_dir: Output directory
            base_name: Base name for output files
            
        Returns:
            List of generated image paths
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Step 1: Convert to PDF using LibreOffice headless
            conversion_logger.info(f"Converting {input_path.name} to PDF")
            
            result = subprocess.run([
                'soffice',
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', str(temp_path),
                str(input_path)
            ], capture_output=True, timeout=120)
            
            if result.returncode != 0:
                conversion_logger.error(f"LibreOffice conversion failed: {result.stderr.decode()}")
                return []
            
            # Find generated PDF
            pdf_files = list(temp_path.glob('*.pdf'))
            if not pdf_files:
                conversion_logger.error("No PDF generated by LibreOffice")
                return []
            
            pdf_path = pdf_files[0]
            
            # Step 2: Convert PDF to images
            return self._convert_pdf(pdf_path, output_dir, base_name)
    
    def _convert_pdf(self, input_path: Path, output_dir: Path, base_name: str) -> List[Path]:
        """
        Convert PDF to images using ImageMagick
        
        Args:
            input_path: Input PDF path
            output_dir: Output directory
            base_name: Base name for output files
            
        Returns:
            List of generated image paths
        """
        conversion_logger.info(f"Converting PDF {input_path.name} to images")
        
        # Use ImageMagick to convert PDF to images
        output_pattern = output_dir / f"{base_name}_%03d.{self.output_format}"
        
        cmd = [
            'convert',
            '-density', str(self.dpi),
            '-quality', str(self.jpeg_quality) if self.output_format == 'jpeg' else '100',
            str(input_path),
            str(output_pattern)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=180)
            
            if result.returncode != 0:
                conversion_logger.error(f"ImageMagick conversion failed: {result.stderr.decode()}")
                return []
            
            # Find generated images
            generated_images = sorted(output_dir.glob(f"{base_name}_*.{self.output_format}"))
            
            # If only one page, rename to simpler name
            if len(generated_images) == 1:
                new_name = output_dir / f"{base_name}.{self.output_format}"
                generated_images[0].rename(new_name)
                generated_images = [new_name]
            
            conversion_logger.info(f"Generated {len(generated_images)} image(s)")
            return generated_images
        
        except subprocess.TimeoutExpired:
            conversion_logger.error("PDF conversion timed out")
            return []
    
    def _convert_image(self, input_path: Path, output_dir: Path, base_name: str) -> List[Path]:
        """
        Re-encode image to strip metadata and potential threats
        
        Args:
            input_path: Input image path
            output_dir: Output directory
            base_name: Base name for output file
            
        Returns:
            List containing single output image path
        """
        conversion_logger.info(f"Re-encoding image {input_path.name}")
        
        try:
            # Open image with PIL
            with Image.open(input_path) as img:
                # Convert to RGB if necessary
                if img.mode not in ('RGB', 'L'):
                    conversion_logger.debug(f"Converting image mode from {img.mode} to RGB")
                    img = img.convert('RGB')
                
                # Resize if too large
                if max(img.size) > self.max_dimension:
                    conversion_logger.info(f"Resizing image from {img.size}")
                    img.thumbnail((self.max_dimension, self.max_dimension), Image.Resampling.LANCZOS)
                
                # Save with new encoding (strips metadata)
                output_path = output_dir / f"{base_name}.{self.output_format}"
                
                save_kwargs = {}
                if self.output_format in ('jpg', 'jpeg'):
                    save_kwargs['quality'] = self.jpeg_quality
                    save_kwargs['optimize'] = True
                elif self.output_format == 'png':
                    save_kwargs['compress_level'] = self.png_compression
                    save_kwargs['optimize'] = True
                
                img.save(output_path, **save_kwargs)
                
                conversion_logger.info(f"Image saved to {output_path}")
                return [output_path]
        
        except Exception as e:
            conversion_logger.error(f"Error re-encoding image: {e}", exc_info=True)
            return []
    
    def _convert_text(self, input_path: Path, output_dir: Path, base_name: str) -> List[Path]:
        """
        Convert text file to image
        
        Args:
            input_path: Input text file path
            output_dir: Output directory
            base_name: Base name for output file
            
        Returns:
            List containing single output image path
        """
        conversion_logger.info(f"Converting text file {input_path.name} to image")
        
        try:
            # Read text content (limit size)
            with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read(100000)  # Limit to 100KB
            
            # Create image with text using PIL
            from PIL import ImageDraw, ImageFont
            
            # Calculate image size based on text
            font_size = 14
            line_height = font_size + 4
            max_width = 800
            
            # Try to use a monospace font
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()
            
            # Wrap text
            lines = []
            for line in text.split('\n'):
                if not line:
                    lines.append('')
                    continue
                
                # Simple word wrapping
                words = line.split(' ')
                current_line = ''
                for word in words:
                    test_line = f"{current_line} {word}".strip()
                    if len(test_line) * (font_size // 2) > max_width:
                        if current_line:
                            lines.append(current_line)
                        current_line = word
                    else:
                        current_line = test_line
                
                if current_line:
                    lines.append(current_line)
            
            # Limit number of lines
            lines = lines[:200]
            
            # Create image
            img_height = len(lines) * line_height + 40
            img = Image.new('RGB', (max_width + 40, img_height), color='white')
            draw = ImageDraw.Draw(img)
            
            # Draw text
            y = 20
            for line in lines:
                draw.text((20, y), line, fill='black', font=font)
                y += line_height
            
            # Save image
            output_path = output_dir / f"{base_name}.{self.output_format}"
            
            save_kwargs = {}
            if self.output_format in ('jpg', 'jpeg'):
                save_kwargs['quality'] = self.jpeg_quality
            elif self.output_format == 'png':
                save_kwargs['compress_level'] = self.png_compression
            
            img.save(output_path, **save_kwargs)
            
            conversion_logger.info(f"Text converted to image: {output_path}")
            return [output_path]
        
        except Exception as e:
            conversion_logger.error(f"Error converting text to image: {e}", exc_info=True)
            return []

