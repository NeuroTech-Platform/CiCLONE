import os
from typing import Optional, Callable, Dict, Any, List, Tuple
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox
from PyQt6.QtCore import QStandardPaths, QObject

from ciclone.models.application_model import ApplicationModel
from ciclone.models.subject_model import SubjectModel, SubjectData
from ciclone.controllers.subject_controller import SubjectController
from ciclone.controllers.processing_controller import ProcessingController
from ciclone.controllers.tree_view_controller import TreeViewController
from ciclone.ui.ImagesViewer import ImagesViewer
from ciclone.services.io.schema_processor import SchemaProcessor


class MainController(QObject):
    """Main controller that coordinates all application operations and manages the overall workflow."""
    
    def __init__(self, config_path: str, verbose_mode: bool = False):
        super().__init__()
        
        # Initialize models
        self.application_model = ApplicationModel(config_path)
        self.subject_model = SubjectModel()
        
        # Initialize child controllers
        self.subject_controller = SubjectController(self.subject_model)
        self.processing_controller = ProcessingController(self.application_model)
        self.tree_view_controller = TreeViewController()
        
        self._view = None
        self._log_callback: Optional[Callable[[str, str], None]] = None
        self._verbose_mode = verbose_mode
        
        # Setup controller relationships
        self._setup_controllers()
        
        # Connect to application model signals for coordination
        self.application_model.output_directory_changed.connect(self._on_output_directory_changed)
        self.application_model.images_viewer_state_changed.connect(self._on_images_viewer_state_changed)
    
    def set_view(self, view):
        """Set the main view and propagate to child controllers."""
        self._view = view
        self.subject_controller.set_view(view)
        self.processing_controller.set_view(view)
        
        # Set up tree view if available
        if hasattr(view, 'subjectTreeView'):
            self.tree_view_controller.set_tree_view(view.subjectTreeView)
        
    def set_log_callback(self, callback: Callable[[str, str], None]):
        """Set logging callback and propagate to child controllers."""
        self._log_callback = callback
        # Pass through the main controller's log method to enable real-time verbose toggling
        controller_callback = lambda level, msg: self._log_message(level, msg)
        self.subject_controller.set_log_callback(controller_callback)
        self.processing_controller.set_log_callback(controller_callback)
        self.tree_view_controller.set_log_callback(controller_callback)
        
    def _log_message(self, level: str, message: str):
        """Log a message if callback is set.
        
        Args:
            level: Log level (debug, info, success, warning, error)
            message: Message to log
        """
        # Filter debug messages based on verbose mode
        if level == "debug" and not self._verbose_mode:
            return
            
        if self._log_callback:
            self._log_callback(level, message)
    
    def _setup_controllers(self):
        """Setup relationships between controllers."""
        # Both controllers should use the same logging
        if self._log_callback:
            self.subject_controller.set_log_callback(self._log_callback)
            self.processing_controller.set_log_callback(self._log_callback)
    
    def _on_output_directory_changed(self, directory_path: str):
        """Handle output directory changes and coordinate updates."""
        # Update subject controller
        self.subject_controller.set_output_directory(directory_path)
        
        # Update tree view controller
        self.tree_view_controller.set_output_directory(directory_path)
        
        self._log_message("debug", f"Output directory changed to: {directory_path}")
    
    def _on_images_viewer_state_changed(self, is_active: bool):
        """Handle images viewer state changes."""
        if not is_active:
            # Clear the reference when viewer is closed
            self.application_model.set_images_viewer_instance(None)
    
    # Directory Management
    def create_output_directory(self) -> Optional[str]:
        """Create a new output directory with user input."""
        dataset_name, ok = QInputDialog.getText(
            self._view, 
            "Folder Name", 
            "Please enter a name"
        )
        
        if not ok or not dataset_name.strip():
            if not dataset_name.strip() and ok:
                QMessageBox.warning(self._view, "Folder Name empty", "Please enter a folder name")
            return None
        
        base_directory = QFileDialog.getExistingDirectory(
            self._view, 
            "Select Output Directory", 
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
        )
        
        if not base_directory:
            return None
        
        try:
            output_directory = os.path.join(base_directory, dataset_name.strip())
            os.makedirs(output_directory, exist_ok=True)
            
            # Update application model
            self.application_model.set_output_directory(output_directory)
            
            self._log_message("success", f"Created output directory: {output_directory}")
            return output_directory
            
        except Exception as e:
            self._log_message("error", f"Failed to create output directory: {str(e)}")
            QMessageBox.critical(
                self._view,
                "Directory Creation Failed",
                f"Failed to create directory '{dataset_name}':\n{str(e)}"
            )
            return None
    
    def open_output_directory(self) -> Optional[str]:
        """Open an existing output directory."""
        output_directory = QFileDialog.getExistingDirectory(
            self._view, 
            "Select Output Directory"
        )
        
        if output_directory:
            # Update application model
            self.application_model.set_output_directory(output_directory)
            self._log_message("debug", f"Opened output directory: {output_directory}")
            return output_directory
        
        return None
    
    def get_output_directory(self) -> Optional[str]:
        """Get the current output directory."""
        return self.application_model.get_output_directory()
    
    # File Browsing Operations
    def browse_file(self, field_type: str) -> Optional[str]:
        """Generic file browser for different field types."""
        if field_type == "Schema":
            # For schema files, use the multiple file browser
            file_paths = self.browse_schema_files()
            if file_paths:
                # Return comma-separated paths for backward compatibility
                return ', '.join(file_paths)
            return None
        
        file_filters = {
            "PreCT": "DICOM files (*.dcm);;NIFTI files (*.nii *.nii.gz)",
            "PreMRI": "DICOM files (*.dcm);;NIFTI files (*.nii *.nii.gz)", 
            "PostCT": "DICOM files (*.dcm);;NIFTI files (*.nii *.nii.gz)",
            "PostMRI": "DICOM files (*.dcm);;NIFTI files (*.nii *.nii.gz)"
        }
        
        file_filter = file_filters.get(field_type, "All Files (*.*)")
        file_path, _ = QFileDialog.getOpenFileName(
            self._view, 
            f"Select {field_type} File", 
            "", 
            file_filter
        )
        
        if file_path:
            self._log_message("debug", f"Selected {field_type} file: {os.path.basename(file_path)}")
            return file_path
        
        return None
    
    def browse_schema_files(self) -> List[str]:
        """Browse for schema files (supports multiple selection and PowerPoint)."""
        file_filter = SchemaProcessor.get_supported_extensions_filter()
        file_paths, _ = QFileDialog.getOpenFileNames(
            self._view,
            "Select Schema Files (Images or PowerPoint)",
            "",
            file_filter
        )
        
        if file_paths:
            # Filter out unsupported files using the centralized check
            supported_files = [path for path in file_paths if SchemaProcessor.is_supported_file(path)]
            
            if supported_files:
                file_names = [os.path.basename(path) for path in supported_files]
                self._log_message("debug", f"Selected {len(supported_files)} schema file(s): {', '.join(file_names)}")
                
                if len(supported_files) != len(file_paths):
                    unsupported_count = len(file_paths) - len(supported_files)
                    self._log_message("warning", f"Filtered out {unsupported_count} unsupported file(s)")
                
                return supported_files
            else:
                self._log_message("warning", "No supported files selected")
        
        return []
    
    # Subject Management (delegated)
    def create_subject(self, subject_data: SubjectData) -> bool:
        """Create a new subject (delegated to SubjectController)."""
        return self.subject_controller.create_subject(subject_data)
    
    def rename_subject(self, current_name: str, new_name: str) -> bool:
        """Rename a subject (delegated to SubjectController)."""
        return self.subject_controller.rename_subject(current_name, new_name)
    
    def delete_subject(self, subject_name: str) -> bool:
        """Delete a subject (delegated to SubjectController)."""
        return self.subject_controller.delete_subject(subject_name)
    
    def delete_multiple_subjects(self, subject_names: List[str]) -> Tuple[int, List[str]]:
        """Delete multiple subjects (delegated to SubjectController)."""
        return self.subject_controller.delete_multiple_subjects(subject_names)
    
    # Processing Management (delegated)
    def run_all_stages(self, selected_subjects: List[str]) -> bool:
        """Run all stages (delegated to ProcessingController)."""
        return self.processing_controller.run_all_stages(selected_subjects)
    
    def run_selected_stages(self, selected_subjects: List[str]) -> bool:
        """Run selected stages (delegated to ProcessingController)."""
        return self.processing_controller.run_selected_stages(selected_subjects)
    
    def stop_processing(self) -> bool:
        """Stop current processing (delegated to ProcessingController)."""
        return self.processing_controller.stop_processing()
    
    def is_processing_running(self) -> bool:
        """Check if processing is running (delegated to ProcessingController)."""
        return self.processing_controller.is_processing_running()
    
    # Images Viewer Management
    def open_nifti_file(self, file_path: str) -> bool:
        """Open a NIFTI file in the images viewer."""
        if not self.is_nifti_file(file_path):
            self._log_message("warning", f"File is not a NIFTI file: {file_path}")
            return False
        
        try:
            # Get or create images viewer
            current_viewer = self.application_model.get_images_viewer_instance()
            
            if not current_viewer:
                # Create new viewer
                images_viewer = ImagesViewer(file_path)
                self.application_model.set_images_viewer_instance(images_viewer)
                self._log_message("info", f"Created new images viewer for: {os.path.basename(file_path)}")
            else:
                # Use existing viewer
                images_viewer = current_viewer
                images_viewer.image_controller.load_image(file_path)
                self._log_message("info", f"Loaded image in existing viewer: {os.path.basename(file_path)}")
            
            # Show and bring to front
            images_viewer.show()
            images_viewer.raise_()
            images_viewer.activateWindow()
            
            return True
            
        except Exception as e:
            self._log_message("error", f"Failed to open NIFTI file: {str(e)}")
            return False
    
    def close_images_viewer(self):
        """Close the images viewer."""
        current_viewer = self.application_model.get_images_viewer_instance()
        if current_viewer:
            current_viewer.close()
            self.application_model.set_images_viewer_instance(None)
            self._log_message("info", "Images viewer closed")
    
    def is_images_viewer_active(self) -> bool:
        """Check if images viewer is active."""
        return self.application_model.is_images_viewer_active()
    
    # Configuration Management
    def reload_configuration(self) -> bool:
        """Reload configuration from file."""
        success = self.application_model.load_configuration()
        if success:
            self._log_message("success", "Configuration reloaded successfully")
        else:
            self._log_message("error", "Failed to reload configuration")
        return success
    
    def get_configuration(self) -> Dict[str, Any]:
        """Get current configuration."""
        return self.application_model.get_config()
    
    def get_stages_config(self) -> List[Dict[str, Any]]:
        """Get stages configuration."""
        return self.application_model.get_stages_config()
    
    # Application State Management
    def get_application_summary(self) -> Dict[str, Any]:
        """Get comprehensive application state summary."""
        app_summary = self.application_model.get_application_summary()
        processing_summary = self.processing_controller.get_processing_summary()
        
        return {
            **app_summary,
            **processing_summary,
            "subject_count": len(self.subject_controller.get_subject_names()),
            "images_viewer_active": self.is_images_viewer_active()
        }
    
    def clear_application_state(self):
        """Clear all application state (useful for reset scenarios)."""
        # Close images viewer
        self.close_images_viewer()
        
        # Stop any running processing
        if self.is_processing_running():
            self.stop_processing()
        
        # Clear application model state
        self.application_model.clear_all_state()
        
        self._log_message("info", "Application state cleared")
    
    # Verbose Mode Management
    def set_verbose_mode(self, enabled: bool):
        """Enable or disable verbose logging mode."""
        self._verbose_mode = enabled
        mode_text = "enabled" if enabled else "disabled"
        self._log_message("info", f"Verbose logging {mode_text}")
    
    def is_verbose_mode(self) -> bool:
        """Check if verbose mode is enabled."""
        return self._verbose_mode
    
    def toggle_verbose_mode(self) -> bool:
        """Toggle verbose mode and return new state.
        
        This can be called anytime, even during processing, for real-time control.
        """
        self._verbose_mode = not self._verbose_mode
        mode_text = "enabled" if self._verbose_mode else "disabled"
        
        # Use info level so this toggle message always shows
        self._log_message("info", f"🔧 Verbose logging {mode_text}")
        
        if self._verbose_mode:
            self._log_message("debug", "Debug messages are now visible - you'll see detailed operations")
        
        return self._verbose_mode
    
    # Validation and Prerequisites
    def validate_application_state(self) -> Tuple[bool, str]:
        """Validate overall application state.
        Returns (is_valid, error_message)."""
        
        if not self.application_model.is_output_directory_set():
            return False, "No output directory set"
        
        if not self.application_model.get_stages_config():
            return False, "No processing stages configured"
        
        if not self.subject_controller.get_subject_names():
            return False, "No subjects available"
        
        return True, ""
    
    # Tree View Management
    def get_file_path_from_tree_index(self, index) -> Optional[str]:
        """Get file path from tree view index."""
        return self.tree_view_controller.get_file_path_from_index(index)
    
    def get_selected_subject_paths_from_tree(self, selected_indexes) -> List[str]:
        """Get selected subject paths from tree view."""
        return self.tree_view_controller.get_selected_subject_paths(selected_indexes)
    
    def get_selected_subject_names_from_tree(self, selected_indexes) -> List[str]:
        """Get selected subject names from tree view."""
        return self.tree_view_controller.get_selected_subject_names(selected_indexes)
    
    def is_nifti_file(self, file_path: str) -> bool:
        """Check if file is a NIFTI file."""
        return self.tree_view_controller.is_nifti_file(file_path)
    
    # Utility Methods
    def refresh_views(self):
        """Refresh all views (useful after major state changes)."""
        # Refresh tree view
        self.tree_view_controller.refresh_tree_view()
        
        if self._view and hasattr(self._view, 'refresh_stages_ui'):
            self._view.refresh_stages_ui() 