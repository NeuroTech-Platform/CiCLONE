from typing import Optional, List, Dict, Any
from PyQt6.QtCore import QObject, pyqtSignal

from ciclone.services.ui.dialog_service import DialogService


class ConfigDialogController(QObject):
    """Controller for managing pipeline configuration dialog operations following MVC architecture."""
    
    # Signals for communicating with view
    pipeline_list_updated = pyqtSignal(list)  # List of pipeline configs
    stage_list_updated = pyqtSignal(list)  # List of stages for selected pipeline
    operation_list_updated = pyqtSignal(list)  # List of operations for selected stage
    stage_details_updated = pyqtSignal(dict)  # Stage details (name, dependencies, auto_clean)
    dependencies_updated = pyqtSignal(list)  # Available dependencies for current stage
    
    def __init__(self, config_service, dialog_service: DialogService):
        super().__init__()
        
        self.config_service = config_service
        self.dialog_service = dialog_service
        
        # Current state
        self._current_pipeline_config = None
        self._current_stage_index = -1
        self._current_operation_index = -1
        self._view = None
        
        # Working copy management
        self._working_configs = []  # List of configs being edited (includes new ones)
        self._original_configs = []  # Original loaded configs for comparison
        self._deleted_configs = []  # List of config names marked for deletion
        self._new_config_counter = 0  # Counter for new config naming
        
        # Dirty state tracking
        self._is_dirty = False
    
    def set_view(self, view):
        """Set the view reference for UI updates."""
        self._view = view
        self._load_initial_data()
    
    def _load_initial_data(self):
        """Load initial data when dialog opens."""
        try:
            # Load original configurations from disk
            self._original_configs = self.config_service.get_available_configs_for_editing()
            
            # Create working copies (deep copies for editing)
            self._working_configs = [self._create_working_copy(config) for config in self._original_configs]
            
            # Update the view
            self.pipeline_list_updated.emit(self._working_configs)
            
            # If we have configs, select the first one
            if self._working_configs:
                self._select_pipeline(0)
                
        except Exception as e:
            self.dialog_service.show_error("Error Loading Configurations", 
                                         f"Failed to load pipeline configurations: {str(e)}")
    
    def _create_working_copy(self, config):
        """Create a working copy of a configuration for editing."""
        import copy
        working_copy = copy.deepcopy(config)
        
        # Mark as existing config (not new)
        if '_metadata' not in working_copy:
            working_copy['_metadata'] = {}
        working_copy['_metadata']['is_new'] = False
        
        return working_copy
    
    def _select_pipeline(self, index: int):
        """Select a pipeline configuration by index."""
        try:
            if 0 <= index < len(self._working_configs):
                self._current_pipeline_config = self._working_configs[index]
                stages = self._current_pipeline_config.get('stages', [])
                self.stage_list_updated.emit(stages)
                
                # Clear stage selection
                self._current_stage_index = -1
                self._current_operation_index = -1
                self.stage_details_updated.emit({})
                self.operation_list_updated.emit([])
                
        except Exception as e:
            self.dialog_service.show_error("Error Selecting Pipeline", 
                                         f"Failed to select pipeline: {str(e)}")
    
    def _select_stage(self, index: int):
        """Select a stage by index."""
        if not self._current_pipeline_config:
            return
            
        try:
            stages = self._current_pipeline_config.get('stages', [])
            if 0 <= index < len(stages):
                self._current_stage_index = index
                stage = stages[index]
                
                # Update available dependencies first (all other stages)
                available_deps = ['none'] + [s.get('name', '') for i, s in enumerate(stages) if i != index]
                self.dependencies_updated.emit(available_deps)
                
                # Update stage details after dependencies are populated
                stage_details = {
                    'name': stage.get('name', ''),
                    'depends_on': stage.get('depends_on', []),
                    'auto_clean': stage.get('auto_clean', True)
                }
                self.stage_details_updated.emit(stage_details)
                
                # Update operations list
                operations = stage.get('operations', [])
                self.operation_list_updated.emit(operations)
                
                # Clear operation selection
                self._current_operation_index = -1
                
        except Exception as e:
            self.dialog_service.show_error("Error Selecting Stage", 
                                         f"Failed to select stage: {str(e)}")
    
    # Public interface methods for view to call
    def on_pipeline_selected(self, index: int):
        """Handle pipeline selection from view."""
        self._select_pipeline(index)
    
    def on_stage_selected(self, index: int):
        """Handle stage selection from view."""
        self._select_stage(index)
    
    def on_operation_selected(self, index: int):
        """Handle operation selection from view."""
        self._current_operation_index = index
    
    def on_add_pipeline(self):
        """Handle add new pipeline request."""
        name, ok = self.dialog_service.get_text_input(
            "New Pipeline", 
            "Enter pipeline name:"
        )
        
        if ok and name and name.strip():
            try:
                # Create new config in memory only (not saved to disk)
                self._new_config_counter += 1
                new_config = {
                    'name': name.strip(),
                    'stages': [],
                    '_metadata': {
                        'is_new': True,
                        'config_name': name.strip(),
                        'display_name': name.strip(),
                        'stage_count': 0,
                        'temp_id': f"new_{self._new_config_counter}"  # Temporary ID for tracking
                    }
                }
                
                # Add to working configs
                self._working_configs.append(new_config)
                
                # Update the view and select the new config
                self.pipeline_list_updated.emit(self._working_configs)
                self._select_pipeline(len(self._working_configs) - 1)
                
                # Mark as dirty since we have unsaved changes
                self._mark_dirty()
                
            except Exception as e:
                self.dialog_service.show_error("Error Adding Pipeline", 
                                             f"Failed to add pipeline: {str(e)}")
    
    def on_delete_pipeline(self, index: int):
        """Handle delete pipeline request."""
        if 0 <= index < len(self._working_configs):
            config = self._working_configs[index]
            config_name = config.get('_metadata', {}).get('config_name', config.get('name', ''))
            is_new = config.get('_metadata', {}).get('is_new', False)
            
            action = "remove" if is_new else "delete"
            if self.dialog_service.show_question("Delete Pipeline", 
                                                f"Are you sure you want to {action} '{config_name}'?"):
                try:
                    # Remove from working configs
                    self._working_configs.pop(index)
                    
                    # If it's not a new config, mark for deletion on save
                    if not is_new:
                        self._deleted_configs.append(config_name)
                    
                    # Update the view
                    self.pipeline_list_updated.emit(self._working_configs)
                    
                    # Select another config if available
                    if self._working_configs:
                        new_index = min(index, len(self._working_configs) - 1)
                        self._select_pipeline(new_index)
                    else:
                        # No configs left
                        self._current_pipeline_config = None
                        self.stage_list_updated.emit([])
                        self.stage_details_updated.emit({})
                        self.operation_list_updated.emit([])
                    
                    # Mark as dirty
                    self._mark_dirty()
                
                except Exception as e:
                    self.dialog_service.show_error("Error Deleting Pipeline", 
                                                 f"Failed to delete pipeline: {str(e)}")
    
    def on_add_stage(self):
        """Handle add new stage request."""
        if not self._current_pipeline_config:
            self.dialog_service.show_warning("No Pipeline Selected", 
                                            "Please select a pipeline first.")
            return
        
        name, ok = self.dialog_service.get_text_input(
            "New Stage", 
            "Enter stage name:"
        )
        
        if ok and name and name.strip():
            try:
                new_stage = {
                    'name': name.strip(),
                    'depends_on': [],
                    'auto_clean': True,
                    'operations': []
                }
                # Add to current pipeline and refresh view
                self._current_pipeline_config['stages'].append(new_stage)
                self._mark_dirty()
                
                # Refresh stage list
                stages = self._current_pipeline_config.get('stages', [])
                self.stage_list_updated.emit(stages)
                
            except Exception as e:
                self.dialog_service.show_error("Error Adding Stage", 
                                             f"Failed to add stage: {str(e)}")
    
    def on_delete_stage(self, index: int):
        """Handle delete stage request."""
        if not self._current_pipeline_config:
            return
            
        try:
            stages = self._current_pipeline_config.get('stages', [])
            if 0 <= index < len(stages):
                stage_name = stages[index].get('name', f'Stage {index+1}')
                
                if self.dialog_service.show_question("Delete Stage", 
                                                    f"Are you sure you want to delete stage '{stage_name}'?"):
                    # Remove the stage
                    stages.pop(index)
                    
                    # Update stage count in metadata
                    if '_metadata' in self._current_pipeline_config:
                        self._current_pipeline_config['_metadata']['stage_count'] = len(stages)
                    
                    # Refresh the stage list
                    self.stage_list_updated.emit(stages)
                    
                    # Clear stage selection and details
                    self._current_stage_index = -1
                    self.stage_details_updated.emit({})
                    self.operation_list_updated.emit([])
                    
                    # Update dependencies for remaining stages
                    self._update_all_stage_dependencies()
                    
                    # Mark as dirty
                    self._mark_dirty()
                    
        except Exception as e:
            self.dialog_service.show_error("Error Deleting Stage", 
                                         f"Failed to delete stage: {str(e)}")
    
    def on_move_stage_up(self, index: int):
        """Handle move stage up request."""
        if not self._current_pipeline_config:
            return
            
        try:
            stages = self._current_pipeline_config.get('stages', [])
            if index > 0 and index < len(stages):
                # Swap with previous stage
                stages[index], stages[index-1] = stages[index-1], stages[index]
                
                # Update stage count in metadata
                if '_metadata' in self._current_pipeline_config:
                    self._current_pipeline_config['_metadata']['stage_count'] = len(stages)
                
                # Refresh the stage list
                self.stage_list_updated.emit(stages)
                
                # Update current selection to follow the moved stage
                self._current_stage_index = index - 1
                
                # Update dependencies for all stages (order might affect dependencies)
                self._update_all_stage_dependencies()
                
                # Mark as dirty
                self._mark_dirty()
                
        except Exception as e:
            self.dialog_service.show_error("Error Moving Stage", 
                                         f"Failed to move stage up: {str(e)}")
    
    def on_move_stage_down(self, index: int):
        """Handle move stage down request."""
        if not self._current_pipeline_config:
            return
            
        try:
            stages = self._current_pipeline_config.get('stages', [])
            if index >= 0 and index < len(stages) - 1:
                # Swap with next stage
                stages[index], stages[index+1] = stages[index+1], stages[index]
                
                # Update stage count in metadata
                if '_metadata' in self._current_pipeline_config:
                    self._current_pipeline_config['_metadata']['stage_count'] = len(stages)
                
                # Refresh the stage list
                self.stage_list_updated.emit(stages)
                
                # Update current selection to follow the moved stage
                self._current_stage_index = index + 1
                
                # Update dependencies for all stages (order might affect dependencies)
                self._update_all_stage_dependencies()
                
                # Mark as dirty
                self._mark_dirty()
                
        except Exception as e:
            self.dialog_service.show_error("Error Moving Stage", 
                                         f"Failed to move stage down: {str(e)}")
    
    def _update_all_stage_dependencies(self):
        """Update dependencies dropdown after stage order changes."""
        if self._current_stage_index >= 0 and self._current_pipeline_config:
            stages = self._current_pipeline_config.get('stages', [])
            if self._current_stage_index < len(stages):
                # Update available dependencies (all other stages)
                available_deps = ['none'] + [s.get('name', '') for i, s in enumerate(stages) if i != self._current_stage_index]
                self.dependencies_updated.emit(available_deps)
    
    def on_stage_details_changed(self, field: str, value):
        """Handle stage details changes."""
        if self._current_stage_index >= 0 and self._current_pipeline_config:
            try:
                stages = self._current_pipeline_config.get('stages', [])
                if self._current_stage_index < len(stages):
                    stages[self._current_stage_index][field] = value
                    self._mark_dirty()
                    
            except Exception as e:
                self.dialog_service.show_error("Error Updating Stage", 
                                             f"Failed to update stage: {str(e)}")
    
    def on_save_changes(self):
        """Handle save changes request - saves all working configs to disk."""
        if not self._is_dirty:
            return True
            
        try:
            # Save all working configs
            for config in self._working_configs:
                config_name = config.get('_metadata', {}).get('config_name', config.get('name', ''))
                is_new = config.get('_metadata', {}).get('is_new', False)
                
                if config_name:
                    # Create a clean copy without metadata for saving
                    clean_config = {
                        'name': config.get('name', config_name),
                        'stages': config.get('stages', [])
                    }
                    
                    if not self.config_service.save_config(config_name, clean_config):
                        raise Exception(f"Failed to save configuration '{config_name}'")
                    
                    # Mark as no longer new
                    if is_new:
                        config['_metadata']['is_new'] = False
            
            # Delete configs marked for deletion
            for config_name in self._deleted_configs:
                if not self.config_service.delete_config(config_name):
                    raise Exception(f"Failed to delete configuration '{config_name}'")
            self._deleted_configs = []
            
            # Clear dirty state
            self._is_dirty = False
            
            # Reload from disk to ensure consistency
            self._load_initial_data()
            
            return True
            
        except Exception as e:
            self.dialog_service.show_error("Error Saving", 
                                         f"Failed to save changes: {str(e)}")
            return False
    
    def on_import_template(self):
        """Handle import template request."""
        file_path = self.dialog_service.browse_file(
            "Import Pipeline Template",
            "YAML files (*.yaml *.yml)"
        )
        
        if file_path:
            try:
                # Load config from file but don't save to disk yet
                import yaml
                from pathlib import Path
                
                with open(file_path, 'r', encoding='utf-8') as file:
                    config_data = yaml.safe_load(file) or {}
                
                # Validate the imported config
                is_valid, error_msg = self.config_service.validate_config_detailed(config_data)
                if not is_valid:
                    raise Exception(f"Invalid configuration file: {error_msg}")
                
                # Create a unique name for imported config
                base_name = Path(file_path).stem
                import_name = self._ensure_unique_name(base_name)
                
                # Create working config
                self._new_config_counter += 1
                imported_config = {
                    'name': import_name,
                    'stages': config_data.get('stages', []),
                    '_metadata': {
                        'is_new': True,
                        'config_name': import_name,
                        'display_name': import_name,
                        'stage_count': len(config_data.get('stages', [])),
                        'temp_id': f"imported_{self._new_config_counter}"
                    }
                }
                
                # Add to working configs
                self._working_configs.append(imported_config)
                
                # Update view and select imported config
                self.pipeline_list_updated.emit(self._working_configs)
                self._select_pipeline(len(self._working_configs) - 1)
                
                # Mark as dirty
                self._mark_dirty()
                
                self.dialog_service.show_information("Import Successful", 
                                            f"Configuration imported as '{import_name}'. Click Save to persist changes.")
                
            except Exception as e:
                self.dialog_service.show_error("Error Importing Template", 
                                             f"Failed to import template: {str(e)}")
    
    def _ensure_unique_name(self, base_name: str) -> str:
        """Ensure a config name is unique among working configs."""
        existing_names = {config.get('name', '') for config in self._working_configs}
        existing_names.update({config.get('_metadata', {}).get('config_name', '') for config in self._working_configs})
        
        if base_name not in existing_names:
            return base_name
        
        counter = 1
        while f"{base_name}_{counter}" in existing_names:
            counter += 1
        return f"{base_name}_{counter}"
    
    def on_preview_yaml(self):
        """Handle preview YAML request."""
        if self._current_pipeline_config:
            try:
                yaml_content = self.config_service.generate_yaml_preview(self._current_pipeline_config)
                # For now, use information dialog - we can create a text dialog later
                self.dialog_service.show_information("YAML Preview", f"<pre>{yaml_content}</pre>")
                
            except Exception as e:
                self.dialog_service.show_error("Error Generating Preview", 
                                             f"Failed to generate YAML preview: {str(e)}")
    
    def _mark_dirty(self):
        """Mark the configuration as having unsaved changes."""
        self._is_dirty = True
    
    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes."""
        return self._is_dirty
    
    def can_close(self) -> bool:
        """Check if dialog can be closed (handle unsaved changes)."""
        if not self._is_dirty:
            return True
            
        # Use a simple question dialog for now
        should_save = self.dialog_service.show_question(
            "Unsaved Changes",
            "You have unsaved changes. Do you want to save them before closing?"
        )
        
        if should_save:
            return self.on_save_changes()
        else:
            return True