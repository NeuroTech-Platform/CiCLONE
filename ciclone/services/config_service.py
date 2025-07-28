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
    
    def get_config_info(self, name: str) -> Optional[ConfigInfo]:
        """Get information about a specific configuration.
        
        Args:
            name: Name of the configuration
            
        Returns:
            ConfigInfo object or None if not found
        """
        config_path = self.config_dir / f"{name}.yaml"
        if not config_path.exists():
            return None
        
        try:
            config_data = self._load_config_file(config_path)
            if self.validate_config(config_data):
                return self._create_config_info(config_path, config_data)
        except Exception:
            return None
        
        return None
    
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
            
            # Clean the config data (remove metadata if present)
            clean_config = self._clean_config_for_save(config_data)
            
            # Ensure config directory exists
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            # Determine file path
            config_path = self.config_dir / f"{config_name}.yaml"
            
            # Save to temporary file first, then rename (atomic operation)
            temp_path = config_path.with_suffix('.yaml.tmp')
            
            with open(temp_path, 'w', encoding='utf-8') as file:
                yaml.dump(clean_config, file, default_flow_style=False, 
                         sort_keys=False, indent=2, allow_unicode=True)
            
            # Atomic rename
            temp_path.rename(config_path)
            
            # Clear cache to force reload
            self._config_cache.pop(config_name, None)
            
            return True
            
        except Exception as e:
            print(f"Error saving config {config_name}: {e}")
            # Clean up temp file if it exists
            temp_path = self.config_dir / f"{config_name}.yaml.tmp"
            if temp_path.exists():
                temp_path.unlink()
            return False
    
    def create_new_config(self, config_name: str, base_template: Optional[str] = None) -> Dict[str, Any]:
        """Create a new pipeline configuration.
        
        Args:
            config_name: Name for the new configuration
            base_template: Optional base template to copy from
            
        Returns:
            New configuration dictionary
        """
        if base_template and base_template != "scratch":
            # Load base template
            base_config = self.load_config(base_template)
            if base_config:
                new_config = base_config.copy()
                new_config['name'] = config_name
                return new_config
        
        # Create from scratch
        return {
            'name': config_name,
            'stages': []
        }
    
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
    
    def duplicate_config(self, source_config: str, new_name: str) -> bool:
        """Duplicate an existing configuration.
        
        Args:
            source_config: Name of the source configuration
            new_name: Name for the new configuration
            
        Returns:
            True if duplicated successfully, False otherwise
        """
        try:
            source_data = self.load_config(source_config)
            if not source_data:
                return False
            
            # Update name and save as new config
            new_config = source_data.copy()
            new_config['name'] = new_name
            
            return self.save_config(new_name, new_config)
            
        except Exception as e:
            print(f"Error duplicating config {source_config} to {new_name}: {e}")
            return False
    
    def import_config_from_file(self, file_path: str, new_name: Optional[str] = None) -> Optional[str]:
        """Import a configuration from an external file.
        
        Args:
            file_path: Path to the configuration file to import
            new_name: Optional new name for the imported config
            
        Returns:
            Name of the imported configuration, or None if failed
        """
        try:
            import_path = Path(file_path)
            if not import_path.exists():
                return None
            
            # Load and validate the config
            with open(import_path, 'r', encoding='utf-8') as file:
                config_data = yaml.safe_load(file) or {}
            
            if not self.validate_config(config_data):
                raise ValueError("Invalid configuration structure in imported file")
            
            # Determine name for imported config
            config_name = new_name or import_path.stem
            
            # Ensure unique name
            config_name = self._ensure_unique_config_name(config_name)
            
            # Update config name if different
            config_data['name'] = config_name
            
            # Save the imported config
            if self.save_config(config_name, config_data):
                return config_name
            
            return None
            
        except Exception as e:
            print(f"Error importing config from {file_path}: {e}")
            return None
    
    def export_config_to_file(self, config_name: str, export_path: str) -> bool:
        """Export a configuration to an external file.
        
        Args:
            config_name: Name of the configuration to export
            export_path: Path where to save the exported file
            
        Returns:
            True if exported successfully, False otherwise
        """
        try:
            config_data = self.load_config(config_name)
            if not config_data:
                return False
            
            # Clean the config for export
            clean_config = self._clean_config_for_save(config_data)
            
            export_file = Path(export_path)
            export_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(export_file, 'w', encoding='utf-8') as file:
                yaml.dump(clean_config, file, default_flow_style=False,
                         sort_keys=False, indent=2, allow_unicode=True)
            
            return True
            
        except Exception as e:
            print(f"Error exporting config {config_name} to {export_path}: {e}")
            return False
    
    def generate_yaml_preview(self, config_data: Dict[str, Any]) -> str:
        """Generate a YAML preview string for a configuration.
        
        Args:
            config_data: Configuration dictionary
            
        Returns:
            YAML string representation
        """
        try:
            clean_config = self._clean_config_for_save(config_data)
            return yaml.dump(clean_config, default_flow_style=False,
                           sort_keys=False, indent=2, allow_unicode=True)
        except Exception as e:
            return f"Error generating preview: {e}"
    
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
                # Add metadata for UI display
                config_data['_metadata'] = {
                    'file_path': config_info.file_path,
                    'display_name': config_info.display_name,
                    'stage_count': config_info.stage_count,
                    'config_name': config_info.name
                }
                configs.append(config_data)
        
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
    
    def _ensure_unique_config_name(self, base_name: str) -> str:
        """Ensure a configuration name is unique by appending numbers if needed.
        
        Args:
            base_name: Base configuration name
            
        Returns:
            Unique configuration name
        """
        config_path = self.config_dir / f"{base_name}.yaml"
        if not config_path.exists():
            return base_name
        
        counter = 1
        while True:
            candidate_name = f"{base_name}_{counter}"
            config_path = self.config_dir / f"{candidate_name}.yaml"
            if not config_path.exists():
                return candidate_name
            counter += 1