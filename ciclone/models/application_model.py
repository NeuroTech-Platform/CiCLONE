import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from PyQt6.QtCore import QObject, pyqtSignal

from ciclone.utils.utility import read_config_file


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
    worker_state_changed = pyqtSignal(bool, int)  # is_running, progress
    images_viewer_state_changed = pyqtSignal(bool)  # is_active
    stages_selection_changed = pyqtSignal(list)  # selected_stage_names
    
    def __init__(self, config_path: Optional[str] = None):
        super().__init__()
        
        # Core application state
        self._output_directory: Optional[str] = None
        self._config: Dict[str, Any] = {}
        self._config_path: Optional[str] = config_path
        
        # Worker state management
        self._worker_state = WorkerState()
        
        # UI state management
        self._ui_state = UIState()
        
        # Load configuration if path provided
        if self._config_path:
            self.load_configuration()
    
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
    
    # Configuration Management
    def load_configuration(self, config_path: Optional[str] = None) -> bool:
        """Load configuration from file."""
        if config_path:
            self._config_path = config_path
        
        if not self._config_path:
            return False
        
        try:
            self._config = read_config_file(self._config_path)
            self.config_loaded.emit(self._config)
            return True
        except Exception:
            self._config = {}
            return False
    
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
        
        # Emit signals for cleared state
        self.worker_state_changed.emit(False, 0)
        self.images_viewer_state_changed.emit(False)
        self.stages_selection_changed.emit([])
    
    def get_application_summary(self) -> Dict[str, Any]:
        """Get a summary of current application state for debugging."""
        return {
            "output_directory": self._output_directory,
            "output_directory_exists": self.is_output_directory_set(),
            "config_loaded": bool(self._config),
            "config_stages_count": len(self.get_stages_config()),
            "worker_running": self._worker_state.is_running,
            "worker_progress": self._worker_state.progress,
            "images_viewer_active": self.is_images_viewer_active(),
            "selected_stages_count": len(self._ui_state.current_stages_selection),
            "selected_stages": self._ui_state.current_stages_selection.copy()
        } 