"""
Registration Target Resolver for resolving image identifiers to file paths.

This module provides functionality to resolve human-readable image identifiers
(like "[Pre] CT" or "[Post] MRI #2") to actual file paths in the subject directory.
"""

import os
import re
from pathlib import Path
from typing import Optional, List, Dict
from ciclone.domain.subject import Subject


class RegistrationTargetResolver:
    """Resolves registration target identifiers to actual file paths."""

    @staticmethod
    def resolve_target(
        subject: Subject,
        target_identifier: str,
        newly_imported_images: Optional[List[Dict]] = None
    ) -> Optional[str]:
        """
        Resolve a registration target identifier to an actual file path.

        Args:
            subject: Subject domain object with directory structure
            target_identifier: Identifier like "[Pre] CT", "[Post] MRI #2", etc.
            newly_imported_images: List of just-imported image dicts with paths

        Returns:
            Absolute path to the target file, or None if not found

        Examples:
            >>> resolver = RegistrationTargetResolver()
            >>> path = resolver.resolve_target(subject, "[Pre] CT")
            >>> path = resolver.resolve_target(subject, "[Post] MRI #2")
        """
        if not target_identifier or target_identifier == "None":
            return None

        # Parse the identifier
        parsed = RegistrationTargetResolver._parse_identifier(target_identifier)
        if not parsed:
            print(f"Warning: Could not parse target identifier: {target_identifier}")
            return None

        session, modality, index = parsed

        # First, check newly imported images (they take precedence)
        if newly_imported_images:
            target_path = RegistrationTargetResolver._find_in_imported_images(
                newly_imported_images, session, modality, index
            )
            if target_path:
                return target_path

        # Then, check existing files in subject directory
        target_path = RegistrationTargetResolver._find_in_subject_directory(
            subject, session, modality, index
        )

        if not target_path:
            print(f"Warning: Could not resolve target '{target_identifier}' for subject {subject.get_subject_name()}")

        return target_path

    @staticmethod
    def _parse_identifier(identifier: str) -> Optional[tuple[str, str, int]]:
        """
        Parse an identifier into components.

        Args:
            identifier: String like "[Pre] CT", "[Post] MRI #2"

        Returns:
            Tuple of (session, modality, index) or None if invalid

        Examples:
            "[Pre] CT" → ("Pre", "CT", 1)
            "[Post] MRI #2" → ("Post", "MRI", 2)
            "[Pre] PET #3" → ("Pre", "PET", 3)
        """
        # Remove " (new)" suffix if present
        identifier = identifier.replace(" (new)", "").strip()

        # Pattern: [Session] Modality [#N]
        pattern = r'\[(\w+)\]\s+(\w+)(?:\s+#(\d+))?'
        match = re.match(pattern, identifier)

        if not match:
            return None

        session = match.group(1)  # "Pre" or "Post"
        modality = match.group(2)  # "CT", "MRI", "PET"
        index_str = match.group(3)  # "2", "3", etc. or None

        # Convert to 1-based index (default to 1 if not specified)
        index = int(index_str) if index_str else 1

        return session, modality, index

    @staticmethod
    def _find_in_imported_images(
        images: List[Dict],
        session: str,
        modality: str,
        index: int
    ) -> Optional[str]:
        """
        Find the Nth image of given session/modality in imported images list.

        Args:
            images: List of image dicts with 'file_path', 'session', 'modality'
            session: "Pre" or "Post"
            modality: "CT", "MRI", or "PET"
            index: 1-based index (1 for first, 2 for second, etc.)

        Returns:
            File path or None if not found
        """
        matching_images = [
            img for img in images
            if img.get('session') == session and img.get('modality') == modality
        ]

        # Check if index is valid (1-based)
        if 0 < index <= len(matching_images):
            return matching_images[index - 1]['file_path']

        return None

    @staticmethod
    def _find_in_subject_directory(
        subject: Subject,
        session: str,
        modality: str,
        index: int
    ) -> Optional[str]:
        """
        Find the Nth image of given session/modality in subject directory.

        Args:
            subject: Subject domain object
            session: "Pre" or "Post"
            modality: "CT", "MRI", or "PET"
            index: 1-based index (1 for first, 2 for second, etc.)

        Returns:
            File path or None if not found
        """
        # Map session to directory
        session_lower = "preop" if session == "Pre" else "postop"
        modality_lower = modality.lower()

        # Get modality directory
        modality_dir = subject.folder_path / 'images' / session_lower / modality_lower

        if not modality_dir.exists():
            return None

        # Find all image files in the directory
        image_files = []
        for file_path in modality_dir.iterdir():
            if file_path.is_file() and RegistrationTargetResolver._is_image_file(file_path):
                image_files.append(file_path)

        # Sort by name for consistent ordering
        image_files.sort()

        # Check if index is valid (1-based)
        if 0 < index <= len(image_files):
            return str(image_files[index - 1])

        return None

    @staticmethod
    def _is_image_file(file_path: Path) -> bool:
        """
        Check if a file is a medical image file.

        Args:
            file_path: Path to check

        Returns:
            True if file is a medical image (.nii, .nii.gz, .dcm)
        """
        name = file_path.name.lower()
        return name.endswith(('.nii', '.nii.gz', '.dcm'))
