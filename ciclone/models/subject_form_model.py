import os
import re
from typing import Dict, Optional, NamedTuple, List
from PyQt6.QtCore import QObject, pyqtSignal

from ciclone.services.io.schema_processor import SchemaProcessor
from ciclone.models.image_entry import ImageEntry


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
    images_list_changed = pyqtSignal()  # Images list has been modified

    def __init__(self):
        super().__init__()

        # Form fields with default values (removed individual image fields)
        self._fields = {
            'name': '',
            'schema': ''
        }

        # List of images to be imported
        self._images: List[ImageEntry] = []

        # Track validation state for each field
        self._field_validity: Dict[str, FieldValidationResult] = {}

        # Form state tracking
        self._is_dirty = False
        self._original_values = self._fields.copy()
        self._original_images = []

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
        # Instead of returning an error, return a warning to allow adding files
        if self._subject_model and self._subject_model.subject_exists(name):
            return FieldValidationResult(True, "", f"Subject '{name}' already exists. Files will be added to existing subject.")

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

        # Validate all images in the list
        for idx, image_entry in enumerate(self._images):
            is_valid, error_msg = image_entry.validate()
            if not is_valid:
                error_messages.append(f"Image {idx + 1}: {error_msg}")

        # Cross-field validation: at least one image or schema should be provided
        has_images = len(self._images) > 0
        has_schema = bool(self._fields['schema'].strip())

        if not has_images and not has_schema:
            error_messages.append("At least one medical image or schema file must be provided")

        is_valid = len(error_messages) == 0
        return FormValidationResult(is_valid, error_messages, warning_messages)
    
    def is_form_valid(self) -> bool:
        """Check if entire form is valid, including cross-field validation."""
        # Check individual field validity
        if not all(result.is_valid for result in self._field_validity.values()):
            return False

        # Check cross-field validation: at least one image or schema must be provided
        has_images = len(self._images) > 0
        has_schema = bool(self._fields['schema'].strip())

        return has_images or has_schema
    
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

        # Update dirty state (check both fields and images)
        fields_changed = self._fields != self._original_values
        images_changed = len(self._images) != len(self._original_images) or \
                         any(img.to_dict() != orig.to_dict()
                             for img, orig in zip(self._images, self._original_images))
        self._is_dirty = fields_changed or images_changed

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

        # Clear images list
        self._images.clear()

        # Reset validation state by actually validating the (now empty) fields
        self._initialize_validation_state()

        # Reset form state
        self._is_dirty = False
        self._original_values = self._fields.copy()
        self._original_images = []

        # Emit reset signal
        self.form_reset.emit()

        # Emit images list changed signal
        self.images_list_changed.emit()

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
        self._original_images = [ImageEntry(img.file_path, img.session, img.modality, img.register_to)
                                  for img in self._images]
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

        # Add images list
        form_data['images'] = [img.to_dict() for img in self._images]

        return form_data

    # Image Management Methods
    def add_image(self, image_entry: ImageEntry) -> bool:
        """
        Add an image to the list.

        Args:
            image_entry: ImageEntry to add

        Returns:
            True if added successfully, False otherwise
        """
        # Validate the image entry
        is_valid, error_msg = image_entry.validate()
        if not is_valid:
            return False

        # Store old states BEFORE making any changes
        old_valid = self.is_form_valid()
        old_dirty = self._is_dirty

        # Add to list
        self._images.append(image_entry)

        # Update form state
        self._update_form_state(old_valid, old_dirty)

        # Emit images list changed signal
        self.images_list_changed.emit()

        return True

    def remove_image(self, index: int) -> bool:
        """
        Remove an image from the list by index.

        Args:
            index: Index of image to remove

        Returns:
            True if removed successfully, False otherwise
        """
        if 0 <= index < len(self._images):
            # Store old states BEFORE making any changes
            old_valid = self.is_form_valid()
            old_dirty = self._is_dirty

            # Remove from list
            self._images.pop(index)

            # Update form state
            self._update_form_state(old_valid, old_dirty)

            # Emit images list changed signal
            self.images_list_changed.emit()

            return True
        return False

    def get_images_list(self) -> List[ImageEntry]:
        """Get the current list of images."""
        return self._images.copy()

    def get_image_count(self) -> int:
        """Get the number of images in the list."""
        return len(self._images)

    def get_available_registration_targets(self) -> List[str]:
        """
        Get list of available registration target identifiers for display in dropdown.
        Combines existing subject images (if any) with newly added images.

        Returns:
            List of human-readable identifiers that can be used as registration targets
        """
        targets = ["None"]  # Always include None as first option

        # First, add existing subject images if we're editing an existing subject
        subject_name = self._fields.get('name', '').strip()
        if subject_name and self._subject_model and self._subject_model.subject_exists(subject_name):
            existing_targets = self._get_existing_subject_targets(subject_name)
            targets.extend(existing_targets)

        # Then, add newly added images from the form
        for idx, img in enumerate(self._images):
            # Create human-readable identifier
            display_name = f"[{img.session}] {img.modality}"
            # Add index if multiple images of same session/modality exist
            count_same_type = sum(1 for i in self._images[:idx+1]
                                 if i.session == img.session and i.modality == img.modality)
            if count_same_type > 1:
                display_name += f" #{count_same_type}"
            # Mark as new to distinguish from existing
            display_name += " (new)"
            targets.append(display_name)

        return targets

    def _get_existing_subject_targets(self, subject_name: str) -> List[str]:
        """
        Get registration targets from existing subject's images.

        Args:
            subject_name: Name of the existing subject

        Returns:
            List of target identifiers from existing images
        """
        if not self._subject_model:
            return []

        subject_data = self._subject_model.get_subject(subject_name)
        if not subject_data or not subject_data.images:
            return []

        targets = []
        for idx, img_dict in enumerate(subject_data.images):
            session = img_dict.get('session', 'Unknown')
            modality = img_dict.get('modality', 'Unknown')
            display_name = f"[{session}] {modality}"
            # Count duplicates
            count_same_type = sum(1 for i in subject_data.images[:idx+1]
                                 if i.get('session') == session and i.get('modality') == modality)
            if count_same_type > 1:
                display_name += f" #{count_same_type}"
            targets.append(display_name)

        return targets

    def load_existing_subject_images(self, subject_name: str) -> List[str]:
        """
        Load images from an existing subject directory and return available targets.

        Args:
            subject_name: Name of the existing subject

        Returns:
            List of registration target identifiers from existing subject
        """
        if not self._subject_model:
            return ["None"]

        subject_data = self._subject_model.get_subject(subject_name)
        if not subject_data or not subject_data.images:
            return ["None"]

        # Build targets from existing images
        targets = ["None"]
        for idx, img_dict in enumerate(subject_data.images):
            session = img_dict.get('session', 'Unknown')
            modality = img_dict.get('modality', 'Unknown')
            display_name = f"[{session}] {modality}"
            # Count duplicates
            count_same_type = sum(1 for i in subject_data.images[:idx+1]
                                 if i.get('session') == session and i.get('modality') == modality)
            if count_same_type > 1:
                display_name += f" #{count_same_type}"
            targets.append(display_name)

        return targets 