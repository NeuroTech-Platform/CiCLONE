import os
from typing import List, Optional, Callable
from PyQt6.QtCore import QObject
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtWidgets import QTreeView


class TreeViewController(QObject):
    """Controller for managing tree view operations and file system model."""
    
    def __init__(self):
        super().__init__()
        self._tree_view: Optional[QTreeView] = None
        self._file_system_model: Optional[QFileSystemModel] = None
        self._output_directory: Optional[str] = None
        self._log_callback: Optional[Callable[[str, str], None]] = None
    
    def set_tree_view(self, tree_view: QTreeView):
        """Set the tree view to manage."""
        self._tree_view = tree_view
    
    def set_log_callback(self, callback: Callable[[str, str], None]):
        """Set logging callback."""
        self._log_callback = callback
    
    def _log_message(self, level: str, message: str):
        """Log a message if callback is set."""
        if self._log_callback:
            self._log_callback(level, message)
    
    def set_output_directory(self, directory_path: str):
        """Set the output directory and update the tree view."""
        if not directory_path or not os.path.exists(directory_path):
            self._log_message("warning", f"Invalid output directory: {directory_path}")
            return False
        
        try:
            self._output_directory = directory_path
            
            # Create and configure file system model
            self._file_system_model = QFileSystemModel()
            self._file_system_model.setReadOnly(True)
            self._file_system_model.setRootPath(directory_path)
            
            if self._tree_view:
                # Set model and root index in tree view
                self._tree_view.setModel(self._file_system_model)
                self._tree_view.setRootIndex(self._file_system_model.index(directory_path))
                
                # Configure tree view appearance
                self._configure_tree_view_appearance()
            
            self._log_message("info", f"Tree view updated for directory: {directory_path}")
            return True
            
        except Exception as e:
            self._log_message("error", f"Failed to set output directory in tree view: {str(e)}")
            return False
    
    def _configure_tree_view_appearance(self):
        """Configure the appearance of the tree view."""
        if not self._tree_view:
            return
        
        self._tree_view.setAnimated(False)
        self._tree_view.setIndentation(20)
        self._tree_view.hideColumn(1)  # Size
        self._tree_view.hideColumn(2)  # Type
        self._tree_view.hideColumn(3)  # Date Modified
        self._tree_view.header().hide()
    
    def get_file_path_from_index(self, index) -> Optional[str]:
        """Get file path from tree view index."""
        if not self._file_system_model or not index.isValid():
            return None
        
        return self._file_system_model.filePath(index)
    
    def get_file_info_from_index(self, index):
        """Get file info from tree view index."""
        if not self._file_system_model or not index.isValid():
            return None
        
        return self._file_system_model.fileInfo(index)
    
    def get_selected_subject_paths(self, selected_indexes) -> List[str]:
        """Extract subject directory paths from selected indexes."""
        if not self._output_directory or not self._file_system_model:
            return []
        
        subject_paths = []
        for idx in selected_indexes:
            file_path = self.get_file_path_from_index(idx)
            file_info = self.get_file_info_from_index(idx)
            
            if (file_path and file_info and 
                file_info.isDir() and 
                os.path.dirname(file_path) == self._output_directory):
                subject_paths.append(file_path)
        
        return subject_paths
    
    def get_selected_subject_names(self, selected_indexes) -> List[str]:
        """Extract subject names from selected indexes."""
        subject_paths = self.get_selected_subject_paths(selected_indexes)
        return [os.path.basename(path) for path in subject_paths]
    
    def refresh_tree_view(self):
        """Refresh the tree view display."""
        if self._tree_view and self._file_system_model and self._output_directory:
            try:
                self._tree_view.setRootIndex(self._file_system_model.index(self._output_directory))
                self._log_message("info", "Tree view refreshed")
            except Exception as e:
                self._log_message("error", f"Failed to refresh tree view: {str(e)}")
    
    def get_output_directory(self) -> Optional[str]:
        """Get the current output directory."""
        return self._output_directory
    
    def is_nifti_file(self, file_path: str) -> bool:
        """Check if a file is a NIFTI file."""
        if not file_path:
            return False
        return file_path.endswith(('.nii', '.nii.gz'))
    
    def clear_tree_view(self):
        """Clear the tree view."""
        if self._tree_view:
            self._tree_view.setModel(None)
        
        self._file_system_model = None
        self._output_directory = None
        self._log_message("info", "Tree view cleared") 