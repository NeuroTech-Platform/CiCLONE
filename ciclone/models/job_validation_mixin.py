"""
Validation mixin for job dataclasses.

This module provides common validation utilities for job objects (CropJob,
RegistrationJob, etc.) to reduce code duplication and ensure consistent
validation patterns across different job types.
"""

import os
from pathlib import Path
from typing import Tuple


class JobValidationMixin:
    """
    Mixin class providing common validation methods for job dataclasses.

    This mixin can be used with any job dataclass that needs to validate
    file paths and directory existence. It provides reusable validation
    utilities that enforce consistent error messages and validation logic.

    Usage:
        @dataclass
        class MyJob(JobValidationMixin):
            input_path: str
            output_path: str

            def validate(self) -> Tuple[bool, str]:
                # Use mixin methods
                is_valid, msg = self._validate_file_exists(self.input_path, "Input file")
                if not is_valid:
                    return False, msg
                ...
    """

    def _validate_file_exists(self, file_path: str, field_name: str = "File") -> Tuple[bool, str]:
        """
        Validate that a file exists at the given path.

        Args:
            file_path: Path to the file to validate
            field_name: Human-readable field name for error messages

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not file_path or not file_path.strip():
            return False, f"{field_name} path is required"

        if not os.path.exists(file_path):
            return False, f"{field_name} does not exist: {file_path}"

        if not os.path.isfile(file_path):
            return False, f"{field_name} path is not a file: {file_path}"

        return True, ""

    def _validate_directory_exists(self, dir_path: str, field_name: str = "Directory") -> Tuple[bool, str]:
        """
        Validate that a directory exists at the given path.

        Args:
            dir_path: Path to the directory to validate
            field_name: Human-readable field name for error messages

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not dir_path or not dir_path.strip():
            return False, f"{field_name} path is required"

        if not os.path.exists(dir_path):
            return False, f"{field_name} does not exist: {dir_path}"

        if not os.path.isdir(dir_path):
            return False, f"{field_name} path is not a directory: {dir_path}"

        return True, ""

    def _validate_output_directory_exists(self, file_path: str, field_name: str = "Output file") -> Tuple[bool, str]:
        """
        Validate that the parent directory of an output file exists.

        This is useful for validating output paths before attempting to write files.
        The file itself doesn't need to exist, but its parent directory must.

        Args:
            file_path: Path to the output file
            field_name: Human-readable field name for error messages

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not file_path or not file_path.strip():
            return False, f"{field_name} path is required"

        # Check that output directory exists
        output_dir = os.path.dirname(file_path)
        if not os.path.exists(output_dir):
            return False, f"Output directory does not exist: {output_dir}"

        return True, ""

    def _validate_path_not_empty(self, path: str, field_name: str = "Path") -> Tuple[bool, str]:
        """
        Validate that a path is not empty or whitespace-only.

        Args:
            path: Path string to validate
            field_name: Human-readable field name for error messages

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not path or not path.strip():
            return False, f"{field_name} is required"

        return True, ""

    def _validate_string_not_empty(self, value: str, field_name: str = "Value") -> Tuple[bool, str]:
        """
        Validate that a string value is not empty or whitespace-only.

        Args:
            value: String value to validate
            field_name: Human-readable field name for error messages

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value or not value.strip():
            return False, f"{field_name} is required"

        return True, ""
