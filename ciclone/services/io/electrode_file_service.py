"""
Electrode File Service for CiCLONE Application

This service handles file operations for electrode definitions,
providing dependency injection for the ElectrodeModel.
"""

import os
from typing import Dict
from pathlib import Path


class ElectrodeFileService:
    """Service for handling electrode definition file operations."""
    
    def __init__(self, config_path: str = None):
        """
        Initialize electrode file service.
        
        Args:
            config_path: Optional custom path to electrode config directory
                        If None, uses default relative path
        """
        if config_path:
            self.config_path = Path(config_path)
        else:
            # Default path relative to the package
            self.config_path = self._get_default_config_path()
    
    def _get_default_config_path(self) -> Path:
        """Get the default configuration path."""
        # Navigate from services/io to config/electrodes
        current_file = Path(__file__)
        package_root = current_file.parent.parent.parent  # ciclone/
        return package_root / "config" / "electrodes"
    
    def load_electrode_definitions(self) -> Dict[str, str]:
        """
        Load electrode definition files from the config directory.
        
        Returns:
            Dict mapping electrode names to file paths
        """
        electrode_files = []
        
        if not self.config_path.exists():
            print(f"Electrode config directory not found: {self.config_path}")
            return {}
        
        print(f"Loading electrode definitions from {self.config_path}")
        
        for file_path in self.config_path.iterdir():
            if file_path.suffix == ".elecdef":
                name = file_path.stem  # filename without extension
                electrode_files.append((name, str(file_path)))
        
        # Sort electrode files alphabetically by name
        electrode_files.sort(key=lambda x: x[0])
        return dict(electrode_files)
    
    def electrode_definition_exists(self, electrode_type: str) -> bool:
        """
        Check if an electrode definition file exists for the given type.
        
        Args:
            electrode_type: The electrode type to check
            
        Returns:
            True if definition file exists
        """
        definition_file = self.config_path / f"{electrode_type}.elecdef"
        return definition_file.exists()
    
    def get_electrode_definition_path(self, electrode_type: str) -> str:
        """
        Get the full path to an electrode definition file.
        
        Args:
            electrode_type: The electrode type
            
        Returns:
            Full path to the definition file
            
        Raises:
            FileNotFoundError: If the definition file doesn't exist
        """
        definition_file = self.config_path / f"{electrode_type}.elecdef"
        if not definition_file.exists():
            raise FileNotFoundError(f"Electrode definition file not found: {definition_file}")
        return str(definition_file)
    
    def list_available_electrode_types(self) -> list[str]:
        """
        Get a list of all available electrode types.
        
        Returns:
            List of electrode type names
        """
        if not self.config_path.exists():
            return []
        
        electrode_types = []
        for file_path in self.config_path.iterdir():
            if file_path.suffix == ".elecdef":
                electrode_types.append(file_path.stem)
        
        return sorted(electrode_types)