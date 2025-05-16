import json
import os
import pickle
import uuid
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import nibabel as nib
import numpy as np
import datetime

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

from PyQt6.QtGui import QFileSystemModel, QImage, QPixmap, QPainter, QColor, QBrush

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
        
        # Initialize coordinate storage for visualization
        # Dictionary to store entry and output points for each electrode
        self.electrode_points = {}  # Format: {electrode_name: {'entry': (x,y,z), 'output': (x,y,z)}}
        self.current_electrode_name = None
        
        # Dictionary to store processed contact points for each electrode
        self.processed_contacts = {}

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
        
        # Connect the ProcessCoordinatesPushButton
        self.ProcessCoordinatesPushButton.clicked.connect(self.process_coordinates_button_clicked)
        
        # Connect the ExportCoordinatesPushButton
        #self.ExportCoordinatesPushButton.clicked.connect(self.export_coordinates_button_clicked)
        
        # Connect the SaveFilePushButton to save in 3D Slicer format
        self.SaveFilePushButton.clicked.connect(self.save_file_button_clicked)

        # Connect the ElectrodesComboBox to update the table when selection changes
        self.ElectrodesComboBox.currentTextChanged.connect(self.on_electrode_selection_changed)

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
        
        # Create a painter to draw on the pixmap
        painter = QPainter(scaled_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get current slice indices
        axial_slice = self.Axial_horizontalSlider.value()
        sagittal_slice = self.Sagittal_horizontalSlider.value()
        coronal_slice = self.Coronal_horizontalSlider.value()
        
        # Draw entry and output points for all electrodes
        for electrode_name, points in self.electrode_points.items():
            # Generate a color based on the electrode name hash
            hue = abs(hash(electrode_name)) % 360
            electrode_color = QColor()
            electrode_color.setHsv(hue, 200, 255, 180)  # Hue, Saturation, Value, Alpha
            
            # Draw entry point if it exists
            if 'entry' in points and points['entry']:
                self.draw_point_if_visible(painter, points['entry'], orientation, 
                                          axial_slice, sagittal_slice, coronal_slice, 
                                          width, height, scaled_width, scaled_height, electrode_color)
            
            # Draw output point if it exists
            if 'output' in points and points['output']:
                self.draw_point_if_visible(painter, points['output'], orientation, 
                                          axial_slice, sagittal_slice, coronal_slice, 
                                          width, height, scaled_width, scaled_height, electrode_color)
        
        # Draw all processed electrode contacts
        for electrode_name, contacts in self.processed_contacts.items():
            # Use a different color for each electrode
            # Generate a color based on the electrode name hash
            hue = abs(hash(electrode_name)) % 360
            contact_color = QColor()
            contact_color.setHsv(hue, 200, 255, 180)  # Hue, Saturation, Value, Alpha
            
            for i, contact_point in enumerate(contacts):
                self.draw_point_if_visible(painter, contact_point, orientation, 
                                          axial_slice, sagittal_slice, coronal_slice, 
                                          width, height, scaled_width, scaled_height, 
                                          contact_color)
        
        painter.end()
        
        label.setPixmap(scaled_pixmap)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    
    def draw_point_if_visible(self, painter, point, orientation, axial_slice, sagittal_slice, 
                             coronal_slice, orig_width, orig_height, scaled_width, scaled_height, color):
        """Draw a point on the current slice if it's visible in this orientation and slice"""
        x, y, z = point
        
        # Check if the point is on the current slice for this orientation
        is_visible = False
        pixel_x, pixel_y = 0, 0
        
        if orientation == 'axial' and abs(z - axial_slice) <= 1:
            # For axial view, x and y are the coordinates on the slice
            is_visible = True
            pixel_x = int(x * scaled_width / self.current_volume_data.shape[0])
            pixel_y = int((self.current_volume_data.shape[1] - 1 - y) * scaled_height / self.current_volume_data.shape[1])
            
        elif orientation == 'sagittal' and abs(x - sagittal_slice) <= 1:
            # For sagittal view, y and z are the coordinates on the slice
            is_visible = True
            pixel_x = int((self.current_volume_data.shape[1] - 1 - y) * scaled_width / self.current_volume_data.shape[1])
            pixel_y = int((self.current_volume_data.shape[2] - 1 - z) * scaled_height / self.current_volume_data.shape[2])
            
        elif orientation == 'coronal' and abs(y - coronal_slice) <= 1:
            # For coronal view, x and z are the coordinates on the slice
            is_visible = True
            pixel_x = int(x * scaled_width / self.current_volume_data.shape[0])
            pixel_y = int((self.current_volume_data.shape[2] - 1 - z) * scaled_height / self.current_volume_data.shape[2])
        
        # Draw the point if it's visible
        if is_visible:
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)  # No outline, just filled circle
            circle_radius = 5  # Size of the circle in pixels
            painter.drawEllipse(pixel_x - circle_radius, pixel_y - circle_radius, 
                               circle_radius * 2, circle_radius * 2)

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
            
            # Get the current electrode name
            electrode_name = self.ElectrodesComboBox.currentText()
            if electrode_name:
                # Initialize the electrode points dictionary entry if needed
                if electrode_name not in self.electrode_points:
                    self.electrode_points[electrode_name] = {}
                
                # Store the entry point for this electrode
                self.electrode_points[electrode_name]['entry'] = (x_coord, y_coord, z_coord)
                self.current_electrode_name = electrode_name
                
                # Update the display to show the marker
                self.update_all_views()
        elif self.setting_output:
            self.OutputCoordinatesLabel.setText(f"Output Coordinates : ({x_coord}, {y_coord}, {z_coord})")
            
            # Get the current electrode name
            electrode_name = self.ElectrodesComboBox.currentText()
            if electrode_name:
                # Initialize the electrode points dictionary entry if needed
                if electrode_name not in self.electrode_points:
                    self.electrode_points[electrode_name] = {}
                
                # Store the output point for this electrode
                self.electrode_points[electrode_name]['output'] = (x_coord, y_coord, z_coord)
                self.current_electrode_name = electrode_name
                
                # Update the display to show the marker
                self.update_all_views()

    def set_entry_button_clicked(self):
        """Toggle entry point setting mode"""
        # Check if an electrode is selected
        electrode_name = self.ElectrodesComboBox.currentText()
        if not electrode_name:
            QMessageBox.warning(self, "Warning", "Please select an electrode first.")
            return
        
        self.setting_entry = not self.setting_entry
        if self.setting_entry:
            self.setting_output = False
            self.SetEntryPushButton.setStyleSheet("color: red;")
            self.SetOutputPushButton.setStyleSheet("")
            self.SetOutputPushButton.setEnabled(False)
            self.current_electrode_name = electrode_name
            
            # Display current entry point if it exists
            if electrode_name in self.electrode_points and 'entry' in self.electrode_points[electrode_name]:
                entry = self.electrode_points[electrode_name]['entry']
                self.EntryCoordinatesLabel.setText(f"Entry Coordinates : ({entry[0]}, {entry[1]}, {entry[2]})")
            else:
                self.EntryCoordinatesLabel.setText("Entry Coordinates : ")
        else:
            self.SetEntryPushButton.setStyleSheet("")
            # Only enable if there are electrodes in the combo box
            has_electrodes = self.ElectrodesComboBox.count() > 0
            self.SetOutputPushButton.setEnabled(has_electrodes)

    def set_output_button_clicked(self):
        """Toggle output point setting mode"""
        # Check if an electrode is selected
        electrode_name = self.ElectrodesComboBox.currentText()
        if not electrode_name:
            QMessageBox.warning(self, "Warning", "Please select an electrode first.")
            return
        
        self.setting_output = not self.setting_output
        if self.setting_output:
            self.setting_entry = False
            self.SetOutputPushButton.setStyleSheet("color: red;")
            self.SetEntryPushButton.setStyleSheet("")
            self.SetEntryPushButton.setEnabled(False)
            self.current_electrode_name = electrode_name
            
            # Display current output point if it exists
            if electrode_name in self.electrode_points and 'output' in self.electrode_points[electrode_name]:
                output = self.electrode_points[electrode_name]['output']
                self.OutputCoordinatesLabel.setText(f"Output Coordinates : ({output[0]}, {output[1]}, {output[2]})")
            else:
                self.OutputCoordinatesLabel.setText("Output Coordinates : ")
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
        current_text = self.ElectrodesComboBox.currentText()
        self.ElectrodesComboBox.blockSignals(True)  # Block signals to prevent triggering selection change
        self.ElectrodesComboBox.clear()
        for row in range(self.ElectrodeTableWidget.rowCount()):
            name_item = self.ElectrodeTableWidget.item(row, 0)  # Get name from first column
            if name_item:
                self.ElectrodesComboBox.addItem(name_item.text())
        
        # Try to restore the previous selection
        index = self.ElectrodesComboBox.findText(current_text)
        if index >= 0:
            self.ElectrodesComboBox.setCurrentIndex(index)
        
        self.ElectrodesComboBox.blockSignals(False)  # Unblock signals
        
        # Enable buttons if there is at least one electrode
        has_electrodes = self.ElectrodesComboBox.count() > 0
        self.SetEntryPushButton.setEnabled(has_electrodes)
        self.SetOutputPushButton.setEnabled(has_electrodes)
        
        # Update the entry/output labels for the selected electrode
        self.update_coordinate_labels()
        
        # Update the contacts table for the selected electrode
        electrode_name = self.ElectrodesComboBox.currentText()
        if electrode_name:
            electrode = next((e for e in self.ElectrodesList if e.name == electrode_name), None)
            if electrode and electrode.contacts:
                self.update_contacts_table(electrode)

    def update_coordinate_labels(self):
        """Update the coordinate labels based on the selected electrode"""
        electrode_name = self.ElectrodesComboBox.currentText()
        if electrode_name and electrode_name in self.electrode_points:
            if 'entry' in self.electrode_points[electrode_name]:
                entry = self.electrode_points[electrode_name]['entry']
                self.EntryCoordinatesLabel.setText(f"Entry Coordinates : ({entry[0]}, {entry[1]}, {entry[2]})")
            else:
                self.EntryCoordinatesLabel.setText("Entry Coordinates : ")
                
            if 'output' in self.electrode_points[electrode_name]:
                output = self.electrode_points[electrode_name]['output']
                self.OutputCoordinatesLabel.setText(f"Output Coordinates : ({output[0]}, {output[1]}, {output[2]})")
            else:
                self.OutputCoordinatesLabel.setText("Output Coordinates : ")
        else:
            self.EntryCoordinatesLabel.setText("Entry Coordinates : ")
            self.OutputCoordinatesLabel.setText("Output Coordinates : ")
    
    def process_coordinates_button_clicked(self):
        """Process coordinates for the selected electrode"""
        # Get the selected electrode from the combo box
        electrode_name = self.ElectrodesComboBox.currentText()
        if not electrode_name:
            QMessageBox.warning(self, "Warning", "Please select an electrode first.")
            return
        
        # Find the electrode in the list
        electrode = next((e for e in self.ElectrodesList if e.name == electrode_name), None)
        if not electrode:
            QMessageBox.warning(self, "Warning", "Selected electrode not found.")
            return
        
        # Check if entry and output points are set for this electrode
        if (electrode_name not in self.electrode_points or 
            'entry' not in self.electrode_points[electrode_name] or 
            'output' not in self.electrode_points[electrode_name]):
            QMessageBox.warning(self, "Warning", f"Please set both entry and output points for electrode {electrode_name}.")
            return
        
        entry_point = self.electrode_points[electrode_name]['entry']
        output_point = self.electrode_points[electrode_name]['output']
        
        try:
            # Load the electrode definition file
            elec_def_path = self.electrodes_def_files.get(electrode.electrode_type)
            if not elec_def_path or not os.path.exists(elec_def_path):
                QMessageBox.warning(self, "Warning", f"Electrode definition file for {electrode.electrode_type} not found.")
                return
            
            # Load electrode definition (pickled dictionary)
            with open(elec_def_path, 'rb') as f:
                elec_def = pickle.load(f)
            
            # Extract plot positions from the electrode definition
            plot_positions = []
            for key, value in elec_def.items():
                if key.startswith('Plot'):
                    position = value.get('position', [0, 0, 0])
                    plot_positions.append((key, position))
            
            # Sort plots by z-position (assuming they're aligned along the z-axis)
            plot_positions.sort(key=lambda x: x[1][2])
            
            # Calculate the direction vector from entry to output
            entry_point_np = np.array(entry_point)
            output_point_np = np.array(output_point)
            direction = output_point_np - entry_point_np
            direction_norm = np.linalg.norm(direction)
            
            if direction_norm == 0:
                QMessageBox.warning(self, "Warning", "Entry and output points are the same.")
                return
            
            direction = direction / direction_norm
            
            # Calculate the contact positions based on the electrode definition
            # and the entry/output points
            contacts = []
            
            # Get the z-span of the electrode in the definition file
            if plot_positions:
                min_z = min(pos[1][2] for pos in plot_positions)
                max_z = max(pos[1][2] for pos in plot_positions)
                z_span = max_z - min_z
                
                # If z_span is zero, we can't calculate relative positions
                if z_span == 0:
                    QMessageBox.warning(self, "Warning", "Invalid electrode definition: all contacts have the same z-coordinate.")
                    return
                
                # Calculate the distance between entry and output
                entry_output_distance = np.linalg.norm(output_point_np - entry_point_np)
                
                # Calculate the contact positions
                for plot_name, plot_pos in plot_positions:
                    # Calculate the relative position of this contact along the electrode
                    relative_pos = (plot_pos[2] - min_z) / z_span
                    
                    # Calculate the position of this contact in the image space
                    contact_pos = entry_point_np + relative_pos * direction * entry_output_distance
                    
                    # Add to contacts list
                    contacts.append(tuple(np.round(contact_pos).astype(int)))
                
                # Store the contacts for this electrode
                self.processed_contacts[electrode_name] = contacts
                
                # Update the electrode object
                electrode.contacts.clear()
                for i, contact_pos in enumerate(contacts):
                    label = f"{electrode_name}{i+1}"
                    electrode.add_contact(label, contact_pos[0], contact_pos[1], contact_pos[2])
                
                # Update the display
                self.update_all_views()
                
                # Update the contacts table
                self.update_contacts_table(electrode)
                
                QMessageBox.information(self, "Success", f"Processed {len(contacts)} contacts for electrode {electrode_name}.")
            else:
                QMessageBox.warning(self, "Warning", f"No plot positions found in electrode definition for {electrode.electrode_type}.")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process coordinates: {str(e)}")
    
    def update_contacts_table(self, electrode):
        """Update the ElectrodesTable with contact information for the given electrode"""
        # Clear the table
        self.ElectrodesTable.setRowCount(0)
        
        # Add each contact to the table
        for i, contact in enumerate(electrode.contacts):
            row_position = self.ElectrodesTable.rowCount()
            self.ElectrodesTable.insertRow(row_position)
            
            # Create and add table items with center alignment
            items = [
                (contact.label, 0),
                (str(int(contact.x)), 1),
                (str(int(contact.y)), 2),
                (str(int(contact.z)), 3)
            ]
            
            for text, col in items:
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.ElectrodesTable.setItem(row_position, col, item)

    def on_electrode_selection_changed(self, electrode_name):
        """Handle electrode selection change in the dropdown"""
        # Update coordinate labels
        self.update_coordinate_labels()
        
        # Update the contacts table for the selected electrode
        if electrode_name:
            electrode = next((e for e in self.ElectrodesList if e.name == electrode_name), None)
            if electrode and electrode.contacts:
                self.update_contacts_table(electrode)
            else:
                # Clear the table if no contacts for this electrode
                self.ElectrodesTable.setRowCount(0)

    def export_coordinates_button_clicked(self):
        """Export all electrode coordinates to a JSON file"""
        if not self.ElectrodesList:
            QMessageBox.warning(self, "Warning", "No electrodes to export.")
            return
        
        # Check if we have processed contacts
        if not any(electrode.contacts for electrode in self.ElectrodesList):
            QMessageBox.warning(self, "Warning", "No processed electrode contacts to export.")
            return
        
        # Ask for the output file
        default_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Electrode Coordinates", default_dir, "JSON Files (*.json)"
        )
        
        if not file_path:
            return  # User cancelled
        
        try:
            # Create a dictionary with all electrode data
            electrodes_data = {}
            
            for electrode in self.ElectrodesList:
                if not electrode.contacts:
                    continue
                
                contacts_data = []
                for contact in electrode.contacts:
                    contacts_data.append({
                        "label": contact.label,
                        "x": int(contact.x),
                        "y": int(contact.y),
                        "z": int(contact.z)
                    })
                
                electrodes_data[electrode.name] = {
                    "type": electrode.electrode_type,
                    "contacts": contacts_data,
                    "entry": self.electrode_points.get(electrode.name, {}).get('entry', None),
                    "output": self.electrode_points.get(electrode.name, {}).get('output', None)
                }
            
            # Write to JSON file
            with open(file_path, 'w') as f:
                json.dump(electrodes_data, f, indent=2)
            
            QMessageBox.information(self, "Success", f"Electrode coordinates exported to {file_path}")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export coordinates: {str(e)}")

    def save_file_button_clicked(self):
        """Save electrode coordinates in 3D Slicer fiducial markup format"""
        if not self.ElectrodesList:
            QMessageBox.warning(self, "Warning", "No electrodes to save.")
            return
        
        # Check if we have processed contacts
        if not any(electrode.contacts for electrode in self.ElectrodesList):
            QMessageBox.warning(self, "Warning", "No processed electrode contacts to save.")
            return
            
        # Check if we have a loaded image with affine transform
        if self.current_nifti_img is None or self.affine is None:
            QMessageBox.warning(self, "Warning", "No image loaded or missing affine transform.")
            return
        
        # Ask for the output file
        default_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Electrode Coordinates", default_dir, "JSON Files (*.json)"
        )
        
        if not file_path:
            return  # User cancelled
        
        try:
            # Create the base structure for 3D Slicer fiducial markup
            slicer_markup = {
                "@schema": "https://raw.githubusercontent.com/slicer/slicer/master/Modules/Loadable/Markups/Resources/Schema/markups-schema-v1.0.3.json#",
                "markups": []
            }
            
            # Create a fiducial markup for each electrode
            for electrode in self.ElectrodesList:
                if not electrode.contacts:
                    continue
                
                # Create the fiducial markup structure
                fiducial = {
                    "type": "Fiducial",
                    "coordinateSystem": "RAS",  # Right-Anterior-Superior coordinate system (Slicer's default)
                    "coordinateUnits": "mm",
                    "locked": False,
                    "fixedNumberOfControlPoints": False,
                    "labelFormat": "%N-%d",
                    "lastUsedControlPointNumber": len(electrode.contacts),
                    "controlPoints": [],
                    "measurements": [],
                    "display": {
                        "visibility": True,
                        "opacity": 1.0,
                        "color": [0.39, 0.78, 0.78],  # Default color (cyan)
                        "selectedColor": [0.39, 1.0, 0.39],
                        "activeColor": [0.4, 1.0, 0.0],
                        "propertiesLabelVisibility": False,
                        "pointLabelsVisibility": True,
                        "textScale": 3.0,
                        "glyphType": "Sphere3D",
                        "glyphScale": 3.0,
                        "glyphSize": 5.0,
                        "useGlyphScale": True,
                        "sliceProjection": False,
                        "sliceProjectionUseFiducialColor": True,
                        "sliceProjectionOutlinedBehindSlicePlane": False,
                        "sliceProjectionColor": [1.0, 1.0, 1.0],
                        "sliceProjectionOpacity": 0.6,
                        "lineThickness": 0.2,
                        "lineColorFadingStart": 1.0,
                        "lineColorFadingEnd": 10.0,
                        "lineColorFadingSaturation": 1.0,
                        "lineColorFadingHueOffset": 0.0,
                        "handlesInteractive": False,
                        "translationHandleVisibility": True,
                        "rotationHandleVisibility": True,
                        "scaleHandleVisibility": True,
                        "interactionHandleScale": 3.0,
                        "snapMode": "toVisibleSurface"
                    }
                }
                
                # Generate a random color for this electrode based on its name
                hue = abs(hash(electrode.name)) % 360
                # Convert HSV to RGB (hue: 0-360, saturation: 0-1, value: 0-1)
                h = hue / 360.0
                s = 0.8  # Saturation
                v = 0.8  # Value
                
                # HSV to RGB conversion
                if s == 0.0:
                    r = g = b = v
                else:
                    h *= 6.0
                    i = int(h)
                    f = h - i
                    p = v * (1.0 - s)
                    q = v * (1.0 - s * f)
                    t = v * (1.0 - s * (1.0 - f))
                    
                    if i == 0:
                        r, g, b = v, t, p
                    elif i == 1:
                        r, g, b = q, v, p
                    elif i == 2:
                        r, g, b = p, v, t
                    elif i == 3:
                        r, g, b = p, q, v
                    elif i == 4:
                        r, g, b = t, p, v
                    else:
                        r, g, b = v, p, q
                
                # Set the color for this electrode
                fiducial["display"]["color"] = [r, g, b]
                
                # Add control points (contacts) for this electrode
                for i, contact in enumerate(electrode.contacts):
                    # Convert voxel coordinates to physical coordinates using the affine transform
                    voxel_coords = np.array([contact.x, contact.y, contact.z, 1.0])
                    physical_coords = np.dot(self.affine, voxel_coords)[:3]
                    
                    # Note on coordinate systems:
                    # The physical coordinates from our NIfTI affine transform 
                    # are already compatible with 3D Slicer's coordinate system.
                    # We'll use them directly without further conversion.
                    ras_coords = physical_coords.tolist()
                    
                    # Create a control point for each contact
                    control_point = {
                        "id": str(i + 1),
                        "label": f"{electrode.name}{i+1}",
                        "description": electrode.electrode_type,
                        "associatedNodeID": "",
                        "position": ras_coords,  # Use RAS coordinates in mm
                        "orientation": [-1.0, -0.0, -0.0, -0.0, -1.0, -0.0, 0.0, 0.0, 1.0],
                        "selected": True,
                        "locked": True,
                        "visibility": True,
                        "positionStatus": "defined"
                    }
                    fiducial["controlPoints"].append(control_point)
                
                # Add this fiducial to the markups
                slicer_markup["markups"].append(fiducial)
            
            # Write to JSON file
            with open(file_path, 'w') as f:
                json.dump(slicer_markup, f, indent=4)
            
            QMessageBox.information(self, "Success", f"Electrode coordinates saved to {file_path} in 3D Slicer format")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save coordinates: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    file_path = sys.argv[1] if len(sys.argv) > 1 else None
    viewer = ImagesViewer(file_path)
    viewer.show()
    sys.exit(app.exec())