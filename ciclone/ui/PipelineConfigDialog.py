from typing import Any
from PyQt6.QtWidgets import QDialog, QListWidgetItem
from PyQt6.QtCore import Qt, QEvent, QTimer

from ciclone.forms.PipelineConfig_ui import Ui_PipelineConfigDialog
from ciclone.controllers.config_dialog_controller import ConfigDialogController
from ciclone.services.config_service import ConfigService
from ciclone.services.ui.dialog_service import DialogService
from ciclone.ui.widgets.MultiSelectComboBox import MultiSelectComboBox
from ciclone.ui.widgets.parameter_widget_factory import ParameterWidgetFactory, ParameterWidget


class PipelineConfigDialog(QDialog, Ui_PipelineConfigDialog):
    """Pipeline configuration management dialog."""
    
    def __init__(self, config_dir: str, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        
        # Initialize parameter widgets list
        self._parameter_widgets = {}
        
        # Initialize services
        self.config_service = ConfigService(config_dir)
        self.dialog_service = DialogService()
        
        # Initialize controller
        self.controller = ConfigDialogController(self.config_service, self.dialog_service)
        
        # Connect controller signals to view updates
        self._connect_controller_signals()
        
        # Connect UI signals to controller
        self._connect_ui_signals()
        
        # Connect pipeline name editing - use editingFinished to avoid prompting on every keystroke
        self.lineEdit_pipeline_name.editingFinished.connect(self._on_pipeline_name_changed)
        
        # Configure list widgets for proper keyboard navigation
        self._configure_list_navigation()
        
        # Initialize operation type combo box BEFORE setting controller view
        self._initialize_operation_types()
        
        # Set controller view reference (this will trigger data loading and UI updates)
        self.controller.set_view(self)
        
        # Set initial state
        self._update_change_indicators()
    
    def _configure_list_navigation(self):
        """Configure list widgets for proper keyboard navigation using Qt built-ins."""
        list_widgets = [
            self.listWidget_pipelines,
            self.listWidget_stages,
            self.listWidget_operations
        ]
        
        for widget in list_widgets:
            # Use Qt's built-in strong focus policy for proper keyboard/mouse focus
            widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            # Install event filter for keyboard navigation
            widget.installEventFilter(self)
            # Connect itemClicked to ensure focus on click
            widget.itemClicked.connect(lambda item, w=widget: w.setFocus())
    
    def eventFilter(self, obj, event):
        """Handle focus for list widgets - simple approach."""
        if obj in (self.listWidget_pipelines, self.listWidget_stages, self.listWidget_operations):
            
            # Handle keyboard navigation - just maintain focus after arrow keys
            if (event.type() == QEvent.Type.KeyPress and 
                event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down)):
                
                result = super().eventFilter(obj, event)
                # Immediately restore focus after navigation
                QTimer.singleShot(0, lambda widget=obj: widget.setFocus())
                return result
                
        return super().eventFilter(obj, event)
    
    
    def _connect_controller_signals(self):
        """Connect controller signals to view update methods."""
        self.controller.pipeline_list_updated.connect(self._update_pipeline_list)
        self.controller.pipeline_selection_updated.connect(self._update_pipeline_selection)
        self.controller.stage_list_updated.connect(self._update_stage_list)
        self.controller.stage_selection_updated.connect(self._update_stage_selection)
        self.controller.operation_list_updated.connect(self._update_operation_list)
        self.controller.operation_selection_updated.connect(self._update_operation_selection)
        self.controller.stage_details_updated.connect(self._update_stage_details)
        self.controller.dependencies_updated.connect(self._update_dependencies)
        self.controller.operation_details_updated.connect(self._update_operation_details)
        self.controller.unsaved_changes_detected.connect(self._on_unsaved_changes_detected)
        self.controller.changes_saved.connect(self._on_changes_saved)
        self.controller.changes_discarded.connect(self._on_changes_discarded)
        self.controller.pipeline_details_updated.connect(self._update_pipeline_details)
    
    def _connect_ui_signals(self):
        """Connect UI signals to controller methods."""
        # Pipeline actions
        self.pushButton_add_pipeline.clicked.connect(self.controller.on_add_pipeline)
        self.pushButton_delete_pipeline.clicked.connect(self._on_delete_pipeline_clicked)
        self.listWidget_pipelines.currentRowChanged.connect(self.controller.on_pipeline_selected)
        
        # Stage actions
        self.pushButton_add_stage.clicked.connect(self.controller.on_add_stage)
        self.pushButton_delete_stage.clicked.connect(self._on_delete_stage_clicked)
        self.pushButton_move_stage_up.clicked.connect(self._on_move_stage_up)
        self.pushButton_move_stage_down.clicked.connect(self._on_move_stage_down)
        self.listWidget_stages.currentRowChanged.connect(self.controller.on_stage_selected)
        
        # Stage details (use editingFinished to avoid prompting on every keystroke)
        self.lineEdit_stage_name.editingFinished.connect(self._on_stage_name_changed)
        self.comboBox_dependencies.selectionChanged.connect(self._on_dependencies_changed)
        self.checkBox_auto_clean.toggled.connect(self._on_auto_clean_changed)
        
        # Operation actions
        self.pushButton_add_operation.clicked.connect(self.controller.on_add_operation)
        self.pushButton_delete_operation.clicked.connect(self._on_delete_operation_clicked)
        self.listWidget_operations.currentRowChanged.connect(self.controller.on_operation_selected)
        
        # Operation configuration (use editingFinished to avoid prompting on every keystroke)
        self.comboBox_operation_type.currentTextChanged.connect(self._on_operation_type_changed)
        self.lineEdit_workdir.editingFinished.connect(self._on_workdir_changed)
        # Note: File input connections are set up dynamically in _setup_file_inputs
        
        # Bottom actions
        self.pushButton_import_template.clicked.connect(self.controller.on_import_template)
        #self.pushButton_preview_yaml.clicked.connect(self.controller.on_preview_yaml)
        self.pushButton_save.clicked.connect(self._on_save_clicked)
    
    def _update_pipeline_list(self, pipelines):
        """Update the pipeline list widget with dirty indicators."""
        # Preserve focus state
        had_focus = self.listWidget_pipelines.hasFocus()
        
        # Block signals to prevent unwanted currentRowChanged events during update
        self.listWidget_pipelines.blockSignals(True)
        
        self.listWidget_pipelines.clear()
        for i, pipeline in enumerate(pipelines):
            metadata = pipeline.get('_metadata', {})
            display_name = metadata.get('display_name', pipeline.get('name', 'Unknown'))
            stage_count = metadata.get('stage_count', 0)
            
            # Check if pipeline is dirty and add * indicator
            if self.controller.transaction_manager.is_pipeline_dirty(i):
                display_name += " *"
            
            item_text = f"{display_name} ({stage_count} stages)"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, pipeline)
            self.listWidget_pipelines.addItem(item)
        
        # Don't set selection here - let the controller manage selection through _update_pipeline_selection
        # The controller will emit pipeline_selection_updated signal when appropriate
        
        # Re-enable signals
        self.listWidget_pipelines.blockSignals(False)
        
        # Restore focus if it was focused before
        if had_focus:
            self.listWidget_pipelines.setFocus()
    
    def _update_pipeline_selection(self, index: int):
        """Update the pipeline list widget selection to match controller state."""
        if 0 <= index < self.listWidget_pipelines.count():
            # Preserve focus state during selection update
            had_focus = self.listWidget_pipelines.hasFocus()
            self.listWidget_pipelines.setCurrentRow(index)
            if had_focus:
                self.listWidget_pipelines.setFocus()
    
    def _update_stage_list(self, stages):
        """Update the stage list widget with dirty indicators."""
        # Preserve focus state
        had_focus = self.listWidget_stages.hasFocus()
        
        # Block signals to prevent unwanted currentRowChanged events during update
        self.listWidget_stages.blockSignals(True)
        
        self.listWidget_stages.clear()
        for i, stage in enumerate(stages):
            stage_name = stage.get('name', f'Stage {i+1}')
            depends_on = stage.get('depends_on', [])
            
            # Check if stage is dirty and add * indicator
            pipeline_idx = self.controller._current_pipeline_index
            if (pipeline_idx >= 0 and 
                self.controller.transaction_manager.is_stage_dirty(pipeline_idx, i)):
                stage_name += " *"
            
            item_text = stage_name
            if depends_on:
                item_text += f" (depends: {', '.join(depends_on)})"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, stage)
            self.listWidget_stages.addItem(item)
        
        # Don't set selection here - let the controller manage selection through _update_stage_selection
        # The controller will emit stage_selection_updated signal when appropriate
        
        # Re-enable signals
        self.listWidget_stages.blockSignals(False)
        
        # Restore focus if it was focused before
        if had_focus:
            self.listWidget_stages.setFocus()
    
    def _update_operation_list(self, operations):
        """Update the operation list widget with dirty indicators."""
        # Preserve focus state
        had_focus = self.listWidget_operations.hasFocus()
        
        # Block signals to prevent unwanted currentRowChanged events during update
        self.listWidget_operations.blockSignals(True)
        
        self.listWidget_operations.clear()
        for i, operation in enumerate(operations):
            op_type = operation.get('type', 'Unknown')
            
            # Check if operation is dirty and add * indicator
            pipeline_idx = self.controller._current_pipeline_index
            stage_idx = self.controller._current_stage_index
            if (pipeline_idx >= 0 and stage_idx >= 0 and 
                self.controller.transaction_manager.is_operation_dirty(pipeline_idx, stage_idx, i)):
                op_type += " *"
            
            item_text = f"{i+1}. {op_type}"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, operation)
            self.listWidget_operations.addItem(item)
        
        # Don't set selection here - let the controller manage selection through _update_operation_selection
        # The controller will emit operation_selection_updated signal when appropriate
        
        # Re-enable signals
        self.listWidget_operations.blockSignals(False)
        
        # Restore focus if it was focused before
        if had_focus:
            self.listWidget_operations.setFocus()
    
    def _update_stage_selection(self, index: int):
        """Update the stage list widget selection to match controller state."""
        if 0 <= index < self.listWidget_stages.count():
            # Preserve focus state during selection update
            had_focus = self.listWidget_stages.hasFocus()
            self.listWidget_stages.setCurrentRow(index)
            if had_focus:
                self.listWidget_stages.setFocus()
    
    def _update_operation_selection(self, index: int):
        """Update the operation list widget selection to match controller state."""
        if 0 <= index < self.listWidget_operations.count():
            # Preserve focus state during selection update
            had_focus = self.listWidget_operations.hasFocus()
            self.listWidget_operations.setCurrentRow(index)
            if had_focus:
                self.listWidget_operations.setFocus()
    
    def _update_stage_details(self, stage_details):
        """Update the stage details form."""
        if not stage_details:
            # Clear form
            self.lineEdit_stage_name.clear()
            self.checkBox_auto_clean.setChecked(True)
            self.comboBox_dependencies.set_selected_items([])
            return
        
        # Block signals to prevent recursive updates
        self.lineEdit_stage_name.blockSignals(True)
        self.checkBox_auto_clean.blockSignals(True)
        self.comboBox_dependencies.blockSignals(True)
        
        self.lineEdit_stage_name.setText(stage_details.get('name', ''))
        self.checkBox_auto_clean.setChecked(stage_details.get('auto_clean', True))
        
        # Handle dependencies - set all selected dependencies
        depends_on = stage_details.get('depends_on', [])
        self.comboBox_dependencies.set_selected_items(depends_on)
        
        # Restore signals
        self.lineEdit_stage_name.blockSignals(False)
        self.checkBox_auto_clean.blockSignals(False)
        self.comboBox_dependencies.blockSignals(False)
    
    def _update_dependencies(self, dependencies):
        """Update the dependencies combo box."""
        self.comboBox_dependencies.blockSignals(True)
        
        # Store current selections to restore if possible
        current_selections = self.comboBox_dependencies.get_selected_items()
        
        # Clear and populate with new items
        self.comboBox_dependencies.clear_items()
        self.comboBox_dependencies.add_items(dependencies)
        
        # Restore previous selections if they still exist
        valid_selections = [dep for dep in current_selections if dep in dependencies]
        self.comboBox_dependencies.set_selected_items(valid_selections)
        
        self.comboBox_dependencies.blockSignals(False)
    
    def _on_delete_pipeline_clicked(self):
        """Handle delete pipeline button click."""
        current_row = self.listWidget_pipelines.currentRow()
        if current_row >= 0:
            self.controller.on_delete_pipeline(current_row)
    
    def _on_delete_stage_clicked(self):
        """Handle delete stage button click."""
        current_row = self.listWidget_stages.currentRow()
        if current_row >= 0:
            self.controller.on_delete_stage(current_row)
    
    def _on_move_stage_up(self):
        """Handle move stage up button click."""
        current_row = self.listWidget_stages.currentRow()
        if current_row > 0:
            self.controller.on_move_stage_up(current_row)
            # Update selection to follow the moved stage
            self.listWidget_stages.setCurrentRow(current_row - 1)
    
    def _on_move_stage_down(self):
        """Handle move stage down button click."""
        current_row = self.listWidget_stages.currentRow()
        if current_row >= 0 and current_row < self.listWidget_stages.count() - 1:
            self.controller.on_move_stage_down(current_row)
            # Update selection to follow the moved stage
            self.listWidget_stages.setCurrentRow(current_row + 1)
    
    def _on_stage_name_changed(self):
        """Handle stage name field changes when editing is finished."""
        text = self.lineEdit_stage_name.text()
        self.controller.on_stage_details_changed('name', text)
    
    def _on_dependencies_changed(self, selected_items):
        """Handle dependencies combo box changes."""
        self.controller.on_stage_details_changed('depends_on', selected_items)
    
    def _on_auto_clean_changed(self, checked):
        """Handle auto clean checkbox changes."""
        self.controller.on_stage_details_changed('auto_clean', checked)
    
    def _on_pipeline_name_changed(self):
        """Handle pipeline name field changes when editing is finished."""
        text = self.lineEdit_pipeline_name.text()
        self.controller.on_pipeline_details_changed('name', text)
    
    def _update_pipeline_details(self, pipeline_details):
        """Update the pipeline details form."""
        if not pipeline_details:
            # Clear form
            self.lineEdit_pipeline_name.clear()
            return
        
        # Block signals to prevent recursive updates
        self.lineEdit_pipeline_name.blockSignals(True)
        
        # Update pipeline name
        pipeline_name = pipeline_details.get('name', '')
        self.lineEdit_pipeline_name.setText(pipeline_name)
        
        # Restore signals
        self.lineEdit_pipeline_name.blockSignals(False)
    
    def _update_operation_description(self, operation_type: str):
        """Update operation description based on selected type."""
        try:
            if hasattr(self, 'controller') and operation_type and operation_type != 'to_be_defined':
                metadata = self.controller.metadata_parser.get_operation_metadata(operation_type)
                if metadata:
                    description = metadata.get('description', 'Select an operation type to see description')
                    self.label_description.setText(description)
                    self._update_parameter_requirements(metadata)
                    return
            
            self.label_description.setText('Select an operation type to see description')
            self.label_requirements.setText('Select an operation to see parameter requirements')
        except Exception as e:
            print(f"Error updating operation description: {e}")
            self.label_description.setText('Select an operation type to see description')
            self.label_requirements.setText('Select an operation to see parameter requirements')
    
    def _update_operation_description_with_metadata(self, operation_type: str, metadata):
        """Update operation description using provided metadata."""
        try:
            if metadata and operation_type and operation_type != 'to_be_defined':
                description = metadata.get('description', 'Select an operation type to see description')
                self.label_description.setText(description)
                self._update_parameter_requirements(metadata)
            else:
                # Fallback to regular description update
                self._update_operation_description(operation_type)
        except Exception as e:
            print(f"Error updating operation description with metadata: {e}")
            self.label_description.setText('Select an operation type to see description')
            self.label_requirements.setText('Select an operation to see parameter requirements')
    
    def _update_parameter_requirements(self, metadata):
        """Update parameter requirements information based on operation metadata."""
        try:
            parameters = metadata.get('parameters', {})
            if not parameters:
                self.label_requirements.setText('This operation does not require any parameters.')
                return
            
            requirements = []
            requirements.append("")  # Empty line for spacing
            requirements.append(f"Required parameters:")
            
            for i, (param_name, param_info) in enumerate(parameters.items(), 1):
                param_desc = param_info.get('description', 'No description available')
                param_type = param_info.get('type', 'Any')
                is_required = param_info.get('required', False)
                required_text = ' (required)' if is_required else ' (optional)'
                requirements.append(f"    {i}. {param_name} ({param_type}){required_text}: {param_desc}")
            self.label_requirements.setText('\n'.join(requirements))
            
        except Exception as e:
            print(f"Error updating parameter requirements: {e}")
            self.label_requirements.setText('Error loading parameter requirements')
    
    def _on_delete_operation_clicked(self):
        """Handle delete operation button click."""
        current_row = self.listWidget_operations.currentRow()
        if current_row >= 0:
            self.controller.on_delete_operation(current_row)
    
    def _on_operation_type_changed(self, text):
        """Handle operation type changes."""
        if text:
            # Update description
            self._update_operation_description(text)
            
            # Update controller with new type
            self.controller.on_operation_details_changed('type', text)
    
    def _on_workdir_changed(self):
        """Handle workdir field changes when editing is finished."""
        text = self.lineEdit_workdir.text()
        self.controller.on_operation_details_changed('workdir', text)
    
    def _on_parameter_changed(self, param_name: str, value: Any):
        """Handle parameter value changes."""
        self.controller.on_operation_parameter_changed(param_name, value)
    
    def _initialize_operation_types(self):
        """Initialize the operation types combo box."""
        operation_types = self.controller.get_available_operation_types()
        self.comboBox_operation_type.clear()
        self.comboBox_operation_type.addItems(operation_types)
    
    
    def _update_operation_details(self, operation_details):
        """Update the operation details form with unified parameters."""
        if not operation_details:
            # Clear form
            self.comboBox_operation_type.setCurrentText('to_be_defined')
            self.lineEdit_workdir.clear()
            self._clear_parameter_widgets()
            # Clear description
            self.label_description.setText('Select an operation type to see description')
            return
        
        # Block signals to prevent recursive updates
        self.comboBox_operation_type.blockSignals(True)
        self.lineEdit_workdir.blockSignals(True)
        
        # Update operation type
        operation_type = operation_details.get('operation', 'to_be_defined')
        
        # Check if the operation type exists in the combo box
        index = self.comboBox_operation_type.findText(operation_type)
        if index >= 0:
            self.comboBox_operation_type.setCurrentIndex(index)
        else:
            # Operation type not found, add it and select it
            print(f"Warning: Operation type '{operation_type}' not found in combo box, adding it")
            self.comboBox_operation_type.addItem(operation_type)
            self.comboBox_operation_type.setCurrentText(operation_type)
        
        # Update workdir
        workdir = operation_details.get('workdir', '')
        self.lineEdit_workdir.setText(workdir)
        
        # Setup parameter widgets based on metadata
        metadata = operation_details.get('metadata')
        parameters = operation_details.get('parameters', {})
        
        self._setup_parameter_widgets(metadata, parameters)
        
        # Update operation description using metadata if available
        self._update_operation_description_with_metadata(operation_type, metadata)
        
        # Restore signals
        self.comboBox_operation_type.blockSignals(False)
        self.lineEdit_workdir.blockSignals(False)
    
    def _setup_parameter_widgets(self, metadata, parameters):
        """Setup parameter input widgets based on operation metadata."""
        # Clear existing parameter widgets first
        self._clear_parameter_widgets()
        
        # Force immediate redraw
        self.groupBox_operation_files.repaint()
        
        if not metadata or not metadata.get('parameters'):
            # No metadata available - skip widget creation
            return
        
        # Create widgets based on metadata
        param_metadata = metadata.get('parameters', {})
        
        for param_name, param_info in param_metadata.items():
            # Get current value from parameters dict
            current_value = parameters.get(param_name, param_info.get('default'))
            
            # Create widget using factory
            widget = ParameterWidgetFactory.create_widget(
                param_name, param_info, self.groupBox_operation_files
            )
            
            if widget:
                # Set current value
                if current_value is not None:
                    widget.set_value(current_value)
                
                # Connect value change signal
                widget.valueChanged.connect(self._on_parameter_changed)
                
                # Add to layout
                self.verticalLayout_operation_files.addWidget(widget)
                
                # Store reference
                self._parameter_widgets[param_name] = widget
    
    
    def _clear_parameter_widgets(self):
        """Clear all dynamically created parameter widgets."""
        # Clear all widgets from the layout immediately
        while self.verticalLayout_operation_files.count():
            child = self.verticalLayout_operation_files.takeAt(0)
            if child.widget():
                child.widget().setParent(None)
                child.widget().deleteLater()
        
        # Clear our tracking dict
        self._parameter_widgets.clear()
    
    
    def _update_change_indicators(self):
        """Update visual indicators for unsaved changes."""
        has_changes = self.controller.has_unsaved_changes()
        
        # Update window title to show unsaved changes
        base_title = "Pipeline Configuration"
        if has_changes:
            self.setWindowTitle(f"{base_title} * (unsaved changes)")
        else:
            self.setWindowTitle(base_title)
        
        # Update save button state
        self.pushButton_save.setEnabled(has_changes)
        
        # Update pipeline name field state based on selection
        has_pipeline_selected = hasattr(self.controller, '_current_pipeline_index') and self.controller._current_pipeline_index >= 0
        self.lineEdit_pipeline_name.setEnabled(has_pipeline_selected)
        
        # Refresh all lists to show updated * indicators
        self._refresh_all_lists()
        
        # Could add more visual indicators here (colors, icons, etc.)
    
    def _refresh_all_lists(self):
        """Refresh all lists to show current dirty state."""
        # Re-emit current data to trigger list updates with * indicators
        working_configs = self.controller.transaction_manager.get_working_configs()
        self.controller.pipeline_list_updated.emit(working_configs)
        
        if self.controller._current_pipeline_index >= 0:
            pipeline = self.controller.transaction_manager.get_pipeline(
                self.controller._current_pipeline_index
            )
            if pipeline:
                stages = pipeline.get('stages', [])
                self.controller.stage_list_updated.emit(stages)
                
                if self.controller._current_stage_index >= 0 and self.controller._current_stage_index < len(stages):
                    stage = stages[self.controller._current_stage_index]
                    operations = stage.get('operations', [])
                    self.controller.operation_list_updated.emit(operations)
    
    def _on_unsaved_changes_detected(self, message: str):
        """Handle unsaved changes detection signal."""
        self._update_change_indicators()
        
        # Could show status message or other feedback
        # self.statusBar().showMessage(message, 3000)
        _ = message  # Parameter kept for future use
    
    def _on_changes_saved(self):
        """Handle changes saved signal."""
        self._update_change_indicators()
        self._refresh_all_lists()
        # Could show success message
    
    def _on_changes_discarded(self):
        """Handle changes discarded signal."""
        self._update_change_indicators()
        self._refresh_all_lists()
        # Could show discard message
    
    def showEvent(self, event):
        """Handle dialog show event to update initial state."""
        super().showEvent(event)
        self._update_change_indicators()
    
    def _on_save_clicked(self):
        """Handle save button click."""
        try:
            if self.controller.on_save_changes():
                # Show success feedback
                self.dialog_service.show_information(
                    "Save Successful",
                    "Configuration changes have been saved successfully."
                )
                self.accept()  # Close dialog on successful save
            else:
                # Error is already shown by controller, just stay open
                pass
        except Exception as e:
            self.dialog_service.show_error(
                "Save Error",
                f"An unexpected error occurred while saving: {str(e)}"
            )
    
    def closeEvent(self, event):
        """Handle dialog close event to check for unsaved changes."""
        try:
            if self.controller.can_close():
                event.accept()
            else:
                event.ignore()
        except Exception as e:
            # Log error but don't prevent closing on error
            print(f"Error during close: {e}")
            event.accept()
    
    def reject(self):
        """Handle dialog rejection (Cancel button)."""
        try:
            if self.controller.can_close():
                super().reject()
        except Exception as e:
            # Log error but don't prevent closing on error
            print(f"Error during reject: {e}")
            super().reject()
    
