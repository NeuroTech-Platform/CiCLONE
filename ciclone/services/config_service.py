"""Configuration discovery and management service."""

import os
import yaml
import shutil
from typing import List, Dict, Any, Optional, NamedTuple, Tuple
from pathlib import Path


class ConfigInfo(NamedTuple):
    """Information about a configuration file."""
    name: str
    file_path: str
    display_name: str
    stage_count: int
    description: Optional[str] = None


class ConfigService:
    """Service for discovering and managing configuration files."""
    
    def __init__(self, config_dir_path: str):
        """Initialize the config service.
        
        Args:
            config_dir_path: Path to the configuration directory
        """
        self.config_dir = Path(config_dir_path)
        self._config_cache: Dict[str, Dict[str, Any]] = {}
    
    def discover_configs(self) -> List[ConfigInfo]:
        """Discover all available configuration files.
        
        Returns:
            List of ConfigInfo objects for available configurations
        """
        configs = []
        
        if not self.config_dir.exists():
            return configs
        
        for yaml_file in self.config_dir.glob("*.yaml"):
            if yaml_file.name.endswith('.template'):
                continue
                
            try:
                config_data = self._load_config_file(yaml_file)
                if self.validate_config(config_data):
                    config_info = self._create_config_info(yaml_file, config_data)
                    configs.append(config_info)
            except Exception as e:
                print(f"Warning: Could not load config {yaml_file.name}: {e}")
                continue
        
        return sorted(configs, key=lambda x: x.name)
    
    def load_config(self, name: str) -> Optional[Dict[str, Any]]:
        """Load a specific configuration by name.
        
        Args:
            name: Name of the configuration (without .yaml extension)
            
        Returns:
            Configuration dictionary or None if not found
        """
        if name in self._config_cache:
            return self._config_cache[name]
        
        config_path = self.config_dir / f"{name}.yaml"
        if not config_path.exists():
            return None
        
        try:
            config_data = self._load_config_file(config_path)
            if self.validate_config(config_data):
                self._config_cache[name] = config_data
                return config_data
        except Exception as e:
            print(f"Error loading config {name}: {e}")
            return None
        
        return None
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate config has required structure."""
        stages = config.get('stages', [])
        if not isinstance(stages, list):
            return False
        
        # Allow empty stages for new configurations
        if not stages:
            return True
        
        # Check each stage has required fields
        for stage in stages:
            if not isinstance(stage, dict):
                return False
            if 'name' not in stage:
                return False
            if not isinstance(stage.get('operations', []), list):
                return False
            
            # Validate simplified format fields
            if 'depends_on' in stage and not isinstance(stage['depends_on'], list):
                return False
            if 'auto_clean' in stage and not isinstance(stage['auto_clean'], bool):
                return False
        
        return True
    
    
    def get_default_config_name(self) -> Optional[str]:
        """Get the default configuration name.
        
        Returns:
            Name of default config or None if no configs available
        """
        configs = self.discover_configs()
        if not configs:
            return None
        
        for config in configs:
            if config.name == 'config':
                return config.name
        
        return configs[0].name
    
    def _load_config_file(self, file_path: Path) -> Dict[str, Any]:
        """Load a YAML configuration file.
        
        Args:
            file_path: Path to the configuration file
            
        Returns:
            Configuration dictionary
        """
        with open(file_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file) or {}
    
    def _create_config_info(self, file_path: Path, config_data: Dict[str, Any]) -> ConfigInfo:
        """Create a ConfigInfo object from file path and config data.
        
        Args:
            file_path: Path to the configuration file
            config_data: Configuration dictionary
            
        Returns:
            ConfigInfo object
        """
        config_id = file_path.stem
        stages = config_data.get('stages', [])
        stage_count = len(stages)
        
        custom_name = config_data.get('name')
        if custom_name:
            display_name = custom_name
        else:
            display_name = config_id.replace('_', ' ').title()
            if display_name == 'Config':
                display_name = 'Default'
        
        description = config_data.get('description')
        
        return ConfigInfo(
            name=config_id,
            file_path=str(file_path),
            display_name=display_name,
            stage_count=stage_count,
            description=description
        )
    
    # Write/Edit capabilities added for pipeline configuration dialog
    
    def save_config(self, config_name: str, config_data: Dict[str, Any]) -> bool:
        """Save a pipeline configuration.
        
        Args:
            config_name: Name for the configuration file (without .yaml)
            config_data: Configuration dictionary to save
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Validate before saving with detailed error information
            is_valid, error_msg = self.validate_config_detailed(config_data)
            if not is_valid:
                raise ValueError(f"Invalid configuration structure: {error_msg}")
            
            # Sanitize config name for filesystem
            safe_config_name = self._sanitize_filename(config_name)
            
            # Clean the config data (remove metadata if present)
            clean_config = self._clean_config_for_save(config_data)
            
            # Ensure config directory exists
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            # Determine file path using sanitized name
            config_path = self.config_dir / f"{safe_config_name}.yaml"
            
            # Save to temporary file first, then rename (atomic operation)
            temp_path = config_path.with_suffix('.yaml.tmp')
            
            with open(temp_path, 'w', encoding='utf-8') as file:
                yaml.dump(clean_config, file, default_flow_style=False, 
                         sort_keys=False, indent=2, allow_unicode=True)
            
            # Atomic rename
            temp_path.rename(config_path)
            
            # Clear cache to force reload (use sanitized name)
            self._config_cache.pop(safe_config_name, None)
            
            return True
            
        except Exception as e:
            print(f"Error saving config {config_name}: {e}")
            # Clean up temp file if it exists (use sanitized name for cleanup)
            safe_config_name = self._sanitize_filename(config_name)
            temp_path = self.config_dir / f"{safe_config_name}.yaml.tmp"
            if temp_path.exists():
                temp_path.unlink()
            return False
    
    
    def delete_config(self, config_name: str) -> bool:
        """Delete a pipeline configuration.
        
        Args:
            config_name: Name of the configuration to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            config_path = self.config_dir / f"{config_name}.yaml"
            if config_path.exists():
                config_path.unlink()
                
                # Clear from cache
                self._config_cache.pop(config_name, None)
                
                return True
            return False
            
        except Exception as e:
            print(f"Error deleting config {config_name}: {e}")
            return False
    
    
    
    
    
    def validate_config_detailed(self, config_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate configuration data and return detailed error information.
        
        Args:
            config_data: Configuration dictionary to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            if not isinstance(config_data, dict):
                return False, "Configuration must be a dictionary"
            
            if 'name' not in config_data:
                return False, "Configuration must have a 'name' field"
            
            stages = config_data.get('stages', [])
            if not isinstance(stages, list):
                return False, "Stages must be a list"
            
            # Allow empty stages for new configurations during editing
            if not stages:
                return True, ""
            
            # Validate each stage
            stage_names = set()
            for i, stage in enumerate(stages):
                if not isinstance(stage, dict):
                    return False, f"Stage {i+1} must be a dictionary"
                
                stage_name = stage.get('name')
                if not stage_name:
                    return False, f"Stage {i+1} must have a 'name' field"
                
                if stage_name in stage_names:
                    return False, f"Duplicate stage name: {stage_name}"
                stage_names.add(stage_name)
                
                # Validate dependencies
                depends_on = stage.get('depends_on', [])
                if not isinstance(depends_on, list):
                    return False, f"Stage '{stage_name}' dependencies must be a list"
                
                # Validate operations
                operations = stage.get('operations', [])
                if not isinstance(operations, list):
                    return False, f"Stage '{stage_name}' operations must be a list"
            
            return True, ""
            
        except Exception as e:
            return False, f"Validation error: {e}"
    
    def get_available_configs_for_editing(self) -> List[Dict[str, Any]]:
        """Get list of available pipeline configurations for editing.
        
        Returns:
            List of configuration dictionaries with metadata
        """
        config_infos = self.discover_configs()
        configs = []
        
        for config_info in config_infos:
            config_data = self.load_config(config_info.name)
            if config_data:
                # Create a deep copy to avoid modifying the cached config
                import copy
                config_copy = copy.deepcopy(config_data)
                
                # Add metadata for UI display to the copy
                config_copy['_metadata'] = {
                    'file_path': config_info.file_path,
                    'display_name': config_info.display_name,
                    'stage_count': config_info.stage_count,
                    'config_name': config_info.name
                }
                configs.append(config_copy)
        
        return configs
    
    def _clean_config_for_save(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean configuration data by removing metadata and UI-specific fields.
        
        Args:
            config_data: Configuration dictionary to clean
            
        Returns:
            Cleaned configuration dictionary
        """
        clean_config = config_data.copy()
        
        # Remove metadata if present
        clean_config.pop('_metadata', None)
        
        return clean_config
    
    def _sanitize_filename(self, filename: str) -> str:
        """Remove or replace invalid filesystem characters from filename.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename safe for filesystem use
        """
        # Characters that are invalid in most filesystems
        invalid_chars = '<>:"/\\|?*'
        
        # Replace invalid characters with underscores
        sanitized = filename
        for char in invalid_chars:
            sanitized = sanitized.replace(char, '_')
        
        # Remove leading/trailing whitespace and dots
        sanitized = sanitized.strip(' .')
        
        # Ensure filename is not empty after sanitization
        if not sanitized:
            sanitized = 'config'
        
        return sanitized
    
