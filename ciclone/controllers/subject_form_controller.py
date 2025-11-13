from typing import Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal

from ciclone.models.subject_form_model import SubjectFormModel, FormValidationResult
from ciclone.models.image_entry import ImageEntry


class SubjectFormController(QObject):
    """Controller for managing subject form operations and coordinating between form model and main controller."""
    
    # Signals for communicating with view
    validation_feedback_ready = pyqtSignal(str, bool, str, str)  # field, valid, error_msg, warning_msg
    form_state_updated = pyqtSignal(bool, bool)  # is_valid, is_dirty
    form_submission_complete = pyqtSignal(bool)  # success
    images_list_changed = pyqtSignal()  # images list has been modified
    
    def __init__(self, main_controller, dialog_service):
        super().__init__()
        
        self.main_controller = main_controller
        self.dialog_service = dialog_service
        self.form_model = SubjectFormModel()
        
        # Set subject model reference for validation
        if hasattr(main_controller, 'subject_controller') and main_controller.subject_controller:
            self.form_model.set_subject_model(main_controller.subject_controller.subject_model)
        
        self._connect_form_model_signals()
        self._view = None
        self._log_callback: Optional[Callable[[str, str], None]] = None
    
    def _connect_form_model_signals(self):
        """Connect form model signals to controller methods."""
        self.form_model.field_validation_changed.connect(self._on_field_validation_changed)
        self.form_model.form_state_changed.connect(self._on_form_state_changed)
        self.form_model.form_reset.connect(self._on_form_reset)
        self.form_model.images_list_changed.connect(self._on_images_list_changed)
    
    def _emit_initial_validation_signals(self):
        """Emit initial validation signals for all fields to update UI."""
        for field_name in self.form_model._fields.keys():
            validation_result = self.form_model._field_validity[field_name]
            self.validation_feedback_ready.emit(
                field_name,
                validation_result.is_valid,
                validation_result.error_message,
                validation_result.warning_message
            )
        
        is_valid = self.form_model.is_form_valid()
        is_dirty = self.form_model.is_form_dirty()
        self.form_state_updated.emit(is_valid, is_dirty)
    
    def set_view(self, view):
        """Set the view reference for UI updates."""
        self._view = view
        self._emit_initial_validation_signals()
    
    def set_log_callback(self, callback: Callable[[str, str], None]):
        """Set callback function for logging messages."""
        self._log_callback = callback
    
    def _log_message(self, level: str, message: str):
        """Log a message if callback is set."""
        if self._log_callback:
            self._log_callback(level, message)
    
    # Form Field Management
    def handle_field_change(self, field_name: str, value: str):
        """Handle form field changes from UI."""
        self.form_model.set_field_value(field_name, value)
    
    def get_field_value(self, field_name: str) -> str:
        """Get current field value."""
        return self.form_model.get_field_value(field_name)
    
    def get_all_field_values(self):
        """Get all current field values."""
        return self.form_model.get_all_field_values()
    
    # Form State Management
    def is_form_valid(self) -> bool:
        """Check if form is currently valid."""
        return self.form_model.is_form_valid()
    
    def is_form_dirty(self) -> bool:
        """Check if form has unsaved changes."""
        return self.form_model.is_form_dirty()
    
    def validate_form_for_submission(self) -> FormValidationResult:
        """Validate form for submission and return detailed results."""
        return self.form_model.validate_form()
    
    def submit_form(self) -> bool:
        """Handle form submission with validation and user feedback."""
        validation_result = self.validate_form_for_submission()
        
        if not validation_result.is_valid:
            error_message = "Form validation failed:\n\n" + "\n".join(validation_result.error_messages)
            if validation_result.warning_messages:
                error_message += "\n\nWarnings:\n" + "\n".join(validation_result.warning_messages)
            
            self.dialog_service.show_warning("Form Validation Error", error_message)
            self._log_message("warning", f"Form submission failed validation: {len(validation_result.error_messages)} errors")
            return False
        
        if not self.main_controller.is_output_directory_set():
            self.dialog_service.show_warning("No Output Directory", "Please select an output directory first")
            return False
        
        try:
            form_data = self.form_model.get_form_data_for_submission()
            self._log_message("info", f"Submitting form for subject '{form_data['name']}'...")
            
            # Show warnings if any (but don't block submission)
            if validation_result.warning_messages:
                warning_message = "Form has warnings:\n\n" + "\n".join(validation_result.warning_messages)
                warning_message += "\n\nDo you want to continue?"
                
                if not self.dialog_service.show_question("Form Warnings", warning_message):
                    self._log_message("info", "Form submission cancelled by user due to warnings")
                    return False
            
            success = self.main_controller.create_subject_from_form_data(form_data)
            
            if success:
                # Check if there are images to import
                has_images = form_data.get('images') and len(form_data['images']) > 0
                if has_images:
                    self._log_message("info", f"Subject '{form_data['name']}' directory created, importing files...")
                else:
                    self._log_message("info", f"Subject '{form_data['name']}' directory created")
                
                self.reset_form()
                self.form_submission_complete.emit(True)
            else:
                self._log_message("error", f"Failed to create subject '{form_data['name']}'")
                self.form_submission_complete.emit(False)
            
            return success
            
        except Exception as e:
            error_msg = f"Unexpected error during form submission: {str(e)}"
            self._log_message("error", error_msg)
            self.dialog_service.show_error("Submission Error", error_msg)
            self.form_submission_complete.emit(False)
            return False
    
    def reset_form(self):
        """Reset form to clean state."""
        self.form_model.reset_form()
        self._log_message("debug", "Form reset to clean state")
    
    def mark_form_as_clean(self):
        """Mark form as clean (typically after successful save)."""
        self.form_model.mark_as_clean()
    
    def browse_for_file(self, field_name: str, file_type: str):
        """Handle file browsing for form fields."""
        if field_name == 'schema':
            schema_files = self.main_controller.browse_schema_files()
            if schema_files:
                schema_text = ', '.join(schema_files)
                self.handle_field_change('schema', schema_text)

                if self._view and hasattr(self._view, 'update_schema_field'):
                    self._view.update_schema_field(schema_text)

    def browse_for_image(self) -> Optional[str]:
        """
        Browse for a medical image file.

        Returns:
            Selected file path or None if cancelled
        """
        filter_text = "Medical Images (*.nii *.nii.gz *.dcm);;All Files (*)"
        title = "Select Medical Image File"

        file_path = self.dialog_service.browse_file(title, filter_text)
        return file_path

    # Image Management Methods
    def add_image_to_list(self, file_path: str, session: str, modality: str, register_to: Optional[str] = None) -> bool:
        """
        Add an image to the form's image list.

        Args:
            file_path: Path to the image file
            session: "Pre" or "Post"
            modality: "CT", "MRI", or "PET"
            register_to: Optional registration target identifier

        Returns:
            True if added successfully, False otherwise
        """
        try:
            image_entry = ImageEntry(file_path, session, modality, register_to)
            success = self.form_model.add_image(image_entry)

            if success:
                self._log_message("debug", f"Added image: [{session}] {modality} - {file_path}")
            else:
                self._log_message("warning", f"Failed to add image: {file_path}")

            return success
        except Exception as e:
            self._log_message("error", f"Error adding image: {str(e)}")
            return False

    def remove_image_from_list(self, index: int) -> bool:
        """
        Remove an image from the form's image list.

        Args:
            index: Index of image to remove

        Returns:
            True if removed successfully, False otherwise
        """
        success = self.form_model.remove_image(index)

        if success:
            self._log_message("debug", f"Removed image at index {index}")
        else:
            self._log_message("warning", f"Failed to remove image at index {index}")

        return success

    def get_images_list(self):
        """Get the current list of images."""
        return self.form_model.get_images_list()

    def get_image_count(self) -> int:
        """Get the number of images in the list."""
        return self.form_model.get_image_count()

    def get_available_registration_targets(self):
        """Get list of available registration target identifiers."""
        return self.form_model.get_available_registration_targets()

    def load_existing_subject_images(self, subject_name: str):
        """
        Load images from an existing subject and return available registration targets.

        Args:
            subject_name: Name of the existing subject

        Returns:
            List of registration target identifiers
        """
        return self.form_model.load_existing_subject_images(subject_name)

    # Signal Handlers
    def _on_field_validation_changed(self, field: str, valid: bool, error_msg: str, warning_msg: str):
        """Handle field validation changes from form model."""
        self.validation_feedback_ready.emit(field, valid, error_msg, warning_msg)

    def _on_form_state_changed(self, is_valid: bool, is_dirty: bool):
        """Handle form state changes from form model."""
        self.form_state_updated.emit(is_valid, is_dirty)

    def _on_form_reset(self):
        """Handle form reset signal from form model."""
        if self._view and hasattr(self._view, 'on_form_reset'):
            self._view.on_form_reset()

    def _on_images_list_changed(self):
        """Handle images list changes from form model."""
        self.images_list_changed.emit()
    
    # Validation Helpers
    def validate_field_for_view(self, field_name: str, value: str):
        """Validate a specific field for immediate view feedback."""
        return self.form_model.validate_field(field_name, value)
    
    def check_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes that would be lost."""
        return self.is_form_dirty() 