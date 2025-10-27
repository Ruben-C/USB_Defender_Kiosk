"""
USB Defender Kiosk - Main Window
Main kiosk interface
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QProgressBar, QTextEdit, QMessageBox, QDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from pathlib import Path
from typing import List, Optional
import uuid
from datetime import datetime

from src.usb.device_monitor import USBDeviceMonitor, USBDevice
from src.usb.file_browser import FileBrowserWidget
from src.scanner.clamav_scanner import ClamAVScanner, ScanResult
from src.scanner.file_validator import FileValidator
from src.converter.converter_manager import ConverterManager
from src.transfer.transfer_manager import create_transfer_manager
from src.transfer.secure_usb_transfer import SecureUSBTransferManager
from src.utils.logger import KioskLogger
from src.utils.config import ConfigManager


logger = KioskLogger.get_logger(__name__)


class ProcessingThread(QThread):
    """Worker thread for file processing"""
    
    progress = pyqtSignal(str, int)  # (message, percentage)
    finished = pyqtSignal(bool, str, dict)  # (success, message, results)
    
    def __init__(self, files: List[Path], config: ConfigManager, session_id: str):
        super().__init__()
        self.files = files
        self.config = config
        self.session_id = session_id
        self.temp_dir = Path('/var/usb-defender/temp') / session_id
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def run(self):
        """Run processing workflow"""
        try:
            total_steps = len(self.files) * 3  # Validate, scan, convert
            current_step = 0
            
            # Step 1: Validate files
            self.progress.emit("Validating files...", 0)
            validator = FileValidator(self.config.get_file_config())
            
            valid_files = []
            for file_path in self.files:
                is_valid, reason = validator.validate_file(file_path)
                if is_valid:
                    valid_files.append(file_path)
                else:
                    logger.warning(f"File validation failed for {file_path.name}: {reason}")
                
                current_step += 1
                progress_pct = int((current_step / total_steps) * 100)
                self.progress.emit(f"Validating: {file_path.name}", progress_pct)
            
            if not valid_files:
                self.finished.emit(False, "No valid files to process", {})
                return
            
            # Step 2: Scan files with ClamAV
            self.progress.emit("Scanning for malware...", 33)
            scanner = ClamAVScanner(self.config.get_clamav_config())
            
            if not scanner.is_available():
                logger.warning("ClamAV not available, skipping virus scan")
            
            clean_files = []
            infected_count = 0
            
            for file_path in valid_files:
                if scanner.is_available():
                    scan_result, details = scanner.scan_file(file_path)
                    
                    if scan_result == ScanResult.CLEAN:
                        clean_files.append(file_path)
                    elif scan_result == ScanResult.INFECTED:
                        infected_count += 1
                        logger.warning(f"Infected file skipped: {file_path.name} - {details}")
                    else:
                        # On error, include file but log warning
                        clean_files.append(file_path)
                        logger.warning(f"Scan error for {file_path.name}, including anyway")
                else:
                    clean_files.append(file_path)
                
                current_step += 1
                progress_pct = int((current_step / total_steps) * 100)
                self.progress.emit(f"Scanning: {file_path.name}", progress_pct)
            
            if not clean_files:
                message = f"All files were infected or invalid ({infected_count} infected)"
                self.finished.emit(False, message, {})
                return
            
            # Step 3: Convert files to images
            self.progress.emit("Converting files to images...", 66)
            converter = ConverterManager(
                self.config.get_conversion_config(),
                self.temp_dir
            )
            
            def conversion_progress(current, total, filename):
                current_step_local = current_step + current
                progress_pct = int((current_step_local / total_steps) * 100)
                self.progress.emit(f"Converting: {filename}", progress_pct)
            
            converter.set_progress_callback(conversion_progress)
            
            conversion_results = converter.convert_files(clean_files, self.session_id)
            
            # Collect all generated images
            converted_images = []
            for result in conversion_results.values():
                if result.success:
                    converted_images.extend(result.output_paths)
            
            if not converted_images:
                self.finished.emit(False, "File conversion failed", {})
                return
            
            # Step 4: Ready for transfer
            self.progress.emit("Conversion complete!", 100)
            
            summary = {
                'original_files': len(self.files),
                'valid_files': len(valid_files),
                'clean_files': len(clean_files),
                'infected_files': infected_count,
                'images_generated': len(converted_images),
                'converted_images': converted_images,
                'conversion_summary': converter.get_conversion_summary(conversion_results)
            }
            
            message = f"Successfully processed {len(clean_files)} file(s)\n"
            message += f"Generated {len(converted_images)} image(s)\n"
            
            if infected_count > 0:
                message += f"\nWarning: {infected_count} infected file(s) were skipped"
            
            self.finished.emit(True, message, summary)
        
        except Exception as e:
            logger.error(f"Processing error: {e}", exc_info=True)
            self.finished.emit(False, f"Error: {str(e)}", {})


class MainWindow(QMainWindow):
    """Main kiosk window"""
    
    def __init__(self, config: ConfigManager):
        """
        Initialize main window
        
        Args:
            config: Configuration manager
        """
        super().__init__()
        
        self.config = config
        self.usb_monitor: Optional[USBDeviceMonitor] = None
        self.current_device: Optional[USBDevice] = None
        self.session_id: Optional[str] = None
        self.waiting_for_secure_usb = False
        self.converted_images: List[Path] = []
        
        self._init_ui()
        self._setup_usb_monitor()
        self._setup_shortcuts()
        
        # Start on waiting screen
        self.show_waiting_screen()
        
        logger.info("Main window initialized")
    
    def _init_ui(self):
        """Initialize user interface"""
        kiosk_config = self.config.get_kiosk_config()
        
        # Window setup
        self.setWindowTitle("USB Defender Kiosk")
        
        if kiosk_config.get('fullscreen', True):
            self.showFullScreen()
        else:
            self.resize(1024, 768)
        
        # Central widget with stacked layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Stacked widget for different screens
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        
        # Create screens
        self.waiting_screen = self._create_waiting_screen()
        self.file_selection_screen = self._create_file_selection_screen()
        self.processing_screen = self._create_processing_screen()
        self.secure_usb_screen = self._create_secure_usb_screen()
        self.complete_screen = self._create_complete_screen()
        
        self.stack.addWidget(self.waiting_screen)
        self.stack.addWidget(self.file_selection_screen)
        self.stack.addWidget(self.processing_screen)
        self.stack.addWidget(self.secure_usb_screen)
        self.stack.addWidget(self.complete_screen)
        
        # Apply UI scaling
        font_scale = self.config.get('ui.font_scale', 1.2)
        font = self.font()
        font.setPointSizeF(font.pointSizeF() * font_scale)
        self.setFont(font)
    
    def _create_waiting_screen(self) -> QWidget:
        """Create waiting for USB screen"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Title
        title = QLabel("USB Defender Kiosk")
        title.setStyleSheet("font-size: 36pt; font-weight: bold; margin-bottom: 30px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Icon/Message
        message = QLabel("Please insert USB drive")
        message.setStyleSheet("font-size: 24pt; margin-bottom: 20px;")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(message)
        
        # Instructions
        instructions = QLabel("Your files will be scanned and safely transferred")
        instructions.setStyleSheet("font-size: 14pt; color: #666;")
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(instructions)
        
        return widget
    
    def _create_file_selection_screen(self) -> QWidget:
        """Create file selection screen"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        self.device_label = QLabel("USB Device Connected")
        self.device_label.setStyleSheet("font-size: 20pt; font-weight: bold;")
        layout.addWidget(self.device_label)
        
        # File browser
        self.file_browser = FileBrowserWidget(self.config.get_file_config())
        layout.addWidget(self.file_browser)
        
        # Button row
        button_layout = QHBoxLayout()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumHeight(60)
        self.cancel_btn.setStyleSheet("font-size: 16pt;")
        self.cancel_btn.clicked.connect(self.cancel_transfer)
        button_layout.addWidget(self.cancel_btn)
        
        button_layout.addStretch()
        
        self.transfer_btn = QPushButton("Transfer Selected Files")
        self.transfer_btn.setMinimumHeight(60)
        self.transfer_btn.setStyleSheet("font-size: 16pt; font-weight: bold; background-color: #4CAF50; color: white;")
        self.transfer_btn.clicked.connect(self.start_transfer)
        self.transfer_btn.setEnabled(False)
        button_layout.addWidget(self.transfer_btn)
        
        layout.addLayout(button_layout)
        
        # Connect file selection signal
        self.file_browser.selection_changed.connect(self._on_selection_changed)
        
        return widget
    
    def _create_processing_screen(self) -> QWidget:
        """Create processing screen"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Title
        title = QLabel("Processing Files")
        title.setStyleSheet("font-size: 28pt; font-weight: bold; margin-bottom: 30px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Status message
        self.status_label = QLabel("Please wait...")
        self.status_label.setStyleSheet("font-size: 16pt; margin-bottom: 20px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(40)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("font-size: 14pt;")
        layout.addWidget(self.progress_bar)
        
        # Warning label
        warning = QLabel("Do not remove USB drive during processing")
        warning.setStyleSheet("font-size: 12pt; color: #FF5722; margin-top: 20px;")
        warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(warning)
        
        return widget
    
    def _create_secure_usb_screen(self) -> QWidget:
        """Create secure USB insertion screen"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Title
        title = QLabel("Files Converted Successfully")
        title.setStyleSheet("font-size: 28pt; font-weight: bold; margin-bottom: 20px; color: #4CAF50;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Instructions
        instructions = QLabel(
            "Please REMOVE the customer's USB drive\n\n"
            "Then INSERT a REGISTERED SECURE USB drive\n"
            "to receive the converted files"
        )
        instructions.setStyleSheet("font-size: 18pt; margin-bottom: 30px;")
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Status label
        self.secure_usb_status = QLabel("Waiting for secure USB...")
        self.secure_usb_status.setStyleSheet("font-size: 14pt; color: #666; margin-bottom: 20px;")
        self.secure_usb_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.secure_usb_status)
        
        # Cancel button
        cancel_secure_btn = QPushButton("Cancel Transfer")
        cancel_secure_btn.setMinimumHeight(60)
        cancel_secure_btn.setStyleSheet("font-size: 16pt;")
        cancel_secure_btn.clicked.connect(self.cancel_secure_usb_wait)
        layout.addWidget(cancel_secure_btn)
        
        return widget
    
    def _create_complete_screen(self) -> QWidget:
        """Create completion screen"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Title
        self.complete_title = QLabel("Transfer Complete")
        self.complete_title.setStyleSheet("font-size: 28pt; font-weight: bold; margin-bottom: 30px;")
        self.complete_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.complete_title)
        
        # Message
        self.complete_message = QTextEdit()
        self.complete_message.setReadOnly(True)
        self.complete_message.setStyleSheet("font-size: 14pt; background-color: #f5f5f5;")
        self.complete_message.setMinimumHeight(200)
        layout.addWidget(self.complete_message)
        
        # Done button
        self.done_btn = QPushButton("Done - Remove USB")
        self.done_btn.setMinimumHeight(60)
        self.done_btn.setStyleSheet("font-size: 16pt; font-weight: bold;")
        self.done_btn.clicked.connect(self.finish_transfer)
        layout.addWidget(self.done_btn)
        
        return widget
    
    def _setup_usb_monitor(self):
        """Set up USB device monitoring"""
        mount_base = self.config.get('usb.mount_base', '/media/usb-defender')
        self.usb_monitor = USBDeviceMonitor(mount_base)
        
        self.usb_monitor.on_device_added = self.on_usb_added
        self.usb_monitor.on_device_removed = self.on_usb_removed
        
        self.usb_monitor.start()
        
        logger.info("USB monitoring started")
    
    def _setup_shortcuts(self):
        """Set up keyboard shortcuts"""
        # Admin dashboard shortcut (Ctrl+Shift+D)
        dashboard_shortcut = QShortcut(QKeySequence("Ctrl+Shift+D"), self)
        dashboard_shortcut.activated.connect(self.show_dashboard)
    
    def show_waiting_screen(self):
        """Show waiting for USB screen"""
        self.stack.setCurrentWidget(self.waiting_screen)
    
    def on_usb_added(self, device: USBDevice):
        """
        Handle USB device insertion
        
        Args:
            device: USB device
        """
        logger.info(f"USB device added: {device}")
        
        # Check if we're waiting for a secure USB
        if self.waiting_for_secure_usb:
            self.on_secure_usb_inserted(device)
            return
        
        self.current_device = device
        
        # Mount device
        if self.usb_monitor.mount_device(device):
            logger.info(f"Device mounted at: {device.mount_point}")
            
            # Update UI
            self.device_label.setText(f"USB Device: {device.get_display_name()}")
            self.file_browser.load_directory(device.mount_point)
            
            # Show file selection screen
            self.stack.setCurrentWidget(self.file_selection_screen)
        else:
            logger.error("Failed to mount device")
            QMessageBox.critical(
                self,
                "Error",
                "Failed to mount USB device.\nPlease try removing and reinserting it."
            )
    
    def on_usb_removed(self, device: USBDevice):
        """
        Handle USB device removal
        
        Args:
            device: USB device
        """
        logger.info(f"USB device removed: {device}")
        
        if device == self.current_device:
            self.current_device = None
            
            # Return to waiting screen if not processing
            if self.stack.currentWidget() != self.processing_screen:
                self.show_waiting_screen()
    
    def _on_selection_changed(self, count: int, total_size: int):
        """
        Handle file selection change
        
        Args:
            count: Number of selected files
            total_size: Total size in bytes
        """
        self.transfer_btn.setEnabled(count > 0)
    
    def start_transfer(self):
        """Start file transfer process"""
        selected_files = self.file_browser.get_selected_files()
        
        if not selected_files:
            QMessageBox.warning(self, "No Files", "Please select files to transfer")
            return
        
        logger.info(f"Starting transfer of {len(selected_files)} files")
        
        # Generate session ID
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Audit log
        KioskLogger.audit_session_start(self.session_id)
        
        # Show processing screen
        self.stack.setCurrentWidget(self.processing_screen)
        self.progress_bar.setValue(0)
        self.status_label.setText("Initializing...")
        
        # Start processing thread
        self.processing_thread = ProcessingThread(selected_files, self.config, self.session_id)
        self.processing_thread.progress.connect(self.on_processing_progress)
        self.processing_thread.finished.connect(self.on_processing_finished)
        self.processing_thread.start()
    
    def on_processing_progress(self, message: str, percentage: int):
        """
        Handle processing progress update
        
        Args:
            message: Status message
            percentage: Progress percentage
        """
        self.status_label.setText(message)
        self.progress_bar.setValue(percentage)
    
    def on_processing_finished(self, success: bool, message: str, results: dict):
        """
        Handle processing completion
        
        Args:
            success: Whether processing was successful
            message: Result message
            results: Results dictionary
        """
        if not success:
            # Processing failed
            self.complete_title.setText("✗ Processing Failed")
            self.complete_title.setStyleSheet("font-size: 28pt; font-weight: bold; margin-bottom: 30px; color: #F44336;")
            self.complete_message.setPlainText(message)
            self.stack.setCurrentWidget(self.complete_screen)
            
            if self.session_id:
                KioskLogger.audit_session_end(self.session_id, 0, "FAILED")
            
            inactivity_timeout = self.config.get('kiosk.inactivity_timeout', 120)
            QTimer.singleShot(inactivity_timeout * 1000, self.check_return_to_home)
            return
        
        # Processing successful - check transfer method
        transfer_method = self.config.get('transfer.method', 'local')
        converted_images = results.get('converted_images', [])
        
        if transfer_method == 'secure_usb':
            # Airgapped mode - show secure USB screen
            logger.info("Airgapped mode: waiting for secure USB")
            self.show_secure_usb_screen(converted_images)
        else:
            # Direct transfer mode (local/network/cloud)
            logger.info(f"Direct transfer mode: {transfer_method}")
            self.perform_direct_transfer(converted_images, results)
    
    def perform_direct_transfer(self, converted_images: List[Path], results: dict):
        """
        Perform direct transfer (non-airgapped mode)
        
        Args:
            converted_images: List of converted images
            results: Processing results
        """
        try:
            self.progress_bar.setValue(90)
            self.status_label.setText("Transferring files...")
            
            transfer_manager = create_transfer_manager(self.config._config)
            transfer_results = transfer_manager.transfer_files(converted_images, self.session_id)
            
            successful_transfers = sum(1 for r in transfer_results.values() if r.success)
            
            if successful_transfers > 0:
                message = f"✓ Transfer Complete\n\n"
                message += f"Successfully processed {results.get('clean_files', 0)} file(s)\n"
                message += f"Generated {len(converted_images)} image(s)\n"
                message += f"Transferred {successful_transfers} file(s)\n\n"
                message += f"Destination: {transfer_manager.get_destination_info()}"
                
                infected_count = results.get('infected_files', 0)
                if infected_count > 0:
                    message += f"\n\nWarning: {infected_count} infected file(s) were skipped"
                
                self.complete_title.setText("✓ Transfer Complete")
                self.complete_title.setStyleSheet("font-size: 28pt; font-weight: bold; margin-bottom: 30px; color: #4CAF50;")
                self.complete_message.setPlainText(message)
                
                KioskLogger.audit_session_end(self.session_id, successful_transfers, "SUCCESS")
            else:
                self.complete_title.setText("✗ Transfer Failed")
                self.complete_title.setStyleSheet("font-size: 28pt; font-weight: bold; margin-bottom: 30px; color: #F44336;")
                self.complete_message.setPlainText("Transfer failed - no files were transferred")
                
                KioskLogger.audit_session_end(self.session_id, 0, "FAILED")
            
            self.stack.setCurrentWidget(self.complete_screen)
            
            inactivity_timeout = self.config.get('kiosk.inactivity_timeout', 120)
            QTimer.singleShot(inactivity_timeout * 1000, self.check_return_to_home)
        
        except Exception as e:
            logger.error(f"Transfer error: {e}", exc_info=True)
            self.complete_title.setText("✗ Transfer Error")
            self.complete_title.setStyleSheet("font-size: 28pt; font-weight: bold; margin-bottom: 30px; color: #F44336;")
            self.complete_message.setPlainText(f"Error during transfer:\n{str(e)}")
            self.stack.setCurrentWidget(self.complete_screen)
    
    def check_return_to_home(self):
        """Check if should return to home screen"""
        # Only return if still on complete screen and no USB inserted
        if self.stack.currentWidget() == self.complete_screen:
            if not self.current_device or not self.current_device.mount_point:
                self.show_waiting_screen()
    
    def cancel_transfer(self):
        """Cancel transfer and return to waiting"""
        if self.current_device:
            self.usb_monitor.unmount_device(self.current_device)
        
        self.show_waiting_screen()
    
    def finish_transfer(self):
        """Finish transfer and clean up"""
        if self.current_device:
            # Unmount device
            if self.config.get('usb.auto_unmount', True):
                timeout = self.config.get('usb.unmount_timeout', 5)
                QTimer.singleShot(timeout * 1000, lambda: self.usb_monitor.unmount_device(self.current_device))
        
        self.show_waiting_screen()
    
    def cancel_secure_usb_wait(self):
        """Cancel waiting for secure USB"""
        self.show_waiting_screen()
    
    def show_secure_usb_screen(self, converted_images: List[Path]):
        """
        Show secure USB insertion screen
        
        Args:
            converted_images: List of converted image files
        """
        self.converted_images = converted_images
        self.waiting_for_secure_usb = True
        self.secure_usb_status.setText("Waiting for registered secure USB...")
        self.stack.setCurrentWidget(self.secure_usb_screen)
        logger.info("Waiting for secure USB insertion")
    
    def on_secure_usb_inserted(self, device: USBDevice):
        """
        Handle secure USB insertion during transfer
        
        Args:
            device: USB device
        """
        if not self.waiting_for_secure_usb:
            return
        
        logger.info(f"Secure USB candidate detected: {device}")
        
        # Check if airgapped/secure USB mode is enabled
        transfer_method = self.config.get('transfer.method', 'local')
        
        if transfer_method != 'secure_usb':
            # Not in secure USB mode
            return
        
        # Verify this is a registered secure USB
        secure_config = self.config.get('transfer.secure_usb', {})
        transfer_manager = SecureUSBTransferManager(secure_config)
        
        # Mount the device
        if not self.usb_monitor.mount_device(device):
            self.secure_usb_status.setText("Error: Failed to mount USB device")
            self.secure_usb_status.setStyleSheet("font-size: 14pt; color: #F44336; margin-bottom: 20px;")
            return
        
        # Verify registration
        is_registered, message = transfer_manager.verify_secure_usb(device)
        
        if is_registered:
            self.secure_usb_status.setText(f"✓ {message}\n\nTransferring files...")
            self.secure_usb_status.setStyleSheet("font-size: 14pt; color: #4CAF50; margin-bottom: 20px;")
            
            # Perform transfer
            self.waiting_for_secure_usb = False
            self.transfer_to_secure_usb(device)
        else:
            self.secure_usb_status.setText(f"✗ {message}\n\nThis USB is not registered.\nPlease remove and insert a registered secure USB.")
            self.secure_usb_status.setStyleSheet("font-size: 14pt; color: #F44336; margin-bottom: 20px;")
            logger.warning(f"Unregistered USB blocked: {message}")
            
            # Unmount the unregistered USB
            self.usb_monitor.unmount_device(device)
    
    def transfer_to_secure_usb(self, device: USBDevice):
        """
        Transfer converted files to secure USB
        
        Args:
            device: Secure USB device
        """
        try:
            secure_config = self.config.get('transfer.secure_usb', {})
            transfer_manager = SecureUSBTransferManager(secure_config)
            
            # Transfer files
            transfer_results = transfer_manager.transfer_files(
                self.converted_images,
                self.session_id,
                device
            )
            
            # Check results
            successful = sum(1 for r in transfer_results.values() if r.success)
            
            if successful > 0:
                message = f"✓ Transfer Complete\n\n"
                message += f"Successfully transferred {successful} file(s) to secure USB\n"
                message += f"Session: {self.session_id}\n\n"
                message += f"You may now remove the secure USB."
                
                self.complete_title.setText("✓ Transfer Complete")
                self.complete_title.setStyleSheet("font-size: 28pt; font-weight: bold; margin-bottom: 30px; color: #4CAF50;")
                self.complete_message.setPlainText(message)
                
                KioskLogger.audit_session_end(self.session_id, successful, "SUCCESS")
            else:
                message = "✗ Transfer Failed\n\nNo files were transferred."
                self.complete_title.setText("✗ Transfer Failed")
                self.complete_title.setStyleSheet("font-size: 28pt; font-weight: bold; margin-bottom: 30px; color: #F44336;")
                self.complete_message.setPlainText(message)
                
                KioskLogger.audit_session_end(self.session_id, 0, "FAILED")
            
            self.stack.setCurrentWidget(self.complete_screen)
            
        except Exception as e:
            logger.error(f"Error transferring to secure USB: {e}", exc_info=True)
            self.complete_title.setText("✗ Transfer Error")
            self.complete_title.setStyleSheet("font-size: 28pt; font-weight: bold; margin-bottom: 30px; color: #F44336;")
            self.complete_message.setPlainText(f"Error during transfer:\n{str(e)}")
            self.stack.setCurrentWidget(self.complete_screen)
    
    def show_dashboard(self):
        """Show admin dashboard"""
        # Import here to avoid circular imports
        from src.dashboard.dashboard import DashboardWindow
        from src.dashboard.usb_registration import USBRegistrationWidget
        
        try:
            # Check if secure USB mode
            transfer_method = self.config.get('transfer.method', 'local')
            
            if transfer_method == 'secure_usb':
                # Show USB registration interface
                dialog = QDialog(self)
                dialog.setWindowTitle("Secure USB Management")
                dialog.resize(800, 600)
                
                layout = QVBoxLayout(dialog)
                
                usb_reg = USBRegistrationWidget(self.config._config, dialog)
                if self.current_device:
                    usb_reg.set_current_device(self.current_device)
                layout.addWidget(usb_reg)
                
                close_btn = QPushButton("Close")
                close_btn.clicked.connect(dialog.accept)
                layout.addWidget(close_btn)
                
                dialog.exec()
            else:
                # Show full dashboard
                dashboard = DashboardWindow(self.config)
                dashboard.show()
        except Exception as e:
            logger.error(f"Error opening dashboard: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "Dashboard Error",
                f"Failed to open dashboard:\n{str(e)}"
            )
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Stop USB monitoring
        if self.usb_monitor:
            self.usb_monitor.stop()
        
        event.accept()

