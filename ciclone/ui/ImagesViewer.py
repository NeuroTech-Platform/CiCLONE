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
    QTableWidgetItem,
    QTreeWidgetItem,
    QMenu,
    QButtonGroup
)
from PyQt6.QtCore import Qt, QStandardPaths

from PyQt6.QtGui import QFileSystemModel, QImage, QPixmap, QPainter, QColor, QBrush, QMouseEvent

from ciclone.services.io.subject_importer import SubjectImporter
from ciclone.models.image_model import ImageModel
from ciclone.utils.utility import read_config_file
from ciclone.controllers.image_controller import ImageController
from ciclone.domain.electrodes import Electrode
from ciclone.controllers.electrode_controller import ElectrodeController
from ciclone.services.io.slicer_file import SlicerFile
from ciclone.ui.Viewer3D import Viewer3D
from ciclone.forms.ImagesViewer_ui import Ui_ImagesViewer

# Import new MVC components
from ciclone.models import ElectrodeModel, CoordinateModel
from ciclone.controllers import ImageController

class ImagesViewer(QMainWindow, Ui_ImagesViewer):

    def __init__(self, file_path=None):
        super(ImagesViewer, self).__init__()
        self.setupUi(self)

        # Initialize MVC components
        self._initialize_mvc_components()
        
        # Initialize UI state
        self.setting_entry = False
        self.setting_output = False
        
        # Setup UI components
        self._setup_ui_components()
        
        # Connect signals to controllers
        self._connect_signals()
        
        # Load initial file if provided
        if file_path is not None:
            self.image_controller.load_image(file_path)
        else:
            self.show_default_display()

    def _initialize_mvc_components(self):
        """Initialize the MVC architecture components."""
        # Initialize models
        self.electrode_model = ElectrodeModel()
        self.coordinate_model = CoordinateModel()
        self.image_model = ImageModel()
        
        # Initialize controllers
        self.electrode_controller = ElectrodeController(
            self.electrode_model, self.coordinate_model
        )
        self.image_controller = ImageController(self.image_model)
        
        # Set view references in controllers
        self.electrode_controller.set_view(self)
        self.image_controller.set_view(self)

    def _setup_ui_components(self):
        """Setup UI components and styling."""
        # Load electrode types into combo box
        self.ElectrodeTypeComboBox.addItems(self.electrode_controller.get_electrode_types())

        # Configure column sizing for ElectrodeTreeWidget
        self.ElectrodeTreeWidget.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.ElectrodeTreeWidget.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.ElectrodeTreeWidget.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.ElectrodeTreeWidget.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.ElectrodeTreeWidget.header().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.ElectrodeTreeWidget.setColumnWidth(0, 80)
        self.ElectrodeTreeWidget.setColumnWidth(1, 80)
        self.ElectrodeTreeWidget.setColumnWidth(2, 70)
        self.ElectrodeTreeWidget.setColumnWidth(3, 70)
        self.ElectrodeTreeWidget.setColumnWidth(4, 70)

        # Enable context menu for ElectrodeTreeWidget
        self.ElectrodeTreeWidget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # Enable multi-selection for electrodes (only top-level items)
        self.ElectrodeTreeWidget.setSelectionMode(self.ElectrodeTreeWidget.SelectionMode.ExtendedSelection)

        # Find and store the vertical spacer
        self.verticalSpacer = self.leftPanelLayout.itemAt(self.leftPanelLayout.count() - 1).spacerItem()

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

        # Make grid layout cells equal size and square
        grid = self.layoutWidget.layout()
        grid.setSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

    def _connect_signals(self):
        """Connect UI signals to controller methods."""
        # Radio button signals
        self.SetEntryRadioButton.clicked.connect(lambda: self.on_coordinate_radio_clicked('entry'))
        self.SetOutputRadioButton.clicked.connect(lambda: self.on_coordinate_radio_clicked('output'))

        # Splitter signal
        self.splitter.splitterMoved.connect(self.refresh_all_views)

        # Slider signals
        self.Axial_horizontalSlider.valueChanged.connect(lambda: self.update_slice_display('axial'))
        self.Sagittal_horizontalSlider.valueChanged.connect(lambda: self.update_slice_display('sagittal'))
        self.Coronal_horizontalSlider.valueChanged.connect(lambda: self.update_slice_display('coronal'))

        # Image click signals
        self.Axial_ImagePreview.clicked.connect(lambda x, y: self.on_image_clicked('axial', x, y))
        self.Sagittal_ImagePreview.clicked.connect(lambda x, y: self.on_image_clicked('sagittal', x, y))
        self.Coronal_ImagePreview.clicked.connect(lambda x, y: self.on_image_clicked('coronal', x, y))

        # Button signals
        self.AddElectrodePushButton.clicked.connect(self.on_add_electrode_clicked)
        self.Viewer3dButton.clicked.connect(self.on_viewer3d_clicked)
        self.ProcessCoordinatesPushButton.clicked.connect(self.on_process_coordinates_clicked)
        self.SaveFilePushButton.clicked.connect(self.on_save_file_clicked)

        # Combo box signals
        self.ElectrodesComboBox.currentTextChanged.connect(self.update_coordinate_display)

        # Context menu signal
        self.ElectrodeTreeWidget.customContextMenuRequested.connect(self.on_electrode_context_menu_requested)

        # ToolBox signal
        self.toolBox.currentChanged.connect(self.adjust_tab_heights)
        self.toolBox.setCurrentIndex(1)
        self.toolBox.setCurrentIndex(0)

    # =============================================================================
    # VIEW INTERFACE METHODS (Called by Controllers)
    # =============================================================================

    def refresh_electrode_list(self):
        """Refresh the electrode combo box with current electrode names."""
        current_text = self.ElectrodesComboBox.currentText()
        self.ElectrodesComboBox.blockSignals(True)
        self.ElectrodesComboBox.clear()
        
        for name in self.electrode_controller.get_electrode_names():
            self.ElectrodesComboBox.addItem(name)
        
        index = self.ElectrodesComboBox.findText(current_text)
        if index >= 0:
            self.ElectrodesComboBox.setCurrentIndex(index)
        
        self.ElectrodesComboBox.blockSignals(False)
        
        has_electrodes = self.ElectrodesComboBox.count() > 0
        self.SetEntryRadioButton.setEnabled(has_electrodes)
        self.SetOutputRadioButton.setEnabled(has_electrodes)
        
        self.update_coordinate_display()

    def refresh_electrode_tree(self):
        """Refresh the electrode tree widget."""
        electrode_name = self.ElectrodesComboBox.currentText()
        if not electrode_name:
            return

        electrode = self.electrode_controller.get_electrode(electrode_name)
        if electrode:
            # Find and update the existing item
            root = self.ElectrodeTreeWidget.invisibleRootItem()
            for i in range(root.childCount()):
                item = root.child(i)
                if item.text(0) == electrode_name:
                    # Remove old item
                    root.removeChild(item)
                    # Add new item with updated contacts
                    new_item = self.electrode_controller.create_tree_item(electrode)
                    root.addChild(new_item)
                    new_item.setExpanded(True)
                    break

    def refresh_image_display(self):
        """Refresh all image displays."""
        self.refresh_all_views()

    def update_coordinate_display(self, electrode_name=None):
        """Update the coordinate labels based on the selected electrode."""
        if electrode_name is None:
            electrode_name = self.ElectrodesComboBox.currentText()
            
        coordinates = self.electrode_controller.get_coordinates(electrode_name)
        
        if coordinates and 'entry' in coordinates:
            entry = coordinates['entry']
            self.EntryCoordinatesLabel.setText(f"Tip - proximal part : ({entry[0]}, {entry[1]}, {entry[2]})")
        else:
            self.EntryCoordinatesLabel.setText("Tip - proximal part : ")
            
        if coordinates and 'output' in coordinates:
            output = coordinates['output']
            self.OutputCoordinatesLabel.setText(f"End - distal part : ({output[0]}, {output[1]}, {output[2]})")
        else:
            self.OutputCoordinatesLabel.setText("End - distal part : ")

    def refresh_coordinate_display(self):
        """Refresh coordinate display for current electrode."""
        self.update_coordinate_display()

    def enable_image_controls(self):
        """Enable image-related controls."""
        self.Axial_horizontalSlider.setEnabled(True)
        self.Sagittal_horizontalSlider.setEnabled(True)
        self.Coronal_horizontalSlider.setEnabled(True)

    def show_default_display(self):
        """Show default message when no image is loaded."""
        for label in [self.Axial_ImagePreview, self.Sagittal_ImagePreview, self.Coronal_ImagePreview]:
            label.clear()
            label.setText("No image loaded")
        
        self.Axial_horizontalSlider.setEnabled(False)
        self.Sagittal_horizontalSlider.setEnabled(False)
        self.Coronal_horizontalSlider.setEnabled(False)

    def clear_electrode_input(self):
        """Clear the electrode input field."""
        self.ElectrodeNameLineEdit.clear()

    def update_slider_ranges(self):
        """Update slider ranges based on current volume dimensions."""
        for orientation, slider in [('axial', self.Axial_horizontalSlider),
                                  ('sagittal', self.Sagittal_horizontalSlider),
                                  ('coronal', self.Coronal_horizontalSlider)]:
            min_val, max_val = self.image_controller.get_slice_range(orientation)
            slider.setRange(min_val, max_val)
            slider.setValue(self.image_controller.get_initial_slice(orientation))

    def refresh_all_views(self):
        """Update all three views if data is loaded."""
        if self.image_controller.is_image_loaded():
            self.update_slice_display('axial')
            self.update_slice_display('sagittal')
            self.update_slice_display('coronal')

    # =============================================================================
    # EVENT HANDLERS (Delegate to Controllers)
    # =============================================================================

    def on_add_electrode_clicked(self):
        """Handle add electrode button click."""
        name = self.ElectrodeNameLineEdit.text()
        electrode_type = self.ElectrodeTypeComboBox.currentText()
        
        if self.electrode_controller.create_electrode(name, electrode_type):
            # Add the electrode to the tree
            electrode = self.electrode_controller.get_electrode(name)
            if electrode:
                item = self.electrode_controller.create_tree_item(electrode)
                self.ElectrodeTreeWidget.addTopLevelItem(item)
                QMessageBox.information(self, "Success", f"Electrode '{name}' of type '{electrode_type}' created successfully.")

    def on_viewer3d_clicked(self):
        """Handle 3D viewer button click."""
        print("Viewer3D button clicked")
        self.viewer3d = Viewer3D(
            nifti_img=self.image_controller.get_current_nifti_image(), 
            current_volume_data=self.image_controller.get_volume_data()
        )
        self.viewer3d.show()

    def on_process_coordinates_clicked(self):
        """Handle process coordinates button click."""
        electrode_name = self.ElectrodesComboBox.currentText()
        self.electrode_controller.process_electrode_coordinates(electrode_name)

    def on_save_file_clicked(self):
        """Handle save file button click."""
        # Check if we have electrodes with contacts
        if not self.electrode_model.has_processed_contacts():
            QMessageBox.warning(self, "Warning", "No processed electrode contacts to save.")
            return
            
        # Check if we have a loaded image with affine transform
        if not self.image_controller.is_image_loaded() or self.image_controller.get_affine_transform() is None:
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
            # Prepare electrode data for the SlicerFile class
            electrodes_data = []
            for electrode in self.electrode_model.get_electrodes_with_contacts():
                contacts = [(contact.x, contact.y, contact.z) for contact in electrode.contacts]
                electrodes_data.append({
                    'name': electrode.name,
                    'type': electrode.electrode_type,
                    'contacts': contacts
                })
            
            # Create and save the markup file
            slicer_file = SlicerFile()
            markup = slicer_file.create_markup(electrodes_data, self.image_controller.get_affine_transform())
            
            if slicer_file.save_to_file(file_path, markup):
                QMessageBox.information(self, "Success", f"Electrode coordinates saved to {file_path} in 3D Slicer format")
            else:
                raise Exception("Failed to save file")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save coordinates: {str(e)}")
            import traceback
            traceback.print_exc()

    def on_electrode_context_menu_requested(self, position):
        """Handle electrode context menu request."""
        item = self.ElectrodeTreeWidget.itemAt(position)
        if item is None:
            return
        
        # Get all selected items
        selected_items = self.ElectrodeTreeWidget.selectedItems()
        
        # Filter to only include top-level electrode items (not contacts)
        electrode_items = [item for item in selected_items if item.parent() is None]
        
        if not electrode_items:
            return
        
        menu = QMenu()
        
        # Show appropriate text based on selection count
        if len(electrode_items) == 1:
            delete_action = menu.addAction("Delete Electrode")
        else:
            delete_action = menu.addAction(f"Delete {len(electrode_items)} Electrodes")
        
        # Show the menu and get the selected action
        action = menu.exec(self.ElectrodeTreeWidget.viewport().mapToGlobal(position))
        
        if action == delete_action:
            self.delete_electrodes(electrode_items)

    def delete_electrodes(self, items):
        """Delete multiple electrodes and their associated data."""
        electrode_names = [item.text(0) for item in items]
        
        if self.electrode_controller.delete_multiple_electrodes(electrode_names):
            # Remove from tree widget in reverse order to avoid index issues
            for item in reversed(items):
                self.ElectrodeTreeWidget.takeTopLevelItem(self.ElectrodeTreeWidget.indexOfTopLevelItem(item))

    def on_coordinate_radio_clicked(self, mode):
        """Handle radio button clicks for both entry and output modes."""
        # Check if an electrode is selected
        electrode_name = self.ElectrodesComboBox.currentText()
        if not electrode_name:
            QMessageBox.warning(self, "Warning", "Please select an electrode first.")
            getattr(self, f"Set{mode.capitalize()}RadioButton").setChecked(False)
            return

        # Get the other mode
        other_mode = 'output' if mode == 'entry' else 'entry'
        
        # Toggle the state
        setattr(self, f"setting_{mode}", not getattr(self, f"setting_{mode}"))
        setattr(self, f"setting_{other_mode}", False)
        
        # Update radio buttons
        getattr(self, f"Set{other_mode.capitalize()}RadioButton").setChecked(False)
        getattr(self, f"Set{other_mode.capitalize()}RadioButton").setStyleSheet("")
        
        # Update UI
        if getattr(self, f"setting_{mode}"):
            getattr(self, f"Set{mode.capitalize()}RadioButton").setStyleSheet("color: red;")
        else:
            getattr(self, f"Set{mode.capitalize()}RadioButton").setStyleSheet("")
        
        # Update coordinate display
        self.update_coordinate_display(electrode_name)

    def on_image_clicked(self, orientation, x, y):
        """Handle clicks on any view by determining the 3D coordinates and updating other views."""
        if not self.image_controller.is_image_loaded():
            return

        # Get the label and its pixmap
        label = getattr(self, f"{orientation.capitalize()}_ImagePreview")
        pixmap = label.pixmap()
        if pixmap is None:
            return

        # Get current slice indices
        current_slices = {
            'axial': self.Axial_horizontalSlider.value(),
            'sagittal': self.Sagittal_horizontalSlider.value(),
            'coronal': self.Coronal_horizontalSlider.value()
        }

        # Get 3D coordinates from image controller
        coords = self.image_controller.get_3d_coordinates_from_click(
            orientation, x, y,
            label.width(), label.height(),
            pixmap.width(), pixmap.height(),
            current_slices
        )

        if coords is None:
            return

        x_coord, y_coord, z_coord = coords

        # Update other views to show the clicked point
        if orientation == 'axial':
            self.Sagittal_horizontalSlider.setValue(x_coord)
            self.Coronal_horizontalSlider.setValue(y_coord)
        elif orientation == 'sagittal':
            self.Axial_horizontalSlider.setValue(z_coord)
            self.Coronal_horizontalSlider.setValue(y_coord)
        else:  # coronal
            self.Axial_horizontalSlider.setValue(z_coord)
            self.Sagittal_horizontalSlider.setValue(x_coord)

        # Handle coordinate setting through controllers
        electrode_name = self.ElectrodesComboBox.currentText()
        if self.setting_entry:
            self.electrode_controller.set_entry_coordinate(electrode_name, coords)
            self.refresh_all_views()
        elif self.setting_output:
            self.electrode_controller.set_output_coordinate(electrode_name, coords)
            self.refresh_all_views()

    # =============================================================================
    # UI UPDATE METHODS
    # =============================================================================

    def update_slice_display(self, orientation):
        """Update the display for a given orientation."""
        if not self.image_controller.is_image_loaded():
            return

        try:
            # Get the appropriate slider and label
            if orientation == 'axial':
                slider = self.Axial_horizontalSlider
                label = self.Axial_ImagePreview
            elif orientation == 'sagittal':
                slider = self.Sagittal_horizontalSlider
                label = self.Sagittal_ImagePreview
            elif orientation == 'coronal':
                slider = self.Coronal_horizontalSlider
                label = self.Coronal_ImagePreview

            # Get current slice indices
            current_slices = {
                'axial': self.Axial_horizontalSlider.value(),
                'sagittal': self.Sagittal_horizontalSlider.value(),
                'coronal': self.Coronal_horizontalSlider.value()
            }

            # Create pixmap with points through image controller
            pixmap = self.image_controller.create_slice_pixmap(
                orientation, slider.value(),
                label.width(), label.height(),
                self.electrode_controller.get_electrode_points_for_display(),
                self.electrode_controller.get_processed_contacts_for_display(),
                current_slices
            )

            if pixmap:
                # Display the pixmap
                label.setPixmap(pixmap)
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to update display: {str(e)}")

    def adjust_tab_heights(self, index):
        """Adjust tab heights based on selected tab."""
        if index == 2:  # Coordinates tab
            # Make the toolbox take up more space when Coordinates tab is active
            self.toolBox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
            self.verticalSpacer.changeSize(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        else:
            # Make the toolbox compact for other tabs
            self.toolBox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
            self.verticalSpacer.changeSize(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        
        # Force layout update
        self.leftPanelLayout.invalidate()
        self.leftPanel.updateGeometry()

    def resizeEvent(self, event):
        """Handle window resize events to update the display."""
        super().resizeEvent(event)
        self.refresh_all_views()

    # =============================================================================
    # LEGACY METHODS (For backward compatibility)
    # =============================================================================

    def load_nifti_file(self, nifti_path):
        """Load NIFTI file - delegates to image controller."""
        self.image_controller.load_image(nifti_path)

    def update_all_views(self):
        """Legacy method - delegates to refresh_all_views."""
        self.refresh_all_views()


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    file_path = sys.argv[1] if len(sys.argv) > 1 else None
    viewer = ImagesViewer(file_path)
    viewer.show()
    sys.exit(app.exec())