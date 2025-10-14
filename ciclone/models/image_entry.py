"""
Image entry data structure for subject image management.

This module defines the ImageEntry dataclass which represents a single
medical image with its metadata (session, modality, registration target).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ImageEntry:
    """
    Represents a single medical image with associated metadata.

    Attributes:
        file_path: Absolute path to the medical image file
        session: Imaging session - "Pre" (preoperative) or "Post" (postoperative)
        modality: Imaging modality - "CT", "MRI", or "PET"
        register_to: Optional registration target (reference to another image identifier)

    Examples:
        >>> entry = ImageEntry("/path/to/ct.nii.gz", "Pre", "CT", None)
        >>> entry.display_name()
        '[Pre] CT - ct.nii.gz'

        >>> entry_with_reg = ImageEntry("/path/to/mri.nii", "Post", "MRI", "pre_ct")
        >>> entry_with_reg.display_name()
        '[Post] MRI - mri.nii → pre_ct'
    """

    file_path: str
    session: str  # "Pre" or "Post"
    modality: str  # "CT", "MRI", "PET"
    register_to: Optional[str] = None  # None or identifier of registration target

    def display_name(self) -> str:
        """
        Generate user-friendly display name for UI list widgets.

        Returns:
            Formatted string showing session, modality, filename, and registration target
        """
        import os
        filename = os.path.basename(self.file_path)
        base_display = f"[{self.session}] {self.modality} - {filename}"

        if self.register_to:
            base_display += f" → {self.register_to}"

        return base_display

    def get_directory_name(self) -> str:
        """
        Get the appropriate subdirectory name for this image.

        Returns:
            Directory name like "preop/ct", "postop/mri", etc.
        """
        session_dir = "preop" if self.session == "Pre" else "postop"
        modality_dir = self.modality.lower()
        return f"{session_dir}/{modality_dir}"

    def to_dict(self) -> dict:
        """
        Convert to dictionary for serialization.

        Returns:
            Dictionary representation of the image entry
        """
        return {
            'file_path': self.file_path,
            'session': self.session,
            'modality': self.modality,
            'register_to': self.register_to
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ImageEntry':
        """
        Create ImageEntry from dictionary.

        Args:
            data: Dictionary with file_path, session, modality, and optional register_to

        Returns:
            New ImageEntry instance
        """
        return cls(
            file_path=data['file_path'],
            session=data['session'],
            modality=data['modality'],
            register_to=data.get('register_to')
        )

    def validate(self) -> tuple[bool, str]:
        """
        Validate the image entry fields.

        Returns:
            Tuple of (is_valid, error_message)
        """
        import os

        if not self.file_path or not self.file_path.strip():
            return False, "File path is required"

        if not os.path.exists(self.file_path):
            return False, f"File does not exist: {self.file_path}"

        if self.session not in ["Pre", "Post"]:
            return False, f"Invalid session: {self.session}. Must be 'Pre' or 'Post'"

        if self.modality not in ["CT", "MRI", "PET"]:
            return False, f"Invalid modality: {self.modality}. Must be 'CT', 'MRI', or 'PET'"

        return True, ""
