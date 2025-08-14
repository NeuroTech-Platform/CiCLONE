from typing import Optional, List, Dict, Any, Tuple
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from ciclone.services.ui.dialog_service import DialogService
from ciclone.services.config_service import ConfigService
from ciclone.services.operation_metadata_parser import OperationMetadataParser
from ciclone.managers.config_transaction_manager import (
    ConfigTransactionManager, EntityLevel, ChangeType
)


class ConfigDialogController(QObject):
    """
    Enhanced controller for managing pipeline configuration with comprehensive
    save/discard workflow at all hierarchy levels.
    """
    
    # Signals for view updates
    pipeline_list_updated = pyqtSignal(list)
    pipeline_selection_updated = pyqtSignal(int)
    pipeline_details_updated = pyqtSignal(dict)
    stage_list_updated = pyqtSignal(list)
    stage_selection_updated = pyqtSignal(int)
    stage_details_updated = pyqtSignal(dict)
    operation_list_updated = pyqtSignal(list)
    operation_selection_updated = pyqtSignal(int)
    operation_details_updated = pyqtSignal(dict)
    dependencies_updated = pyqtSignal(list)
    
    # Workflow signals
    unsaved_changes_detected = pyqtSignal(str)  # Message about unsaved changes
    save_prompt_required = pyqtSignal(str, object)  # Context, callback
    changes_saved = pyqtSignal()
    changes_discarded = pyqtSignal()
    
    def __init__(self, config_service: ConfigService, dialog_service: DialogService):
        super().__init__()
        
        self.config_service = config_service
        self.dialog_service = dialog_service
        self.metadata_parser = OperationMetadataParser()
        
        # Initialize unified transaction manager
        self.transaction_manager = ConfigTransactionManager()
        
        # Current selection tracking
        self._current_pipeline_index = -1
        self._current_stage_index = -1
        self._current_operation_index = -1
        
        # View reference
        self._view = None
        
        # Flags for preventing recursive prompts
        self._switching_context = False
        self._saving_in_progress = False
        
        # Setup change listener
        self.transaction_manager.add_change_listener(self._on_change_recorded)
    
    def set_view(self, view) -> None:
        """Set the view reference and initialize data."""
        self._view = view
        self._initialize_data()
    
    def _cleanup_transaction_state(self):
        """Clean up any existing transaction state before starting a new one."""
        if self.transaction_manager._transaction_state:
            try:
                # Force rollback any active transaction
                self.transaction_manager.rollback_transaction()
            except Exception:
                # If rollback fails, reset transaction state manually
                self.transaction_manager._transaction_state = None
                self.transaction_manager._snapshots.clear()
        
        # Reset current context
        self._current_pipeline_index = -1
        self._current_stage_index = -1
        self._current_operation_index = -1
    
    def _initialize_data(self):
        """Load initial configuration data."""
        try:
            # Clean up any existing transaction state
            self._cleanup_transaction_state()
            
            # Load configurations from disk
            original_configs = self.config_service.get_available_configs_for_editing()
            
            # Begin transaction with original configs
            working_configs = self.transaction_manager.begin_transaction(original_configs)
            
            # Update view with working configs
            self.pipeline_list_updated.emit(working_configs)
            
            # Select first pipeline if available
            if working_configs:
                self._select_pipeline_with_check(0)
            
            # Use QTimer to end initialization after all signal processing is complete
            QTimer.singleShot(0, self._finalize_initialization)
            
        except Exception as e:
            self.dialog_service.show_error(
                "Initialization Error",
                f"Failed to load configurations: {str(e)}"
            )
    
    def _finalize_initialization(self):
        """Finalize initialization after all UI updates are complete."""
        # End initialization mode
        self.transaction_manager.end_initialization()
    
    # ==================== Selection Management ====================
    
    def on_pipeline_selected(self, index: int) -> None:
        """Handle pipeline selection from view."""
        if self._switching_context:
            return
        
        # Check for unsaved changes before switching
        if self._check_and_prompt_unsaved_changes(
            EntityLevel.PIPELINE, 
            new_pipeline=index
        ):
            # User chose to stay - restore previous selection
            self.pipeline_selection_updated.emit(self._current_pipeline_index)
            return
        
        self._select_pipeline_with_check(index)
    
    def on_stage_selected(self, index: int) -> None:
        """Handle stage selection from view."""
        if self._switching_context:
            return
        
        # Check for unsaved changes before switching
        if self._check_and_prompt_unsaved_changes(
            EntityLevel.STAGE,
            new_stage=index
        ):
            # User chose to stay - restore previous selection
            self.stage_selection_updated.emit(self._current_stage_index)
            return
        
        self._select_stage_with_check(index)
    
    def on_operation_selected(self, index: int) -> None:
        """Handle operation selection from view."""
        if self._switching_context:
            return
        
        # If selecting the same operation, don't trigger change detection
        if index == self._current_operation_index:
            return
        
        # Check for unsaved changes before switching
        if self._check_and_prompt_unsaved_changes(
            EntityLevel.OPERATION,
            new_operation=index
        ):
            # User chose to stay - restore previous selection
            self.operation_selection_updated.emit(self._current_operation_index)
            return
        
        self._select_operation_with_check(index)
    
    def _select_pipeline_with_check(self, index: int):
        """Select a pipeline after change checks."""
        pipeline = self.transaction_manager.get_pipeline(index)
        if not pipeline:
            return
        
        self._current_pipeline_index = index
        self.transaction_manager.set_current_context(pipeline_index=index)
        
        # Update pipeline details
        self.pipeline_details_updated.emit({
            'name': pipeline.get('name', ''),
            'description': pipeline.get('description', '')
        })
        
        # Update stage list
        stages = pipeline.get('stages', [])
        self.stage_list_updated.emit(stages)
        
        # Select first stage if available
        if stages:
            self._select_stage_with_check(0)
        else:
            self._clear_stage_selection()
        
        # Update selection in view
        self.pipeline_selection_updated.emit(index)
    
    def _select_stage_with_check(self, index: int):
        """Select a stage after change checks."""
        stage = self.transaction_manager.get_stage(self._current_pipeline_index, index)
        if not stage:
            return
        
        self._current_stage_index = index
        self.transaction_manager.set_current_context(
            pipeline_index=self._current_pipeline_index,
            stage_index=index
        )
        
        # Update available dependencies
        pipeline = self.transaction_manager.get_pipeline(self._current_pipeline_index)
        if pipeline:
            stages = pipeline.get('stages', [])
            available_deps = ['none'] + [
                s.get('name', '') for i, s in enumerate(stages) if i != index
            ]
            self.dependencies_updated.emit(available_deps)
        
        # Update stage details
        self.stage_details_updated.emit({
            'name': stage.get('name', ''),
            'depends_on': stage.get('depends_on', []),
            'auto_clean': stage.get('auto_clean', True)
        })
        
        # Update operation list
        operations = stage.get('operations', [])
        self.operation_list_updated.emit(operations)
        
        # Select first operation if available
        if operations:
            self._select_operation_with_check(0)
        else:
            self._clear_operation_selection()
        
        # Update selection in view
        self.stage_selection_updated.emit(index)
    
    def _select_operation_with_check(self, index: int):
        """Select an operation after change checks."""
        operation = self.transaction_manager.get_operation(
            self._current_pipeline_index,
            self._current_stage_index,
            index
        )
        if not operation:
            return
        
        self._current_operation_index = index
        self.transaction_manager.set_current_context(
            pipeline_index=self._current_pipeline_index,
            stage_index=self._current_stage_index,
            operation_index=index
        )
        
        # Get metadata for this operation type
        operation_type = operation.get('type', '')
        metadata = self.metadata_parser.get_operation_metadata(operation_type)
        
        # Convert to dialog format for view with metadata
        operation_details = {
            'operation': operation_type,
            'workdir': operation.get('workdir', ''),
            'parameters': operation.get('parameters', {}),  # Unified parameters
            'metadata': metadata  # Include metadata for parameter widget generation
        }
        
        self.operation_details_updated.emit(operation_details)
        self.operation_selection_updated.emit(index)
    
    def _clear_stage_selection(self):
        """Clear stage selection and related data."""
        self._current_stage_index = -1
        self._current_operation_index = -1
        self.stage_details_updated.emit({})
        self.operation_list_updated.emit([])
        self._clear_operation_selection()
    
    def _clear_operation_selection(self):
        """Clear operation selection and related data."""
        self._current_operation_index = -1
        self.operation_details_updated.emit({})
    
    def _force_commit_pending_edits(self):
        """Force any pending field edits to be committed by clearing focus."""
        if hasattr(self, '_view') and self._view:
            # Clear focus from any currently focused widget to trigger editingFinished
            focused_widget = self._view.focusWidget()
            if focused_widget:
                # This will cause editingFinished to be emitted for any QLineEdit
                focused_widget.clearFocus()
    
    def _check_and_prompt_unsaved_changes(self, level: EntityLevel, 
                                         new_pipeline: int = None,
                                         new_stage: int = None,
                                         new_operation: int = None) -> bool:
        """
        Check for unsaved changes and prompt user if needed.
        
        Returns:
            True if user chose to stay (cancel switch), False to proceed
        """
        if self._switching_context or self._saving_in_progress:
            return False
        
        # Force any pending field edits to be committed before checking changes
        self._force_commit_pending_edits()
        
        # Don't prompt if there are no changes at all
        has_changes = self.transaction_manager.has_changes()
        if not has_changes:
            return False
        
        # Check if switching would lose changes
        context_switch_check = self.transaction_manager.check_context_switch(
            new_pipeline, new_stage, new_operation
        )
        if not context_switch_check:
            return False
        
        # Get change summary for context
        summary = self.transaction_manager.get_change_summary()
        
        # Build prompt message with new text
        level_name = level.name.lower()
        message = f"You have {summary['total_changes']} unsaved changes in current {level_name}.\n\n"
        message += f"Keep changes in memory before switching {level_name}?"
        
        self._switching_context = True
        try:
            result = self.dialog_service.show_question_with_cancel(
                "Unsaved Changes",
                message,
                "Keep Changes", "Discard Changes", "Cancel"
            )
            
            if result == "Keep Changes":
                # Keep changes in memory and proceed
                return False  # Proceed with switch
            elif result == "Discard Changes":
                # Discard changes at current level and proceed
                self._discard_current_level_changes(level)
                return False  # Proceed with switch
            else:  # Cancel
                return True  # Stay at current selection
                
        finally:
            self._switching_context = False
    
    def _refresh_current_view(self):
        """Refresh the current view to show rolled back state."""
        # Refresh pipeline list
        working_configs = self.transaction_manager.get_working_configs()
        self.pipeline_list_updated.emit(working_configs)
        
        # Restore current selections if still valid
        if self._current_pipeline_index >= 0:
            self._select_pipeline_with_check(self._current_pipeline_index)
    
    def _refresh_all_affected_lists_after_operation_change(self):
        """Refresh operation, stage, and pipeline lists after an operation change.
        
        This is important for updating dirty indicators (*) when an operation
        revert causes parent entities to be cleaned.
        """
        # Always refresh operation list
        stage = self.transaction_manager.get_stage(
            self._current_pipeline_index, self._current_stage_index
        )
        if stage:
            operations = stage.get('operations', [])
            self.operation_list_updated.emit(operations)
        
        # Refresh stage list to update dirty indicators
        pipeline = self.transaction_manager.get_pipeline(self._current_pipeline_index)
        if pipeline:
            stages = pipeline.get('stages', [])
            self.stage_list_updated.emit(stages)
        
        # Refresh pipeline list to update dirty indicators
        working_configs = self.transaction_manager.get_working_configs()
        self.pipeline_list_updated.emit(working_configs)
    
    def _discard_current_level_changes(self, level: EntityLevel):
        """Discard changes at the current level only (no disk I/O)."""
        
        try:
            success = False
            
            # Use context-specific rollback methods
            if level == EntityLevel.PIPELINE and self._current_pipeline_index >= 0:
                success = self.transaction_manager.rollback_pipeline_context(
                    self._current_pipeline_index
                )
            elif level == EntityLevel.STAGE and self._current_stage_index >= 0:
                success = self.transaction_manager.rollback_stage_context(
                    self._current_pipeline_index,
                    self._current_stage_index
                )
            elif level == EntityLevel.OPERATION and self._current_operation_index >= 0:
                success = self.transaction_manager.rollback_operation_context(
                    self._current_pipeline_index,
                    self._current_stage_index,
                    self._current_operation_index
                )
            
            if not success:
                self.dialog_service.show_error(
                    "Discard Error",
                    "Failed to discard changes"
                )
                return
            
            # Refresh UI to reflect rolled back state
            self._refresh_current_view()
            
            self.changes_discarded.emit()
            
        except Exception as e:
            self.dialog_service.show_error(
                "Discard Error",
                f"Failed to discard changes: {str(e)}"
            )
    
    def _on_change_recorded(self, change_record):
        """Handle change record events from transaction manager."""
        # Could be used for real-time change indicators in UI
        if self.transaction_manager.has_changes():
            summary = self.transaction_manager.get_change_summary()
            self.unsaved_changes_detected.emit(
                f"{summary['total_changes']} unsaved changes"
            )
    
    # ==================== Pipeline Operations ====================
    
    def on_add_pipeline(self) -> None:
        """Handle add pipeline request."""
        name, ok = self.dialog_service.get_text_input(
            "New Pipeline",
            "Enter pipeline name:"
        )
        
        if ok and name and name.strip():
            pipeline_data = {
                'name': name.strip(),
                'stages': []
            }
            
            new_index = self.transaction_manager.add_pipeline(pipeline_data)
            
            # Update view
            self.pipeline_list_updated.emit(self.transaction_manager.get_working_configs())
            
            # Select the new pipeline
            self._select_pipeline_with_check(new_index)
    
    def on_delete_pipeline(self, index: int) -> None:
        """Handle delete pipeline request."""
        working_configs = self.transaction_manager.get_working_configs()
        if 0 <= index < len(working_configs):
            config = working_configs[index]
            config_name = config.get('_metadata', {}).get('config_name', config.get('name', ''))
            is_new = config.get('_metadata', {}).get('is_new', False)
            
            action = "remove" if is_new else "delete"
            if self.dialog_service.show_question("Delete Pipeline", 
                                                f"Are you sure you want to {action} '{config_name}'?"):
                try:
                    # Use transaction manager to delete
                    if self.transaction_manager.delete_pipeline(index):
                        # Update the view
                        updated_configs = self.transaction_manager.get_working_configs()
                        self.pipeline_list_updated.emit(updated_configs)
                        
                        # Select another config if available
                        if updated_configs:
                            # Select the previous pipeline, or first if we deleted the first
                            new_index = max(0, min(index - 1, len(updated_configs) - 1))
                            self._select_pipeline_with_check(new_index)
                        else:
                            # No configs left - clear everything
                            self._current_pipeline_index = -1
                            self._current_stage_index = -1
                            self._current_operation_index = -1
                            self.stage_list_updated.emit([])
                            self.stage_details_updated.emit({})
                            self.operation_list_updated.emit([])
                    else:
                        self.dialog_service.show_error("Delete Failed", "Failed to delete pipeline")
                
                except Exception as e:
                    self.dialog_service.show_error("Error Deleting Pipeline", 
                                                 f"Failed to delete pipeline: {str(e)}")
    
    def on_add_stage(self) -> None:
        """Handle add new stage request."""
        if self._current_pipeline_index < 0:
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
                
                # Add using transaction manager
                new_index = self.transaction_manager.add_stage(
                    self._current_pipeline_index, new_stage
                )
                
                if new_index >= 0:
                    # Update view with current pipeline's stages
                    pipeline = self.transaction_manager.get_pipeline(self._current_pipeline_index)
                    if pipeline:
                        stages = pipeline.get('stages', [])
                        self.stage_list_updated.emit(stages)
                        
                        # Select the new stage
                        self._select_stage_with_check(new_index)
                else:
                    self.dialog_service.show_error("Error Adding Stage", "Failed to add stage")
                
            except Exception as e:
                self.dialog_service.show_error("Error Adding Stage", 
                                             f"Failed to add stage: {str(e)}")
    
    def on_delete_stage(self, index: int):
        """Handle delete stage request."""
        if self._current_pipeline_index < 0:
            return
            
        try:
            stage = self.transaction_manager.get_stage(self._current_pipeline_index, index)
            if stage:
                stage_name = stage.get('name', f'Stage {index+1}')
                
                if self.dialog_service.show_question("Delete Stage", 
                                                    f"Are you sure you want to delete stage '{stage_name}'?"):
                    # Use transaction manager to delete
                    if self.transaction_manager.delete_stage(self._current_pipeline_index, index):
                        # Update view
                        pipeline = self.transaction_manager.get_pipeline(self._current_pipeline_index)
                        if pipeline:
                            stages = pipeline.get('stages', [])
                            self.stage_list_updated.emit(stages)
                            
                            # Auto-select another stage if the deleted one was selected
                            if index == self._current_stage_index:
                                if stages:
                                    # Select the previous stage, or first if we deleted the first
                                    new_index = max(0, min(index - 1, len(stages) - 1))
                                    self._select_stage_with_check(new_index)
                                else:
                                    # No stages left - clear selection
                                    self._current_stage_index = -1
                                    self._current_operation_index = -1
                                    self.stage_details_updated.emit({})
                                    self.operation_list_updated.emit([])
                            elif index < self._current_stage_index:
                                # Deleted stage was before current selection, adjust current index
                                self._current_stage_index -= 1
                            
                            # Update dependencies for remaining stages  
                            self._update_all_stage_dependencies()
                    else:
                        self.dialog_service.show_error("Delete Failed", "Failed to delete stage")
                    
        except Exception as e:
            self.dialog_service.show_error("Error Deleting Stage", 
                                         f"Failed to delete stage: {str(e)}")
    
    def on_move_stage_up(self, index: int):
        """Handle move stage up request."""
        if self._current_pipeline_index < 0:
            return
            
        try:
            if index > 0:
                # Use transaction manager to reorder
                if self.transaction_manager.reorder_stage(
                    self._current_pipeline_index, index, index - 1
                ):
                    # Update view
                    pipeline = self.transaction_manager.get_pipeline(self._current_pipeline_index)
                    if pipeline:
                        stages = pipeline.get('stages', [])
                        self.stage_list_updated.emit(stages)
                        
                        # Update current selection to follow the moved stage
                        if index == self._current_stage_index:
                            self._current_stage_index = index - 1
                        
                        # Update dependencies for all stages (order might affect dependencies)
                        self._update_all_stage_dependencies()
                else:
                    self.dialog_service.show_error("Move Failed", "Failed to move stage up")
                
        except Exception as e:
            self.dialog_service.show_error("Error Moving Stage", 
                                         f"Failed to move stage up: {str(e)}")
    
    def on_move_stage_down(self, index: int):
        """Handle move stage down request."""
        if self._current_pipeline_index < 0:
            return
            
        try:
            pipeline = self.transaction_manager.get_pipeline(self._current_pipeline_index)
            if pipeline:
                stages = pipeline.get('stages', [])
                if index >= 0 and index < len(stages) - 1:
                    # Use transaction manager to reorder
                    if self.transaction_manager.reorder_stage(
                        self._current_pipeline_index, index, index + 1
                    ):
                        # Update view
                        updated_pipeline = self.transaction_manager.get_pipeline(self._current_pipeline_index)
                        if updated_pipeline:
                            stages = updated_pipeline.get('stages', [])
                            self.stage_list_updated.emit(stages)
                            
                            # Update current selection to follow the moved stage
                            if index == self._current_stage_index:
                                self._current_stage_index = index + 1
                            
                            # Update dependencies for all stages (order might affect dependencies)
                            self._update_all_stage_dependencies()
                    else:
                        self.dialog_service.show_error("Move Failed", "Failed to move stage down")
                
        except Exception as e:
            self.dialog_service.show_error("Error Moving Stage", 
                                         f"Failed to move stage down: {str(e)}")
    
    def _update_all_stage_dependencies(self):
        """Update dependencies dropdown after stage order changes."""
        if self._current_stage_index >= 0 and self._current_pipeline_index >= 0:
            pipeline = self.transaction_manager.get_pipeline(self._current_pipeline_index)
            if pipeline:
                stages = pipeline.get('stages', [])
                if self._current_stage_index < len(stages):
                    # Update available dependencies (all other stages)
                    available_deps = ['none'] + [s.get('name', '') for i, s in enumerate(stages) if i != self._current_stage_index]
                    self.dependencies_updated.emit(available_deps)
    
    def on_stage_details_changed(self, field: str, value) -> None:
        """Handle stage details changes."""
        if self._current_stage_index >= 0 and self._current_pipeline_index >= 0:
            try:
                # Use transaction manager to update stage
                if not self.transaction_manager.update_stage(
                    self._current_pipeline_index, self._current_stage_index, field, value
                ):
                    self.dialog_service.show_error("Update Failed", "Failed to update stage")
                else:
                    # Refresh stage and pipeline lists in case of revert
                    pipeline = self.transaction_manager.get_pipeline(self._current_pipeline_index)
                    if pipeline:
                        stages = pipeline.get('stages', [])
                        self.stage_list_updated.emit(stages)
                    
                    working_configs = self.transaction_manager.get_working_configs()
                    self.pipeline_list_updated.emit(working_configs)
                    
            except Exception as e:
                self.dialog_service.show_error("Error Updating Stage", 
                                             f"Failed to update stage: {str(e)}")
    
    def on_save_changes(self) -> bool:
        """Save all changes to disk."""
        if self._saving_in_progress:
            return False
        
        self._saving_in_progress = True
        try:
            # First validate that we can save all configs before committing
            working_configs = self.transaction_manager.get_working_configs()
            deleted_names = self.transaction_manager._transaction_state.deleted_pipeline_names if self.transaction_manager._transaction_state else set()
            
            # Validate all configs can be saved
            for config in working_configs:
                # Get the config name for validation (use pipeline name for validation messages)
                pipeline_name = config.get('name', '')
                if pipeline_name:
                    # Clean config for validation (remove metadata)
                    clean_config = {
                        'name': pipeline_name,
                        'stages': config.get('stages', [])
                    }
                    
                    # Test validation without actually saving
                    is_valid, error_msg = self.config_service.validate_config_detailed(clean_config)
                    if not is_valid:
                        raise Exception(f"Invalid config '{pipeline_name}': {error_msg}")
            
            # Now commit the transaction since validation passed
            configs, deleted_names = self.transaction_manager.commit_transaction()
            
            # Save each config to disk
            failed_saves = []
            for config in configs:
                # Get the original config file name from metadata, not the pipeline name
                metadata = config.get('_metadata', {})
                original_config_name = metadata.get('config_name')
                pipeline_name = config.get('name', '')
                is_new = metadata.get('is_new', False)
                
                # For existing configs, use the original file name
                # For new configs, use the pipeline name as file name
                if is_new or not original_config_name:
                    # New pipeline - use pipeline name (which should already be unique)
                    save_name = pipeline_name
                else:
                    # Existing pipeline - use original config file name
                    save_name = original_config_name
                
                if not save_name:
                    continue  # Skip configs without names
                
                # Clean config for saving (remove metadata)
                clean_config = {
                    'name': pipeline_name,  # Pipeline name goes in the file content
                    'stages': config.get('stages', [])
                }
                
                if not self.config_service.save_config(save_name, clean_config):
                    failed_saves.append(save_name)
            
            # Delete removed configs
            failed_deletes = []
            for name in deleted_names:
                if not self.config_service.delete_config(name):
                    failed_deletes.append(name)
            
            # Check if any operations failed
            if failed_saves or failed_deletes:
                error_msg = []
                if failed_saves:
                    error_msg.append(f"Failed to save: {', '.join(failed_saves)}")
                if failed_deletes:
                    error_msg.append(f"Failed to delete: {', '.join(failed_deletes)}")
                raise Exception("; ".join(error_msg))
            
            # Store current selection before reinitializing
            current_pipeline = self._current_pipeline_index
            current_stage = self._current_stage_index
            current_operation = self._current_operation_index
            
            # Reinitialize with saved data
            self._initialize_data()
            
            # Restore previous selection if still valid
            self._restore_selection_after_save(current_pipeline, current_stage, current_operation)
            
            self.changes_saved.emit()
            return True
            
        except Exception as e:
            self.dialog_service.show_error(
                "Save Failed",
                f"Failed to save changes: {str(e)}"
            )
            
            # Store selection before reinitializing
            current_pipeline = self._current_pipeline_index
            current_stage = self._current_stage_index
            current_operation = self._current_operation_index
            
            # Reinitialize to refresh from disk state
            self._initialize_data()
            
            # Restore selection
            self._restore_selection_after_save(current_pipeline, current_stage, current_operation)
            
            return False
            
        finally:
            self._saving_in_progress = False
    
    def on_import_template(self):
        """Handle import template request."""
        file_path = self.dialog_service.browse_file(
            "Import Pipeline Template",
            "YAML files (*.yaml *.yml)"
        )
        
        if file_path:
            try:
                import yaml
                from pathlib import Path
                
                with open(file_path, 'r', encoding='utf-8') as file:
                    config_data = yaml.safe_load(file) or {}
                
                # Validate the imported config
                is_valid, error_msg = self.config_service.validate_config_detailed(config_data)
                if not is_valid:
                    raise Exception(f"Invalid configuration: {error_msg}")
                
                # Create unique name
                base_name = Path(file_path).stem
                pipeline_data = {
                    'name': self._ensure_unique_name(base_name),
                    'stages': config_data.get('stages', [])
                }
                
                # Add to transaction
                new_index = self.transaction_manager.add_pipeline(pipeline_data)
                
                # Update view and select
                self.pipeline_list_updated.emit(self.transaction_manager.get_working_configs())
                self._select_pipeline_with_check(new_index)
                
                self.dialog_service.show_information(
                    "Import Successful",
                    f"Configuration imported as '{pipeline_data['name']}'"
                )
                
            except Exception as e:
                self.dialog_service.show_error(
                    "Import Failed",
                    f"Failed to import template: {str(e)}"
                )
    
    def _ensure_unique_name(self, base_name: str) -> str:
        """Ensure a configuration name is unique both in memory and on disk."""
        # Check against loaded configs in transaction
        configs = self.transaction_manager.get_working_configs()
        existing_names = {c.get('name', '') for c in configs}
        
        # Also check against files on disk to prevent overwriting
        disk_configs = self.config_service.discover_configs()
        existing_names.update({config.name for config in disk_configs})
        
        if base_name not in existing_names:
            return base_name
        
        counter = 1
        while f"{base_name}_{counter}" in existing_names:
            counter += 1
        return f"{base_name}_{counter}"
    
    def _restore_selection_after_save(self, pipeline_index: int, stage_index: int, operation_index: int):
        """Restore selection state after save and reinitialize."""
        try:
            working_configs = self.transaction_manager.get_working_configs()
            
            # Restore pipeline selection if still valid
            if 0 <= pipeline_index < len(working_configs):
                self._select_pipeline_with_check(pipeline_index)
                
                # Restore stage selection if still valid
                pipeline = working_configs[pipeline_index]
                stages = pipeline.get('stages', [])
                if 0 <= stage_index < len(stages):
                    self._select_stage_with_check(stage_index)
                    
                    # Restore operation selection if still valid
                    stage = stages[stage_index]
                    operations = stage.get('operations', [])
                    if 0 <= operation_index < len(operations):
                        self._select_operation_with_check(operation_index)
                    elif operations:
                        # If previous operation index is invalid, select first operation
                        self._select_operation_with_check(0)
                elif stages:
                    # If previous stage index is invalid, select first stage
                    self._select_stage_with_check(0)
            elif working_configs:
                # If previous pipeline index is invalid, select first pipeline
                self._select_pipeline_with_check(0)
                
        except Exception as e:
            # If restoration fails, fall back to default selection
            print(f"Warning: Could not restore selection after save: {e}")
            if working_configs:
                self._select_pipeline_with_check(0)
    
    
    
    def can_close(self) -> bool:
        """Check if dialog can be closed."""
        if not self.transaction_manager.has_changes():
            return True
        
        summary = self.transaction_manager.get_change_summary()
        
        result = self.dialog_service.show_question_with_cancel(
            "Unsaved Changes",
            f"You have {summary['total_changes']} unsaved configuration changes.\n\n"
            "What would you like to do?",
            "Save and Close", "Discard and Close", "Cancel"
        )
        
        if result == "Save and Close":
            return self.on_save_changes()
        elif result == "Discard and Close":
            self.transaction_manager.rollback_transaction()
            return True
        else:  # Cancel
            return False
    
    def has_unsaved_changes(self) -> bool:
        """Check if there are any unsaved changes."""
        return self.transaction_manager.has_changes()
    
    def on_pipeline_details_changed(self, field: str, value):
        """Handle pipeline details changes."""
        if self._current_pipeline_index >= 0:
            try:
                # Use transaction manager to update pipeline
                if not self.transaction_manager.update_pipeline(
                    self._current_pipeline_index, field, value
                ):
                    self.dialog_service.show_error("Update Failed", "Failed to update pipeline")
                else:
                    # Refresh pipeline list in case of revert
                    working_configs = self.transaction_manager.get_working_configs()
                    self.pipeline_list_updated.emit(working_configs)
                    
            except Exception as e:
                self.dialog_service.show_error(
                    "Error Updating Pipeline", 
                    f"Failed to update pipeline: {str(e)}"
                )
    
    # ==================== Operation Management ====================
    
    def on_add_operation(self):
        """Handle add new operation request."""
        if self._current_pipeline_index < 0 or self._current_stage_index < 0:
            self.dialog_service.show_warning(
                "No Stage Selected", 
                "Please select a stage first."
            )
            return
        
        # Create a new operation with default values
        new_operation = {
            'type': 'to_be_defined',
            'workdir': '',
            'files': []
        }
        
        try:
            # Add using transaction manager
            new_index = self.transaction_manager.add_operation(
                self._current_pipeline_index,
                self._current_stage_index,
                new_operation
            )
            
            if new_index >= 0:
                # Update view with current stage's operations
                stage = self.transaction_manager.get_stage(
                    self._current_pipeline_index, self._current_stage_index
                )
                if stage:
                    operations = stage.get('operations', [])
                    self.operation_list_updated.emit(operations)
                    
                    # Select the new operation
                    self._select_operation_with_check(new_index)
            else:
                self.dialog_service.show_error("Error Adding Operation", "Failed to add operation")
                
        except Exception as e:
            self.dialog_service.show_error(
                "Error Adding Operation", 
                f"Failed to add operation: {str(e)}"
            )
    
    def on_delete_operation(self, index: int = None):
        """Handle delete operation request."""
        if self._current_pipeline_index < 0 or self._current_stage_index < 0:
            return
        
        # Use current selection if no index provided
        if index is None:
            index = self._current_operation_index
        
        if index < 0:
            return
            
        try:
            operation = self.transaction_manager.get_operation(
                self._current_pipeline_index, self._current_stage_index, index
            )
            
            if operation:
                op_type = operation.get('type', 'Unknown')
                
                if self.dialog_service.show_question(
                    "Delete Operation", 
                    f"Are you sure you want to delete operation '{op_type}'?"
                ):
                    # Use transaction manager to delete
                    if self.transaction_manager.delete_operation(
                        self._current_pipeline_index, self._current_stage_index, index
                    ):
                        # Update view
                        stage = self.transaction_manager.get_stage(
                            self._current_pipeline_index, self._current_stage_index
                        )
                        if stage:
                            operations = stage.get('operations', [])
                            self.operation_list_updated.emit(operations)
                            
                            # Auto-select another operation if the deleted one was selected
                            if index == self._current_operation_index:
                                if operations:
                                    # Select the previous operation, or first if we deleted the first
                                    new_index = max(0, min(index - 1, len(operations) - 1))
                                    self._select_operation_with_check(new_index)
                                else:
                                    # No operations left - clear selection
                                    self._current_operation_index = -1
                                    self.operation_details_updated.emit({})
                            elif index < self._current_operation_index:
                                # Deleted operation was before current selection, adjust current index
                                self._current_operation_index -= 1
                    else:
                        self.dialog_service.show_error("Delete Failed", "Failed to delete operation")
                    
        except Exception as e:
            self.dialog_service.show_error(
                "Error Deleting Operation", 
                f"Failed to delete operation: {str(e)}"
            )
    
    def on_operation_details_changed(self, field: str, value):
        """Handle operation details changes (legacy method for compatibility)."""
        if (self._current_operation_index >= 0 and 
            self._current_stage_index >= 0 and 
            self._current_pipeline_index >= 0):
            
            try:
                # Get current operation data
                operation = self.transaction_manager.get_operation(
                    self._current_pipeline_index,
                    self._current_stage_index,
                    self._current_operation_index
                )
                
                if operation:
                    # Create updated operation data
                    updated_operation = operation.copy()
                    
                    # Handle different field types
                    if field == 'type':
                        updated_operation['type'] = value
                    elif field == 'workdir':
                        updated_operation['workdir'] = value
                    
                    # Update using transaction manager
                    if not self.transaction_manager.update_operation(
                        self._current_pipeline_index,
                        self._current_stage_index,
                        self._current_operation_index,
                        updated_operation
                    ):
                        self.dialog_service.show_error("Update Failed", "Failed to update operation")
                    else:
                        # Refresh all affected lists (operation, stage, pipeline)
                        self._refresh_all_affected_lists_after_operation_change()
                        
                        # Also re-emit operation details to update the UI with new metadata if type changed
                        if field == 'type':
                            updated_operation_for_ui = {
                                'operation': updated_operation.get('type', ''),
                                'workdir': updated_operation.get('workdir', ''),
                                'parameters': updated_operation.get('parameters', {}),  # Unified parameters
                                'metadata': self.metadata_parser.get_operation_metadata(value)
                            }
                            self.operation_details_updated.emit(updated_operation_for_ui)
                    
            except Exception as e:
                self.dialog_service.show_error(
                    "Error Updating Operation", 
                    f"Failed to update operation: {str(e)}"
                )
    
    def on_operation_parameter_changed(self, param_name: str, value):
        """Handle operation parameter changes (new unified parameter system)."""
        if (self._current_operation_index >= 0 and 
            self._current_stage_index >= 0 and 
            self._current_pipeline_index >= 0):
            
            try:
                # Get current operation data
                operation = self.transaction_manager.get_operation(
                    self._current_pipeline_index,
                    self._current_stage_index,
                    self._current_operation_index
                )
                
                if operation:
                    # Create updated operation data (deep copy to avoid modifying original)
                    import copy
                    updated_operation = copy.deepcopy(operation)
                    
                    # Initialize parameters dict if not present
                    if 'parameters' not in updated_operation:
                        updated_operation['parameters'] = {}
                    
                    # Update the specific parameter
                    updated_operation['parameters'][param_name] = value
                    
                    # Update using transaction manager
                    update_result = self.transaction_manager.update_operation(
                        self._current_pipeline_index,
                        self._current_stage_index,
                        self._current_operation_index,
                        updated_operation
                    )
                    if not update_result:
                        self.dialog_service.show_error("Update Failed", "Failed to update operation parameter")
                    else:
                        # Refresh all affected lists (operation, stage, pipeline)
                        self._refresh_all_affected_lists_after_operation_change()
                        
            except Exception as e:
                self.dialog_service.show_error(
                    "Error Updating Parameter", 
                    f"Failed to update parameter: {str(e)}"
                )
    
    def get_available_operation_types(self) -> List[str]:
        """Get list of available operation types from metadata parser."""
        try:
            all_operations = self.metadata_parser.get_all_operations()
            operation_types = ['to_be_defined'] + list(all_operations.keys())
            return sorted(operation_types)
        except Exception as e:
            # Fallback to static list if metadata parsing fails
            print(f"Warning: Failed to load operations from metadata: {e}")
            return [
                'to_be_defined',
                'reorient_to_standard', 
                'crop_image',
                'move_image',
                'open_fsleyes',
                'bet',
                'fast',
                'first',
                'flirt',
                'fnirt',
                'applywarp',
                'fslmaths',
                'custom_command'
            ]