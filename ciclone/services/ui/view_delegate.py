"""
View Delegate Service for CiCLONE Application

This service handles UI-related business logic that doesn't belong in controllers,
maintaining proper MVC separation by providing a bridge between controllers and views.
"""

from typing import List, Optional, Callable, Any, Dict
from PyQt6.QtWidgets import QTreeView, QAbstractItemView
from PyQt6.QtCore import QModelIndex, QObject, pyqtSignal
from pathlib import Path
import os


class ViewDelegate(QObject):
    """Service for handling UI business logic while maintaining MVC architecture."""
    
    # Signals for communicating with controllers
    selection_changed = pyqtSignal(list)  # List of selected items
    item_activated = pyqtSignal(str)      # Activated item path
    context_menu_requested = pyqtSignal(object, list)  # Position, selected items
    
    def __init__(self, parent: Optional[QObject] = None):
        """
        Initialize view delegate.
        
        Args:
            parent: Parent QObject
        """
        super().__init__(parent)
        self._tree_view: Optional[QTreeView] = None
        self._main_view = None
        self._output_directory: Optional[str] = None
    
    def set_tree_view(self, tree_view: QTreeView):
        """Set the tree view to manage."""
        self._tree_view = tree_view
        self._setup_tree_view_connections()
    
    def set_main_view(self, main_view):
        """Set reference to main view."""
        self._main_view = main_view
    
    def set_output_directory(self, output_directory: str):
        """Set the output directory for tree operations."""
        self._output_directory = output_directory
    
    def _setup_tree_view_connections(self):
        """Connect tree view signals to delegate methods."""
        if not self._tree_view:
            return
        
        selection_model = self._tree_view.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._on_selection_changed)
        
        self._tree_view.activated.connect(self._on_item_activated)
    
    def _on_selection_changed(self, selected, deselected):
        """Handle tree view selection changes."""
        selected_items = self.get_selected_items()
        self.selection_changed.emit(selected_items)
    
    def _on_item_activated(self, index: QModelIndex):
        """Handle tree view item activation (double-click)."""
        file_path = self.get_file_path_from_index(index)
        if file_path:
            self.item_activated.emit(file_path)
    
    # Tree View Operations
    
    def get_selected_items(self) -> List[str]:
        """Get list of selected item paths from tree view."""
        if not self._tree_view:
            return []
        
        selection_model = self._tree_view.selectionModel()
        if not selection_model:
            return []
        
        selected_indexes = selection_model.selectedIndexes()
        filtered_indexes = self._filter_indexes_by_column(selected_indexes, column=0)
        
        selected_paths = []
        for index in filtered_indexes:
            file_path = self.get_file_path_from_index(index)
            if file_path:
                selected_paths.append(file_path)
        
        return selected_paths
    
    def _filter_indexes_by_column(self, indexes: List[QModelIndex], column: int = 0) -> List[QModelIndex]:
        """Filter model indexes to only include specified column."""
        return [index for index in indexes if index.column() == column and index.isValid()]
    
    def get_selected_subject_names(self) -> List[str]:
        """Extract subject names from selected tree items."""
        selected_paths = self.get_selected_items()
        subject_names = []
        
        for path in selected_paths:
            if os.path.isdir(path):
                subject_names.append(os.path.basename(path))
            else:
                parent_dir = os.path.dirname(path)
                if parent_dir:
                    subject_names.append(os.path.basename(parent_dir))
        
        return list(dict.fromkeys(subject_names))
    
    def get_file_path_from_index(self, index: QModelIndex) -> Optional[str]:
        """Extract file path from tree view model index."""
        if not index.isValid() or not self._tree_view:
            return None
        
        model = self._tree_view.model()
        if not model:
            return None
        
        if hasattr(model, 'filePath'):
            return model.filePath(index)
        elif hasattr(model, 'data'):
            file_path = model.data(index, role=0x100)  # QFileSystemModel::FilePathRole
            if file_path:
                return file_path
        
        return None
    
    def select_items_by_path(self, paths: List[str]):
        """Select items in tree view by their paths."""
        if not self._tree_view or not paths:
            return
        
        model = self._tree_view.model()
        if not model:
            return
        
        selection_model = self._tree_view.selectionModel()
        if not selection_model:
            return
        
        selection_model.clear()
        
        for path in paths:
            index = self._find_index_by_path(path)
            if index.isValid():
                selection_model.select(index, QAbstractItemView.SelectionFlag.Select)
    
    def _find_index_by_path(self, path: str) -> QModelIndex:
        """Find model index for a given file path."""
        if not self._tree_view:
            return QModelIndex()
        
        model = self._tree_view.model()
        if not model:
            return QModelIndex()
        
        if hasattr(model, 'index') and hasattr(model, 'filePath'):
            return model.index(path)
        
        return QModelIndex()
    
    def expand_path(self, path: str):
        """Expand tree view to show the given path."""
        if not self._tree_view:
            return
        
        index = self._find_index_by_path(path)
        if index.isValid():
            self._tree_view.expand(index)
            self._tree_view.scrollTo(index)
    
    def refresh_tree_view(self):
        """Refresh the tree view display while maintaining current directory."""
        if not self._tree_view:
            return
        
        model = self._tree_view.model()
        if not model:
            return
        
        try:
            if hasattr(model, 'rootPath') and hasattr(model, 'index'):
                if self._output_directory and os.path.exists(self._output_directory):
                    output_index = model.index(self._output_directory)
                    if output_index.isValid():
                        self._tree_view.setRootIndex(output_index)
                        self._tree_view.update()
                        self._tree_view.repaint()
                        return
                
                current_root = model.rootPath()
                if current_root and os.path.exists(current_root):
                    current_index = model.index(current_root)
                    if current_index.isValid():
                        self._tree_view.setRootIndex(current_index)
                        self._tree_view.update()
                        return
            
            if hasattr(model, 'refresh'):
                model.refresh()
            else:
                self._tree_view.reset()
                
        except Exception as e:
            try:
                self._tree_view.reset()
            except:
                pass
    
    # File Type Checking and Classification
    
    def classify_file_types(self, file_paths: List[str]) -> Dict[str, List[str]]:
        """Classify files by their types."""
        classification = {
            'nifti': [],
            'dicom': [],
            'image': [],
            'markdown': [],
            'config': [],
            'electrode': [],
            'other': []
        }
        
        for file_path in file_paths:
            if self.is_nifti_file(file_path):
                classification['nifti'].append(file_path)
            elif self.is_dicom_file(file_path):
                classification['dicom'].append(file_path)
            elif self.is_image_file(file_path):
                classification['image'].append(file_path)
            elif self.is_markdown_file(file_path):
                classification['markdown'].append(file_path)
            elif self.is_config_file(file_path):
                classification['config'].append(file_path)
            elif self.is_electrode_file(file_path):
                classification['electrode'].append(file_path)
            else:
                classification['other'].append(file_path)
        
        return classification
    
    def is_nifti_file(self, file_path: str) -> bool:
        """Check if file is a NIFTI file."""
        if not file_path:
            return False
        return Path(file_path).suffix.lower() in ['.nii', '.gz'] or \
               file_path.lower().endswith('.nii.gz')
    
    def is_dicom_file(self, file_path: str) -> bool:
        """Check if file is a DICOM file."""
        if not file_path:
            return False
        return Path(file_path).suffix.lower() in ['.dcm', '.dicom']
    
    def is_image_file(self, file_path: str) -> bool:
        """Check if file is a standard image file."""
        if not file_path:
            return False
        image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.tif']
        return Path(file_path).suffix.lower() in image_extensions
    
    def is_markdown_file(self, file_path: str) -> bool:
        """Check if file is a Markdown file."""
        if not file_path:
            return False
        return Path(file_path).suffix.lower() in ['.md', '.markdown']
    
    def is_config_file(self, file_path: str) -> bool:
        """Check if file is a configuration file."""
        if not file_path:
            return False
        config_extensions = ['.yaml', '.yml', '.json', '.ini', '.cfg', '.conf']
        return Path(file_path).suffix.lower() in config_extensions
    
    def is_electrode_file(self, file_path: str) -> bool:
        """Check if file is an electrode definition file."""
        if not file_path:
            return False
        return Path(file_path).suffix.lower() == '.elecdef'
    
    def is_previewable_file(self, file_path: str) -> bool:
        """Check if file can be previewed in the application."""
        return (self.is_nifti_file(file_path) or 
                self.is_image_file(file_path) or 
                self.is_markdown_file(file_path))
    
    def is_openable_file(self, file_path: str) -> bool:
        """Check if file can be opened by the application."""
        return (self.is_previewable_file(file_path) or 
                self.is_config_file(file_path) or 
                self.is_electrode_file(file_path))
    
    # UI State Management
    
    def get_ui_state_summary(self) -> Dict[str, Any]:
        """Get summary of current UI state."""
        selected_items = self.get_selected_items()
        selected_subjects = self.get_selected_subject_names()
        
        return {
            'selected_items_count': len(selected_items),
            'selected_subjects_count': len(selected_subjects),
            'selected_items': selected_items,
            'selected_subjects': selected_subjects,
            'output_directory': self._output_directory
        }
    
    def validate_selection_for_operation(self, operation_type: str) -> tuple[bool, str]:
        """Validate current selection for a specific operation type."""
        selected_items = self.get_selected_items()
        selected_subjects = self.get_selected_subject_names()
        
        if operation_type == 'processing':
            if not selected_subjects:
                return False, "No subjects selected for processing"
            
            if not self._output_directory:
                return False, "No output directory set"
            
            return True, f"Ready to process {len(selected_subjects)} subject(s)"
        
        elif operation_type == 'delete':
            if not selected_items:
                return False, "No items selected for deletion"
            
            return True, f"Ready to delete {len(selected_items)} item(s)"
        
        elif operation_type == 'preview':
            if len(selected_items) != 1:
                return False, "Select exactly one file to preview"
            
            file_path = selected_items[0]
            if not self.is_previewable_file(file_path):
                return False, "Selected file cannot be previewed"
            
            return True, f"Ready to preview {os.path.basename(file_path)}"
        
        return False, f"Unknown operation type: {operation_type}"
    
    # Helper Methods for Controllers
    
    def get_operation_context(self, operation_type: str) -> Dict[str, Any]:
        """Get context information for a specific operation."""
        context = self.get_ui_state_summary()
        context['operation_type'] = operation_type
        
        is_valid, message = self.validate_selection_for_operation(operation_type)
        context['is_valid'] = is_valid
        context['validation_message'] = message
        
        return context
    
    def filter_items_for_operation(self, operation_type: str) -> List[str]:
        """Filter selected items based on operation requirements."""
        selected_items = self.get_selected_items()
        
        if operation_type == 'nifti_preview':
            return [item for item in selected_items if self.is_nifti_file(item)]
        elif operation_type == 'image_preview':
            return [item for item in selected_items if self.is_image_file(item)]
        elif operation_type == 'markdown_preview':
            return [item for item in selected_items if self.is_markdown_file(item)]
        
        return selected_items 