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

#from ..forms.ImagesViewer_ui import Ui_ImagesViewer
from ciclone.forms.ImagesViewer_ui import Ui_ImagesViewer

class ImagesViewer(QMainWindow, Ui_ImagesViewer):

    def __init__(self, file_path=None):
        super(ImagesViewer, self).__init__()
        self.setupUi(self)

        # Add volume data caching
        self.current_volume_data = None
        self.current_nifti_path = None
        self.current_nifti_img = None

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
            label.setMaximumSize(512, 512)
            label.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Ignored
            )

        # Connect slider signals
        self.Axial_horizontalSlider.valueChanged.connect(lambda: self.update_slice_display('axial'))
        self.Sagittal_horizontalSlider.valueChanged.connect(lambda: self.update_slice_display('sagittal'))
        self.Coronal_horizontalSlider.valueChanged.connect(lambda: self.update_slice_display('coronal'))

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
        """Load NIFTI file and store the data"""
        try:
            self.current_nifti_img = nib.load(nifti_path)
            self.current_volume_data = self.current_nifti_img.get_fdata()
            self.current_nifti_path = nifti_path
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
            aspect_ratio = pixdim[1] / pixdim[0]
        elif orientation == 'sagittal':
            aspect_ratio = pixdim[2] / pixdim[1]
        else:  # coronal
            aspect_ratio = pixdim[2] / pixdim[0]

        # Calculate dimensions that maintain aspect ratio and fit within label
        if width / height >= aspect_ratio:
            # Image is wider than its natural aspect ratio
            scaled_width = label.height()
            scaled_height = int(label.height() / (width / height * 1 / aspect_ratio))
        else:
            # Image is taller than its natural aspect ratio
            scaled_height = label.width()
            scaled_width = int(label.width() * (width / height * aspect_ratio))

        # Ensure dimensions don't exceed label size
        scaled_width = min(scaled_width, label.width())
        scaled_height = min(scaled_height, label.height())

        # Scale the image
        scaled_pixmap = QPixmap.fromImage(q_img).scaled(
            scaled_width, scaled_height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        label.setPixmap(scaled_pixmap)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    file_path = sys.argv[1] if len(sys.argv) > 1 else None
    viewer = ImagesViewer(file_path)
    viewer.show()
    sys.exit(app.exec())