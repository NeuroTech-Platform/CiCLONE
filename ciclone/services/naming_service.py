"""Service for managing file naming conventions."""

import yaml
from pathlib import Path
from typing import Dict, Optional, Any
from string import Template


class NamingService:
    """Service to handle configurable file naming conventions."""
    
    # Default naming patterns for backward compatibility
    DEFAULT_NAMING = {
        'pre_ct': '${name}_CT_Bone',
        'post_ct': '${name}_CT_Electrodes',
        'pre_mri': '${name}_${modality}',
        'post_mri': '${name}_${modality}'
    }
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the naming service.
        
        Args:
            config_path: Path to naming conventions config file.
                        If None, uses default path or built-in defaults.
        """
        self._naming_patterns = self._load_naming_conventions(config_path)
    
    def _load_naming_conventions(self, config_path: Optional[Path]) -> Dict[str, str]:
        """Load naming conventions from configuration file.
        
        Args:
            config_path: Path to config file or None
            
        Returns:
            Dictionary of naming patterns
        """
        # If no path provided, try default location
        if config_path is None:
            # Try to find config relative to this file
            default_path = Path(__file__).parent.parent / 'config' / 'naming_conventions.yaml'
            if default_path.exists():
                config_path = default_path
        
        # Load from file if available
        if config_path and config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    if config and 'file_naming' in config:
                        # Merge with defaults to ensure all keys exist
                        patterns = self.DEFAULT_NAMING.copy()
                        patterns.update(config['file_naming'])
                        return patterns
            except Exception as e:
                print(f"Warning: Could not load naming conventions from {config_path}: {e}")
                print("Using default naming conventions.")
        
        # Return defaults if no config or loading failed
        return self.DEFAULT_NAMING.copy()
    
    def get_filename(self, file_type: str, subject_name: str, 
                     modality: Optional[str] = None) -> str:
        """Generate a filename based on configured naming pattern.
        
        Args:
            file_type: Type of file ('pre_ct', 'post_ct', 'pre_mri', 'post_mri')
            subject_name: Name of the subject
            modality: MRI modality (for MRI files only)
            
        Returns:
            Generated filename (without extension)
        """
        pattern = self._naming_patterns.get(file_type)
        if not pattern:
            # Fallback to subject name if pattern not found
            return subject_name
        
        # Create substitution dictionary
        substitutions = {
            'name': subject_name,
            'modality': modality or 'MRI'  # Default to 'MRI' if modality not provided
        }
        
        # Use Template for safe substitution
        template = Template(pattern)
        try:
            return template.substitute(substitutions)
        except KeyError as e:
            print(f"Warning: Missing variable {e} in naming pattern for {file_type}")
            return subject_name
    
    def get_pre_ct_filename(self, subject_name: str) -> str:
        """Get filename for preoperative CT.
        
        Args:
            subject_name: Name of the subject
            
        Returns:
            Generated filename (without extension)
        """
        return self.get_filename('pre_ct', subject_name)
    
    def get_post_ct_filename(self, subject_name: str) -> str:
        """Get filename for postoperative CT.
        
        Args:
            subject_name: Name of the subject
            
        Returns:
            Generated filename (without extension)
        """
        return self.get_filename('post_ct', subject_name)
    
    def get_pre_mri_filename(self, subject_name: str, modality: str) -> str:
        """Get filename for preoperative MRI.
        
        Args:
            subject_name: Name of the subject
            modality: MRI modality (T1, T2, FLAIR, etc.)
            
        Returns:
            Generated filename (without extension)
        """
        return self.get_filename('pre_mri', subject_name, modality)
    
    def get_post_mri_filename(self, subject_name: str, modality: str) -> str:
        """Get filename for postoperative MRI.
        
        Args:
            subject_name: Name of the subject
            modality: MRI modality (T1, T2, FLAIR, etc.)
            
        Returns:
            Generated filename (without extension)
        """
        return self.get_filename('post_mri', subject_name, modality)
    
    def get_current_patterns(self) -> Dict[str, str]:
        """Get the current naming patterns in use.
        
        Returns:
            Dictionary of file type to naming pattern
        """
        return self._naming_patterns.copy()
    
    def update_pattern(self, file_type: str, pattern: str) -> None:
        """Update a naming pattern at runtime.
        
        Args:
            file_type: Type of file to update pattern for
            pattern: New naming pattern
        """
        if file_type in self._naming_patterns:
            self._naming_patterns[file_type] = pattern
        else:
            print(f"Warning: Unknown file type '{file_type}'")