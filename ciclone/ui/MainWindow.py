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
from ciclone.utility import read_config_file
from ciclone.workers.ImageProcessingWorker import ImageProcessingWorker

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

        # Style the image preview labels
        for label in [self.Axial_ImagePreview, self.Sagittal_ImagePreview, self.Coronal_ImagePreview]:
            label.setStyleSheet("""
                QLabel {
                    background-color: black;
                    border: 1px solid #666666;
                    min-width: 256px;
                    min-height: 256px;
                    max-width: 256px;
                    max-height: 256px;
                }
            """)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding
            )

        # Add volume data caching
        self.current_volume_data = None
        self.current_nifti_path = None
        self.current_nifti_img = None
        
        # Connect slider signals
        self.Axial_horizontalSlider.valueChanged.connect(lambda: self.update_slice_display('axial'))
        self.Sagittal_horizontalSlider.valueChanged.connect(lambda: self.update_slice_display('sagittal'))
        self.Coronal_horizontalSlider.valueChanged.connect(lambda: self.update_slice_display('coronal'))

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
        """Handle tree item clicks to display NIFTI files when selected"""
        # Get the file path from the model
        file_path = self.subjectModel.filePath(index)
        if file_path.endswith(('.nii', '.nii.gz')):
            # Only load the file if it's different from the current one
            if file_path != self.current_nifti_path:
                self.load_nifti_file(file_path)
            
            # Update all views with the loaded data
            self.update_slice_display('axial')
            self.update_slice_display('sagittal')
            self.update_slice_display('coronal')
            
            # Update slider ranges
            self.update_slider_ranges()

    def load_nifti_file(self, nifti_path):
        """Load NIFTI file and store the data"""
        try:
            self.current_nifti_img = nib.load(nifti_path)
            self.current_volume_data = self.current_nifti_img.get_fdata()
            self.current_nifti_path = nifti_path
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load NIFTI file: {str(e)}")
            self.current_volume_data = None
            self.current_nifti_path = None
            self.current_nifti_img = None

    def update_slider_ranges(self):
        """Update slider ranges based on current volume dimensions"""
        if self.current_volume_data is not None:
            self.Axial_horizontalSlider.setRange(0, self.current_volume_data.shape[2] - 1)
            self.Sagittal_horizontalSlider.setRange(0, self.current_volume_data.shape[0] - 1)
            self.Coronal_horizontalSlider.setRange(0, self.current_volume_data.shape[1] - 1)
            
            # Set initial positions to middle slices
            self.Axial_horizontalSlider.setValue(self.current_volume_data.shape[2] // 2)
            self.Sagittal_horizontalSlider.setValue(self.current_volume_data.shape[0] // 2)
            self.Coronal_horizontalSlider.setValue(self.current_volume_data.shape[1] // 2)

    def update_slice_display(self, orientation):
        """Update the display for a specific orientation using cached data"""
        if self.current_volume_data is None:
            return

        try:
            # Get the appropriate slice based on orientation and slider value
            if orientation == 'axial':
                slice_index = self.Axial_horizontalSlider.value()
                slice_data = self.current_volume_data[:, :, slice_index]
                label = self.Axial_ImagePreview
            elif orientation == 'sagittal':
                slice_index = self.Sagittal_horizontalSlider.value()
                slice_data = self.current_volume_data[slice_index, :, :]
                label = self.Sagittal_ImagePreview
            elif orientation == 'coronal':
                slice_index = self.Coronal_horizontalSlider.value()
                slice_data = self.current_volume_data[:, slice_index, :]
                label = self.Coronal_ImagePreview
            
            # Apply orientation-specific transformations
            slice_data = np.rot90(slice_data)
            if orientation == 'sagittal':
                slice_data = np.fliplr(slice_data)
            
            # Normalize the data to 0-255 range for display
            slice_data = slice_data.astype(float)
            slice_data = ((slice_data - slice_data.min()) / 
                         (slice_data.max() - slice_data.min()) * 255).astype(np.uint8)
            
            # Create QImage from numpy array
            height, width = slice_data.shape
            bytes_per_line = width
            q_img = QImage(slice_data.tobytes(), width, height, bytes_per_line, 
                          QImage.Format.Format_Grayscale8)
            
            # Get the fixed size of the label
            label_size = label.width()
            
            # Calculate aspect ratio based on voxel dimensions
            pixdim = self.current_nifti_img.header.get_zooms()
            if orientation == 'axial':
                aspect_ratio = pixdim[1] / pixdim[0]
            elif orientation == 'sagittal':
                aspect_ratio = pixdim[2] / pixdim[1]
            else:  # coronal
                aspect_ratio = pixdim[2] / pixdim[0]
            
            # Calculate dimensions that maintain aspect ratio and fit within label
            if width / height > aspect_ratio:
                scaled_width = label_size
                scaled_height = int(label_size / (width / height * 1/aspect_ratio))
            else:
                scaled_height = label_size
                scaled_width = int(label_size * (width / height * aspect_ratio))
            
            # Ensure dimensions don't exceed label size
            scaled_width = min(scaled_width, label_size)
            scaled_height = min(scaled_height, label_size)
            
            # Scale the image
            scaled_pixmap = QPixmap.fromImage(q_img).scaled(
                scaled_width, scaled_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            label.setPixmap(scaled_pixmap)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to update display: {str(e)}")

    def display_nifti_slice(self, nifti_path, label, slice_index=None, orientation='axial'):
        try:
            # Load the NIFTI file
            nifti_img = nib.load(nifti_path)
            volume_data = nifti_img.get_fdata()
            
            # Get voxel dimensions
            pixdim = nifti_img.header.get_zooms()
            
            # Choose the slice based on orientation and apply correct orientation
            if orientation == 'axial':
                if slice_index is None:
                    slice_index = volume_data.shape[2] // 2
                slice_data = volume_data[:, :, slice_index]
                slice_data = np.rot90(slice_data)
                
            elif orientation == 'sagittal':
                if slice_index is None:
                    slice_index = volume_data.shape[0] // 2
                slice_data = volume_data[slice_index, :, :]
                slice_data = np.rot90(slice_data)
                slice_data = np.fliplr(slice_data)
                
            elif orientation == 'coronal':
                if slice_index is None:
                    slice_index = volume_data.shape[1] // 2
                slice_data = volume_data[:, slice_index, :]
                slice_data = np.rot90(slice_data)
            
            # Normalize the data to 0-255 range for display
            slice_data = slice_data.astype(float)
            slice_data = ((slice_data - slice_data.min()) / 
                         (slice_data.max() - slice_data.min()) * 255).astype(np.uint8)
            
            # Create QImage from numpy array
            height, width = slice_data.shape
            bytes_per_line = width
            q_img = QImage(slice_data.tobytes(), width, height, bytes_per_line, 
                          QImage.Format.Format_Grayscale8)
            
            # Get the fixed size of the label (256x256)
            label_size = label.width()  # Should be 256
            
            # Calculate aspect ratio based on voxel dimensions
            if orientation == 'axial':
                aspect_ratio = pixdim[1] / pixdim[0]
            elif orientation == 'sagittal':
                aspect_ratio = pixdim[2] / pixdim[1]
            elif orientation == 'coronal':
                aspect_ratio = pixdim[2] / pixdim[0]
            
            # Calculate dimensions that maintain aspect ratio and fit within label
            if width / height > aspect_ratio:
                # Image is wider than its natural aspect ratio
                scaled_width = label_size
                scaled_height = int(label_size / (width / height * 1/aspect_ratio))
            else:
                # Image is taller than its natural aspect ratio
                scaled_height = label_size
                scaled_width = int(label_size * (width / height * aspect_ratio))
            
            # Ensure dimensions don't exceed label size
            scaled_width = min(scaled_width, label_size)
            scaled_height = min(scaled_height, label_size)
            
            # Scale the image
            scaled_pixmap = QPixmap.fromImage(q_img).scaled(
                scaled_width, scaled_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,  # We're handling the aspect ratio ourselves
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Center the pixmap in the label
            # label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setPixmap(scaled_pixmap)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load NIFTI file: {str(e)}")