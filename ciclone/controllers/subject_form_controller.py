from typing import Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal

from ciclone.models.subject_form_model import SubjectFormModel, FormValidationResult


class SubjectFormController(QObject):
    """Controller for managing subject form operations and coordinating between form model and main controller."""
    
    # Signals for communicating with view
    validation_feedback_ready = pyqtSignal(str, bool, str, str)  # field, valid, error_msg, warning_msg
    form_state_updated = pyqtSignal(bool, bool)  # is_valid, is_dirty
    form_submission_complete = pyqtSignal(bool)  # success
    
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
                self._log_message("success", f"Subject '{form_data['name']}' created successfully")
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
        else:
            file_filters = {
                'pre_ct': "CT Images (*.nii *.nii.gz *.dcm);;All Files (*)",
                'pre_mri': "MRI Images (*.nii *.nii.gz *.dcm);;All Files (*)",
                'post_ct': "CT Images (*.nii *.nii.gz *.dcm);;All Files (*)",
                'post_mri': "MRI Images (*.nii *.nii.gz *.dcm);;All Files (*)"
            }
            
            filter_text = file_filters.get(field_name, "Medical Images (*.nii *.nii.gz *.dcm);;All Files (*)")
            title = f"Select {field_name.replace('_', ' ').title()} File"
            
            file_path = self.dialog_service.browse_file(title, filter_text)
            if file_path:
                self.handle_field_change(field_name, file_path)
                
                if self._view and hasattr(self._view, 'update_field'):
                    self._view.update_field(field_name, file_path)
    
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
    
    # Validation Helpers
    def validate_field_for_view(self, field_name: str, value: str):
        """Validate a specific field for immediate view feedback."""
        return self.form_model.validate_field(field_name, value)
    
    def check_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes that would be lost."""
        return self.is_form_dirty() 