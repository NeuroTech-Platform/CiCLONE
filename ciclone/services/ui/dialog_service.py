"""
Dialog Service for CiCLONE Application

This service provides a clean interface for controllers to request UI dialogs
without directly handling UI widgets, maintaining proper MVC separation.
"""

from typing import Optional, List, Tuple
from PyQt6.QtWidgets import (
    QWidget, QMessageBox, QInputDialog, QFileDialog, QProgressDialog
)
from PyQt6.QtCore import QStandardPaths


class DialogService:
    """
    Service for handling UI dialogs in a way that maintains MVC architecture.
    
    Controllers can use this service to request user interaction without
    directly creating UI components, maintaining separation of concerns.
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize dialog service with parent widget.
        
        Args:
            parent: Parent widget for dialogs (typically the main window)
        """
        self.parent = parent
    
    def set_parent(self, parent: QWidget):
        """Set the parent widget for dialogs."""
        self.parent = parent
    
    # Information and Confirmation Dialogs
    
    def show_information(self, title: str, message: str) -> None:
        """Show an information dialog."""
        QMessageBox.information(self.parent, title, message)
    
    def show_warning(self, title: str, message: str) -> None:
        """Show a warning dialog."""
        QMessageBox.warning(self.parent, title, message)
    
    def show_error(self, title: str, message: str) -> None:
        """Show an error dialog."""
        QMessageBox.critical(self.parent, title, message)
    
    def show_confirmation(self, title: str, message: str, 
                         default_no: bool = True) -> bool:
        """
        Show a confirmation dialog with Yes/No buttons.
        
        Args:
            title: Dialog title
            message: Dialog message
            default_no: If True, No is the default button
            
        Returns:
            True if user clicked Yes, False otherwise
        """
        default_button = (QMessageBox.StandardButton.No if default_no 
                         else QMessageBox.StandardButton.Yes)
        
        reply = QMessageBox.question(
            self.parent,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            default_button
        )
        
        return reply == QMessageBox.StandardButton.Yes
    
    def show_question(self, title: str, message: str) -> bool:
        """
        Show a question dialog with Yes/No buttons.
        
        Args:
            title: Dialog title
            message: Dialog message
            
        Returns:
            True if user clicked Yes, False otherwise
        """
        reply = QMessageBox.question(
            self.parent,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        return reply == QMessageBox.StandardButton.Yes
    
    def show_question_with_cancel(self, title: str, message: str, 
                                 button1_text: str = "Yes",
                                 button2_text: str = "No", 
                                 button3_text: str = "Cancel") -> str:
        """
        Show a question dialog with three custom buttons.
        
        Args:
            title: Dialog title
            message: Dialog message
            button1_text: Text for first button (default action)
            button2_text: Text for second button (alternative action)  
            button3_text: Text for cancel button
            
        Returns:
            Text of the button clicked
        """
        msg_box = QMessageBox(self.parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        button1 = msg_box.addButton(button1_text, QMessageBox.ButtonRole.AcceptRole)
        button2 = msg_box.addButton(button2_text, QMessageBox.ButtonRole.DestructiveRole)
        button3 = msg_box.addButton(button3_text, QMessageBox.ButtonRole.RejectRole)
        
        msg_box.setDefaultButton(button3)  # Cancel is default
        
        result = msg_box.exec()
        clicked = msg_box.clickedButton()
        
        if clicked == button1:
            return button1_text
        elif clicked == button2:
            return button2_text
        else:
            return button3_text
    
    # Input Dialogs
    
    def get_text_input(self, title: str, prompt: str, 
                      default_text: str = "") -> Tuple[Optional[str], bool]:
        """
        Get text input from user.
        
        Args:
            title: Dialog title
            prompt: Input prompt
            default_text: Default text in input field
            
        Returns:
            Tuple of (text, ok) where text is the input and ok indicates if user clicked OK
        """
        text, ok = QInputDialog.getText(
            self.parent,
            title,
            prompt,
            text=default_text
        )
        
        return (text.strip() if ok and text.strip() else None, ok)
    
    
    # File and Directory Dialogs
    
    def browse_directory(self, title: str, start_dir: Optional[str] = None) -> Optional[str]:
        """
        Browse for a directory.
        
        Args:
            title: Dialog title
            start_dir: Starting directory (defaults to desktop)
            
        Returns:
            Selected directory path or None if cancelled
        """
        if start_dir is None:
            start_dir = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.DesktopLocation
            )
        
        directory = QFileDialog.getExistingDirectory(
            self.parent,
            title,
            start_dir
        )
        
        return directory if directory else None
    
    def browse_file(self, title: str, file_filter: str = "All Files (*.*)",
                   start_dir: str = "") -> Optional[str]:
        """
        Browse for a single file.
        
        Args:
            title: Dialog title
            file_filter: File filter string
            start_dir: Starting directory
            
        Returns:
            Selected file path or None if cancelled
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self.parent,
            title,
            start_dir,
            file_filter
        )
        
        return file_path if file_path else None
    
    def browse_files(self, title: str, file_filter: str = "All Files (*.*)",
                    start_dir: str = "") -> List[str]:
        """
        Browse for multiple files.
        
        Args:
            title: Dialog title
            file_filter: File filter string
            start_dir: Starting directory
            
        Returns:
            List of selected file paths (empty if cancelled)
        """
        file_paths, _ = QFileDialog.getOpenFileNames(
            self.parent,
            title,
            start_dir,
            file_filter
        )
        
        return file_paths if file_paths else []
    
    
    # Specialized Dialogs for CiCLONE
    
    def get_dataset_name_and_location(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Get dataset name and base directory for new output directory.
        
        Returns:
            Tuple of (dataset_name, base_directory) or (None, None) if cancelled
        """
        # Get dataset name
        dataset_name, ok = self.get_text_input(
            "Folder Name",
            "Please enter a name"
        )
        
        if not ok or not dataset_name:
            if not dataset_name and ok:
                self.show_warning("Folder Name empty", "Please enter a folder name")
            return None, None
        
        # Get base directory
        base_directory = self.browse_directory("Select Output Directory")
        
        if not base_directory:
            return None, None
        
        return dataset_name, base_directory
    
    def browse_medical_image_file(self, image_type: str) -> Optional[str]:
        """
        Browse for medical image files with appropriate filters.
        
        Args:
            image_type: Type of image (e.g., "PreCT", "PostMRI")
            
        Returns:
            Selected file path or None if cancelled
        """
        file_filter = "DICOM files (*.dcm);;NIFTI files (*.nii *.nii.gz)"
        return self.browse_file(f"Select {image_type} File", file_filter)
    
    def browse_schema_files(self) -> List[str]:
        """
        Browse for schema files (electrode definition files).
        
        Returns:
            List of selected schema file paths
        """
        file_filter = "Electrode Definition files (*.elecdef);;JSON files (*.json);;All Files (*.*)"
        return self.browse_files("Select Electrode Schema Files", file_filter)
    
    def confirm_subject_deletion(self, subject_name: str) -> bool:
        """
        Confirm deletion of a single subject.
        
        Args:
            subject_name: Name of subject to delete
            
        Returns:
            True if user confirms deletion
        """
        message = (
            f"Are you sure you want to delete subject '{subject_name}'?\n\n"
            "This action cannot be undone and will permanently delete all files "
            "and data associated with this subject."
        )
        return self.show_confirmation("Delete Subject", message)
    
    def confirm_multiple_subject_deletion(self, subject_names: List[str]) -> bool:
        """
        Confirm deletion of multiple subjects.
        
        Args:
            subject_names: List of subject names to delete
            
        Returns:
            True if user confirms deletion
        """
        subject_count = len(subject_names)
        subject_list = "\n".join(f"• {name}" for name in subject_names)
        
        message = (
            f"Are you sure you want to delete the following {subject_count} subjects?\n\n"
            f"{subject_list}\n\n"
            "This action cannot be undone and will permanently delete all files "
            "and data associated with these subjects."
        )
        return self.show_confirmation(f"Delete {subject_count} Subjects", message)
    
    def confirm_stop_processing(self) -> bool:
        """
        Confirm stopping current processing operation.
        
        Returns:
            True if user confirms stopping
        """
        message = (
            "Are you sure you want to stop the current processing operation?\n\n"
            "This will interrupt the current operation and may leave some subjects "
            "partially processed."
        )
        return self.show_confirmation("Stop Processing", message)
    
    def show_subject_operation_result(self, operation: str, subject_name: str, 
                                    success: bool, error_details: str = "") -> None:
        """
        Show result of subject operation (create, rename, delete).
        
        Args:
            operation: Operation performed (e.g., "Import", "Rename", "Delete")
            subject_name: Name of subject
            success: Whether operation succeeded
            error_details: Additional error information if failed
        """
        if success:
            if operation == "Import":
                message = f"Subject '{subject_name}' has been imported successfully!"
            elif operation == "Rename":
                # For rename, subject_name should be "old_name' has been renamed to 'new_name"
                message = f"Subject {subject_name}"
            elif operation == "Delete":
                message = f"Subject '{subject_name}' has been deleted successfully."
            else:
                message = f"{operation} of subject '{subject_name}' completed successfully."
            
            self.show_information(f"{operation} Successful", message)
        else:
            base_message = f"Failed to {operation.lower()} subject '{subject_name}'."
            if error_details:
                message = f"{base_message}\n\n{error_details}"
            else:
                message = f"{base_message} Check the log for details."
            
            self.show_error(f"{operation} Failed", message)
    
    def show_multiple_subject_deletion_result(self, success_count: int, 
                                            failed_subjects: List[str]) -> None:
        """
        Show result of multiple subject deletion.
        
        Args:
            success_count: Number of successfully deleted subjects
            failed_subjects: List of subjects that failed to delete
        """
        total_count = success_count + len(failed_subjects)
        
        if not failed_subjects:
            # All succeeded
            self.show_information(
                "Delete Successful",
                f"All {total_count} subjects have been deleted successfully."
            )
        elif success_count > 0:
            # Partial success
            failed_list = "\n".join(f"• {name}" for name in failed_subjects)
            message = (
                f"Successfully deleted {success_count} subjects.\n\n"
                f"Failed to delete {len(failed_subjects)} subjects:\n"
                f"{failed_list}\n\n"
                "Check the log for details."
            )
            self.show_warning("Partial Success", message)
        else:
            # All failed
            self.show_error(
                "Delete Failed",
                f"Failed to delete all {total_count} subjects.\n"
                "Check the log for details."
            )
    
    def show_processing_result(self, success: bool, operation: str = "Processing") -> None:
        """
        Show processing operation result.
        
        Args:
            success: Whether processing succeeded
            operation: Name of the operation
        """
        if success:
            self.show_information(
                f"{operation} Successful",
                f"{operation} has been completed successfully."
            )
        else:
            self.show_warning(
                f"{operation} Failed",
                f"Failed to complete {operation.lower()}. Check the log for details."
            )
    
    def show_save_discard_cancel(self, title: str, message: str) -> str:
        """
        Specialized method for save/discard/cancel workflow.
        
        Args:
            title: Dialog title
            message: Question message
            
        Returns:
            "save", "discard", or "cancel"
        """
        result = self.show_question_with_cancel(
            title,
            message,
            "Save Changes",
            "Discard Changes",
            "Cancel"
        )
        
        if result == "Save Changes":
            return "save"
        elif result == "Discard Changes":
            return "discard"
        else:
            return "cancel"
    
    def show_progress_dialog(self, title: str, message: str, 
                           maximum: int = 0) -> QProgressDialog:
        """
        Show a progress dialog.
        
        Args:
            title: Dialog title
            message: Progress message
            maximum: Maximum value (0 for indeterminate)
            
        Returns:
            ProgressDialog instance
        """
        progress = QProgressDialog(message, "Cancel", 0, maximum, self.parent)
        progress.setWindowTitle(title)
        progress.setWindowModality(QProgressDialog.WindowModality.WindowModal)
        
        if maximum == 0:
            progress.setRange(0, 0)  # Indeterminate progress
        
        progress.show()
        return progress
    
    def confirm_destructive_action(self, action_name: str, 
                                  item_description: str = None) -> bool:
        """
        Show a confirmation dialog for destructive actions.
        
        Args:
            action_name: Name of the action (e.g., "delete", "remove")
            item_description: Description of what will be affected
            
        Returns:
            True if user confirms, False otherwise
        """
        if item_description:
            message = f"Are you sure you want to {action_name} {item_description}?\n\n"
            message += "This action cannot be undone."
        else:
            message = f"Are you sure you want to {action_name}?\n\n"
            message += "This action cannot be undone."
        
        msg_box = QMessageBox(self.parent)
        msg_box.setWindowTitle(f"Confirm {action_name.title()}")
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | 
            QMessageBox.StandardButton.No
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        
        # Make the Yes button red to indicate danger
        yes_button = msg_box.button(QMessageBox.StandardButton.Yes)
        if yes_button:
            yes_button.setStyleSheet("QPushButton { color: red; }")
        
        result = msg_box.exec()
        return result == QMessageBox.StandardButton.Yes
    
    def show_unsaved_changes_dialog(self, context: str = "closing") -> str:
        """
        Specialized dialog for unsaved changes scenarios.
        
        Args:
            context: Context of the unsaved changes (e.g., "closing", "switching")
            
        Returns:
            "save", "discard", or "cancel"
        """
        if context == "closing":
            message = "You have unsaved changes. What would you like to do before closing?"
            title = "Unsaved Changes - Closing"
        elif context == "switching":
            message = "You have unsaved changes. What would you like to do before switching?"
            title = "Unsaved Changes - Switching"
        else:
            message = "You have unsaved changes. What would you like to do?"
            title = "Unsaved Changes"
        
        return self.show_save_discard_cancel(title, message)
    
    # Contextual dialog methods for configuration management
    def show_pipeline_switch_confirmation(self, current_pipeline: str,
                                         new_pipeline: str,
                                         change_count: int) -> str:
        """
        Show confirmation dialog when switching pipelines with unsaved changes.
        
        Args:
            current_pipeline: Name of current pipeline
            new_pipeline: Name of target pipeline
            change_count: Number of unsaved changes
            
        Returns:
            "save", "discard", or "cancel"
        """
        message = f"You have {change_count} unsaved changes in pipeline '{current_pipeline}'.\n\n"
        message += f"What would you like to do before switching to '{new_pipeline}'?"
        
        return self.show_save_discard_cancel(
            "Unsaved Pipeline Changes",
            message
        )
    
    def show_close_with_changes_summary(self, summary: dict) -> str:
        """
        Show dialog when closing with a summary of all unsaved changes.
        
        Args:
            summary: Dictionary with change summary information
            
        Returns:
            "save", "discard", or "cancel"
        """
        message = "You have unsaved changes:\n\n"
        
        if summary.get('total_changes', 0) > 0:
            message += f"• Total changes: {summary['total_changes']}\n"
        
        if summary.get('deleted_pipelines', 0) > 0:
            message += f"• Deleted pipelines: {summary['deleted_pipelines']}\n"
        
        by_type = summary.get('by_type', {})
        if by_type:
            message += "\nChanges by type:\n"
            for change_type, count in by_type.items():
                if count > 0:
                    message += f"• {change_type}: {count}\n"
        
        message += "\nWhat would you like to do?"
        
        return self.show_save_discard_cancel(
            "Close with Unsaved Changes",
            message
        )