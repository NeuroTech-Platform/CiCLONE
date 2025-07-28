from PyQt6.QtWidgets import QDialog, QListWidgetItem
from PyQt6.QtCore import Qt

from ciclone.forms.PipelineConfig_ui import Ui_PipelineConfigDialog
from ciclone.controllers.config_dialog_controller import ConfigDialogController
from ciclone.services.config_service import ConfigService
from ciclone.services.ui.dialog_service import DialogService


class PipelineConfigDialog(QDialog, Ui_PipelineConfigDialog):
    """Pipeline configuration management dialog."""
    
    def __init__(self, config_dir: str, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        
        # Initialize services
        self.config_service = ConfigService(config_dir)
        self.dialog_service = DialogService()
        
        # Initialize controller
        self.controller = ConfigDialogController(self.config_service, self.dialog_service)
        
        # Connect controller signals to view updates
        self._connect_controller_signals()
        
        # Connect UI signals to controller
        self._connect_ui_signals()
        
        # Set controller view reference
        self.controller.set_view(self)
    
    def _connect_controller_signals(self):
        """Connect controller signals to view update methods."""
        self.controller.pipeline_list_updated.connect(self._update_pipeline_list)
        self.controller.stage_list_updated.connect(self._update_stage_list)
        self.controller.operation_list_updated.connect(self._update_operation_list)
        self.controller.stage_details_updated.connect(self._update_stage_details)
        self.controller.dependencies_updated.connect(self._update_dependencies)
    
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
        
        # Stage details
        self.lineEdit_stage_name.textChanged.connect(self._on_stage_name_changed)
        self.comboBox_dependencies.currentTextChanged.connect(self._on_dependencies_changed)
        self.checkBox_auto_clean.toggled.connect(self._on_auto_clean_changed)
        
        # Operation actions
        self.pushButton_add_operation.clicked.connect(self._on_add_operation)
        self.pushButton_edit_operation.clicked.connect(self._on_edit_operation)
        self.pushButton_delete_operation.clicked.connect(self._on_delete_operation)
        self.listWidget_operations.currentRowChanged.connect(self.controller.on_operation_selected)
        
        # Bottom actions
        self.pushButton_import_template.clicked.connect(self.controller.on_import_template)
        self.pushButton_preview_yaml.clicked.connect(self.controller.on_preview_yaml)
        self.pushButton_save.clicked.connect(self._on_save_clicked)
    
    def _update_pipeline_list(self, pipelines):
        """Update the pipeline list widget."""
        self.listWidget_pipelines.clear()
        for pipeline in pipelines:
            metadata = pipeline.get('_metadata', {})
            display_name = metadata.get('display_name', pipeline.get('name', 'Unknown'))
            stage_count = metadata.get('stage_count', 0)
            
            item_text = f"{display_name} ({stage_count} stages)"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, pipeline)
            self.listWidget_pipelines.addItem(item)
    
    def _update_stage_list(self, stages):
        """Update the stage list widget."""
        self.listWidget_stages.clear()
        for i, stage in enumerate(stages):
            stage_name = stage.get('name', f'Stage {i+1}')
            depends_on = stage.get('depends_on', [])
            
            item_text = stage_name
            if depends_on:
                item_text += f" (depends: {', '.join(depends_on)})"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, stage)
            self.listWidget_stages.addItem(item)
    
    def _update_operation_list(self, operations):
        """Update the operation list widget."""
        self.listWidget_operations.clear()
        for i, operation in enumerate(operations):
            op_type = operation.get('type', 'Unknown')
            workdir = operation.get('workdir', '')
            files = operation.get('files', [])
            
            item_text = f"{i+1}. {op_type}"
            if workdir:
                item_text += f" (workdir: {workdir})"
            if files:
                file_info = f" [{len(files)} files]"
                item_text += file_info
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, operation)
            self.listWidget_operations.addItem(item)
    
    def _update_stage_details(self, stage_details):
        """Update the stage details form."""
        if not stage_details:
            # Clear form
            self.lineEdit_stage_name.clear()
            self.checkBox_auto_clean.setChecked(True)
            self.comboBox_dependencies.setCurrentText('none')
            return
        
        # Block signals to prevent recursive updates
        self.lineEdit_stage_name.blockSignals(True)
        self.checkBox_auto_clean.blockSignals(True)
        self.comboBox_dependencies.blockSignals(True)
        
        self.lineEdit_stage_name.setText(stage_details.get('name', ''))
        self.checkBox_auto_clean.setChecked(stage_details.get('auto_clean', True))
        
        # Handle dependencies - show first dependency or 'none'
        depends_on = stage_details.get('depends_on', [])
        if depends_on and len(depends_on) > 0:
            # For now, show the first dependency (we could enhance this later for multiple deps)
            dependency_name = depends_on[0]
            # Check if this dependency exists in the combo box
            index = self.comboBox_dependencies.findText(dependency_name)
            if index >= 0:
                self.comboBox_dependencies.setCurrentText(dependency_name)
            else:
                self.comboBox_dependencies.setCurrentText('none')
        else:
            self.comboBox_dependencies.setCurrentText('none')
        
        # Restore signals
        self.lineEdit_stage_name.blockSignals(False)
        self.checkBox_auto_clean.blockSignals(False)
        self.comboBox_dependencies.blockSignals(False)
    
    def _update_dependencies(self, dependencies):
        """Update the dependencies combo box."""        
        self.comboBox_dependencies.blockSignals(True)
        
        # Store current selection to restore if possible
        current_text = self.comboBox_dependencies.currentText()
        
        self.comboBox_dependencies.clear()
        self.comboBox_dependencies.addItems(dependencies)
        
        # Try to restore previous selection, default to 'none' if not available
        if current_text in dependencies:
            self.comboBox_dependencies.setCurrentText(current_text)
        else:
            self.comboBox_dependencies.setCurrentText('none')
        
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
    
    def _on_stage_name_changed(self, text):
        """Handle stage name field changes."""
        self.controller.on_stage_details_changed('name', text)
    
    def _on_dependencies_changed(self, text):
        """Handle dependencies combo box changes."""
        deps = [] if text == 'none' else [text]
        self.controller.on_stage_details_changed('depends_on', deps)
    
    def _on_auto_clean_changed(self, checked):
        """Handle auto clean checkbox changes."""
        self.controller.on_stage_details_changed('auto_clean', checked)
    
    def _on_add_operation(self):
        """Handle add operation button click."""
        # TODO: Implement operation editing dialog
        pass
    
    def _on_edit_operation(self):
        """Handle edit operation button click."""
        # TODO: Implement operation editing dialog
        pass
    
    def _on_delete_operation(self):
        """Handle delete operation button click."""
        # TODO: Implement operation deletion
        pass
    
    def _on_save_clicked(self):
        """Handle save button click."""
        if self.controller.on_save_changes():
            self.accept()  # Close dialog on successful save
    
    def closeEvent(self, event):
        """Handle dialog close event to check for unsaved changes."""
        if self.controller.can_close():
            event.accept()
        else:
            event.ignore()
    
    def reject(self):
        """Handle dialog rejection (Cancel button)."""
        if self.controller.can_close():
            super().reject()