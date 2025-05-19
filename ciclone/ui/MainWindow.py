import json
import os
from pathlib import Path
from typing import Dict, Optional
import nibabel as nib
import numpy as np

from PyQt6.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QInputDialog,
    QListWidgetItem,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QStandardPaths

from PyQt6.QtGui import QFileSystemModel, QImage, QPixmap

from ciclone.core.subject_importer import SubjectImporter
from ciclone.core.utility import read_config_file
from ciclone.workers.ImageProcessingWorker import ImageProcessingWorker
from ciclone.ui.ImagesViewer import ImagesViewer

from ..forms.MainWindow_ui import Ui_MainWindow

class MainWindow(QMainWindow, Ui_MainWindow):
    config_path = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "config/config.yaml"))
    __worker = None
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)
        
        # File menu actions
        self.actionNew_Output_Directory.triggered.connect(self.create_output_directory)
        self.actionOpen_Output_Directory.triggered.connect(self.open_output_directory)
        
        # Directory and subject management
        self.lineEdit_outputDirectory.textChanged.connect(self.on_output_directory_changed)
        self.pushButton_addSubject.clicked.connect(self.add_subject)
        
        # Subject tree view
        self.subjectTreeView.clicked.connect(self.on_tree_item_clicked)

        # Browse buttons
        self.browse_Schema.clicked.connect(lambda: self._browse_file("Schema"))
        self.browse_preCT.clicked.connect(lambda: self._browse_file("PreCT"))
        self.browse_preMRI.clicked.connect(lambda: self._browse_file("PreMRI"))
        self.browse_postCT.clicked.connect(lambda: self._browse_file("PostCT"))
        self.browse_postMRI.clicked.connect(lambda: self._browse_file("PostMRI"))

        # Run stages buttons
        self.runAllStages_PushButton.clicked.connect(self.run_all_stages)
        self.runSelectedStages_pushButton.clicked.connect(self.run_selected_stages)

        # Read config file
        self.config = read_config_file(self.config_path)

        # Load config file in the list widget
        stages = self.config["stages"]
        for stage in stages:
            item = QListWidgetItem(stage["name"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.stages_listWidget.addItem(item)

    def create_output_directory(self):
        self.output_directory = QFileDialog.getExistingDirectory(self, "Select Output Directory", QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation))
        if self.output_directory:
            dataset_name = QInputDialog.getText(self, "Folder Name", "Please enter a name")[0]
            if dataset_name == "":
                QMessageBox.warning(self, "Folder Name empty", "Please enter a folder name")
                return
            self.output_directory = os.path.join(self.output_directory, dataset_name)
            os.makedirs(self.output_directory, exist_ok=True)
            self.lineEdit_outputDirectory.setText(self.output_directory)
        
    def open_output_directory(self):
        self.output_directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        self.lineEdit_outputDirectory.setText(self.output_directory)

    def on_output_directory_changed(self):
        # Define file system model for the output directory
        self.subjectModel = QFileSystemModel()
        self.subjectModel.setReadOnly(True)
        self.subjectModel.setRootPath(self.output_directory)

        # Set model and root index in tree view
        self.subjectTreeView.setModel(self.subjectModel)
        self.subjectTreeView.setRootIndex(self.subjectModel.index(self.output_directory))

        # Configure tree view appearance
        self.subjectTreeView.setAnimated(False)
        self.subjectTreeView.setIndentation(20)
        self.subjectTreeView.hideColumn(1)
        self.subjectTreeView.hideColumn(2) 
        self.subjectTreeView.hideColumn(3)
        self.subjectTreeView.header().hide()

    def _browse_file(self, field_type: str):
        """Generic file browser for different fields"""
        file_filters = {
            "Schema": "JPG files (*.jpg);;PNG files (*.png)",
            "PreCT": "DICOM files (*.dcm);;NIFTI files (*.nii *.nii.gz)",
            "PreMRI": "DICOM files (*.dcm);;NIFTI files (*.nii *.nii.gz)", 
            "PostCT": "DICOM files (*.dcm);;NIFTI files (*.nii *.nii.gz)",
            "PostMRI": "DICOM files (*.dcm);;NIFTI files (*.nii *.nii.gz)"
        }
        file_path, _ = QFileDialog.getOpenFileName(self, f"Select {field_type} File", "", file_filters.get(field_type, "All Files (*.*)"))
        if file_path:
            if field_type == "Schema":
                self.lineEdit_Schema.setText(file_path)
            elif field_type == "PreCT":
                self.lineEdit_preCT.setText(file_path)
                if file_path.endswith(('.nii', '.nii.gz')):
                    self.display_nifti_slice(file_path, self.Axial_ImagePreview, orientation='axial')
                    self.display_nifti_slice(file_path, self.Sagittal_ImagePreview, orientation='sagittal')
                    self.display_nifti_slice(file_path, self.Coronal_ImagePreview, orientation='coronal')
            elif field_type == "PreMRI":
                self.lineEdit_preMRI.setText(file_path)
            elif field_type == "PostCT":
                self.lineEdit_postCT.setText(file_path)
            elif field_type == "PostMRI":
                self.lineEdit_postMRI.setText(file_path)

    def add_subject(self):
        """Add a new subject to the current output directory"""
        if not self.output_directory:
            QMessageBox.warning(self, "Error", "Please select an output directory first")
            return
            
        subject_name = self.lineEdit_Name.text().strip()
        if not subject_name:
            QMessageBox.warning(self, "Error", "Please enter a subject name")
            return

        subject_dir = os.path.join(self.output_directory, subject_name)
        if os.path.exists(subject_dir):
            QMessageBox.warning(self, "Error", "Subject already exists")
            return

        subject_data = {
            "name": subject_name,
            "schema": self.lineEdit_Schema.text(),
            "pre_ct": self.lineEdit_preCT.text(),
            "pre_mri": self.lineEdit_preMRI.text(),
            "post_ct": self.lineEdit_postCT.text(),
            "post_mri": self.lineEdit_postMRI.text()
        }
        SubjectImporter.import_subject(self.output_directory, subject_data)
        # Refresh the tree view
        self.subjectTreeView.setRootIndex(self.subjectModel.index(self.output_directory))

    def run_all_stages(self):
        # Check if a process is already running
        if hasattr(self, '__worker') and self.__worker.isRunning():
            print("[run_all_stages] Run all stages is already in progress")
            return

        subject_list = [item.data() for item in self.subjectTreeView.selectedIndexes()]
        if len(subject_list) == 0:
            QMessageBox.warning(self, "Error", "Please select at least one subject")
            return

        # Clear the text browser and reset progress bar
        self.textBrowser.clear()
        self.progressBar.setValue(0)
        
        # Log the start of processing
        self.add_log_message("info", "run_all_stages => Starting processing...")

        # Create worker
        self.__worker = ImageProcessingWorker(self.output_directory, subject_list, self.config["stages"])

        # Connect signals
        self.__worker.update_progress_signal.connect(self.progressBar.setValue)
        self.__worker.log_signal.connect(self.add_log_message)
        self.__worker.finished.connect(self.on_worker_finished)

        # Start the worker thread
        self.__worker.start()

    def run_selected_stages(self):
        # Check if a process is already running
        if hasattr(self, '__worker') and self.__worker.isRunning():
            print("[run_all_stages] Run all stages is already in progress")
            return

        # Get selected subjects from the tree view
        subject_list = [item.data() for item in self.subjectTreeView.selectedIndexes()]
        if len(subject_list) == 0:
            QMessageBox.warning(self, "Error", "Please select at least one subject")
            return

        # Clear the text browser and reset progress bar
        self.textBrowser.clear()
        self.progressBar.setValue(0)
        
        # Log the start of processing
        self.add_log_message("info", "run_selected_stages => Starting processing...")

        # Get stages that are checked in the UI
        selected_stage_names = []
        for i in range(self.stages_listWidget.count()):
            item = self.stages_listWidget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_stage_names.append(item.text())
        
        stages = [stage for stage in self.config["stages"] if stage["name"] in selected_stage_names]
        
        # Create worker
        self.__worker = ImageProcessingWorker(self.output_directory, subject_list, stages)

        # Connect signals
        self.__worker.update_progress_signal.connect(self.progressBar.setValue)
        self.__worker.log_signal.connect(self.add_log_message)
        self.__worker.finished.connect(self.on_worker_finished)

        # Start the worker thread
        self.__worker.start()

    def on_worker_finished(self):
        """Handle cleanup after the worker thread finishes"""
        self.add_log_message("info", "Processing completed")
        self.__worker.deleteLater()

    def add_log_message(self, level: str, message: str):
        """Add a log message to the text browser with appropriate formatting"""
        color_map = {
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
        """Handle tree item clicks to display NIFTI files in ImagesViewer window"""
        file_path = self.subjectModel.filePath(index)
        if file_path.endswith(('.nii', '.nii.gz')):
            if not hasattr(self, 'images_viewer') or self.images_viewer is None:
                self.images_viewer = ImagesViewer(file_path)
            else:
                self.images_viewer.load_nifti_file(file_path)
                self.images_viewer.update_slider_ranges()
                self.images_viewer.update_slice_display('axial')
                self.images_viewer.update_slice_display('sagittal')
                self.images_viewer.update_slice_display('coronal')
            self.images_viewer.show()
            self.images_viewer.raise_()  # Bring window to front
