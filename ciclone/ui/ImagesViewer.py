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
    QVBoxLayout
)
from PyQt6.QtCore import Qt, QStandardPaths

from PyQt6.QtGui import QFileSystemModel, QImage, QPixmap

from ciclone.core.subject_importer import SubjectImporter
from ciclone.ui.Viewer3D import Viewer3D
from ciclone.utility import read_config_file
from ciclone.workers.ImageProcessingWorker import ImageProcessingWorker

#from ..forms.ImagesViewer_ui import Ui_ImagesViewer
from ciclone.forms.ImagesViewer_ui import Ui_ImagesViewer

class ImagesViewer(QMainWindow, Ui_ImagesViewer):

    def __init__(self, file_path=None):
        super(ImagesViewer, self).__init__()
        self.setupUi(self)

        # Set the initial size of the groupbox to 25% of the total width
        total_width = self.splitter.width()
        self.splitter.setSizes([int(total_width * 0.25), int(total_width * 0.75)])
        # Prevent splitter from resetting on double click
        self.splitter.setChildrenCollapsible(False)

        # Configure column resize behavior
        self.electrodesTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.electrodesTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.electrodesTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.electrodesTable.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        # Set fixed width for the first column
        self.electrodesTable.setColumnWidth(0, 100)
        
        # Add volume data caching
        self.current_volume_data = None
        self.current_nifti_path = None
        self.current_nifti_img = None
        self.affine = None

        # Style the image preview labels
        for label in [self.Axial_ImagePreview, self.Sagittal_ImagePreview, self.Coronal_ImagePreview]:
            label.setStyleSheet("""
                QLabel {
                    background-color: red;
                    border: 1px solid #666666;
                }
            """)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setMinimumSize(256, 256)
            label.setMaximumSize(512, 512)
            label.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Ignored
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

    def on_image_clicked(self, orientation, x, y):
        """
        Handle clicks on any view by determining the 3D coordinates and updating other views.

        Args:
            orientation: The orientation of the view that was clicked ('axial', 'sagittal', 'coronal')
            x: The x-coordinate of the click in the label's coordinate system
            y: The y-coordinate of the click in the label's coordinate system
        Note:
            This function handles coordinate transformations between display space and volume
            data space, accounting for different orientations and scaling factors.
            
            Coordinate system differences:
            - Medical imaging convention: Bottom-left origin coordinate system
            - Display convention: Top-left origin coordinate system
            
            Axis flipping requirements by view:
            - Axial view: Y-coordinate needs to be flipped
            - Sagittal view: Both Y and Z coordinates need to be flipped
            - Coronal view: Z-coordinate needs to be flipped
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
        
        # Convert clicked position (image_x, image_y) to volume coordinates
        # Medical imaging convention: origin at bottom-left corner
        # Display convention: origin at top-left corner
        # We need to scale the coordinates and flip the y/z axes as appropriate
        if orientation == 'axial':
            # In axial view, we display [x, y, slice_index]
            scaled_x = int(image_x * (self.current_volume_data.shape[0] / pixmap_width))
            scaled_y = int(image_y * (self.current_volume_data.shape[1] / pixmap_height))
            
            scaled_y = self.current_volume_data.shape[1] - 1 - scaled_y
                        
            # Update sagittal and coronal views
            self.Sagittal_horizontalSlider.setValue(scaled_x)
            self.Coronal_horizontalSlider.setValue(scaled_y)
            
        elif orientation == 'sagittal':
            # In sagittal view, we display [slice_index, y, z]
            scaled_y = int(image_x * (self.current_volume_data.shape[1] / pixmap_width))
            scaled_z = int(image_y * (self.current_volume_data.shape[2] / pixmap_height))
            
            scaled_y = self.current_volume_data.shape[1] - 1 - scaled_y
            scaled_z = self.current_volume_data.shape[2] - 1 - scaled_z
                        
            # Update axial and coronal views
            self.Axial_horizontalSlider.setValue(scaled_z)
            self.Coronal_horizontalSlider.setValue(scaled_y)
            
        elif orientation == 'coronal':
            # In coronal view, we display [x, slice_index, z]
            scaled_x = int(image_x * (self.current_volume_data.shape[0] / pixmap_width))
            scaled_z = int(image_y * (self.current_volume_data.shape[2] / pixmap_height))
            
            scaled_z = self.current_volume_data.shape[2] - 1 - scaled_z
            
            # Update axial and sagittal views
            self.Axial_horizontalSlider.setValue(scaled_z)
            self.Sagittal_horizontalSlider.setValue(scaled_x)


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    file_path = sys.argv[1] if len(sys.argv) > 1 else None
    viewer = ImagesViewer(file_path)
    viewer.show()
    sys.exit(app.exec())