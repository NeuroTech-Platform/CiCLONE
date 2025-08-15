import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from PyQt6.QtCore import QObject, pyqtSignal, QSettings

from ciclone.services.config_service import ConfigService, ConfigInfo


@dataclass
class WorkerState:
    """State information for image processing worker."""
    is_running: bool = False
    worker_instance: Optional[Any] = None
    progress: int = 0


@dataclass
class UIState:
    """State information for UI components."""
    images_viewer_instance: Optional[Any] = None
    current_stages_selection: List[str] = None
    
    def __post_init__(self):
        if self.current_stages_selection is None:
            self.current_stages_selection = []


class ApplicationModel(QObject):
    """Model for managing centralized application state and configuration."""
    
    # Signals for notifying controllers/views of state changes
    output_directory_changed = pyqtSignal(str)  # new_directory_path
    config_loaded = pyqtSignal(dict)  # config_data
    config_changed = pyqtSignal(str)  # config_name
    configs_discovered = pyqtSignal(list)  # available_configs
    worker_state_changed = pyqtSignal(bool, int)  # is_running, progress
    images_viewer_state_changed = pyqtSignal(bool)  # is_active
    stages_selection_changed = pyqtSignal(list)  # selected_stage_names
    
    def __init__(self, config_dir_path: str):
        """Initialize ApplicationModel with multi-config support.
        
        Args:
            config_dir_path: Path to directory containing configuration files
        """
        super().__init__()
        self._init_state()
        self._init_config_system(config_dir_path)
    
    def _init_state(self):
        """Initialize core application state."""
        self._output_directory: Optional[str] = None
        self._config: Dict[str, Any] = {}
        self._worker_state = WorkerState()
        self._ui_state = UIState()
        self._config_service: Optional[ConfigService] = None
        self._available_configs: List[ConfigInfo] = []
        self._current_config_name: Optional[str] = None
        self._settings = QSettings("CiCLONE", "Application")
    
    def _init_config_system(self, config_dir_path: str):
        """Initialize multi-configuration system."""
        self._config_service = ConfigService(config_dir_path)
        self._discover_configs()
    
    # Output Directory Management
    def set_output_directory(self, directory_path: str):
        """Set the output directory and emit signal if changed."""
        if directory_path != self._output_directory:
            self._output_directory = directory_path
            self.output_directory_changed.emit(directory_path)
    
    def get_output_directory(self) -> Optional[str]:
        """Get the current output directory."""
        return self._output_directory
    
    def is_output_directory_set(self) -> bool:
        """Check if output directory is set and exists."""
        return self._output_directory is not None and os.path.exists(self._output_directory)
    
    
    def get_config(self) -> Dict[str, Any]:
        """Get the current configuration."""
        return self._config.copy()
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a specific configuration value."""
        return self._config.get(key, default)
    
    def get_stages_config(self) -> List[Dict[str, Any]]:
        """Get the stages configuration."""
        return self._config.get("stages", [])
    
    def update_config_value(self, key: str, value: Any):
        """Update a configuration value."""
        self._config[key] = value
    
    # Worker State Management
    def set_worker_running(self, worker_instance: Any, is_running: bool = True):
        """Set worker running state."""
        self._worker_state.is_running = is_running
        self._worker_state.worker_instance = worker_instance if is_running else None
        if not is_running:
            self._worker_state.progress = 0
        self.worker_state_changed.emit(is_running, self._worker_state.progress)
    
    def set_worker_stopped(self):
        """Set worker as stopped."""
        self._worker_state.is_running = False
        self._worker_state.worker_instance = None
        self._worker_state.progress = 0
        self.worker_state_changed.emit(False, 0)
    
    def update_worker_progress(self, progress: int):
        """Update worker progress."""
        self._worker_state.progress = max(0, min(100, progress))
        self.worker_state_changed.emit(self._worker_state.is_running, self._worker_state.progress)
    
    def is_worker_running(self) -> bool:
        """Check if worker is currently running."""
        return self._worker_state.is_running
    
    def get_worker_instance(self) -> Optional[Any]:
        """Get the current worker instance."""
        return self._worker_state.worker_instance
    
    def get_worker_progress(self) -> int:
        """Get current worker progress."""
        return self._worker_state.progress
    
    # Images Viewer State Management
    def set_images_viewer_instance(self, viewer_instance: Optional[Any]):
        """Set the images viewer instance."""
        self._ui_state.images_viewer_instance = viewer_instance
        self.images_viewer_state_changed.emit(viewer_instance is not None)
    
    def get_images_viewer_instance(self) -> Optional[Any]:
        """Get the current images viewer instance."""
        return self._ui_state.images_viewer_instance
    
    def is_images_viewer_active(self) -> bool:
        """Check if images viewer is active."""
        return self._ui_state.images_viewer_instance is not None
    
    # Stages Selection Management
    def set_selected_stages(self, stage_names: List[str]):
        """Set the selected stages."""
        self._ui_state.current_stages_selection = stage_names.copy()
        self.stages_selection_changed.emit(self._ui_state.current_stages_selection)
    
    def get_selected_stages(self) -> List[str]:
        """Get the currently selected stages."""
        return self._ui_state.current_stages_selection.copy()
    
    def add_selected_stage(self, stage_name: str):
        """Add a stage to the selection."""
        if stage_name not in self._ui_state.current_stages_selection:
            self._ui_state.current_stages_selection.append(stage_name)
            self.stages_selection_changed.emit(self._ui_state.current_stages_selection)
    
    def remove_selected_stage(self, stage_name: str):
        """Remove a stage from the selection."""
        if stage_name in self._ui_state.current_stages_selection:
            self._ui_state.current_stages_selection.remove(stage_name)
            self.stages_selection_changed.emit(self._ui_state.current_stages_selection)
    
    def toggle_stage_selection(self, stage_name: str):
        """Toggle a stage selection."""
        if stage_name in self._ui_state.current_stages_selection:
            self.remove_selected_stage(stage_name)
        else:
            self.add_selected_stage(stage_name)
    
    def get_selected_stages_config(self) -> List[Dict[str, Any]]:
        """Get configuration for currently selected stages."""
        all_stages = self.get_stages_config()
        selected_names = self.get_selected_stages()
        return [stage for stage in all_stages if stage.get("name") in selected_names]
    
    # Application State Utilities
    def clear_all_state(self):
        """Clear all application state (useful for reset/logout scenarios)."""
        self._output_directory = None
        self._worker_state = WorkerState()
        self._ui_state = UIState()
        
        self.worker_state_changed.emit(False, 0)
        self.images_viewer_state_changed.emit(False)
        self.stages_selection_changed.emit([])
    
    # Multi-Config Management
    def get_available_configs(self) -> List[ConfigInfo]:
        """Get list of available configurations."""
        return self._available_configs.copy()
    
    def get_current_config_name(self) -> Optional[str]:
        """Get the name of the currently active configuration."""
        return self._current_config_name
    
    def switch_config(self, config_name: str) -> bool:
        """Switch to a different configuration.
        
        Args:
            config_name: Name of the configuration to switch to
            
        Returns:
            True if switch was successful, False otherwise
        """
        if not self._config_service:
            return False
        
        # Load the new configuration
        new_config = self._config_service.load_config(config_name)
        if new_config is None:
            return False
        
        # Update internal state
        self._config = new_config
        self._current_config_name = config_name
        
        self._settings.setValue("last_config", config_name)
        
        self._ui_state.current_stages_selection = []
        
        self.config_loaded.emit(self._config)
        self.config_changed.emit(config_name)
        self.stages_selection_changed.emit([])
        
        return True
    
    def refresh_available_configs(self):
        """Refresh the list of available configurations."""
        if self._config_service:
            self._discover_configs()
    
    def _discover_configs(self):
        """Discover available configurations and emit signal."""
        if not self._config_service:
            return
        
        self._available_configs = self._config_service.discover_configs()
        self.configs_discovered.emit(self._available_configs)
        
        if not self._current_config_name and self._available_configs:
            last_config = self._settings.value("last_config", None)
            if last_config and any(c.name == last_config for c in self._available_configs):
                self.switch_config(last_config)
            else:
                default_config = self._config_service.get_default_config_name()
                if default_config:
                    self.switch_config(default_config)
    
    def get_application_summary(self) -> Dict[str, Any]:
        """Get a summary of current application state for debugging."""
        return {
            "output_directory": self._output_directory,
            "output_directory_exists": self.is_output_directory_set(),
            "config_loaded": bool(self._config),
            "current_config_name": self._current_config_name,
            "available_configs_count": len(self._available_configs),
            "config_stages_count": len(self.get_stages_config()),
            "worker_running": self._worker_state.is_running,
            "worker_progress": self._worker_state.progress,
            "images_viewer_active": self.is_images_viewer_active(),
            "selected_stages_count": len(self._ui_state.current_stages_selection),
            "selected_stages": self._ui_state.current_stages_selection.copy()
        } 