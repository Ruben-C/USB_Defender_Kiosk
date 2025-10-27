"""
USB Defender Kiosk - USB Registration Interface
Admin interface for registering secure USB devices
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QDialog, QDialogButtonBox,
    QFormLayout, QLineEdit, QTextEdit, QMessageBox, QFileDialog,
    QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal
from pathlib import Path

from src.usb.secure_usb_manager import SecureUSBManager, SecureUSBDevice
from src.usb.device_monitor import USBDevice
from src.transfer.secure_usb_transfer import SecureUSBTransferManager
from src.utils.logger import KioskLogger


logger = KioskLogger.get_logger(__name__)


class RegisterUSBDialog(QDialog):
    """Dialog for registering a new secure USB device"""
    
    def __init__(self, device_info: dict, parent=None):
        super().__init__(parent)
        
        self.device_info = device_info
        self.device = None
        
        self.setWindowTitle("Register Secure USB")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Register New Secure USB Device")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Device info display
        info_label = QLabel("Device Information:")
        info_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(info_label)
        
        info_text = f"""
Serial Number: {device_info.get('serial', 'UNKNOWN')}
Vendor ID: {device_info.get('vendor_id', 'UNKNOWN')}
Product ID: {device_info.get('product_id', 'UNKNOWN')}
Device Node: {device_info.get('device_node', 'UNKNOWN')}
Size: {device_info.get('size', 'UNKNOWN')}
        """.strip()
        
        info_display = QLabel(info_text)
        info_display.setStyleSheet("background-color: #f0f0f0; padding: 10px; margin-bottom: 10px;")
        layout.addWidget(info_display)
        
        # Warning if serial is unknown
        if device_info.get('serial') == 'UNKNOWN':
            warning = QLabel("⚠️ Warning: Unable to read serial number. This device may not be reliably identified.")
            warning.setStyleSheet("color: #FF5722; font-weight: bold;")
            layout.addWidget(warning)
        
        # Registration form
        form = QFormLayout()
        
        self.label_field = QLineEdit()
        self.label_field.setPlaceholderText("e.g., Secure USB #1")
        form.addRow("Label*:", self.label_field)
        
        self.notes_field = QTextEdit()
        self.notes_field.setPlaceholderText("Optional notes about this device")
        self.notes_field.setMaximumHeight(80)
        form.addRow("Notes:", self.notes_field)
        
        layout.addLayout(form)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept_registration)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.label_field.setFocus()
    
    def accept_registration(self):
        """Validate and accept registration"""
        label = self.label_field.text().strip()
        
        if not label:
            QMessageBox.warning(self, "Missing Information", "Please provide a label for this device.")
            return
        
        if self.device_info.get('serial') == 'UNKNOWN':
            reply = QMessageBox.question(
                self,
                "Confirm Registration",
                "This device has no readable serial number. It may not be reliably identified. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Create device object
        self.device = SecureUSBDevice(
            serial=self.device_info.get('serial', 'UNKNOWN'),
            vendor_id=self.device_info.get('vendor_id', 'UNKNOWN'),
            product_id=self.device_info.get('product_id', 'UNKNOWN'),
            label=label,
            notes=self.notes_field.toPlainText().strip()
        )
        
        self.accept()


class USBRegistrationWidget(QWidget):
    """Widget for managing secure USB registration"""
    
    # Signal when registrations change
    registrations_changed = pyqtSignal()
    
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        
        self.config = config
        db_path = config.get('transfer', {}).get('secure_usb', {}).get('database_path', 
                                                                        '/etc/usb-defender/secure_usb.db')
        self.usb_manager = SecureUSBManager(db_path)
        self.transfer_manager = SecureUSBTransferManager(config.get('transfer', {}).get('secure_usb', {}))
        
        self.current_device: USBDevice = None
        
        self._init_ui()
        self._load_registered_devices()
    
    def _init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Secure USB Registration")
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(title)
        
        # Instructions
        instructions = QLabel(
            "Register USB drives that are authorized to receive converted files in airgapped mode.\n"
            "Only registered USB devices will be allowed to receive files."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("margin-bottom: 10px; color: #666;")
        layout.addWidget(instructions)
        
        # Current device section
        current_device_label = QLabel("Current USB Device:")
        current_device_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(current_device_label)
        
        self.current_device_info = QLabel("No USB device detected")
        self.current_device_info.setStyleSheet("background-color: #f0f0f0; padding: 10px; margin-bottom: 10px;")
        layout.addWidget(self.current_device_info)
        
        # Buttons for current device
        current_buttons = QHBoxLayout()
        
        self.register_current_btn = QPushButton("Register Current USB")
        self.register_current_btn.clicked.connect(self.register_current_device)
        self.register_current_btn.setEnabled(False)
        current_buttons.addWidget(self.register_current_btn)
        
        self.refresh_device_btn = QPushButton("Refresh")
        self.refresh_device_btn.clicked.connect(self.refresh_current_device)
        current_buttons.addWidget(self.refresh_device_btn)
        
        current_buttons.addStretch()
        
        layout.addLayout(current_buttons)
        
        # Registered devices section
        registered_label = QLabel("Registered Secure USB Devices:")
        registered_label.setStyleSheet("font-weight: bold; margin-top: 20px;")
        layout.addWidget(registered_label)
        
        # Table
        self.devices_table = QTableWidget()
        self.devices_table.setColumnCount(5)
        self.devices_table.setHorizontalHeaderLabels(["Label", "Serial", "Vendor ID", "Product ID", "Registered Date"])
        self.devices_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.devices_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.devices_table)
        
        # Device count
        self.device_count_label = QLabel()
        self.device_count_label.setStyleSheet("margin-top: 5px; color: #666;")
        layout.addWidget(self.device_count_label)
        
        # Table buttons
        table_buttons = QHBoxLayout()
        
        self.unregister_btn = QPushButton("Unregister Selected")
        self.unregister_btn.clicked.connect(self.unregister_selected)
        table_buttons.addWidget(self.unregister_btn)
        
        self.view_usage_btn = QPushButton("View Usage History")
        self.view_usage_btn.clicked.connect(self.view_usage_history)
        table_buttons.addWidget(self.view_usage_btn)
        
        table_buttons.addStretch()
        
        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self.export_registrations)
        table_buttons.addWidget(self.export_btn)
        
        self.import_btn = QPushButton("Import")
        self.import_btn.clicked.connect(self.import_registrations)
        table_buttons.addWidget(self.import_btn)
        
        layout.addLayout(table_buttons)
    
    def set_current_device(self, device: USBDevice):
        """
        Set current USB device
        
        Args:
            device: USB device
        """
        self.current_device = device
        self.update_current_device_display()
    
    def update_current_device_display(self):
        """Update display of current device"""
        if not self.current_device:
            self.current_device_info.setText("No USB device detected")
            self.register_current_btn.setEnabled(False)
            return
        
        # Get device info
        device_info = self.transfer_manager.get_device_info_for_registration(self.current_device)
        
        info_text = f"""
Device: {self.current_device.get_display_name()}
Serial: {device_info.get('serial', 'UNKNOWN')}
Vendor ID: {device_info.get('vendor_id', 'UNKNOWN')}
Product ID: {device_info.get('product_id', 'UNKNOWN')}
        """.strip()
        
        # Check if already registered
        serial = device_info.get('serial')
        if serial and serial != 'UNKNOWN':
            if self.usb_manager.is_registered(serial):
                registered_device = self.usb_manager.get_registered_device(serial)
                info_text += f"\n\n✓ Already registered as: {registered_device.label}"
                self.current_device_info.setStyleSheet("background-color: #C8E6C9; padding: 10px; margin-bottom: 10px;")
                self.register_current_btn.setEnabled(False)
            else:
                info_text += "\n\n✗ Not registered"
                self.current_device_info.setStyleSheet("background-color: #FFECB3; padding: 10px; margin-bottom: 10px;")
                self.register_current_btn.setEnabled(True)
        else:
            info_text += "\n\n⚠️ Warning: No serial number detected"
            self.current_device_info.setStyleSheet("background-color: #FFCCBC; padding: 10px; margin-bottom: 10px;")
            self.register_current_btn.setEnabled(True)
        
        self.current_device_info.setText(info_text)
    
    def refresh_current_device(self):
        """Refresh current device information"""
        if self.current_device:
            self.update_current_device_display()
        else:
            QMessageBox.information(self, "No Device", "No USB device currently connected.\n\nInsert a USB device and try again.")
    
    def register_current_device(self):
        """Register the current USB device"""
        if not self.current_device:
            QMessageBox.warning(self, "No Device", "No USB device to register.")
            return
        
        # Get device info
        device_info = self.transfer_manager.get_device_info_for_registration(self.current_device)
        
        # Show registration dialog
        dialog = RegisterUSBDialog(device_info, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.device:
            # Register device
            if self.usb_manager.register_usb(dialog.device):
                QMessageBox.information(
                    self,
                    "Success",
                    f"USB device '{dialog.device.label}' registered successfully."
                )
                self._load_registered_devices()
                self.update_current_device_display()
                self.registrations_changed.emit()
            else:
                QMessageBox.critical(
                    self,
                    "Error",
                    "Failed to register USB device. Check logs for details."
                )
    
    def _load_registered_devices(self):
        """Load registered devices into table"""
        devices = self.usb_manager.get_all_registered()
        
        self.devices_table.setRowCount(len(devices))
        
        for i, device in enumerate(devices):
            self.devices_table.setItem(i, 0, QTableWidgetItem(device.label))
            self.devices_table.setItem(i, 1, QTableWidgetItem(device.serial))
            self.devices_table.setItem(i, 2, QTableWidgetItem(device.vendor_id))
            self.devices_table.setItem(i, 3, QTableWidgetItem(device.product_id))
            self.devices_table.setItem(i, 4, QTableWidgetItem(device.registered_date[:10]))  # Date only
        
        self.device_count_label.setText(f"Total: {len(devices)} registered device(s)")
    
    def unregister_selected(self):
        """Unregister selected device"""
        selected_rows = self.devices_table.selectionModel().selectedRows()
        
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select a device to unregister.")
            return
        
        row = selected_rows[0].row()
        label = self.devices_table.item(row, 0).text()
        serial = self.devices_table.item(row, 1).text()
        
        reply = QMessageBox.question(
            self,
            "Confirm Unregister",
            f"Are you sure you want to unregister '{label}'?\n\nThis device will no longer be able to receive files.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.usb_manager.unregister_usb(serial):
                QMessageBox.information(self, "Success", f"Device '{label}' unregistered.")
                self._load_registered_devices()
                self.update_current_device_display()
                self.registrations_changed.emit()
            else:
                QMessageBox.critical(self, "Error", "Failed to unregister device.")
    
    def view_usage_history(self):
        """View usage history for selected device"""
        selected_rows = self.devices_table.selectionModel().selectedRows()
        
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select a device to view usage history.")
            return
        
        row = selected_rows[0].row()
        label = self.devices_table.item(row, 0).text()
        serial = self.devices_table.item(row, 1).text()
        
        history = self.usb_manager.get_usage_history(serial, limit=100)
        
        if not history:
            QMessageBox.information(self, "No History", f"No usage history for '{label}'.")
            return
        
        # Show history dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Usage History - {label}")
        dialog.resize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Timestamp", "Session ID", "Files Transferred"])
        table.setRowCount(len(history))
        
        for i, entry in enumerate(history):
            table.setItem(i, 0, QTableWidgetItem(entry['timestamp'][:19]))
            table.setItem(i, 1, QTableWidgetItem(entry['session_id']))
            table.setItem(i, 2, QTableWidgetItem(str(entry['file_count'])))
        
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()
    
    def export_registrations(self):
        """Export registrations to file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Registrations",
            f"secure_usb_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json)"
        )
        
        if file_path:
            if self.usb_manager.export_registrations(Path(file_path)):
                QMessageBox.information(self, "Success", f"Registrations exported to:\n{file_path}")
            else:
                QMessageBox.critical(self, "Error", "Failed to export registrations.")
    
    def import_registrations(self):
        """Import registrations from file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Registrations",
            "",
            "JSON Files (*.json)"
        )
        
        if file_path:
            reply = QMessageBox.question(
                self,
                "Import Mode",
                "Do you want to merge with existing registrations?\n\n"
                "Yes = Merge (add to existing)\n"
                "No = Replace (clear existing first)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Cancel:
                return
            
            merge = (reply == QMessageBox.StandardButton.Yes)
            
            successful, failed = self.usb_manager.import_registrations(Path(file_path), merge)
            
            if successful > 0:
                QMessageBox.information(
                    self,
                    "Import Complete",
                    f"Successfully imported {successful} device(s).\n"
                    f"Failed: {failed}"
                )
                self._load_registered_devices()
                self.registrations_changed.emit()
            else:
                QMessageBox.critical(self, "Error", f"Import failed. No devices imported.")

