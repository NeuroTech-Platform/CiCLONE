"""Configuration discovery and management service."""

import os
import yaml
from typing import List, Dict, Any, Optional, NamedTuple
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
        if not isinstance(stages, list) or not stages:
            return False
        
        # Check each stage has required fields
        for stage in stages:
            if not isinstance(stage, dict):
                return False
            if 'name' not in stage:
                return False
            if not isinstance(stage.get('operations', []), list):
                return False
            # Check new inline format fields
            if 'depends_on' in stage and not isinstance(stage['depends_on'], list):
                return False
            if 'outputs' in stage and not isinstance(stage['outputs'], list):
                return False
            if 'cleanup_patterns' in stage and not isinstance(stage['cleanup_patterns'], list):
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