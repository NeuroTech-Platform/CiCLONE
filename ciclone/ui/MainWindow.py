import os
from PyQt6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QInputDialog,
    QListWidgetItem,
    QMenu
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from ciclone.controllers.main_controller import MainController
from ciclone.services.processing.tool_config import tool_config

from ..forms.MainWindow_ui import Ui_MainWindow

class MainWindow(QMainWindow, Ui_MainWindow):
    config_path = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "config/config.yaml"))
    
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)
        
        # Check neuroimaging environment (FSL and FreeSurfer) before initializing controllers
        self._check_neuroimaging_environment()
        
        # Initialize main controller (coordinates all other controllers and models)
        self.main_controller = MainController(self.config_path)
        self.main_controller.set_view(self)
        self.main_controller.set_log_callback(self.add_log_message)
        
        # File menu actions
        self.actionNew_Output_Directory.triggered.connect(self.create_output_directory)
        self.actionOpen_Output_Directory.triggered.connect(self.open_output_directory)
        
        # Directory and subject management
        self.lineEdit_outputDirectory.textChanged.connect(self.on_output_directory_changed)
        self.pushButton_addSubject.clicked.connect(self.add_subject)
        
        # Subject tree view
        self.subjectTreeView.clicked.connect(self.on_tree_item_clicked)
        
        # Set up context menu for subject tree view
        self.subjectTreeView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.subjectTreeView.customContextMenuRequested.connect(self.show_context_menu)

        # Browse buttons
        self.browse_Schema.clicked.connect(lambda: self._browse_file("Schema"))
        self.browse_preCT.clicked.connect(lambda: self._browse_file("PreCT"))
        self.browse_preMRI.clicked.connect(lambda: self._browse_file("PreMRI"))
        self.browse_postCT.clicked.connect(lambda: self._browse_file("PostCT"))
        self.browse_postMRI.clicked.connect(lambda: self._browse_file("PostMRI"))

        # Run stages buttons
        self.runAllStages_PushButton.clicked.connect(self.run_all_stages)
        self.runSelectedStages_pushButton.clicked.connect(self.run_selected_stages)
        
        # Stop processing button (defined in UI file)
        self.stopProcessing_pushButton.clicked.connect(self.stop_processing)

        # Initialize stages UI from main controller
        self._setup_stages_ui()
        
        # Connect to application model signals through main controller
        self.main_controller.connect_worker_state_signal(self.update_processing_ui)
        
        # Add verbose mode toggle (Ctrl+V)
        self.verbose_action = QAction("Toggle Verbose Logging", self)
        self.verbose_action.setShortcut("Ctrl+V")
        self.verbose_action.triggered.connect(self.toggle_verbose_mode)
        self.addAction(self.verbose_action)
        
        # Add right-click context menu to log area
        self.textBrowser.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.textBrowser.customContextMenuRequested.connect(self.show_log_context_menu)

    def _check_neuroimaging_environment(self):
        """
        Check if FSL and FreeSurfer are properly configured.
        Show warning dialog if there are issues.
        """
        print("Checking neuroimaging environment...")
        is_configured, error_messages = tool_config.validate_environment()
        
        if not is_configured:
            error_text = "The following neuroimaging tools are not properly configured:\n\n" + \
                        "\n".join(error_messages) + \
                        "\n\nSome features may not work correctly. " + \
                        "Please ensure these tools are installed and their environment variables are set:\n" + \
                        "- FSL: Set FSLDIR environment variable\n" + \
                        "- FreeSurfer: Set FREESURFER_HOME environment variable"
            
            QMessageBox.warning(
                self,
                "Neuroimaging Environment Warning",
                error_text
            )
    
    @property
    def output_directory(self):
        """Get output directory from main controller."""
        return self.main_controller.get_output_directory()
    
    @output_directory.setter  
    def output_directory(self, value):
        """Set output directory through main controller."""
        if value:
            self.main_controller.set_output_directory(value)

    def create_output_directory(self):
        """Create new output directory using main controller."""
        output_directory = self.main_controller.create_output_directory()
        if output_directory:
            self.output_directory = output_directory
            self.lineEdit_outputDirectory.setText(output_directory)
        
    def open_output_directory(self):
        """Open existing output directory using main controller."""
        output_directory = self.main_controller.open_output_directory()
        if output_directory:
            self.output_directory = output_directory
            self.lineEdit_outputDirectory.setText(output_directory)

    def on_output_directory_changed(self):
        """Handle output directory changes and update UI."""
        # Get directory from line edit and notify main controller
        directory_text = self.lineEdit_outputDirectory.text().strip()
        if directory_text:
            self.main_controller.set_output_directory(directory_text)

    def _browse_file(self, field_type: str):
        """Generic file browser for different fields using main controller."""
        file_path = self.main_controller.browse_file(field_type)
        if file_path:
            if field_type == "Schema":
                self.lineEdit_Schema.setText(file_path)
                # Set tooltip to show all selected files for schema
                if ',' in file_path:
                    schema_files = [path.strip() for path in file_path.split(',') if path.strip()]
                    file_names = [os.path.basename(path) for path in schema_files]
                    tooltip_text = f"Selected {len(schema_files)} file(s):\n" + "\n".join(file_names)
                    self.lineEdit_Schema.setToolTip(tooltip_text)
                else:
                    self.lineEdit_Schema.setToolTip(os.path.basename(file_path))
            elif field_type == "PreCT":
                self.lineEdit_preCT.setText(file_path)
            elif field_type == "PreMRI":
                self.lineEdit_preMRI.setText(file_path)
            elif field_type == "PostCT":
                self.lineEdit_postCT.setText(file_path)
            elif field_type == "PostMRI":
                self.lineEdit_postMRI.setText(file_path)

    def add_subject(self):
        """Add a new subject to the current output directory"""
        if not self.main_controller.is_output_directory_set():
            QMessageBox.warning(self, "Error", "Please select an output directory first")
            return
            
        subject_name = self.lineEdit_Name.text().strip()
        if not subject_name:
            QMessageBox.warning(self, "Error", "Please enter a subject name")
            return

        # Collect form data and pass to controller
        form_data = {
            'name': subject_name,
            'schema': self.lineEdit_Schema.text(),
            'pre_ct': self.lineEdit_preCT.text(),
            'pre_mri': self.lineEdit_preMRI.text(),
            'post_ct': self.lineEdit_postCT.text(),
            'post_mri': self.lineEdit_postMRI.text()
        }
        
        # Handle multiple schema files
        schema_text = self.lineEdit_Schema.text().strip()
        if schema_text:
            schema_files = [path.strip() for path in schema_text.split(',') if path.strip()]
            form_data['schema_files'] = schema_files
        
        # Use main controller to create subject from form data
        success = self.main_controller.create_subject_from_form_data(form_data)
        
        if success:
            # Show success message box
            QMessageBox.information(
                self, 
                "Import Successful", 
                f"Subject '{subject_name}' has been imported successfully!"
            )
        else:
            # Show error message box (detailed error already logged by controller)
            QMessageBox.critical(
                self, 
                "Import Failed", 
                f"Failed to import subject '{subject_name}'. Check the log for details."
            )

    def run_all_stages(self):
        """Run all configured stages for selected subjects."""
        subject_list = self._get_selected_subjects()
        if not subject_list:
            QMessageBox.warning(self, "Error", "Please select at least one subject")
            return
        
        # Use main controller to run all stages
        success = self.main_controller.run_all_stages(subject_list)
        if not success:
            # Error already logged by controller
            pass

    def run_selected_stages(self):
        """Run only the selected stages for selected subjects."""
        subject_list = self._get_selected_subjects()
        if not subject_list:
            QMessageBox.warning(self, "Error", "Please select at least one subject")
            return
        
        # Update stages selection from UI first
        self._update_stages_selection_from_ui()
        
        # Use main controller to run selected stages
        success = self.main_controller.run_selected_stages(subject_list)
        if not success:
            # Error already logged by controller
            pass

    def add_log_message(self, level: str, message: str):
        """Add a log message to the text browser with appropriate formatting"""
        color_map = {
            "debug": "gray",
            "info": "black",
            "success": "green",
            "error": "red",
            "warning": "orange"
        }
        color = color_map.get(level, "black")
        formatted_message = f'<p style="color:{color}"><b>[{level.upper()}]</b> {message}</p>'
        self.textBrowser.append(formatted_message)
        # Ensure the latest message is visible
        self.textBrowser.ensureCursorVisible()

    def on_tree_item_clicked(self, index):
        """Handle tree item clicks to display files in appropriate viewer/preview"""
        file_path = self.main_controller.get_file_path_from_tree_index(index)
        if file_path and self.main_controller.is_previewable_file(file_path):
            # Use main controller to open appropriate preview for any supported file type
            self.main_controller.open_file_preview(file_path)

    def show_context_menu(self, position):
        """Show context menu for subject management"""
        index = self.subjectTreeView.indexAt(position)
        if not index.isValid():
            return
            
        # Get all selected indexes
        selected_indexes = self.subjectTreeView.selectedIndexes()
        if not selected_indexes:
            return
        
        # Get subject paths through main controller
        subject_paths = self.main_controller.get_selected_subject_paths_from_tree(selected_indexes)
        
        if not subject_paths:
            return
        
        context_menu = QMenu(self)
        
        if len(subject_paths) == 1:
            # Single subject selected - show rename and delete options
            single_path = subject_paths[0]
            
            # Rename action
            rename_action = QAction("Rename Subject", self)
            rename_action.triggered.connect(lambda: self.rename_subject(single_path))
            context_menu.addAction(rename_action)
            
            # Delete action
            delete_action = QAction("Delete Subject", self)
            delete_action.triggered.connect(lambda: self.delete_subject(single_path))
            context_menu.addAction(delete_action)
        else:
            # Multiple subjects selected - show only delete option
            delete_action = QAction(f"Delete {len(subject_paths)} Subjects", self)
            delete_action.triggered.connect(lambda: self.delete_multiple_subjects(subject_paths))
            context_menu.addAction(delete_action)
        
        # Show menu at cursor position
        context_menu.exec(self.subjectTreeView.mapToGlobal(position))

    def rename_subject(self, subject_path):
        """Rename a subject directory"""
        current_name = os.path.basename(subject_path)
        new_name, ok = QInputDialog.getText(
            self, 
            "Rename Subject", 
            f"Enter new name for subject '{current_name}':",
            text=current_name
        )
        
        if not ok or not new_name.strip():
            return
            
        new_name = new_name.strip()
        if new_name == current_name:
            return
            
        # Use main controller to rename subject
        success = self.main_controller.rename_subject(current_name, new_name)
        
        if success:
            QMessageBox.information(
                self, 
                "Rename Successful", 
                f"Subject '{current_name}' has been renamed to '{new_name}'"
            )
        else:
            # Show error message box (detailed error already logged by controller)
            QMessageBox.critical(
                self, 
                "Rename Failed", 
                f"Failed to rename subject '{current_name}'. Check the log for details."
            )

    def delete_subject(self, subject_path):
        """Delete a subject directory"""
        subject_name = os.path.basename(subject_path)
        
        # Confirmation dialog
        reply = QMessageBox.question(
            self,
            "Delete Subject",
            f"Are you sure you want to delete subject '{subject_name}'?\n\n"
            "This action cannot be undone and will permanently delete all files "
            "and data associated with this subject.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
            
        # Use main controller to delete subject
        success = self.main_controller.delete_subject(subject_name)
        
        if success:
            QMessageBox.information(
                self, 
                "Delete Successful", 
                f"Subject '{subject_name}' has been deleted successfully."
            )
        else:
            # Show error message box (detailed error already logged by controller)
            QMessageBox.critical(
                self, 
                "Delete Failed", 
                f"Failed to delete subject '{subject_name}'. Check the log for details."
            )
    
    def delete_multiple_subjects(self, subject_paths):
        """Delete multiple selected subjects"""
        subject_names = [os.path.basename(path) for path in subject_paths]
        subject_count = len(subject_names)
        
        # Confirmation dialog for multiple subjects
        subject_list = "\n".join(f"• {name}" for name in subject_names)
        reply = QMessageBox.question(
            self,
            f"Delete {subject_count} Subjects",
            f"Are you sure you want to delete the following {subject_count} subjects?\n\n"
            f"{subject_list}\n\n"
            "This action cannot be undone and will permanently delete all files "
            "and data associated with these subjects.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Use main controller to delete multiple subjects
        success_count, failed_subjects = self.main_controller.delete_multiple_subjects(subject_names)
        
        # Show results
        if failed_subjects:
            if success_count > 0:
                QMessageBox.warning(
                    self,
                    "Partial Success",
                    f"Successfully deleted {success_count} subjects.\n\n"
                    f"Failed to delete {len(failed_subjects)} subjects:\n" +
                    "\n".join(f"• {name}" for name in failed_subjects) +
                    "\n\nCheck the log for details."
                )
            else:
                QMessageBox.critical(
                    self,
                    "Delete Failed",
                    f"Failed to delete all {subject_count} subjects.\n"
                    "Check the log for details."
                )
        else:
            QMessageBox.information(
                self,
                "Delete Successful",
                f"All {subject_count} subjects have been deleted successfully."
            )
    
    def refresh_subject_tree(self):
        """Refresh the subject tree view (called by controller after operations)."""
        self.main_controller.refresh_views()
    
    def _setup_stages_ui(self):
        """Initialize the stages UI from main controller configuration."""
        stages = self.main_controller.get_stages_config()
        for stage in stages:
            item = QListWidgetItem(stage["name"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.stages_listWidget.addItem(item)
        
        # Set initial selection in application model through main controller
        stage_names = [stage["name"] for stage in stages]
        self.main_controller.set_selected_stages(stage_names)
    
    def _get_selected_subjects(self):
        """Get list of selected subject names from the tree view."""
        selected_indexes = self.subjectTreeView.selectedIndexes()
        return self.main_controller.get_selected_subject_names_from_tree(selected_indexes)
    
    def _update_stages_selection_from_ui(self):
        """Update the application model with current UI stage selection."""
        selected_stage_names = []
        for i in range(self.stages_listWidget.count()):
            item = self.stages_listWidget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_stage_names.append(item.text())
        
        self.main_controller.update_stage_selection_from_ui(selected_stage_names)
    
    def update_processing_ui(self, is_running: bool, progress: int):
        """Update UI based on processing state changes (called by application model signal)."""
        if is_running:
            # Clear the text browser and reset progress bar when starting
            if progress == 0:
                self.textBrowser.clear()
        
        # Update progress bar
        self.progressBar.setValue(progress)
        
        # Update button states
        self.runAllStages_PushButton.setEnabled(not is_running)
        self.runSelectedStages_pushButton.setEnabled(not is_running)
        
        # Update stop button state
        self.stopProcessing_pushButton.setEnabled(is_running)
    
    def clear_processing_log(self):
        """Clear the processing log (called by processing controller)."""
        self.textBrowser.clear()
    
    def toggle_verbose_mode(self):
        """Toggle verbose logging mode."""
        new_state = self.main_controller.toggle_verbose_mode()
        # The log message in the controller provides feedback, no popup needed
        # This allows for seamless toggling during processes
    
    def show_log_context_menu(self, position):
        """Show context menu for the log area."""
        context_menu = QMenu(self)
        
        # Clear log action
        clear_action = QAction("Clear Log", self)
        clear_action.triggered.connect(self.clear_processing_log)
        context_menu.addAction(clear_action)
        
        context_menu.addSeparator()
        
        # Verbose mode toggle
        verbose_mode = self.main_controller.is_verbose_mode()
        verbose_text = "Disable Verbose Mode" if verbose_mode else "Enable Verbose Mode"
        verbose_action = QAction(verbose_text, self)
        verbose_action.triggered.connect(self.toggle_verbose_mode)
        context_menu.addAction(verbose_action)
        
        # Show menu at cursor position
        context_menu.exec(self.textBrowser.mapToGlobal(position))
    
    def stop_processing(self):
        """Stop the current processing operation."""
        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Stop Processing",
            "Are you sure you want to stop the current processing operation?\n\n"
            "This will interrupt the current operation and may leave some subjects "
            "partially processed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success = self.main_controller.stop_processing()
            if success:
                QMessageBox.information(
                    self,
                    "Processing Stopped",
                    "Processing has been stopped successfully."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Stop Failed",
                    "Failed to stop processing. Check the log for details."
                )
