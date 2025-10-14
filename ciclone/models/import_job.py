"""
Import Job data structure for unified image import workflow.

This module defines the ImportJob dataclass which represents a single image
import operation that may include cropping and optional coregistration.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional

from ciclone.models.job_validation_mixin import JobValidationMixin


@dataclass
class ImportJob(JobValidationMixin):
    """
    Represents a single image import job with optional crop and registration.

    This unified job combines what was previously separate CropJob and RegistrationJob
    into a single atomic operation.

    Attributes:
        subject_name: Name of the subject this import belongs to
        source_image_path: Absolute path to the source image file
        output_path: Absolute path where final processed image will be saved
        image_identifier: Human-readable identifier (e.g., "[Pre] CT", "[Post] MRI #2")
        needs_crop: Whether this image should be cropped with FSL robustfov (default True)
        registration_target_path: Optional path to reference image for coregistration
        registration_target_identifier: Optional human-readable identifier for reference image
        temp_crop_path: Optional temporary path for cropped image (used when registering)

    Examples:
        >>> # Simple import with crop only
        >>> job = ImportJob(
        ...     subject_name="Patient01",
        ...     source_image_path="/data/source/ct.nii.gz",
        ...     output_path="/data/Patient01/images/preop/ct/Patient01_CT.nii.gz",
        ...     image_identifier="[Pre] CT",
        ...     needs_crop=True,
        ...     registration_target_path=None
        ... )

        >>> # Import with crop and registration
        >>> job = ImportJob(
        ...     subject_name="Patient01",
        ...     source_image_path="/data/source/mri.nii.gz",
        ...     output_path="/data/Patient01/images/postop/mri/Patient01_T1_reg.nii.gz",
        ...     image_identifier="[Post] MRI",
        ...     needs_crop=True,
        ...     registration_target_path="/data/Patient01/images/preop/ct/Patient01_CT.nii.gz",
        ...     registration_target_identifier="[Pre] CT"
        ... )
    """

    subject_name: str
    source_image_path: str
    output_path: str
    image_identifier: str
    needs_crop: bool = True
    registration_target_path: Optional[str] = None
    registration_target_identifier: Optional[str] = None
    temp_crop_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for multiprocessing serialization.

        Returns:
            Dictionary representation of the import job
        """
        return {
            'subject_name': self.subject_name,
            'source_image_path': self.source_image_path,
            'output_path': self.output_path,
            'image_identifier': self.image_identifier,
            'needs_crop': self.needs_crop,
            'registration_target_path': self.registration_target_path,
            'registration_target_identifier': self.registration_target_identifier,
            'temp_crop_path': self.temp_crop_path
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImportJob':
        """
        Create ImportJob from dictionary.

        Args:
            data: Dictionary with all required fields

        Returns:
            New ImportJob instance
        """
        return cls(
            subject_name=data['subject_name'],
            source_image_path=data['source_image_path'],
            output_path=data['output_path'],
            image_identifier=data['image_identifier'],
            needs_crop=data.get('needs_crop', True),
            registration_target_path=data.get('registration_target_path'),
            registration_target_identifier=data.get('registration_target_identifier'),
            temp_crop_path=data.get('temp_crop_path')
        )

    def validate(self) -> tuple[bool, str]:
        """
        Validate the import job fields.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate subject name
        is_valid, error_msg = self._validate_string_not_empty(self.subject_name, "Subject name")
        if not is_valid:
            return False, error_msg

        # Validate source image path
        is_valid, error_msg = self._validate_path_not_empty(self.source_image_path, "Source image path")
        if not is_valid:
            return False, error_msg

        is_valid, error_msg = self._validate_file_exists(self.source_image_path, "Source image")
        if not is_valid:
            return False, error_msg

        # Validate output path
        is_valid, error_msg = self._validate_path_not_empty(self.output_path, "Output path")
        if not is_valid:
            return False, error_msg

        is_valid, error_msg = self._validate_output_directory_exists(self.output_path, "Output file")
        if not is_valid:
            return False, error_msg

        # Note: We do NOT validate that registration_target_path exists here
        # because in batch imports, the target may be created by a previous job
        # in the same batch. The actual registration process will check for
        # target existence at execution time.

        return True, ""

    def get_display_name(self) -> str:
        """
        Get a human-readable display name for this import job.

        Returns:
            Formatted string describing the import operation
        """
        if self.registration_target_path:
            return f"{self.image_identifier} → {self.registration_target_identifier}"
        else:
            return f"{self.image_identifier}"

    def needs_registration(self) -> bool:
        """Check if this job includes registration."""
        return self.registration_target_path is not None
