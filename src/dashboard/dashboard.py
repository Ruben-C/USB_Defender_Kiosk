"""
USB Defender Kiosk - Admin Dashboard
Administration and monitoring interface
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTextEdit, QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QLineEdit, QDialog, QDialogButtonBox, QFormLayout, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from pathlib import Path
from datetime import datetime
import subprocess

from src.dashboard.auth import DashboardAuth
from src.utils.logger import KioskLogger
from src.utils.config import ConfigManager


logger = KioskLogger.get_logger(__name__)


class LoginDialog(QDialog):
    """Login dialog for dashboard access"""
    
    def __init__(self, auth: DashboardAuth, parent=None):
        super().__init__(parent)
        
        self.auth = auth
        self.authenticated = False
        
        self.setWindowTitle("Dashboard Login")
        self.setModal(True)
        self.setMinimumWidth(300)
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Admin Dashboard Access")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Password field
        form = QFormLayout()
        self.password_field = QLineEdit()
        self.password_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_field.returnPressed.connect(self.check_password)
        form.addRow("Password:", self.password_field)
        layout.addLayout(form)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.check_password)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.password_field.setFocus()
    
    def check_password(self):
        """Check entered password"""
        password = self.password_field.text()
        
        if self.auth.verify_password(password):
            self.authenticated = True
            self.accept()
        else:
            QMessageBox.warning(self, "Access Denied", "Incorrect password")
            self.password_field.clear()
            self.password_field.setFocus()


class DashboardWindow(QMainWindow):
    """Admin dashboard window"""
    
    def __init__(self, config: ConfigManager):
        super().__init__()
        
        self.config = config
        self.auth = DashboardAuth(config.get_dashboard_config())
        
        # Authenticate user
        login_dialog = LoginDialog(self.auth, self)
        if login_dialog.exec() != QDialog.DialogCode.Accepted or not login_dialog.authenticated:
            self.close()
            return
        
        self._init_ui()
        self._load_data()
        
        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._refresh_data)
        self.refresh_timer.start(10000)  # Refresh every 10 seconds
        
        logger.info("Dashboard opened")
    
    def _init_ui(self):
        """Initialize user interface"""
        self.setWindowTitle("USB Defender - Admin Dashboard")
        self.resize(1000, 700)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Title
        title = QLabel("USB Defender Admin Dashboard")
        title.setStyleSheet("font-size: 20pt; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Create tabs
        self.overview_tab = self._create_overview_tab()
        self.logs_tab = self._create_logs_tab()
        self.system_tab = self._create_system_tab()
        
        self.tabs.addTab(self.overview_tab, "Overview")
        self.tabs.addTab(self.logs_tab, "Logs")
        self.tabs.addTab(self.system_tab, "System")
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_data)
        button_layout.addWidget(refresh_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _create_overview_tab(self) -> QWidget:
        """Create overview tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # System status
        status_label = QLabel("System Status")
        status_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(status_label)
        
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(200)
        layout.addWidget(self.status_text)
        
        # Recent transfers
        transfers_label = QLabel("Recent Transfers")
        transfers_label.setStyleSheet("font-size: 14pt; font-weight: bold; margin-top: 20px;")
        layout.addWidget(transfers_label)
        
        self.transfers_table = QTableWidget()
        self.transfers_table.setColumnCount(4)
        self.transfers_table.setHorizontalHeaderLabels(["Time", "Session ID", "Files", "Status"])
        layout.addWidget(self.transfers_table)
        
        return widget
    
    def _create_logs_tab(self) -> QWidget:
        """Create logs tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Log type selector
        log_buttons = QHBoxLayout()
        
        self.app_log_btn = QPushButton("Application Log")
        self.app_log_btn.clicked.connect(lambda: self._load_log('app'))
        log_buttons.addWidget(self.app_log_btn)
        
        self.audit_log_btn = QPushButton("Audit Log")
        self.audit_log_btn.clicked.connect(lambda: self._load_log('audit'))
        log_buttons.addWidget(self.audit_log_btn)
        
        self.transfer_log_btn = QPushButton("Transfer Log")
        self.transfer_log_btn.clicked.connect(lambda: self._load_log('transfer'))
        log_buttons.addWidget(self.transfer_log_btn)
        
        log_buttons.addStretch()
        
        layout.addLayout(log_buttons)
        
        # Log display
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.log_text.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.log_text)
        
        return widget
    
    def _create_system_tab(self) -> QWidget:
        """Create system tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # ClamAV status
        clamav_label = QLabel("ClamAV Status")
        clamav_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(clamav_label)
        
        self.clamav_status = QTextEdit()
        self.clamav_status.setReadOnly(True)
        self.clamav_status.setMaximumHeight(150)
        layout.addWidget(self.clamav_status)
        
        # ClamAV actions
        clamav_buttons = QHBoxLayout()
        
        update_signatures_btn = QPushButton("Update Virus Signatures")
        update_signatures_btn.clicked.connect(self._update_clamav_signatures)
        clamav_buttons.addWidget(update_signatures_btn)
        
        restart_clamav_btn = QPushButton("Restart ClamAV")
        restart_clamav_btn.clicked.connect(self._restart_clamav)
        clamav_buttons.addWidget(restart_clamav_btn)
        
        clamav_buttons.addStretch()
        
        layout.addLayout(clamav_buttons)
        
        # Disk space
        disk_label = QLabel("Disk Space")
        disk_label.setStyleSheet("font-size: 14pt; font-weight: bold; margin-top: 20px;")
        layout.addWidget(disk_label)
        
        self.disk_info = QTextEdit()
        self.disk_info.setReadOnly(True)
        self.disk_info.setMaximumHeight(150)
        layout.addWidget(self.disk_info)
        
        layout.addStretch()
        
        return widget
    
    def _load_data(self):
        """Load dashboard data"""
        self._load_system_status()
        self._load_recent_transfers()
        self._load_log('app')
        self._load_clamav_status()
        self._load_disk_info()
    
    def _refresh_data(self):
        """Refresh dashboard data"""
        current_tab = self.tabs.currentIndex()
        
        if current_tab == 0:  # Overview
            self._load_system_status()
            self._load_recent_transfers()
        elif current_tab == 1:  # Logs
            # Don't auto-refresh logs
            pass
        elif current_tab == 2:  # System
            self._load_clamav_status()
            self._load_disk_info()
    
    def _load_system_status(self):
        """Load system status information"""
        status = []
        
        # Current time
        status.append(f"Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Check if services are running
        services = ['clamav-daemon', 'udisks2']
        for service in services:
            try:
                result = subprocess.run(
                    ['systemctl', 'is-active', service],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                state = result.stdout.strip()
                status.append(f"{service}: {state}")
            except Exception:
                status.append(f"{service}: unknown")
        
        # Transfer destination
        transfer_config = self.config.get_transfer_config()
        method = transfer_config.get('method', 'local')
        status.append(f"\nTransfer Method: {method}")
        
        self.status_text.setPlainText("\n".join(status))
    
    def _load_recent_transfers(self):
        """Load recent transfer information"""
        # Read from audit log
        audit_log = Path('/var/log/usb-defender/audit.log')
        
        if not audit_log.exists():
            return
        
        try:
            # Read last 100 lines
            with open(audit_log, 'r') as f:
                lines = f.readlines()[-100:]
            
            # Parse transfer sessions
            sessions = {}
            for line in lines:
                if 'SESSION_STARTED' in line:
                    parts = line.split('|')
                    if len(parts) >= 3:
                        timestamp = parts[0].strip()
                        session_id = parts[2].split('=')[1].strip() if '=' in parts[2] else ''
                        sessions[session_id] = {
                            'time': timestamp,
                            'files': 0,
                            'status': 'In Progress'
                        }
                elif 'SESSION_ENDED' in line:
                    parts = line.split('|')
                    if len(parts) >= 5:
                        session_id = parts[2].split('=')[1].strip() if '=' in parts[2] else ''
                        if session_id in sessions:
                            files = parts[3].split('=')[1].strip() if '=' in parts[3] else '0'
                            status = parts[4].split('=')[1].strip() if '=' in parts[4] else 'UNKNOWN'
                            sessions[session_id]['files'] = files
                            sessions[session_id]['status'] = status
            
            # Update table
            self.transfers_table.setRowCount(len(sessions))
            for i, (session_id, data) in enumerate(sessions.items()):
                self.transfers_table.setItem(i, 0, QTableWidgetItem(data['time']))
                self.transfers_table.setItem(i, 1, QTableWidgetItem(session_id))
                self.transfers_table.setItem(i, 2, QTableWidgetItem(str(data['files'])))
                self.transfers_table.setItem(i, 3, QTableWidgetItem(data['status']))
        
        except Exception as e:
            logger.error(f"Error loading recent transfers: {e}")
    
    def _load_log(self, log_type: str):
        """
        Load and display log file
        
        Args:
            log_type: Type of log (app, audit, transfer)
        """
        log_files = {
            'app': '/var/log/usb-defender/app.log',
            'audit': '/var/log/usb-defender/audit.log',
            'transfer': '/var/log/usb-defender/transfer.log'
        }
        
        log_file = Path(log_files.get(log_type, ''))
        
        if not log_file.exists():
            self.log_text.setPlainText(f"Log file not found: {log_file}")
            return
        
        try:
            # Read last 500 lines
            with open(log_file, 'r') as f:
                lines = f.readlines()[-500:]
            
            self.log_text.setPlainText(''.join(lines))
            
            # Scroll to bottom
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum()
            )
        
        except Exception as e:
            self.log_text.setPlainText(f"Error reading log: {e}")
    
    def _load_clamav_status(self):
        """Load ClamAV status"""
        status = []
        
        try:
            # Check service status
            result = subprocess.run(
                ['systemctl', 'status', 'clamav-daemon'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Parse output
            for line in result.stdout.split('\n')[:10]:
                status.append(line)
        
        except Exception as e:
            status.append(f"Error checking ClamAV status: {e}")
        
        self.clamav_status.setPlainText('\n'.join(status))
    
    def _load_disk_info(self):
        """Load disk space information"""
        try:
            result = subprocess.run(
                ['df', '-h', '/var/usb-defender', '/var/log/usb-defender'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            self.disk_info.setPlainText(result.stdout)
        
        except Exception as e:
            self.disk_info.setPlainText(f"Error checking disk space: {e}")
    
    def _update_clamav_signatures(self):
        """Update ClamAV virus signatures"""
        try:
            QMessageBox.information(
                self,
                "Updating",
                "Updating virus signatures...\nThis may take a few minutes."
            )
            
            result = subprocess.run(
                ['sudo', 'freshclam'],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                QMessageBox.information(self, "Success", "Virus signatures updated successfully")
            else:
                QMessageBox.warning(self, "Error", f"Update failed:\n{result.stderr}")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update signatures:\n{e}")
    
    def _restart_clamav(self):
        """Restart ClamAV daemon"""
        try:
            result = subprocess.run(
                ['sudo', 'systemctl', 'restart', 'clamav-daemon'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                QMessageBox.information(self, "Success", "ClamAV restarted successfully")
                self._load_clamav_status()
            else:
                QMessageBox.warning(self, "Error", f"Restart failed:\n{result.stderr}")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to restart ClamAV:\n{e}")
    
    def closeEvent(self, event):
        """Handle window close"""
        self.refresh_timer.stop()
        logger.info("Dashboard closed")
        event.accept()


def main():
    """Main function for standalone dashboard"""
    import sys
    from PyQt6.QtWidgets import QApplication
    
    # Load configuration
    config = ConfigManager()
    
    # Configure logging
    KioskLogger.configure(config.get_logging_config())
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("USB Defender Dashboard")
    
    # Create and show dashboard
    dashboard = DashboardWindow(config)
    dashboard.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

