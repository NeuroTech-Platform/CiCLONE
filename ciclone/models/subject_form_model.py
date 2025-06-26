import os
import re
from typing import Dict, Optional, NamedTuple, List
from PyQt6.QtCore import QObject, pyqtSignal

from ciclone.services.io.schema_processor import SchemaProcessor


class FieldValidationResult(NamedTuple):
    """Result of individual field validation."""
    is_valid: bool
    error_message: str = ""
    warning_message: str = ""


class FormValidationResult(NamedTuple):
    """Result of complete form validation."""
    is_valid: bool
    error_messages: List[str]
    warning_messages: List[str]


class SubjectFormModel(QObject):
    """Model for managing subject form validation, state, and real-time feedback."""
    
    # Signals for real-time validation feedback
    field_validation_changed = pyqtSignal(str, bool, str, str)  # field, valid, error_msg, warning_msg
    form_state_changed = pyqtSignal(bool, bool)  # is_valid, is_dirty
    form_reset = pyqtSignal()  # Form has been reset
    
    def __init__(self):
        super().__init__()
        
        # Form fields with default values
        self._fields = {
            'name': '',
            'schema': '',
            'pre_ct': '',
            'pre_mri': '',
            'post_ct': '',
            'post_mri': ''
        }
        
        # Track validation state for each field
        self._field_validity: Dict[str, FieldValidationResult] = {}
        
        # Form state tracking
        self._is_dirty = False
        self._original_values = self._fields.copy()
        
        # Dependencies
        self._subject_model = None
        
        # Initialize validation state
        self._initialize_validation_state()
    
    def set_subject_model(self, subject_model):
        """Set reference to subject model for validation."""
        self._subject_model = subject_model
    
    def _initialize_validation_state(self):
        """Initialize validation state for all fields by actually validating them."""
        for field_name in self._fields.keys():
            # Actually validate the current field value (which starts as empty)
            validation_result = self.validate_field(field_name, self._fields[field_name])
            self._field_validity[field_name] = validation_result
    
    def set_field_value(self, field_name: str, value: str):
        """Set field value and trigger validation and state updates."""
        if field_name not in self._fields:
            return
        
        # Store old states BEFORE making any changes
        old_form_valid = self.is_form_valid()
        old_dirty = self._is_dirty
        old_value = self._fields[field_name]
        
        # Update field value
        self._fields[field_name] = value.strip()
        
        # Validate the field and update validity
        validation_result = self.validate_field(field_name, self._fields[field_name])
        self._field_validity[field_name] = validation_result
        
        # Emit field validation signal
        self.field_validation_changed.emit(
            field_name, 
            validation_result.is_valid,
            validation_result.error_message,
            validation_result.warning_message
        )
        
        # Update form state with old states for comparison
        self._update_form_state(old_form_valid, old_dirty)
    
    def get_field_value(self, field_name: str) -> str:
        """Get current field value."""
        return self._fields.get(field_name, '')
    
    def get_all_field_values(self) -> Dict[str, str]:
        """Get all current field values."""
        return self._fields.copy()
    
    def validate_field(self, field_name: str, value: str) -> FieldValidationResult:
        """Validate individual field with specific rules."""
        if field_name == 'name':
            return self._validate_subject_name(value)
        elif field_name == 'schema':
            return self._validate_schema_field(value)
        elif field_name in ['pre_ct', 'pre_mri', 'post_ct', 'post_mri']:
            return self._validate_file_path(value, field_name)
        else:
            return FieldValidationResult(True)
    
    def _validate_subject_name(self, name: str) -> FieldValidationResult:
        """Validate subject name field."""
        if not name.strip():
            return FieldValidationResult(False, "Subject name is required")
        
        # Check for invalid characters
        if not re.match(r'^[a-zA-Z0-9_\-\s]+$', name):
            return FieldValidationResult(False, "Subject name contains invalid characters")
        
        # Check if name already exists (if subject model is available)
        if self._subject_model and self._subject_model.subject_exists(name):
            return FieldValidationResult(False, f"Subject '{name}' already exists")
        
        # Check length
        if len(name) > 100:
            return FieldValidationResult(False, "Subject name too long (max 100 characters)")
        
        return FieldValidationResult(True)
    
    def _validate_schema_field(self, schema_path: str) -> FieldValidationResult:
        """Validate schema field (supports multiple files)."""
        if not schema_path.strip():
            return FieldValidationResult(True, "", "Schema is optional")
        
        # Handle multiple files (comma-separated)
        schema_files = [path.strip() for path in schema_path.split(',') if path.strip()]
        
        invalid_files = []
        unsupported_files = []
        
        for file_path in schema_files:
            if not os.path.exists(file_path):
                invalid_files.append(f"'{os.path.basename(file_path)}' not found")
            elif not SchemaProcessor.is_supported_file(file_path):
                unsupported_files.append(f"'{os.path.basename(file_path)}' unsupported format")
        
        if invalid_files:
            return FieldValidationResult(False, f"Files not found: {', '.join(invalid_files)}")
        
        if unsupported_files:
            return FieldValidationResult(False, f"Unsupported files: {', '.join(unsupported_files)}")
        
        return FieldValidationResult(True)
    
    def _validate_file_path(self, file_path: str, field_type: str) -> FieldValidationResult:
        """Validate file path fields (CT/MRI files)."""
        if not file_path.strip():
            return FieldValidationResult(True, "", f"{field_type.replace('_', ' ').title()} is optional")
        
        if not os.path.exists(file_path):
            return FieldValidationResult(False, f"File not found: '{os.path.basename(file_path)}'")
        
        if not os.path.isfile(file_path):
            return FieldValidationResult(False, "Path is not a file")
        
        # Check file extension for medical images
        valid_extensions = ['.nii', '.nii.gz', '.dcm', '.img', '.hdr']
        file_ext = ''.join(os.path.splitext(file_path))
        if file_path.endswith('.nii.gz'):
            file_ext = '.nii.gz'
        
        if not any(file_path.lower().endswith(ext) for ext in valid_extensions):
            return FieldValidationResult(
                True, "", 
                f"File format '{file_ext}' may not be supported (expected: {', '.join(valid_extensions)})"
            )
        
        return FieldValidationResult(True)
    
    def validate_form(self) -> FormValidationResult:
        """Validate entire form and return comprehensive result."""
        error_messages = []
        warning_messages = []
        
        # Validate all fields
        for field_name, value in self._fields.items():
            validation = self.validate_field(field_name, value)
            if not validation.is_valid:
                error_messages.append(f"{field_name.replace('_', ' ').title()}: {validation.error_message}")
            elif validation.warning_message:
                warning_messages.append(f"{field_name.replace('_', ' ').title()}: {validation.warning_message}")
        
        # Cross-field validation: at least one image file should be provided
        image_fields = ['pre_ct', 'pre_mri', 'post_ct', 'post_mri']
        has_image = any(self._fields[field].strip() for field in image_fields)
        
        if not has_image:
            warning_messages.append("Consider adding at least one medical image file")
        
        is_valid = len(error_messages) == 0
        return FormValidationResult(is_valid, error_messages, warning_messages)
    
    def is_form_valid(self) -> bool:
        """Check if entire form is valid."""
        return all(result.is_valid for result in self._field_validity.values())
    
    def is_form_dirty(self) -> bool:
        """Check if form has unsaved changes."""
        return self._is_dirty
    
    def _update_form_state(self, old_form_valid: bool = None, old_dirty: bool = None):
        """Update form state and emit signals if changed."""
        # If old states not provided, calculate them (for backward compatibility)
        if old_form_valid is None:
            old_form_valid = self.is_form_valid()
        if old_dirty is None:
            old_dirty = self._is_dirty
        
        # Update dirty state
        self._is_dirty = self._fields != self._original_values
        
        # Calculate new state
        new_valid = self.is_form_valid()
        new_dirty = self._is_dirty
        
        # Emit state change signal if state changed
        if old_form_valid != new_valid or old_dirty != new_dirty:
            self.form_state_changed.emit(new_valid, new_dirty)
    
    def reset_form(self):
        """Reset form to clean state."""
        # Reset all field values
        for field_name in self._fields:
            self._fields[field_name] = ''
        
        # Reset validation state by actually validating the (now empty) fields
        self._initialize_validation_state()
        
        # Reset form state
        self._is_dirty = False
        self._original_values = self._fields.copy()
        
        # Emit reset signal
        self.form_reset.emit()
        
        # Emit validation signals for all fields with correct validation results
        for field_name in self._fields:
            validation_result = self._field_validity[field_name]
            self.field_validation_changed.emit(
                field_name,
                validation_result.is_valid,
                validation_result.error_message,
                validation_result.warning_message
            )
        
        # Emit correct form state (should be invalid since name field is now empty)
        is_valid = self.is_form_valid()
        self.form_state_changed.emit(is_valid, False)
    
    def mark_as_clean(self):
        """Mark form as clean (typically after successful save)."""
        self._original_values = self._fields.copy()
        self._is_dirty = False
        self.form_state_changed.emit(self.is_form_valid(), False)
    
    def get_schema_files_list(self) -> List[str]:
        """Get schema files as a list (handles comma-separated values)."""
        schema_text = self._fields.get('schema', '').strip()
        if not schema_text:
            return []
        
        return [path.strip() for path in schema_text.split(',') if path.strip()]
    
    def get_form_data_for_submission(self) -> Dict[str, any]:
        """Get form data formatted for subject creation."""
        form_data = self._fields.copy()
        
        # Add schema files list for proper processing
        schema_files = self.get_schema_files_list()
        if schema_files:
            form_data['schema_files'] = schema_files
        
        return form_data 