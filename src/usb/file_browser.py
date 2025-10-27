"""
USB Defender Kiosk - File Browser
Simple file browser for selecting files from USB
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QCheckBox, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from pathlib import Path
from typing import List, Set
from src.utils.logger import KioskLogger


logger = KioskLogger.get_logger(__name__)


class FileBrowserWidget(QWidget):
    """File browser widget for USB device contents"""
    
    # Signal emitted when selection changes
    selection_changed = pyqtSignal(int, int)  # (selected_count, total_size)
    
    def __init__(self, config: dict, parent=None):
        """
        Initialize file browser widget
        
        Args:
            config: File configuration
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.config = config
        self.root_path: Path = None
        self.selected_files: Set[Path] = set()
        self.file_items = {}  # Map Path to QTreeWidgetItem
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout(self)
        
        # Info label
        self.info_label = QLabel("Select files to transfer:")
        self.info_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(self.info_label)
        
        # File tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["File", "Size", "Type"])
        self.tree.setColumnWidth(0, 400)
        self.tree.setColumnWidth(1, 100)
        self.tree.setAlternatingRowColors(True)
        self.tree.itemChanged.connect(self._on_item_changed)
        
        layout.addWidget(self.tree)
        
        # Selection info
        self.selection_label = QLabel("No files selected")
        self.selection_label.setStyleSheet("font-size: 12pt;")
        layout.addWidget(self.selection_label)
        
        # Button row
        button_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all)
        self.select_all_btn.setMinimumHeight(40)
        button_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        self.deselect_all_btn.setMinimumHeight(40)
        button_layout.addWidget(self.deselect_all_btn)
        
        layout.addLayout(button_layout)
    
    def load_directory(self, directory: Path):
        """
        Load directory contents into tree
        
        Args:
            directory: Directory path to load
        """
        self.root_path = directory
        self.tree.clear()
        self.selected_files.clear()
        self.file_items.clear()
        
        if not directory or not directory.exists():
            logger.warning(f"Directory does not exist: {directory}")
            return
        
        logger.info(f"Loading directory: {directory}")
        
        try:
            self._load_directory_recursive(directory, self.tree.invisibleRootItem())
            self.tree.expandAll()
            
            # Update selection display
            self._update_selection_label()
        
        except Exception as e:
            logger.error(f"Error loading directory: {e}", exc_info=True)
    
    def _load_directory_recursive(self, directory: Path, parent_item: QTreeWidgetItem):
        """
        Recursively load directory contents
        
        Args:
            directory: Directory to load
            parent_item: Parent tree item
        """
        try:
            # Get and sort items (directories first, then files)
            items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            
            for item in items:
                # Skip hidden files
                if item.name.startswith('.'):
                    continue
                
                if item.is_dir():
                    # Create directory item
                    dir_item = QTreeWidgetItem(parent_item)
                    dir_item.setText(0, f"📁 {item.name}")
                    dir_item.setText(2, "Directory")
                    
                    # Recursively load subdirectory
                    self._load_directory_recursive(item, dir_item)
                
                elif item.is_file():
                    # Create file item with checkbox
                    file_item = QTreeWidgetItem(parent_item)
                    file_item.setFlags(file_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    file_item.setCheckState(0, Qt.CheckState.Unchecked)
                    
                    # File name
                    file_item.setText(0, item.name)
                    
                    # File size
                    size = item.stat().st_size
                    file_item.setText(1, self._format_size(size))
                    
                    # File type
                    extension = item.suffix.lower().lstrip('.')
                    file_item.setText(2, extension.upper() if extension else "File")
                    
                    # Store mapping
                    self.file_items[item] = file_item
                    
                    # Store path in item data
                    file_item.setData(0, Qt.ItemDataRole.UserRole, str(item))
        
        except PermissionError:
            logger.warning(f"Permission denied accessing: {directory}")
        except Exception as e:
            logger.error(f"Error loading directory {directory}: {e}")
    
    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        """
        Handle item check state change
        
        Args:
            item: Tree item
            column: Column index
        """
        if column != 0:
            return
        
        # Get file path from item
        file_path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if not file_path_str:
            return
        
        file_path = Path(file_path_str)
        
        # Update selected files set
        if item.checkState(0) == Qt.CheckState.Checked:
            self.selected_files.add(file_path)
        else:
            self.selected_files.discard(file_path)
        
        # Update selection label
        self._update_selection_label()
    
    def _update_selection_label(self):
        """Update selection information label"""
        count = len(self.selected_files)
        
        if count == 0:
            self.selection_label.setText("No files selected")
        else:
            # Calculate total size
            total_size = sum(f.stat().st_size for f in self.selected_files if f.exists())
            size_str = self._format_size(total_size)
            
            self.selection_label.setText(f"Selected: {count} file(s), {size_str}")
            
            # Emit signal
            self.selection_changed.emit(count, total_size)
    
    def select_all(self):
        """Select all files"""
        for file_path, item in self.file_items.items():
            item.setCheckState(0, Qt.CheckState.Checked)
    
    def deselect_all(self):
        """Deselect all files"""
        for file_path, item in self.file_items.items():
            item.setCheckState(0, Qt.CheckState.Unchecked)
    
    def get_selected_files(self) -> List[Path]:
        """
        Get list of selected files
        
        Returns:
            List of selected file paths
        """
        return list(self.selected_files)
    
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

