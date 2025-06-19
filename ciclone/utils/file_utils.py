"""
Centralized file utilities for CiCLONE application.
Consolidates common file operations to reduce redundancy.
"""

import os
import shutil
from pathlib import Path
from typing import List, Optional, Tuple, Union
from PIL import Image


class FileUtils:
    """Centralized file utilities for common operations."""
    
    # Common file extensions
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp'}
    NIFTI_EXTENSIONS = {'.nii', '.nii.gz'}
    POWERPOINT_EXTENSIONS = {'.ppt', '.pptx'}
    MARKDOWN_EXTENSIONS = {'.md', '.markdown', '.txt'}
    
    @classmethod
    def get_file_extension(cls, file_path: str) -> str:
        """Get file extension, handling compound extensions like .nii.gz"""
        path = Path(file_path)
        if path.name.endswith('.nii.gz'):
            return '.nii.gz'
        return path.suffix.lower()
    
    @classmethod
    def is_file_type(cls, file_path: str, extensions: set) -> bool:
        """Check if file matches any of the given extensions."""
        return cls.get_file_extension(file_path) in extensions
    
    @classmethod
    def ensure_directory(cls, directory_path: str) -> bool:
        """Ensure directory exists, create if necessary."""
        try:
            os.makedirs(directory_path, exist_ok=True)
            return True
        except (OSError, PermissionError):
            return False
    
    @classmethod
    def safe_copy_file(cls, source_path: str, dest_path: str, 
                      convert_for_compatibility: bool = True) -> Tuple[bool, str]:
        """
        Safely copy a file with optional format conversion.
        
        Args:
            source_path: Source file path
            dest_path: Destination file path
            convert_for_compatibility: Whether to convert RGBA to RGB for JPEG
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            source = Path(source_path)
            dest = Path(dest_path)
            
            if not source.exists():
                return False, f"Source file does not exist: {source_path}"
            
            # Ensure destination directory exists
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            # For image files, use PIL for better format handling
            if cls.is_file_type(source_path, cls.IMAGE_EXTENSIONS) and convert_for_compatibility:
                with Image.open(source) as img:
                    # Convert RGBA to RGB for JPEG compatibility
                    dest_ext = cls.get_file_extension(str(dest))
                    if dest_ext in ['.jpg', '.jpeg'] and img.mode in ('RGBA', 'LA'):
                        img = img.convert('RGB')
                    img.save(dest)
            else:
                # Use standard file copy for non-images or when no conversion needed
                shutil.copy2(source, dest)
            
            return True, ""
            
        except Exception as e:
            return False, f"Copy failed: {str(e)}"
    
    @classmethod
    def generate_filename(cls, base_name: str, extension: str, 
                         index: Optional[int] = None, total_count: int = 1) -> str:
        """
        Generate filename with consistent naming convention.
        
        Args:
            base_name: Base name for the file
            extension: File extension (with or without dot)
            index: File index (1-based) for numbered files
            total_count: Total number of files (affects numbering format)
        
        Returns:
            Generated filename
        """
        if not extension.startswith('.'):
            extension = f'.{extension}'
        
        if total_count == 1:
            return f"{base_name}{extension}"
        else:
            # Use 3-digit padding for multiple files
            return f"{base_name}_{index:03d}{extension}"
    
    @classmethod
    def create_file_filter(cls, file_types: dict) -> str:
        """
        Create a file filter string for file dialogs.
        
        Args:
            file_types: Dict of {name: extensions_set}
        
        Returns:
            File filter string for QFileDialog
        """
        filters = []
        
        # Create individual type filters
        for name, extensions in file_types.items():
            ext_patterns = [f"*{ext}" for ext in extensions]
            filters.append(f"{name} ({' '.join(ext_patterns)})")
        
        # Add combined filter if multiple types
        if len(file_types) > 1:
            all_extensions = set()
            for extensions in file_types.values():
                all_extensions.update(extensions)
            all_patterns = [f"*{ext}" for ext in all_extensions]
            filters.insert(0, f"All supported ({' '.join(all_patterns)})")
        
        # Add "All files" option
        filters.append("All files (*.*)")
        
        return ";;".join(filters) 