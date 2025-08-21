import os
import shutil
from typing import Optional, Callable, List, Tuple
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ciclone.models.subject_model import SubjectModel, SubjectData, SubjectValidationResult
from ciclone.services.io.subject_importer import SubjectImporter
from ciclone.services.naming_service import NamingService


class SubjectController:
    """Controller for managing subject operations and coordinating between subject model and services."""
    
    def __init__(self, subject_model: SubjectModel):
        self.subject_model = subject_model
        self._view = None
        self._log_callback: Optional[Callable[[str, str], None]] = None
        self._dialog_service = None
        self._naming_service = NamingService()  # Initialize naming service with defaults
        
    def set_view(self, view):
        """Set the view reference for UI updates."""
        self._view = view
        
    def set_log_callback(self, callback: Callable[[str, str], None]):
        """Set callback function for logging messages."""
        self._log_callback = callback
    
    def set_dialog_service(self, dialog_service):
        """Set dialog service for user feedback."""
        self._dialog_service = dialog_service
        
    def _log_message(self, level: str, message: str):
        """Log a message if callback is set."""
        if self._log_callback:
            self._log_callback(level, message)
    
    def set_output_directory(self, directory_path: str):
        """Set the output directory in the model."""
        self.subject_model.set_output_directory(directory_path)
        
    def get_output_directory(self) -> Optional[str]:
        """Get the current output directory."""
        return self.subject_model.get_output_directory()
    
    def create_subject(self, subject_data: SubjectData) -> bool:
        """Create a new subject with validation and file operations."""
        # Validate the subject data
        validation = self.subject_model.validate_subject_data(subject_data)
        if not validation.is_valid:
            self._log_message("error", f"Validation failed: {validation.error_message}")
            return False
        
        output_directory = self.subject_model.get_output_directory()
        if not output_directory:
            self._log_message("error", "Output directory not set")
            return False
        
        # Show loading cursor during import
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        try:
            self._log_message("info", f"Starting import of subject '{subject_data.name}'...")
            
            # Convert SubjectData to dictionary for SubjectImporter
            subject_dict = {
                "name": subject_data.name,
                "schema": subject_data.schema,
                "schema_files": subject_data.get_schema_files(),
                "pre_ct": subject_data.pre_ct,
                "pre_mri": subject_data.pre_mri,
                "post_ct": subject_data.post_ct,
                "post_mri": subject_data.post_mri
            }
            
            # Perform the actual file operations with naming service
            SubjectImporter.import_subject(output_directory, subject_dict, self._naming_service)
            
            # Add to model if file operations succeeded
            success = self.subject_model.add_subject(subject_data, skip_existence_check=True)
            if success:
                self._log_message("success", f"Subject '{subject_data.name}' imported successfully")
                
                # Show success feedback to user
                if self._dialog_service:
                    self._dialog_service.show_subject_operation_result(
                        "Import", subject_data.name, True
                    )
                
                # Notify view to refresh if available
                if self._view and hasattr(self._view, 'refresh_subject_tree'):
                    self._view.refresh_subject_tree()
                    
                return True
            else:
                self._log_message("error", f"Failed to add subject to model")
                
                # Show error feedback to user
                if self._dialog_service:
                    self._dialog_service.show_subject_operation_result(
                        "Import", subject_data.name, False, "Failed to add subject to model"
                    )
                
                return False
                
        except Exception as e:
            self._log_message("error", f"Failed to import subject '{subject_data.name}': {str(e)}")
            
            # Show error feedback to user
            if self._dialog_service:
                self._dialog_service.show_subject_operation_result(
                    "Import", subject_data.name, False, str(e)
                )
            
            return False
        finally:
            QApplication.restoreOverrideCursor()
    
    def rename_subject(self, current_name: str, new_name: str) -> bool:
        """Rename a subject with validation and file operations, including renaming internal files."""
        # Validate the rename operation
        validation = self.subject_model.validate_subject_rename(current_name, new_name)
        if not validation.is_valid:
            self._log_message("error", f"Rename validation failed: {validation.error_message}")
            return False
        
        output_directory = self.subject_model.get_output_directory()
        if not output_directory:
            self._log_message("error", "Output directory not set")
            return False
        
        current_path = os.path.join(output_directory, current_name)
        new_path = os.path.join(output_directory, new_name)
        
        # Show loading cursor during rename
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        try:
            self._log_message("info", f"Renaming subject '{current_name}' to '{new_name}'...")
            
            # First, rename internal files that contain the subject name
            renamed_files = self._rename_internal_files(current_path, current_name, new_name)
            
            # Then rename the directory itself
            os.rename(current_path, new_path)
            
            # Update model if file operation succeeded
            success = self.subject_model.rename_subject(current_name, new_name)
            if success:
                if renamed_files > 0:
                    self._log_message("success", f"Subject renamed from '{current_name}' to '{new_name}' (including {renamed_files} internal files)")
                else:
                    self._log_message("success", f"Subject renamed from '{current_name}' to '{new_name}'")
                
                # Notify view to refresh if available
                if self._view and hasattr(self._view, 'refresh_subject_tree'):
                    self._view.refresh_subject_tree()
                    
                return True
            else:
                # Rollback: rename directory back and restore files
                os.rename(new_path, current_path)
                self._rename_internal_files(current_path, new_name, current_name)
                self._log_message("error", f"Failed to update model after rename")
                return False
                
        except Exception as e:
            self._log_message("error", f"Failed to rename subject: {str(e)}")
            return False
        finally:
            QApplication.restoreOverrideCursor()
    
    def _rename_internal_files(self, subject_path: str, old_name: str, new_name: str) -> int:
        """Rename files within the subject directory that contain the old subject name.
        Returns the number of files renamed."""
        renamed_count = 0
        
        try:
            # Walk through all files and subdirectories
            for root, dirs, files in os.walk(subject_path):
                # Rename files that contain the old subject name
                for filename in files:
                    if old_name in filename:
                        old_file_path = os.path.join(root, filename)
                        new_filename = filename.replace(old_name, new_name)
                        new_file_path = os.path.join(root, new_filename)
                        
                        # Only rename if the new filename is different and doesn't already exist
                        if new_filename != filename and not os.path.exists(new_file_path):
                            os.rename(old_file_path, new_file_path)
                            renamed_count += 1
                            self._log_message("debug", f"Renamed file: {filename} → {new_filename}")
                
                # Rename directories that contain the old subject name (excluding the root)
                for dirname in dirs[:]:  # Use slice copy to avoid modification during iteration
                    if old_name in dirname:
                        old_dir_path = os.path.join(root, dirname)
                        new_dirname = dirname.replace(old_name, new_name)
                        new_dir_path = os.path.join(root, new_dirname)
                        
                        # Only rename if the new dirname is different and doesn't already exist
                        if new_dirname != dirname and not os.path.exists(new_dir_path):
                            os.rename(old_dir_path, new_dir_path)
                            renamed_count += 1
                            self._log_message("debug", f"Renamed directory: {dirname} → {new_dirname}")
                            
                            # Update the dirs list to reflect the change for further walking
                            dirs[dirs.index(dirname)] = new_dirname
        
        except Exception as e:
            self._log_message("warning", f"Error renaming internal files: {str(e)}")
        
        return renamed_count
    
    def duplicate_subject(self, original_name: str, new_name: str) -> bool:
        """Duplicate a subject with validation and file operations, including renaming internal files."""
        # Validate the duplication operation (reusing rename validation logic)
        validation = self.subject_model.validate_subject_rename(original_name, new_name)
        if not validation.is_valid:
            self._log_message("error", f"Duplication validation failed: {validation.error_message}")
            return False
        
        output_directory = self.subject_model.get_output_directory()
        if not output_directory:
            self._log_message("error", "Output directory not set")
            return False
        
        original_path = os.path.join(output_directory, original_name)
        new_path = os.path.join(output_directory, new_name)
        
        # Show loading cursor during duplication
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        try:
            self._log_message("info", f"Duplicating subject '{original_name}' as '{new_name}'...")
            
            # Copy the entire subject directory
            shutil.copytree(original_path, new_path)
            
            # Rename internal files that contain the original subject name
            renamed_files = self._rename_internal_files(new_path, original_name, new_name)
            
            # Get the original subject data to copy its metadata
            original_subject = self.subject_model.get_subject(original_name)
            if not original_subject:
                # This should not happen if validation passed, but handle it gracefully
                shutil.rmtree(new_path)
                self._log_message("error", f"Original subject '{original_name}' not found in model")
                return False
            
            # Create a copy of the subject data with the new name
            new_subject_data = SubjectData(
                name=new_name,
                schema=original_subject.schema,
                pre_ct=original_subject.pre_ct,
                pre_mri=original_subject.pre_mri,
                post_ct=original_subject.post_ct,
                post_mri=original_subject.post_mri
            )
            
            # Add the new subject to the model (skip existence check since we just created it)
            new_subject = self.subject_model.add_subject(new_subject_data, skip_existence_check=True)
            
            if new_subject:
                if renamed_files > 0:
                    self._log_message("success", f"Subject duplicated as '{new_name}' (including {renamed_files} renamed internal files)")
                else:
                    self._log_message("success", f"Subject duplicated as '{new_name}'")
                
                # Notify view to refresh if available
                if self._view and hasattr(self._view, 'refresh_subject_tree'):
                    self._view.refresh_subject_tree()
                    
                return True
            else:
                # If model update failed, clean up the copied directory
                shutil.rmtree(new_path)
                self._log_message("error", "Failed to register duplicated subject in model")
                return False
                
        except Exception as e:
            self._log_message("error", f"Failed to duplicate subject: {str(e)}")
            # Clean up if directory was partially created
            if os.path.exists(new_path):
                try:
                    shutil.rmtree(new_path)
                except:
                    pass
            return False
        finally:
            QApplication.restoreOverrideCursor()
    
    def delete_file(self, file_path: str) -> bool:
        """Delete a file within a subject folder with validation."""
        if not os.path.exists(file_path):
            self._log_message("error", f"File does not exist: {file_path}")
            return False
        
        if not os.path.isfile(file_path):
            self._log_message("error", f"Path is not a file: {file_path}")
            return False
        
        output_directory = self.subject_model.get_output_directory()
        if not output_directory:
            self._log_message("error", "Output directory not set")
            return False
        
        # Verify file is within a subject directory
        try:
            rel_path = os.path.relpath(file_path, output_directory)
            if rel_path.startswith('..'):
                self._log_message("error", f"File is outside output directory: {file_path}")
                return False
            
            path_parts = rel_path.split(os.sep)
            if len(path_parts) < 2:
                self._log_message("error", f"File is not within a subject folder: {file_path}")
                return False
            
            subject_name = path_parts[0]
            
            # Verify the subject exists
            if subject_name not in self.subject_model.get_subject_names():
                self._log_message("error", f"Subject '{subject_name}' not found in model")
                return False
            
            # Don't allow deletion of protected directories
            protected_dirs = {'images', 'documents', 'processed_tmp', 'pipeline_output'}
            parent_dir = os.path.basename(os.path.dirname(file_path))
            file_name = os.path.basename(file_path)
            
            # Check if trying to delete a protected directory itself
            if file_name in protected_dirs and os.path.isdir(file_path):
                self._log_message("error", f"Cannot delete protected directory: {file_name}")
                return False
            
            # Delete the file
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                os.remove(file_path)
                self._log_message("success", f"Deleted file: {file_name} from subject '{subject_name}'")
                
                # Refresh view if available
                if self._view and hasattr(self._view, 'refresh_subject_tree'):
                    self._view.refresh_subject_tree()
                
                return True
                
            except Exception as e:
                self._log_message("error", f"Failed to delete file: {str(e)}")
                return False
            finally:
                QApplication.restoreOverrideCursor()
                
        except Exception as e:
            self._log_message("error", f"Error processing file path: {str(e)}")
            return False
    
    def delete_subject(self, subject_name: str) -> bool:
        """Delete a single subject with validation and file operations."""
        return self._delete_single_subject(subject_name, show_cursor=True, refresh_view=True)
    
    def delete_multiple_subjects(self, subject_names: List[str]) -> Tuple[int, List[str]]:
        """Delete multiple subjects with batch processing.
        Returns a tuple of (success_count, failed_subject_names)."""
        if not subject_names:
            return 0, []
        
        success_count = 0
        failed_subjects = []
        total_count = len(subject_names)
        
        # Show loading cursor during batch deletion
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        try:
            self._log_message("info", f"Starting batch deletion of {total_count} subjects...")
            
            for i, subject_name in enumerate(subject_names, 1):
                self._log_message("info", f"Deleting subject '{subject_name}' ({i}/{total_count})...")
                
                # Use the single deletion method without cursor/view management
                if self._delete_single_subject(subject_name, show_cursor=False, refresh_view=False):
                    success_count += 1
                else:
                    failed_subjects.append(subject_name)
            
            # Log final results
            if failed_subjects:
                self._log_message("warning", f"Batch deletion completed: {success_count} successful, {len(failed_subjects)} failed")
            else:
                self._log_message("success", f"Batch deletion completed: all {total_count} subjects deleted successfully")
            
            # Refresh view once at the end for batch operations
            if self._view and hasattr(self._view, 'refresh_subject_tree'):
                self._view.refresh_subject_tree()
            
            return success_count, failed_subjects
            
        except Exception as e:
            self._log_message("error", f"Critical error during batch deletion: {str(e)}")
            return success_count, subject_names[success_count:]
        finally:
            QApplication.restoreOverrideCursor()
    
    def _delete_single_subject(self, subject_name: str, show_cursor: bool = True, refresh_view: bool = True) -> bool:
        """Internal method to delete a single subject.
        
        Args:
            subject_name: Name of the subject to delete
            show_cursor: Whether to show loading cursor (for single operations)
            refresh_view: Whether to refresh the view after deletion (for single operations)
        """
        # Validate the deletion operation
        validation = self.subject_model.validate_subject_deletion(subject_name)
        if not validation.is_valid:
            self._log_message("error", f"Delete validation failed: {validation.error_message}")
            return False
        
        output_directory = self.subject_model.get_output_directory()
        if not output_directory:
            self._log_message("error", "Output directory not set")
            return False
        
        subject_path = os.path.join(output_directory, subject_name)
        
        # Show loading cursor only for single operations
        if show_cursor:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        try:
            if not show_cursor:  # Only log for single operations when not in batch
                pass
            else:
                self._log_message("info", f"Deleting subject '{subject_name}'...")
            
            # Perform the actual file operation
            shutil.rmtree(subject_path)
            
            # Update model if file operation succeeded
            success = self.subject_model.remove_subject(subject_name)
            if success:
                self._log_message("success", f"Subject '{subject_name}' deleted successfully")
                
                # Notify view to refresh only for single operations
                if refresh_view and self._view and hasattr(self._view, 'refresh_subject_tree'):
                    self._view.refresh_subject_tree()
                    
                return True
            else:
                self._log_message("error", f"Failed to update model after deletion")
                return False
                
        except Exception as e:
            self._log_message("error", f"Failed to delete subject: {str(e)}")
            return False
        finally:
            if show_cursor:
                QApplication.restoreOverrideCursor()
    
    def get_subject_path(self, subject_name: str) -> Optional[str]:
        """Get the full path to a subject directory."""
        return self.subject_model.get_subject_path(subject_name)
    
    def get_all_subjects(self):
        """Get all subjects from the model."""
        return self.subject_model.get_all_subjects()
    
    def get_subject_names(self):
        """Get all subject names from the model."""
        return self.subject_model.get_subject_names()
    
    def subject_exists(self, subject_name: str) -> bool:
        """Check if a subject exists."""
        return self.subject_model.subject_exists(subject_name)
    
    def validate_subject_name(self, name: str) -> SubjectValidationResult:
        """Validate a subject name without full subject data."""
        if not name.strip():
            return SubjectValidationResult(False, "Subject name cannot be empty")
        return SubjectValidationResult(True)
    
    def is_output_directory_set(self) -> bool:
        """Check if output directory is set."""
        return self.subject_model.is_output_directory_set() 