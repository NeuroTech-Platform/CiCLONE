import os
from pathlib import Path
from typing import Dict, List, Optional, NamedTuple
from dataclasses import dataclass
from PyQt6.QtCore import QObject, pyqtSignal

from ciclone.domain.subject import Subject


@dataclass
class SubjectData:
    """Data structure for subject information."""
    name: str
    schema: str = ""  # For backward compatibility (will store comma-separated paths)
    schema_files: List[str] = None  # List of schema file paths
    pre_ct: str = ""
    pre_mri: str = ""
    post_ct: str = ""
    post_mri: str = ""
    
    def __post_init__(self):
        """Initialize schema_files list if not provided."""
        if self.schema_files is None:
            self.schema_files = []
            # If schema (legacy) is provided, add it to schema_files
            if self.schema:
                self.schema_files = [path.strip() for path in self.schema.split(',') if path.strip()]
    
    def get_schema_files(self) -> List[str]:
        """Get list of schema files."""
        return self.schema_files if self.schema_files else []
    
    def set_schema_files(self, file_paths: List[str]):
        """Set schema files and update legacy schema field."""
        self.schema_files = file_paths if file_paths else []
        self.schema = ', '.join(self.schema_files)
    
    def add_schema_file(self, file_path: str):
        """Add a single schema file."""
        if not self.schema_files:
            self.schema_files = []
        if file_path not in self.schema_files:
            self.schema_files.append(file_path)
            self.schema = ', '.join(self.schema_files)
    
    def has_schema_files(self) -> bool:
        """Check if any schema files are configured."""
        return len(self.get_schema_files()) > 0


class SubjectValidationResult(NamedTuple):
    """Result of subject validation."""
    is_valid: bool
    error_message: str = ""


class SubjectModel(QObject):
    """Model for managing subject data, validation, and state."""
    
    # Signals for notifying controllers/views of state changes
    subject_added = pyqtSignal(str)  # subject_name
    subject_removed = pyqtSignal(str)  # subject_name
    subject_renamed = pyqtSignal(str, str)  # old_name, new_name
    
    def __init__(self):
        super().__init__()
        self._output_directory: Optional[str] = None
        self._subjects: Dict[str, SubjectData] = {}
        
    def set_output_directory(self, directory_path: str):
        """Set the output directory and scan for existing subjects."""
        self._output_directory = directory_path
        self._scan_existing_subjects()
    
    def get_output_directory(self) -> Optional[str]:
        """Get the current output directory."""
        return self._output_directory
    
    def _scan_existing_subjects(self):
        """Scan the output directory for existing subjects."""
        self._subjects.clear()
        
        if not self._output_directory or not os.path.exists(self._output_directory):
            return
            
        for item in os.listdir(self._output_directory):
            item_path = os.path.join(self._output_directory, item)
            if os.path.isdir(item_path):
                # Create a basic SubjectData for existing subjects
                self._subjects[item] = SubjectData(name=item)
    
    def validate_subject_data(self, subject_data: SubjectData) -> SubjectValidationResult:
        """Validate subject data before creation."""
        if not subject_data.name.strip():
            return SubjectValidationResult(False, "Subject name cannot be empty")
        
        if not self._output_directory:
            return SubjectValidationResult(False, "Output directory not set")
        
        subject_dir = os.path.join(self._output_directory, subject_data.name)
        if os.path.exists(subject_dir):
            return SubjectValidationResult(False, "Subject already exists")
        
        return SubjectValidationResult(True)
    
    def validate_subject_rename(self, current_name: str, new_name: str) -> SubjectValidationResult:
        """Validate subject rename operation."""
        if not new_name.strip():
            return SubjectValidationResult(False, "New name cannot be empty")
        
        if new_name == current_name:
            return SubjectValidationResult(False, "New name must be different from current name")
        
        if not self._output_directory:
            return SubjectValidationResult(False, "Output directory not set")
        
        new_path = os.path.join(self._output_directory, new_name)
        if os.path.exists(new_path):
            return SubjectValidationResult(False, f"A subject named '{new_name}' already exists")
        
        current_path = os.path.join(self._output_directory, current_name)
        if not os.path.exists(current_path):
            return SubjectValidationResult(False, f"Subject '{current_name}' does not exist")
        
        return SubjectValidationResult(True)
    
    def validate_subject_deletion(self, subject_name: str) -> SubjectValidationResult:
        """Validate subject deletion operation."""
        if not self._output_directory:
            return SubjectValidationResult(False, "Output directory not set")
        
        subject_path = os.path.join(self._output_directory, subject_name)
        if not os.path.exists(subject_path):
            return SubjectValidationResult(False, f"Subject '{subject_name}' does not exist")
        
        return SubjectValidationResult(True)
    
    def add_subject(self, subject_data: SubjectData, skip_existence_check: bool = False) -> bool:
        """Add a subject to the model (without file operations).
        
        Args:
            subject_data: The subject data to add
            skip_existence_check: If True, skip checking if directory already exists 
                                (useful when adding after directory creation)
        """
        if not subject_data.name.strip():
            return False
        
        if not self._output_directory:
            return False
        
        # Only check for existing directory if skip_existence_check is False
        if not skip_existence_check:
            subject_dir = os.path.join(self._output_directory, subject_data.name)
            if os.path.exists(subject_dir):
                return False
        
        self._subjects[subject_data.name] = subject_data
        self.subject_added.emit(subject_data.name)
        return True
    
    def remove_subject(self, subject_name: str) -> bool:
        """Remove a subject from the model (without file operations)."""
        if subject_name in self._subjects:
            del self._subjects[subject_name]
            self.subject_removed.emit(subject_name)
            return True
        return False
    
    def rename_subject(self, old_name: str, new_name: str) -> bool:
        """Rename a subject in the model (without file operations)."""
        if old_name in self._subjects:
            subject_data = self._subjects[old_name]
            subject_data.name = new_name
            del self._subjects[old_name]
            self._subjects[new_name] = subject_data
            self.subject_renamed.emit(old_name, new_name)
            return True
        return False
    
    def get_subject(self, name: str) -> Optional[SubjectData]:
        """Get subject data by name."""
        return self._subjects.get(name)
    
    def get_all_subjects(self) -> List[SubjectData]:
        """Get all subjects."""
        return list(self._subjects.values())
    
    def get_subject_names(self) -> List[str]:
        """Get all subject names."""
        return list(self._subjects.keys())
    
    def get_subject_path(self, subject_name: str) -> Optional[str]:
        """Get the full path to a subject directory."""
        if not self._output_directory:
            return None
        return os.path.join(self._output_directory, subject_name)
    
    def create_subject_domain_object(self, subject_name: str) -> Optional[Subject]:
        """Create a Subject domain object for the given subject name."""
        subject_path = self.get_subject_path(subject_name)
        if subject_path and os.path.exists(subject_path):
            return Subject(subject_path)
        return None
    
    def subject_exists(self, subject_name: str) -> bool:
        """Check if a subject exists."""
        return subject_name in self._subjects
    
    def is_output_directory_set(self) -> bool:
        """Check if output directory is set."""
        return self._output_directory is not None 