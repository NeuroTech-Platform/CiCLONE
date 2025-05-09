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
    QSizePolicy,
    QHeaderView,
    QVBoxLayout,
    QTableWidgetItem
)
from PyQt6.QtCore import Qt, QStandardPaths

from PyQt6.QtGui import QFileSystemModel, QImage, QPixmap

from ciclone.core.subject_importer import SubjectImporter
from ciclone.ui.Viewer3D import Viewer3D
from ciclone.utility import read_config_file
from ciclone.workers.ImageProcessingWorker import ImageProcessingWorker
from ciclone.utils.electrodes import Electrode

#from ..forms.ImagesViewer_ui import Ui_ImagesViewer
from ciclone.forms.ImagesViewer_ui import Ui_ImagesViewer

class ImagesViewer(QMainWindow, Ui_ImagesViewer):

    def __init__(self, file_path=None):
        super(ImagesViewer, self).__init__()
        self.setupUi(self)

        # Initialize the electrodes list
        self.ElectrodesList = []

        # Initialize coordinate setting state
        self.setting_entry = False
        self.setting_output = False

        # Connect the table's itemChanged signal to update the combo box
        self.ElectrodeTableWidget.itemChanged.connect(self.update_electrodes_combo)

        # Set the initial size of the groupbox to 25% of the total width
        total_width = self.splitter.width()
        self.splitter.setSizes([int(total_width * 0.25), int(total_width * 0.75)])
        # Prevent splitter from resetting on double click
        self.splitter.setChildrenCollapsible(False)
        
        # Make splitter update views when moved
        self.splitter.splitterMoved.connect(self.update_all_views)

        # Load electrodes def files
        self.electrodes_def_files = {}
        for file in os.listdir("ciclone/config/electrodes"):
            if file.endswith(".elecdef"):
                name = file.replace(".elecdef", "")
                full_path = os.path.join("ciclone/config/electrodes", file)
                self.electrodes_def_files[name] = full_path
                self.ElectrodeTypeComboBox.addItem(name)

        # Configure column resize behavior
        self.ElectrodeTableWidget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.ElectrodeTableWidget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        # Configure buttons
        self.SetEntryPushButton.clicked.connect(self.set_entry_button_clicked)
        self.SetOutputPushButton.clicked.connect(self.set_output_button_clicked)
        
        # Disable buttons initially since there are no electrodes
        self.SetEntryPushButton.setEnabled(False)
        self.SetOutputPushButton.setEnabled(False)

        # Configure column resize behavior
        self.ElectrodesTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.ElectrodesTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.ElectrodesTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.ElectrodesTable.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        # Set fixed width for the first column
        self.ElectrodesTable.setColumnWidth(0, 100)
        
        # Add volume data caching
        self.current_volume_data = None
        self.current_nifti_path = None
        self.current_nifti_img = None
        self.affine = None

        # Style the image preview labels
        for label in [self.Axial_ImagePreview, self.Sagittal_ImagePreview, self.Coronal_ImagePreview]:
            label.setStyleSheet("""
                QLabel {
                    background-color: black;
                    border: 1px solid #666666;
                }
            """)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setMinimumSize(256, 256)
            label.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding
            )

        # Connect slider signals
        self.Axial_horizontalSlider.valueChanged.connect(lambda: self.update_slice_display('axial'))
        self.Sagittal_horizontalSlider.valueChanged.connect(lambda: self.update_slice_display('sagittal'))
        self.Coronal_horizontalSlider.valueChanged.connect(lambda: self.update_slice_display('coronal'))

        # Connect clickable image labels to on_image_clicked
        self.Axial_ImagePreview.clicked.connect(lambda x, y: self.on_image_clicked('axial', x, y))
        self.Sagittal_ImagePreview.clicked.connect(lambda x, y: self.on_image_clicked('sagittal', x, y))
        self.Coronal_ImagePreview.clicked.connect(lambda x, y: self.on_image_clicked('coronal', x, y))

        # If a file path is provided, load it
        if file_path is not None:
            self.load_nifti_file(file_path)
            self.update_slider_ranges()
            self.update_slice_display('axial')
            self.update_slice_display('sagittal')
            self.update_slice_display('coronal')
        else:
            # Show a default display (e.g., clear labels or show a message)
            self.show_default_display()

        self.AddElectrodePushButton.clicked.connect(self.add_electrode_button_clicked)
        self.Viewer3dButton.clicked.connect(self.viewer3d_button_clicked)

    def viewer3d_button_clicked(self):
        print("Viewer3D button clicked")
        self.viewer3d = Viewer3D(nifti_img=self.current_nifti_img, current_volume_data=self.current_volume_data)
        self.viewer3d.show()

    def show_default_display(self):
        """Show a default message or blank image in the labels."""
        for label in [self.Axial_ImagePreview, self.Sagittal_ImagePreview, self.Coronal_ImagePreview]:
            label.clear()
            label.setText("No image loaded")
        # Optionally, disable sliders
        self.Axial_horizontalSlider.setEnabled(False)
        self.Sagittal_horizontalSlider.setEnabled(False)
        self.Coronal_horizontalSlider.setEnabled(False)

    def load_nifti_file(self, nifti_path):
        """Load NIFTI file and store the data (no reorientation)"""
        try:
            self.current_nifti_img = nib.load(nifti_path)
            self.current_volume_data = self.current_nifti_img.get_fdata()
            self.current_nifti_path = nifti_path
            self.affine = self.current_nifti_img.affine
            # Enable sliders
            self.Axial_horizontalSlider.setEnabled(True)
            self.Sagittal_horizontalSlider.setEnabled(True)
            self.Coronal_horizontalSlider.setEnabled(True)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load NIFTI file: {str(e)}")
            self.current_volume_data = None
            self.current_nifti_path = None
            self.current_nifti_img = None
            self.show_default_display()

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
        if self.current_volume_data is None:
            return

        try:
            # Get the appropriate slice and label
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

            self.display_slice_on_label(slice_data, label, orientation, self.current_nifti_img)

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to update display: {str(e)}")

    def display_nifti_slice(self, nifti_path, label, slice_index=None, orientation='axial'):
        try:
            nifti_img = nib.load(nifti_path)
            volume_data = nifti_img.get_fdata()
            if orientation == 'axial':
                if slice_index is None:
                    slice_index = volume_data.shape[2] // 2
                slice_data = volume_data[:, :, slice_index]
            elif orientation == 'sagittal':
                if slice_index is None:
                    slice_index = volume_data.shape[0] // 2
                slice_data = volume_data[slice_index, :, :]
            elif orientation == 'coronal':
                if slice_index is None:
                    slice_index = volume_data.shape[1] // 2
                slice_data = volume_data[:, slice_index, :]
            self.display_slice_on_label(slice_data, label, orientation, nifti_img)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load NIFTI file: {str(e)}")

    def display_slice_on_label(self, slice_data, label, orientation, nifti_img):
        # Apply orientation-specific transformations
        slice_data = np.rot90(slice_data)
        if orientation == 'sagittal':
            slice_data = np.fliplr(slice_data)
        # Normalize to 0-255 for display
        slice_data = slice_data.astype(float)
        slice_data = ((slice_data - slice_data.min()) /
                      (slice_data.max() - slice_data.min()) * 255).astype(np.uint8)
        # Create QImage
        height, width = slice_data.shape
        bytes_per_line = width
        q_img = QImage(slice_data.tobytes(), width, height, bytes_per_line, QImage.Format.Format_Grayscale8)
        
        # Calculate aspect ratio based on voxel dimensions
        pixdim = nifti_img.header.get_zooms()
        if orientation == 'axial':
            aspect_ratio = pixdim[1] / pixdim[0]  # y/x
        elif orientation == 'sagittal':
            aspect_ratio = 1 / (pixdim[2] / pixdim[1])  # z/y
        else:  # coronal
            aspect_ratio = 1 / (pixdim[2] / pixdim[0])  # z/x
            
        # Get the label dimensions
        label_width = label.width()
        label_height = label.height()
        
        # Calculate dimensions to fill the label while maintaining the correct aspect ratio
        image_aspect = width / height
        corrected_aspect = image_aspect * aspect_ratio
        
        if corrected_aspect >= label_width / label_height:
            # Width limited by label width
            scaled_width = label_width
            scaled_height = int(scaled_width / corrected_aspect)
        else:
            # Height limited by label height
            scaled_height = label_height
            scaled_width = int(scaled_height * corrected_aspect)
            
        # Scale the image
        scaled_pixmap = QPixmap.fromImage(q_img).scaled(
            scaled_width, scaled_height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        label.setPixmap(scaled_pixmap)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def resizeEvent(self, event):
        """
        Handle window resize events to update the display.
        """
        super().resizeEvent(event)
        # Update all views when window is resized
        self.update_all_views()
        
    def update_all_views(self):
        """
        Update all three views if data is loaded.
        """
        if self.current_volume_data is not None:
            self.update_slice_display('axial')
            self.update_slice_display('sagittal')
            self.update_slice_display('coronal')

    def on_image_clicked(self, orientation, x, y):
        """
        Handle clicks on any view by determining the 3D coordinates and updating other views.
        If in coordinate setting mode, also update the corresponding coordinate field.
        """
        if self.current_volume_data is None:
            return
        
        # Get the dimensions of the label and current slice
        label = getattr(self, f"{orientation.capitalize()}_ImagePreview")
        pixmap = label.pixmap()
        if pixmap is None:
            return
        
        # Calculate scale factors to convert from label coordinates to image coordinates
        label_width, label_height = label.width(), label.height()
        pixmap_width, pixmap_height = pixmap.width(), pixmap.height()
        
        # Adjust for the image being centered in the label
        offset_x = (label_width - pixmap_width) // 2
        offset_y = (label_height - pixmap_height) // 2
        
        # Convert from label coordinates to image coordinates
        # Check if the click is outside the image area
        if x < offset_x or y < offset_y or x >= offset_x + pixmap_width or y >= offset_y + pixmap_height:
            return
        
        image_x = x - offset_x
        image_y = y - offset_y
        
        # Get the current slice indices
        axial_slice = self.Axial_horizontalSlider.value()
        sagittal_slice = self.Sagittal_horizontalSlider.value()
        coronal_slice = self.Coronal_horizontalSlider.value()
        
        # Calculate 3D coordinates based on the view that was clicked
        # Note: Medical imaging convention uses bottom-left origin, while display uses top-left
        if orientation == 'axial':
            # In axial view, we display [x, y, slice_index]
            x_coord = int(image_x * (self.current_volume_data.shape[0] / pixmap_width))
            y_coord = self.current_volume_data.shape[1] - 1 - int(image_y * (self.current_volume_data.shape[1] / pixmap_height))
            z_coord = axial_slice
            # Update sagittal and coronal views to show the clicked point
            self.Sagittal_horizontalSlider.setValue(x_coord)
            self.Coronal_horizontalSlider.setValue(y_coord)
        elif orientation == 'sagittal':
            # In sagittal view, we display [slice_index, y, z]
            x_coord = sagittal_slice
            y_coord = self.current_volume_data.shape[1] - 1 - int(image_x * (self.current_volume_data.shape[1] / pixmap_width))
            z_coord = self.current_volume_data.shape[2] - 1 - int(image_y * (self.current_volume_data.shape[2] / pixmap_height))
            # Update axial and coronal views to show the clicked point
            self.Axial_horizontalSlider.setValue(z_coord)
            self.Coronal_horizontalSlider.setValue(y_coord)
        else:  # coronal
            # In coronal view, we display [x, slice_index, z]
            x_coord = int(image_x * (self.current_volume_data.shape[0] / pixmap_width))
            y_coord = coronal_slice
            z_coord = self.current_volume_data.shape[2] - 1 - int(image_y * (self.current_volume_data.shape[2] / pixmap_height))
            # Update axial and sagittal views to show the clicked point
            self.Axial_horizontalSlider.setValue(z_coord)
            self.Sagittal_horizontalSlider.setValue(x_coord)
        
        # Update the coordinate fields if in setting mode
        if self.setting_entry:
            self.EntryCoordinatesLabel.setText(f"Entry Coordinates : ({x_coord}, {y_coord}, {z_coord})")
        elif self.setting_output:
            self.OutputCoordinatesLabel.setText(f"Output Coordinates : ({x_coord}, {y_coord}, {z_coord})")

    def set_entry_button_clicked(self):
        """Toggle entry point setting mode"""
        self.setting_entry = not self.setting_entry
        if self.setting_entry:
            self.setting_output = False
            self.SetEntryPushButton.setStyleSheet("color: red;")
            self.SetOutputPushButton.setStyleSheet("")
            self.SetOutputPushButton.setEnabled(False)
        else:
            self.SetEntryPushButton.setStyleSheet("")
            # Only enable if there are electrodes in the combo box
            has_electrodes = self.ElectrodesComboBox.count() > 0
            self.SetOutputPushButton.setEnabled(has_electrodes)

    def set_output_button_clicked(self):
        """Toggle output point setting mode"""
        self.setting_output = not self.setting_output
        if self.setting_output:
            self.setting_entry = False
            self.SetOutputPushButton.setStyleSheet("color: red;")
            self.SetEntryPushButton.setStyleSheet("")
            self.SetEntryPushButton.setEnabled(False)
        else:
            self.SetOutputPushButton.setStyleSheet("")
            # Only enable if there are electrodes in the combo box
            has_electrodes = self.ElectrodesComboBox.count() > 0
            self.SetEntryPushButton.setEnabled(has_electrodes)

    def add_electrode_button_clicked(self):
        electrode_type = self.ElectrodeTypeComboBox.currentText()
        
        # Get electrode name from the UI
        electrode_name = self.ElectrodeNameLineEdit.text()
        if not electrode_name:
            QMessageBox.critical(self, "Input Error", "Please enter an electrode name.")
            return
        
        # Check that there is not an electrode with the same name
        if any(electrode.name == electrode_name for electrode in self.ElectrodesList):
            QMessageBox.critical(self, "Input Error", "An electrode with this name already exists.")
            return
        
        # Create electrode with name and type and add to list
        electrode = Electrode(name=electrode_name, electrode_type=electrode_type)
        self.ElectrodesList.append(electrode)

        # Add the electrode to the table
        row_position = self.ElectrodeTableWidget.rowCount()
        self.ElectrodeTableWidget.insertRow(row_position)

        # Create and add table items with center alignment
        items = [
            (electrode.name, 0),
            (electrode.electrode_type, 1)
        ]
        
        for text, col in items:
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.ElectrodeTableWidget.setItem(row_position, col, item)

    def update_electrodes_combo(self):
        """Update the ElectrodesComboBox with current electrode names"""
        self.ElectrodesComboBox.clear()
        for row in range(self.ElectrodeTableWidget.rowCount()):
            name_item = self.ElectrodeTableWidget.item(row, 0)  # Get name from first column
            if name_item:
                self.ElectrodesComboBox.addItem(name_item.text())
        
        # Enable buttons if there is at least one electrode
        has_electrodes = self.ElectrodesComboBox.count() > 0
        self.SetEntryPushButton.setEnabled(has_electrodes)
        self.SetOutputPushButton.setEnabled(has_electrodes)

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    file_path = sys.argv[1] if len(sys.argv) > 1 else None
    viewer = ImagesViewer(file_path)
    viewer.show()
    sys.exit(app.exec())