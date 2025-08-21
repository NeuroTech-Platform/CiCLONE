import os
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import numpy as np
import tempfile

from ciclone.models.image_model import ImageModel
from ciclone.controllers.image_controller import ImageController
from ciclone.domain.electrodes import Electrode
from ciclone.controllers.electrode_controller import ElectrodeController
from ciclone.services.io.slicer_file import SlicerFile
from ciclone.services.processing.operations import transform_coordinates
from ciclone.ui.Viewer3D import Viewer3D
from ciclone.forms.ImagesViewer_ui import Ui_ImagesViewer
from ciclone.interfaces.view_interfaces import IImageView, IBaseView
from ciclone.domain.subject import Subject

from PyQt6.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QInputDialog,
    QSizePolicy,
    QHeaderView,
    QVBoxLayout,
    QTreeWidgetItem,
    QMenu,
    QSlider,
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QWidgetAction
)
from PyQt6.QtCore import Qt, QStandardPaths, QTimer
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QBrush, QMouseEvent, QAction, QCursor

# Import new MVC components
from ciclone.models import ElectrodeModel, CoordinateModel, CrosshairModel
from ciclone.controllers import CrosshairController

class ImagesViewer(QMainWindow, Ui_ImagesViewer):

    def __init__(self, file_path=None):
        super(ImagesViewer, self).__init__()
        self.setupUi(self)

        # Initialize MVC components
        self._initialize_mvc_components()
        
        # Initialize UI state
        self.last_clicked_coordinates = None  # Store coordinates of last image click
        self.drag_electrode_info = None
        
        # Setup UI components
        self._setup_ui_components()
        
        # Connect signals to controllers
        self._connect_signals()
        
        # Load initial file if provided
        if file_path is not None:
            self.image_controller.load_image(file_path)
        else:
            self.show_default_display()

        # Track if we're in fitted mode (auto-resize) or user zoom mode
        self._is_fitted_mode = True
        
        # Timer for debouncing resize events
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self.refresh_all_views)
        
        # Cleanup callback for when window is closed
        self._cleanup_callback = None

    def _initialize_mvc_components(self):
        """Initialize the MVC architecture components."""
        # Initialize models
        self.electrode_model = ElectrodeModel()
        self.coordinate_model = CoordinateModel()
        self.image_model = ImageModel()
        self.crosshair_model = CrosshairModel()
        
        # Initialize controllers
        self.electrode_controller = ElectrodeController(
            self.electrode_model, self.coordinate_model
        )
        self.image_controller = ImageController(self.image_model)
        self.crosshair_controller = CrosshairController(
            self.crosshair_model, self.image_controller
        )
        
        # Set view references in controllers
        self.electrode_controller.set_view(self)
        self.image_controller.set_view(self)
        self.crosshair_controller.set_view(self)

    def _setup_ui_components(self):
        """Setup UI components and styling."""
        # Load electrode types into combo box
        self.ElectrodeTypeComboBox.addItems(self.electrode_controller.get_electrode_types())

        # Configure column sizing for DataTreeWidget
        self.DataTreeWidget.setColumnCount(2)
        self.DataTreeWidget.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.DataTreeWidget.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.DataTreeWidget.setColumnWidth(1, 70)
        self.DataTreeWidget.header().setStretchLastSection(False)  # Prevent last section from stretching
        
        # Setup opacity controls near image sliders
        self.setup_image_opacity_controls()
        
        # Configure column sizing for ElectrodeTreeWidget
        # Add the Move column header
        self.ElectrodeTreeWidget.setHeaderLabels(["Name", "X", "Y", "Z", "Move"])
        
        self.ElectrodeTreeWidget.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.ElectrodeTreeWidget.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.ElectrodeTreeWidget.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.ElectrodeTreeWidget.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.ElectrodeTreeWidget.header().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.ElectrodeTreeWidget.setColumnWidth(0, 80)
        self.ElectrodeTreeWidget.setColumnWidth(1, 80)
        self.ElectrodeTreeWidget.setColumnWidth(2, 70)
        self.ElectrodeTreeWidget.setColumnWidth(3, 70)
        self.ElectrodeTreeWidget.setColumnWidth(4, 60)  # Fixed width for toggle button

        # Enable context menu for ElectrodeTreeWidget
        self.ElectrodeTreeWidget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # Enable context menu for DataTreeWidget
        self.DataTreeWidget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # Enable multi-selection for data tree (images)
        self.DataTreeWidget.setSelectionMode(self.DataTreeWidget.SelectionMode.ExtendedSelection)
        
        # Enable multi-selection for electrodes (only top-level items)
        self.ElectrodeTreeWidget.setSelectionMode(self.ElectrodeTreeWidget.SelectionMode.ExtendedSelection)

        # Find and store the vertical spacer
        self.verticalSpacer = self.leftPanelLayout.itemAt(self.leftPanelLayout.count() - 1).spacerItem()
        
        # Optimize layout for compact tabs
        # Make the toolbox compact and let the spacer expand to push content up
        self.toolBox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.verticalSpacer.changeSize(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

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

        # Style the toolbar to make checked crosshair button green (same as visibility buttons)
        self.mainToolBar.setStyleSheet("""
            QToolButton {
                border: 1px solid transparent;
                border-radius: 3px;
            }
            QToolButton:checked {
                background-color: #4CAF50;
                border: 1px solid #45a049;
                border-radius: 3px;
                color: white;
            }
            QToolButton:checked:hover {
                background-color: #45a049;
            }
        """)
    
    def toggle_crosshairs(self, checked):
        """Toggle crosshair display on all views."""
        self.crosshair_controller.toggle_crosshairs(checked)

    def setup_image_opacity_controls(self):
        """Setup gear buttons near image sliders that open overlay control panels."""
        from PyQt6.QtWidgets import QComboBox
        
        # Initialize shared overlay controls (will be used in popup menus)
        self.base_image_combo = None
        self.overlay_image_combo = None
        self.opacity_slider = None
        self.opacity_percentage_label = None
        
        # Dictionary to store opacity menus for each view
        self.opacity_menus = {}
        
        # Add gear buttons for each view
        for orientation in ['Axial', 'Sagittal', 'Coronal']:
            # Get the vertical layout for this orientation
            layout = getattr(self, f"{orientation}_verticalLayout")
            
            # Create horizontal layout for slider and button
            slider_layout = QHBoxLayout()
            
            # Get the existing slider
            slider = getattr(self, f"{orientation}_horizontalSlider")
            
            # Remove slider from its current parent
            layout.removeWidget(slider)
            
            # Create gear button
            gear_btn = QToolButton()
            gear_btn.setText("⚙")
            gear_btn.setFixedSize(24, 24)
            gear_btn.setStyleSheet("""
                QToolButton {
                    background-color: #404040;
                    border: 1px solid #606060;
                    border-radius: 3px;
                    color: white;
                    font-size: 12px;
                }
                QToolButton:hover {
                    background-color: #505050;
                }
                QToolButton:pressed {
                    background-color: #303030;
                }
            """)
            
            # Create overlay control menu
            overlay_menu = QMenu()
            gear_btn.setMenu(overlay_menu)
            gear_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            
            # Store reference to menu
            self.opacity_menus[orientation.lower()] = overlay_menu
            
            # Add button and slider to horizontal layout (button on left)
            slider_layout.addWidget(gear_btn)
            slider_layout.addWidget(slider)
            
            # Add the horizontal layout to the vertical layout
            layout.insertLayout(0, slider_layout)
        
        # Initialize all menus with the overlay controls
        self.rebuild_all_overlay_menus()
    
    def rebuild_all_overlay_menus(self):
        """Rebuild all overlay control menus with the current two-image system."""
        from PyQt6.QtWidgets import QWidgetAction, QComboBox
        
        # Get current state from model (the source of truth)
        current_base = self.image_controller.get_current_base_image_name()
        current_overlay = self.image_controller.get_current_overlay_image_name()
        current_opacity = self.image_controller.get_overlay_opacity() * 100  # Convert to percentage
        
        for menu in self.opacity_menus.values():
            # Clear existing actions
            menu.clear()
            
            # Get loaded images
            loaded_images = self.image_controller.get_loaded_images() if hasattr(self, 'image_controller') else []
            
            if not loaded_images:
                # Add placeholder if no images
                no_images_action = menu.addAction("No images loaded")
                no_images_action.setEnabled(False)
                return
            
            # Create overlay controls container
            container_widget = QWidget()
            container_layout = QVBoxLayout(container_widget)
            container_layout.setContentsMargins(8, 8, 8, 8)
            container_layout.setSpacing(6)
            
            # Title
            title_label = QLabel("Image Overlay Controls")
            title_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #333;")
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            container_layout.addWidget(title_label)
            
            # Main horizontal layout: slider on left, dropdowns on right
            main_layout = QHBoxLayout()
            main_layout.setSpacing(10)
            
            # Left side: Opacity slider with percentage
            slider_container = QWidget()
            slider_layout = QVBoxLayout(slider_container)
            slider_layout.setContentsMargins(0, 0, 0, 0)
            slider_layout.setSpacing(3)
            
            opacity_slider = QSlider(Qt.Orientation.Vertical)
            opacity_slider.setRange(0, 100)
            opacity_slider.setValue(int(current_opacity))
            opacity_slider.setFixedHeight(80)
            opacity_slider.setEnabled(len(loaded_images) >= 2)
            
            percentage_label = QLabel(f"{int(current_opacity)}%")
            percentage_label.setStyleSheet("font-size: 9px; color: #666; font-weight: bold;")
            percentage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            percentage_label.setFixedWidth(35)
            
            slider_layout.addWidget(opacity_slider)
            slider_layout.addWidget(percentage_label)
            
            # Right side: Dropdowns with aligned labels (centered vertically)
            dropdowns_container = QWidget()
            dropdowns_layout = QVBoxLayout(dropdowns_container)
            dropdowns_layout.setContentsMargins(0, 0, 0, 0)
            dropdowns_layout.setSpacing(8)
            
            # Add stretch at top to center content
            dropdowns_layout.addStretch()
            
            # Overlay image section (horizontal: label + dropdown)
            overlay_section = QWidget()
            overlay_section_layout = QHBoxLayout(overlay_section)
            overlay_section_layout.setContentsMargins(0, 0, 0, 0)
            overlay_section_layout.setSpacing(6)
            
            overlay_label = QLabel("Overlay Image:")
            overlay_label.setStyleSheet("font-size: 10px; color: #555; font-weight: bold;")
            overlay_label.setFixedWidth(85)
            overlay_combo = QComboBox()
            overlay_combo.setMinimumWidth(230)
            
            overlay_section_layout.addWidget(overlay_label)
            overlay_section_layout.addWidget(overlay_combo)
            
            # Base image section (horizontal: label + dropdown)
            base_section = QWidget()
            base_section_layout = QHBoxLayout(base_section)
            base_section_layout.setContentsMargins(0, 0, 0, 0)
            base_section_layout.setSpacing(6)
            
            base_label = QLabel("Base Image:")
            base_label.setStyleSheet("font-size: 10px; color: #555; font-weight: bold;")
            base_label.setFixedWidth(85)
            base_combo = QComboBox()
            base_combo.setMinimumWidth(230)
            
            base_section_layout.addWidget(base_label)
            base_section_layout.addWidget(base_combo)
            
            # Populate dropdowns with image names
            import os
            image_names = [os.path.basename(path) for path in loaded_images]
            
            if len(loaded_images) >= 1:
                # Add "None" option as first item in both dropdowns
                base_combo.addItem("None")
                base_combo.addItems(image_names)
                base_combo.setEnabled(True)
                
                overlay_combo.addItem("None")
                if len(loaded_images) >= 2:
                    overlay_combo.addItems(image_names)
                    overlay_combo.setEnabled(True)
                else:
                    overlay_combo.setEnabled(False)
                    
                # Set selections based on model state
                if current_base and current_base in image_names:
                    base_combo.setCurrentText(current_base)
                else:
                    base_combo.setCurrentText("None")
                
                if current_overlay and current_overlay in image_names:
                    overlay_combo.setCurrentText(current_overlay)
                else:
                    overlay_combo.setCurrentText("None")
                    
            else:
                base_combo.addItem("No images loaded")
                overlay_combo.addItem("No images loaded")
                base_combo.setEnabled(False)
                overlay_combo.setEnabled(False)
            
            # Add sections to dropdowns container
            dropdowns_layout.addWidget(overlay_section)
            dropdowns_layout.addWidget(base_section)
            
            # Add stretch at bottom to center content
            dropdowns_layout.addStretch()
            
            # Add slider and dropdowns to main layout
            main_layout.addWidget(slider_container)
            main_layout.addWidget(dropdowns_container)
            
            # Add main layout to container
            container_layout.addLayout(main_layout)
            
            # Connect signals
            base_combo.currentTextChanged.connect(self.on_base_image_changed)
            overlay_combo.currentTextChanged.connect(self.on_overlay_image_changed)
            opacity_slider.valueChanged.connect(lambda value, label=percentage_label: self.on_opacity_slider_changed(value, label))
            
            # Set container size
            container_widget.setFixedWidth(390)
            container_widget.adjustSize()
            
            # Create widget action and add to menu
            widget_action = QWidgetAction(menu)
            widget_action.setDefaultWidget(container_widget)
            menu.addAction(widget_action)

    def on_base_image_changed(self, image_name):
        """Handle base image selection change."""
        self._update_overlay_from_combo_change(is_base=True, selected_image=image_name)

    def on_overlay_image_changed(self, image_name):
        """Handle overlay image selection change."""
        self._update_overlay_from_combo_change(is_base=False, selected_image=image_name)

    def on_opacity_slider_changed(self, value, label=None):
        """Handle opacity slider change."""
        if label:
            label.setText(f"{value}%")
        
        # Get current selections and update
        base_image, overlay_image = self._get_current_combo_selections()
        if self._are_valid_selections(base_image, overlay_image):
            opacity = value / 100.0
            self.image_controller.set_overlay_images(base_image, overlay_image, opacity)
            self.refresh_all_views()

    def _update_overlay_from_combo_change(self, is_base: bool, selected_image: str):
        """Update overlay when a combo box changes."""
        if not selected_image or selected_image == "No images loaded":
            return
            
        base_image, overlay_image = self._get_current_combo_selections()
        
        if is_base:
            base_image = selected_image
        else:
            overlay_image = selected_image
            
        # Convert "None" to actual None for processing
        base_name = None if base_image == "None" else base_image
        overlay_name = None if overlay_image == "None" else overlay_image
        
        # Handle the selections
        if base_name and overlay_name:
            if base_name == overlay_name:
                # Same image in both dropdowns - show only this image
                self.image_controller.set_overlay_images(base_name, base_name, 0.0)
            else:
                # Different images - show as overlay
                opacity = self._get_current_opacity_value()
                self.image_controller.set_overlay_images(base_name, overlay_name, opacity)
        elif base_name and not overlay_name:
            # Only base image, no overlay
            self.image_controller.set_overlay_images(base_name, base_name, 0.0)
        elif not base_name and overlay_name:
            # Only overlay, promote to base
            self.image_controller.set_overlay_images(overlay_name, overlay_name, 0.0)
        else:
            # Both None - clear display
            self.image_controller.clear_overlay_state()
                
        self.update_all_visibility_buttons()
        self.refresh_all_views()

    def _get_current_combo_selections(self):
        """Get current base and overlay selections from any active menu."""
        from PyQt6.QtWidgets import QComboBox
        
        for menu in self.opacity_menus.values():
            for action in menu.actions():
                if hasattr(action, 'defaultWidget') and action.defaultWidget():
                    widget = action.defaultWidget()
                    combos = widget.findChildren(QComboBox)
                    if len(combos) >= 2:
                        # Order: overlay (0), base (1)
                        overlay_image = combos[0].currentText()
                        base_image = combos[1].currentText()
                        return base_image, overlay_image
        return None, None

    def _get_current_opacity_value(self):
        """Get current opacity value from any active menu."""
        for menu in self.opacity_menus.values():
            for action in menu.actions():
                if hasattr(action, 'defaultWidget') and action.defaultWidget():
                    widget = action.defaultWidget()
                    sliders = widget.findChildren(QSlider)
                    if sliders:
                        return sliders[0].value() / 100.0
        return 1.0

    def _are_valid_selections(self, base_image, overlay_image):
        """Check if the selections are valid for overlay."""
        return (base_image and base_image not in ["No images loaded", "None"] and
                overlay_image and overlay_image not in ["No images loaded", "None"] and
                base_image != overlay_image)

    def update_image_combo_boxes(self):
        """Update the overlay control menus with currently loaded images."""
        self.rebuild_all_overlay_menus()
        self.update_all_visibility_buttons()

    def on_visibility_toggle(self, file_path: str, checked: bool):
        """Handle visibility button toggle."""
        import os
        file_name = os.path.basename(file_path)
        
        # Get actual current state from model
        current_base = self.image_controller.get_current_base_image_name()
        current_overlay = self.image_controller.get_current_overlay_image_name()
        
        if checked:
            # Show image: add as base if empty, otherwise as overlay
            if not current_base:
                self._set_overlay_images_and_update(file_name, None)
            else:
                self._set_overlay_images_and_update(current_base, file_name)
        else:
            # Hide image: remove from current display
            if current_base == file_name and current_overlay == file_name:
                # Same image in both slots, clear everything
                self._set_overlay_images_and_update(None, None)
            elif current_base == file_name:
                # Removing base: promote overlay to base if it exists
                if current_overlay and current_overlay != file_name:
                    self._set_overlay_images_and_update(current_overlay, None)
                else:
                    self._set_overlay_images_and_update(None, None)
            elif current_overlay == file_name:
                # Removing overlay: keep base only
                self._set_overlay_images_and_update(current_base, None)
            # If file_name is not currently displayed, do nothing

    def _set_overlay_images_and_update(self, base_name, overlay_name):
        """Set overlay images and update all UI elements."""
        if base_name and overlay_name and base_name != overlay_name:
            # Two different images
            opacity = self._get_current_opacity_value()
            self.image_controller.set_overlay_images(base_name, overlay_name, opacity)
        elif base_name and not overlay_name:
            # Only base image, no overlay
            opacity = self._get_current_opacity_value()
            self.image_controller.set_overlay_images(base_name, base_name, 0.0)
        else:
            # Clear everything (base_name is None)
            self.image_controller.clear_overlay_state()
        
        # Update UI
        self._sync_dropdown_selections()
        self.update_all_visibility_buttons()
        self.refresh_all_views()

    def _sync_dropdown_selections(self):
        """Update dropdown selections to match current overlay state."""
        from PyQt6.QtWidgets import QComboBox
        
        # Get actual current state from model (not from dropdowns)
        base_image = self.image_controller.get_current_base_image_name()
        overlay_image = self.image_controller.get_current_overlay_image_name()
        
        # Check if this is a single image display (base and overlay are the same with 0 opacity)
        opacity = self.image_controller.get_overlay_opacity()
        is_single_image = (base_image and overlay_image and 
                          base_image == overlay_image and 
                          opacity <= 0.0)
        
        # Update all dropdown menus
        for menu in self.opacity_menus.values():
            for action in menu.actions():
                if hasattr(action, 'defaultWidget') and action.defaultWidget():
                    widget = action.defaultWidget()
                    combos = widget.findChildren(QComboBox)
                    if len(combos) >= 2:
                        # Order: overlay (0), base (1)
                        overlay_combo = combos[0]
                        base_combo = combos[1]
                        
                        # Block signals to prevent recursion
                        overlay_combo.blockSignals(True)
                        base_combo.blockSignals(True)
                        
                        # Update base selection
                        if base_image and base_combo.findText(base_image) >= 0:
                            base_combo.setCurrentText(base_image)
                        else:
                            base_combo.setCurrentText("None")
                        
                        # Update overlay selection - show None for single image display
                        if is_single_image:
                            overlay_combo.setCurrentText("None")
                        elif overlay_image and overlay_combo.findText(overlay_image) >= 0:
                            overlay_combo.setCurrentText(overlay_image)
                        else:
                            overlay_combo.setCurrentText("None")
                        
                        # Re-enable signals
                        overlay_combo.blockSignals(False)
                        base_combo.blockSignals(False)

    def update_all_visibility_buttons(self):
        """Update the appearance of all visibility buttons based on current overlay state."""
        # Get actual current state from model
        base_image = self.image_controller.get_current_base_image_name()
        overlay_image = self.image_controller.get_current_overlay_image_name()
        
        # Get currently displayed images
        displayed_images = set()
        if base_image:
            displayed_images.add(base_image)
        if overlay_image:
            displayed_images.add(overlay_image)
        
        # Update all buttons
        root = self.DataTreeWidget.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            file_path = item.data(0, Qt.ItemDataRole.UserRole)
            if file_path:
                import os
                file_name = os.path.basename(file_path)
                
                # Find the button widget
                widget = self.DataTreeWidget.itemWidget(item, 1)
                if widget:
                    button = widget.findChild(QPushButton)
                    if button:
                        is_displayed = file_name in displayed_images
                        button.setChecked(is_displayed)
                        self.update_visibility_button_appearance(button, is_displayed)

    def update_visibility_button_appearance(self, button, is_visible):
        """Update the appearance of a visibility button."""
        if is_visible:
            button.setText("👁")  # Eye emoji for visible
            button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    border: 1px solid #45a049;
                    border-radius: 3px;
                    color: white;
                    font-size: 10px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
        else:
            button.setText("◯")  # Empty circle for hidden
            button.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    color: #666;
                    font-size: 10px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """)

    def _connect_signals(self):
        """Connect UI signals to controller methods."""
        # Push button signals for coordinate setting
        self.SetEntryPushButton.clicked.connect(self.on_set_entry_clicked)
        self.SetOutputPushButton.clicked.connect(self.on_set_output_clicked)

        # Splitter signal - removed to prevent excessive refreshes during zoom
        # self.splitter.splitterMoved.connect(self.refresh_all_views)

        # Slider signals
        self.Axial_horizontalSlider.valueChanged.connect(lambda: self.update_slice_display('axial'))
        self.Sagittal_horizontalSlider.valueChanged.connect(lambda: self.update_slice_display('sagittal'))
        self.Coronal_horizontalSlider.valueChanged.connect(lambda: self.update_slice_display('coronal'))

        # Image click signals
        self.Axial_ImagePreview.clicked.connect(lambda x, y: self.on_image_clicked('axial', x, y))
        self.Sagittal_ImagePreview.clicked.connect(lambda x, y: self.on_image_clicked('sagittal', x, y))
        self.Coronal_ImagePreview.clicked.connect(lambda x, y: self.on_image_clicked('coronal', x, y))
        
        # Electrode drag signals
        self.Axial_ImagePreview.marker_drag_started.connect(lambda e, c, i: self.on_marker_drag_started('axial', e, c, i))
        self.Sagittal_ImagePreview.marker_drag_started.connect(lambda e, c, i: self.on_marker_drag_started('sagittal', e, c, i))
        self.Coronal_ImagePreview.marker_drag_started.connect(lambda e, c, i: self.on_marker_drag_started('coronal', e, c, i))
        
        self.Axial_ImagePreview.marker_drag_ended.connect(lambda e, c, i, x, y: self.on_marker_drag_ended('axial', e, c, i, x, y))
        self.Sagittal_ImagePreview.marker_drag_ended.connect(lambda e, c, i, x, y: self.on_marker_drag_ended('sagittal', e, c, i, x, y))
        self.Coronal_ImagePreview.marker_drag_ended.connect(lambda e, c, i, x, y: self.on_marker_drag_ended('coronal', e, c, i, x, y))
        
        # Set movement enabled callback for each image label
        if self.electrode_controller:
            self.Axial_ImagePreview.set_movement_enabled_callback(self.electrode_controller.is_electrode_movement_enabled)
            self.Sagittal_ImagePreview.set_movement_enabled_callback(self.electrode_controller.is_electrode_movement_enabled)
            self.Coronal_ImagePreview.set_movement_enabled_callback(self.electrode_controller.is_electrode_movement_enabled)

        # Button signals
        self.AddElectrodePushButton.clicked.connect(self.on_add_electrode_clicked)
        self.LoadElectrodesPushButton.clicked.connect(self.on_load_electrodes_clicked)
        self.Viewer3dButton.clicked.connect(self.on_viewer3d_clicked)
        self.ProcessCoordinatesPushButton.clicked.connect(self.on_process_coordinates_clicked)
        self.SaveFilePushButton.clicked.connect(self.on_save_file_clicked)
        self.ExportMniPushButton.clicked.connect(self.on_export_mni_clicked)

        # Combo box signals
        self.ElectrodesComboBox.currentTextChanged.connect(self.update_coordinate_display)

        # Context menu signals
        self.ElectrodeTreeWidget.customContextMenuRequested.connect(self.on_electrode_context_menu_requested)
        self.DataTreeWidget.customContextMenuRequested.connect(self.on_data_tree_context_menu_requested)

        # Crosshair action from toolbar
        self.actionCrosshairs.triggered.connect(self.toggle_crosshairs)

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
        self.SetEntryPushButton.setEnabled(has_electrodes)
        self.SetOutputPushButton.setEnabled(has_electrodes)
        
        self.update_coordinate_display()

    def refresh_electrode_tree(self, specific_electrode_name=None):
        """Refresh the electrode tree widget."""
        electrode_name = specific_electrode_name or self.ElectrodesComboBox.currentText()
        if not electrode_name:
            return

        electrode = self.electrode_controller.get_electrode(electrode_name)
        if electrode:
            # Find and update the existing item
            root = self.ElectrodeTreeWidget.invisibleRootItem()
            for i in range(root.childCount()):
                item = root.child(i)
                if item.text(0) == electrode_name:
                    # Remember movement state and expansion state
                    movement_enabled = False
                    was_expanded = item.isExpanded()
                    if self.electrode_controller:
                        movement_enabled = self.electrode_controller.is_electrode_movement_enabled(electrode_name)
                    
                    # Remove old item
                    root.removeChild(item)
                    # Add new item with updated contacts
                    new_item = self.electrode_controller.create_tree_item(electrode)
                    root.insertChild(i, new_item)  # Insert at same position
                    new_item.setExpanded(was_expanded)  # Preserve expansion state
                    
                    # Add movement toggle button and restore state
                    self.add_movement_toggle_button(new_item, electrode_name)
                    if movement_enabled:
                        self.update_electrode_movement_state(electrode_name, True)
                    break

    def rebuild_electrode_tree(self):
        """Rebuild the entire electrode tree widget with all electrodes."""
        # Get all existing electrode names in the tree
        existing_names = set()
        root = self.ElectrodeTreeWidget.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            existing_names.add(item.text(0))
        
        # Add any missing electrodes from the model
        for electrode_name in self.electrode_controller.get_electrode_names():
            if electrode_name not in existing_names:
                electrode = self.electrode_controller.get_electrode(electrode_name)
                if electrode:
                    tree_item = self.electrode_controller.create_tree_item(electrode)
                    self.ElectrodeTreeWidget.addTopLevelItem(tree_item)
                    tree_item.setExpanded(True)  # Expand to show contacts
                    
                    # Add movement toggle button
                    self.add_movement_toggle_button(tree_item, electrode_name)

    def update_electrode_tree_item(self, old_name: str, new_name: str):
        """Update a specific electrode tree item after rename."""
        root = self.ElectrodeTreeWidget.invisibleRootItem()
        
        # Find and remove the old item
        for i in range(root.childCount()):
            item = root.child(i)
            if item.text(0) == old_name:
                # Remember if it was expanded
                was_expanded = item.isExpanded()
                
                # Remove the old item
                root.removeChild(item)
                
                # Get the renamed electrode and create new tree item
                electrode = self.electrode_controller.get_electrode(new_name)
                if electrode:
                    new_item = self.electrode_controller.create_tree_item(electrode)
                    root.insertChild(i, new_item)  # Insert at same position
                    new_item.setExpanded(was_expanded)  # Preserve expansion state
                    
                    # Add movement toggle button
                    self.add_movement_toggle_button(new_item, new_name)
                break
    
    def add_movement_toggle_button(self, tree_item, electrode_name):
        """Add movement toggle button to a tree item."""
        button = QPushButton()
        button.setCheckable(True)
        button.setChecked(False)  # Default: movement disabled
        button.setMaximumSize(50, 25)
        button.setToolTip("Enable/disable electrode movement")
        
        # Set button text and style
        self.update_toggle_button_appearance(button, False)
        
        # Connect button to handler
        button.clicked.connect(lambda checked, name=electrode_name: self.on_movement_toggle_clicked(name, checked))
        
        # Add button to tree widget
        self.ElectrodeTreeWidget.setItemWidget(tree_item, 4, button)
    
    def update_toggle_button_appearance(self, button, enabled):
        """Update the appearance of a movement toggle button."""
        if enabled:
            button.setText("🔓")
            button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: 1px solid #45a049;
                    border-radius: 3px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
        else:
            button.setText("🔐")
            button.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0;
                    color: #666;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """)
    
    def on_movement_toggle_clicked(self, electrode_name, enabled):
        """Handle movement toggle button click."""
        if self.electrode_controller:
            success = self.electrode_controller.toggle_electrode_movement(electrode_name, enabled)
            if success:
                # Update button appearance
                button = self.get_movement_toggle_button(electrode_name)
                if button:
                    self.update_toggle_button_appearance(button, enabled)
                
                # Show visual feedback
                status = "enabled" if enabled else "disabled"
                self.show_status_message(f"Movement {status} for electrode '{electrode_name}'", 2000)
    
    def get_movement_toggle_button(self, electrode_name):
        """Get the movement toggle button for a specific electrode."""
        root = self.ElectrodeTreeWidget.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.text(0) == electrode_name:
                return self.ElectrodeTreeWidget.itemWidget(item, 4)
        return None
    
    def update_electrode_movement_state(self, electrode_name, enabled):
        """Update electrode movement state in the UI."""
        button = self.get_movement_toggle_button(electrode_name)
        if button:
            button.setChecked(enabled)
            self.update_toggle_button_appearance(button, enabled)
    
    def show_status_message(self, message: str, timeout: int = 0) -> None:
        """Show status message in the status bar."""
        if hasattr(self, 'statusbar'):
            self.statusbar.showMessage(message, timeout)
    
    def on_marker_drag_started(self, orientation, electrode_name, coord_type, contact_index):
        """Handle marker drag started event."""
        # Visual feedback (orientation and contact_index are used for interface consistency)
        self.show_status_message(f"Dragging {electrode_name} {coord_type} point", 0)
    
    
    def on_marker_drag_ended(self, orientation, electrode_name, coord_type, contact_index, x, y):
        """Handle marker drag ended event - treat it like a click at the new position."""
        # Store the coordinates and electrode info for use in the simulated click
        self.last_clicked_coordinates = None
        self.drag_electrode_info = {
            'electrode_name': electrode_name,
            'coord_type': coord_type,
            'contact_index': contact_index
        }
        
        # Simulate a click at the drag end position - this uses the exact same logic as normal clicks
        self.on_image_clicked(orientation, x, y)
        
        # Now use the coordinates that were calculated by on_image_clicked
        if self.last_clicked_coordinates and self.electrode_controller:
            coords = self.last_clicked_coordinates
            
            # Update the electrode coordinate - same as setting it manually
            if coord_type in ['entry', 'output']:
                # Update entry/output point
                success = self.electrode_controller.move_electrode_coordinate(electrode_name, coord_type, coords)
            else:
                # Update individual contact point
                success = self.electrode_controller.move_contact_coordinate(electrode_name, contact_index, coords)
            
            if success:
                self.show_status_message(f"Moved {electrode_name} {coord_type} point to {coords}", 3000)
            else:
                self.show_status_message(f"Failed to move {electrode_name} {coord_type} point", 3000)
        else:
            self.show_status_message("No coordinates calculated", 3000)
        
        # Clean up
        self.drag_electrode_info = None

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

    def add_file_to_data_tree(self, file_path: str):
        """Add a loaded file to the DataTreeWidget."""
        import os
        
        # Extract filename from path
        file_name = os.path.basename(file_path)
        
        # Check if file already exists in tree
        root = self.DataTreeWidget.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.data(0, Qt.ItemDataRole.UserRole) == file_path:
                return
        
        # Create new tree item
        item = QTreeWidgetItem()
        item.setText(0, file_name)
        item.setData(0, Qt.ItemDataRole.UserRole, file_path)
        
        # Add to tree
        self.DataTreeWidget.addTopLevelItem(item)
        
        # Create visibility toggle button
        visibility_widget = QWidget()
        visibility_layout = QHBoxLayout(visibility_widget)
        visibility_layout.setContentsMargins(5, 0, 5, 0)
        
        visibility_btn = QPushButton()
        visibility_btn.setFixedSize(24, 24)
        visibility_btn.setCheckable(True)
        visibility_btn.setProperty('file_path', file_path)
        visibility_btn.clicked.connect(lambda checked, path=file_path: self.on_visibility_toggle(path, checked))
        
        # Set initial appearance
        self.update_visibility_button_appearance(visibility_btn, False)
        
        visibility_layout.addStretch()
        visibility_layout.addWidget(visibility_btn)
        visibility_layout.addStretch()
        
        # Set the widget in the second column
        self.DataTreeWidget.setItemWidget(item, 1, visibility_widget)
        
        # Auto-display first image when loaded
        current_base = self.image_controller.get_current_base_image_name()
        if not current_base:
            # No image currently displayed, make this one the base
            self.image_controller.set_overlay_images(file_name, file_name, 0.0)
        
        # Update all UI to reflect current state
        self.update_image_combo_boxes()
        self.update_all_visibility_buttons()
        self.refresh_all_views()

    def remove_file_from_data_tree(self, file_path: str):
        """Remove a file from the DataTreeWidget."""
        root = self.DataTreeWidget.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.data(0, Qt.ItemDataRole.UserRole) == file_path:
                root.removeChild(item)
                break
        
        # Update combo boxes after removing image
        self.update_image_combo_boxes()

    def remove_image(self, file_path: str):
        """Remove an image from the viewer."""
        self.image_controller.remove_image(file_path)
        
        # Update UI components after removal
        self.update_image_combo_boxes()  # Rebuild dropdown menus
        self.update_all_visibility_buttons()  # Update visibility button states
        self.refresh_all_views()  # Refresh the display

    def refresh_data_tree(self):
        """Refresh the data tree display."""
        # This method can be used to update the display status or other info
        # Currently just ensures the tree is properly displayed
        self.DataTreeWidget.update()

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

    def on_load_electrodes_clicked(self):
        """Handle load electrodes button click."""
        # Check if an image is loaded (required for coordinate transformation)
        if not self.image_controller.is_image_loaded():
            QMessageBox.warning(
                self, 
                "Warning", 
                "Please load an image first. The image is required for proper coordinate transformation."
            )
            return
        
        # Open file dialog to select electrode file
        default_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Load Electrode Coordinates", 
            default_dir, 
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return  # User cancelled
        
        # Get transformation data (image center and affine transform)
        image_center = self.image_controller.get_image_center_physical()
        affine_transform = self.image_controller.get_affine_transform()
        
        # Load electrodes using the controller
        success = self.electrode_controller.load_electrodes_from_file(
            file_path, 
            image_center, 
            affine_transform
        )
        
        if success:
            # Update electrode combo box to include newly loaded electrodes
            self.refresh_electrode_list()
            # Update coordinate display to show entry/output coordinates for loaded electrodes
            self.refresh_coordinate_display()

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
        if not self.electrode_controller.has_processed_contacts():
            QMessageBox.warning(self, "Warning", "No processed electrode contacts to save.")
            return
            
        # Check if we have a loaded image with affine transform
        if not self.image_controller.is_image_loaded() or self.image_controller.get_affine_transform() is None:
            QMessageBox.warning(self, "Warning", "No image loaded or missing affine transform.")
            return
        
        # Auto-detect subject directory from loaded images
        loaded_images = self.image_controller.get_loaded_images()
        if not loaded_images:
            QMessageBox.warning(self, "Warning", "No images loaded. Cannot detect subject directory.")
            return
            
        # Use first loaded image to detect subject directory
        image_path = Path(loaded_images[0])
        subject_dir = self._detect_subject_directory(image_path)
        
        if not subject_dir:
            # Fallback to manual selection
            subject_dir = QFileDialog.getExistingDirectory(self, "Select subject directory")
            if not subject_dir:
                return
            subject_dir = Path(subject_dir)
        
        # Create Subject instance and get transformation matrix
        subject = Subject(subject_dir)
        subject_name = subject.get_subject_name()

        # Ask where to save output (default to pipeline_output folder)
        default_path = str(subject.pipeline_output / f"{subject_name}_coordinates.json")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Subject Coordinates", 
            default_path,
            "JSON Files (*.json)"
        )
        
        if not file_path:
            return  # User cancelled
        
        try:
            # Prepare electrode data for the SlicerFile class
            electrodes_data = []
            for electrode in self.electrode_controller.get_electrodes_with_contacts():
                contacts = [(contact.x, contact.y, contact.z) for contact in electrode.contacts]
                electrodes_data.append({
                    'name': electrode.name,
                    'type': electrode.electrode_type,
                    'contacts': contacts
                })
            
            # Get image center for center-relative coordinates
            image_center = self.image_controller.get_image_center_physical()
            
            # Create and save the markup file
            slicer_file = SlicerFile()
            markup = slicer_file.create_markup(
                electrodes_data, 
                self.image_controller.get_affine_transform(),
                image_center
            )
            
            if slicer_file.save_to_file(file_path, markup):
                QMessageBox.information(self, "Success", f"Electrode coordinates saved to {file_path} in 3D Slicer format")
            else:
                raise Exception("Failed to save file")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save coordinates: {str(e)}")
            import traceback
            traceback.print_exc()

    def on_export_mni_clicked(self):
        """Handle export to MNI button click with automatic subject detection."""
        # Check if we have electrodes with contacts
        if not self.electrode_controller.has_processed_contacts():
            QMessageBox.warning(self, "Warning", "No processed electrode contacts to export.")
            return

        try:
            # Save coordinates to temp file (reuse existing save logic)
            temp_coord_file = os.path.join(tempfile.mkdtemp(), "temp_coordinates.json")
            
            # Prepare electrode data for the SlicerFile class
            electrodes_data = []
            for electrode in self.electrode_controller.get_electrodes_with_contacts():
                contacts = [(contact.x, contact.y, contact.z) for contact in electrode.contacts]
                electrodes_data.append({
                    'name': electrode.name,
                    'type': electrode.electrode_type,
                    'contacts': contacts
                })
            
            # Get image center for center-relative coordinates
            image_center = self.image_controller.get_image_center_physical()
            
            # Create and save the markup file
            slicer_file = SlicerFile()
            markup = slicer_file.create_markup(
                electrodes_data, 
                self.image_controller.get_affine_transform(),
                image_center
            )
            slicer_file.save_to_file(temp_coord_file, markup)
            
            # Auto-detect subject directory from loaded images
            loaded_images = self.image_controller.get_loaded_images()
            if not loaded_images:
                QMessageBox.warning(self, "Warning", "No images loaded. Cannot detect subject directory.")
                return
            
            # Use first loaded image to detect subject directory
            image_path = Path(loaded_images[0])
            subject_dir = self._detect_subject_directory(image_path)
            
            if not subject_dir:
                # Fallback to manual selection
                subject_dir = QFileDialog.getExistingDirectory(self, "Select subject directory")
                if not subject_dir:
                    return
                subject_dir = Path(subject_dir)
            
            # Create Subject instance and get transformation matrix
            subject = Subject(subject_dir)
            subject_name = subject.get_subject_name()
            transform_mat = subject.get_mni_transformation_matrix()
            
            if not transform_mat:
                QMessageBox.critical(self, "Error", 
                    f"Transformation matrix not found in pipeline_output.\n"
                    f"Expected patterns: MNI_{subject_name}_*.mat")
                return
            
            # Ask where to save output (default to pipeline_output folder)
            default_path = str(subject.pipeline_output / f"MNI_{subject_name}_coordinates.json")
            output_file, _ = QFileDialog.getSaveFileName(
                self, "Save MNI Coordinates", 
                default_path,
                "JSON Files (*.json)"
            )
            if not output_file:
                return
            
            # Call same function as CLI
            transform_coordinates(temp_coord_file, transform_mat, output_file)
            
            QMessageBox.information(self, "Success", f"Coordinates exported to MNI space:\n{output_file}")
            
            # Cleanup
            os.remove(temp_coord_file)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export to MNI: {str(e)}")

    def _detect_subject_directory(self, image_path: Path) -> Optional[Path]:
        """Detect subject root directory by traversing upward from image path."""
        current = image_path.parent
        
        # Traverse up to find directory containing expected subject structure
        for _ in range(10):  # Limit traversal depth
            if (current / 'images').exists() and (current / 'pipeline_output').exists():
                return current
            current = current.parent
            if current == current.parent:  # Reached filesystem root
                break
        
        return None

    def on_data_tree_context_menu_requested(self, position):
        """Handle right-click context menu for loaded images."""
        item = self.DataTreeWidget.itemAt(position)
        if item is None:
            return
        
        # Get selected items
        selected_items = self.DataTreeWidget.selectedItems()
        
        if not selected_items:
            return
        
        # Create context menu
        context_menu = QMenu(self)
        
        if len(selected_items) == 1:
            remove_action = context_menu.addAction("Remove Image")
        else:
            remove_action = context_menu.addAction(f"Remove {len(selected_items)} Images")
        
        # Show context menu and handle action
        action = context_menu.exec(self.DataTreeWidget.mapToGlobal(position))
        
        if action == remove_action:
            self.remove_selected_images(selected_items)

    def remove_selected_images(self, items):
        """Remove selected images from the viewer."""
        for item in items:
            file_path = item.data(0, Qt.ItemDataRole.UserRole)
            if file_path:
                self.remove_image(file_path)

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
        
        # Add rename option only for single electrode selection
        rename_action = None
        if len(electrode_items) == 1:
            rename_action = menu.addAction("Rename Electrode")
            menu.addSeparator()
        
        # Show appropriate delete text based on selection count
        if len(electrode_items) == 1:
            delete_action = menu.addAction("Delete Electrode")
        else:
            delete_action = menu.addAction(f"Delete {len(electrode_items)} Electrodes")
        
        # Show the menu and get the selected action
        action = menu.exec(self.ElectrodeTreeWidget.viewport().mapToGlobal(position))

        if action is not None and action is rename_action:
            self.rename_electrode(electrode_items[0])
        elif action is not None and action is delete_action:
            self.delete_electrodes(electrode_items)

    def delete_electrodes(self, items):
        """Delete multiple electrodes and their associated data."""
        electrode_names = [item.text(0) for item in items]
        
        if self.electrode_controller.delete_multiple_electrodes(electrode_names):
            # Remove from tree widget in reverse order to avoid index issues
            for item in reversed(items):
                self.ElectrodeTreeWidget.takeTopLevelItem(self.ElectrodeTreeWidget.indexOfTopLevelItem(item))

    def rename_electrode(self, item):
        """Rename an electrode and update all related data."""
        old_name = item.text(0)
        
        # Show input dialog to get new name
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(
            self, 
            "Rename Electrode", 
            f"Enter new name for electrode '{old_name}':",
            text=old_name
        )
        
        if not ok or not new_name.strip():
            return
        
        new_name = new_name.strip()
        
        # Check if new name is different
        if new_name == old_name:
            return
        
        # Check if new name already exists
        if self.electrode_controller.electrode_model.electrode_exists(new_name):
            QMessageBox.warning(self, "Warning", f"An electrode with the name '{new_name}' already exists.")
            return
        
        # Perform the rename through the controller
        if self.electrode_controller.rename_electrode(old_name, new_name):
            # Update the specific tree item with the new name and contacts
            self.update_electrode_tree_item(old_name, new_name)
            
            # Update combo box
            self.refresh_electrode_list()
            
            # Update coordinate display if this electrode was selected
            current_electrode = self.ElectrodesComboBox.currentText()
            if current_electrode == new_name:
                self.update_coordinate_display(new_name)
            
            # Refresh image display to update any markers
            self.refresh_image_display()
        else:
            QMessageBox.critical(self, "Error", f"Failed to rename electrode '{old_name}' to '{new_name}'.")

    def on_set_entry_clicked(self):
        """Handle set entry button click."""
        # Check if an electrode is selected
        electrode_name = self.ElectrodesComboBox.currentText()
        if not electrode_name:
            QMessageBox.warning(self, "Warning", "Please select an electrode first.")
            return

        # Check if we have stored coordinates from a previous image click
        if self.last_clicked_coordinates is None:
            QMessageBox.information(self, "Information", "Please click on an image first to select coordinates.")
            return

        # Set the entry coordinates using the stored coordinates
        self.electrode_controller.set_entry_coordinate(electrode_name, self.last_clicked_coordinates)
        
        # Update coordinate display
        self.update_coordinate_display(electrode_name)
        
        # Refresh all views to show the electrode marker immediately
        self.refresh_all_views()
        
        # Clear the stored coordinates after use
        self.last_clicked_coordinates = None

    def on_set_output_clicked(self):
        """Handle set output button click."""
        # Check if an electrode is selected
        electrode_name = self.ElectrodesComboBox.currentText()
        if not electrode_name:
            QMessageBox.warning(self, "Warning", "Please select an electrode first.")
            return

        # Check if we have stored coordinates from a previous image click
        if self.last_clicked_coordinates is None:
            QMessageBox.information(self, "Information", "Please click on an image first to select coordinates.")
            return

        # Set the output coordinates using the stored coordinates
        self.electrode_controller.set_output_coordinate(electrode_name, self.last_clicked_coordinates)
        
        # Update coordinate display
        self.update_coordinate_display(electrode_name)
        
        # Refresh all views to show the electrode marker immediately
        self.refresh_all_views()
        
        # Clear the stored coordinates after use
        self.last_clicked_coordinates = None

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

        # Note: x, y are now in pixmap coordinates (from the enhanced ClickableImageLabel)
        # We need to convert these to label coordinates for the existing coordinate system
        
        # For the enhanced ClickableImageLabel, coordinates are already in pixmap space
        # So we need to calculate the offset to simulate the label coordinate system
        pixmap_width = pixmap.width()
        pixmap_height = pixmap.height()
        label_width = label.width()
        label_height = label.height()
        
        # Calculate offset as if the pixmap was centered in the label
        x_offset = (label_width - pixmap_width) // 2
        y_offset = (label_height - pixmap_height) // 2
        
        # Convert pixmap coordinates to label coordinates
        label_x = x + x_offset
        label_y = y + y_offset

        # Get 3D coordinates from image controller using the converted coordinates
        coords = self.image_controller.get_3d_coordinates_from_click(
            orientation, label_x, label_y,
            label_width, label_height,
            pixmap_width, pixmap_height,
            current_slices
        )

        if coords is None:
            return

        x_coord, y_coord, z_coord = coords

        # If crosshairs are enabled, set the crosshair position to the clicked point
        if self.crosshair_controller.is_enabled():
            self.crosshair_controller.set_crosshair_position((x_coord, y_coord, z_coord))

        # Update other views to show the clicked point (same for crosshairs or normal mode)
        if orientation == 'axial':
            self.Sagittal_horizontalSlider.setValue(x_coord)
            self.Coronal_horizontalSlider.setValue(y_coord)
        elif orientation == 'sagittal':
            self.Axial_horizontalSlider.setValue(z_coord)
            self.Coronal_horizontalSlider.setValue(y_coord)
        else:  # coronal
            self.Axial_horizontalSlider.setValue(z_coord)
            self.Sagittal_horizontalSlider.setValue(x_coord)

        # Store the coordinates for later use by the push buttons
        self.last_clicked_coordinates = coords
        
        # Refresh all views if crosshairs are enabled
        if self.crosshair_controller.is_enabled():
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

            # Create clean pixmap without electrode points (just the image)
            slice_data = self.image_controller.get_slice_data_for_display(orientation, slider.value())
            if slice_data is None:
                # No image data - clear the display
                label.clear()
                label.setText("No image loaded")
                return
                
            # Create pixmap without electrode overlays
            pixmap = self.image_controller.create_clean_pixmap_for_display(
                slice_data, orientation, label.width(), label.height()
            )

            if pixmap:
                # Set the clean pixmap (this will preserve zoom due to our improved setPixmap method)
                label.setPixmap(pixmap)
                
                # Clear existing markers and lines for this view
                label.clear_markers()
                label.clear_lines()
                
                # Add markers for visible electrode points
                self._add_visible_electrode_markers(label, orientation, slider.value())

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to update display: {str(e)}")
    
    def _add_visible_electrode_markers(self, label, orientation, slice_index):
        """Add markers for electrode points visible on the current slice."""
        # Get current slice indices
        current_slices = {
            'axial': self.Axial_horizontalSlider.value(),
            'sagittal': self.Sagittal_horizontalSlider.value(),
            'coronal': self.Coronal_horizontalSlider.value()
        }
        
        # Get the actual pixmap to determine scaling
        pixmap = label.pixmap()
        if not pixmap:
            return
        
        scaled_width = pixmap.width()
        scaled_height = pixmap.height()
        
        # Update crosshairs if enabled (efficient update, no redraw)
        if self.crosshair_controller.is_enabled():
            self.crosshair_controller.update_crosshairs_for_view(label, orientation, current_slices, scaled_width, scaled_height)
        
        # Get electrode points
        electrode_points = self.electrode_controller.get_electrode_points_for_display()
        processed_contacts = self.electrode_controller.get_processed_contacts_for_display()
        electrode_structures = self.electrode_controller.get_electrode_structures_for_display()
        
        # Add entry/output point markers
        for electrode_name, points in electrode_points.items():
            hue = abs(hash(electrode_name)) % 360
            from PyQt6.QtGui import QColor
            electrode_color = QColor()
            electrode_color.setHsv(hue, 200, 255, 180)
            
            for point_type, point in points.items():
                if self.image_controller.is_point_visible_on_slice(point, orientation, current_slices):
                    pixel_coords = self.image_controller.convert_3d_to_pixel_coords(
                        point, orientation, scaled_width, scaled_height
                    )
                    if pixel_coords:
                        x, y = pixel_coords
                        label.add_marker(x, y, electrode_color, radius=0.5, 
                                       electrode_name=electrode_name, 
                                       coord_type=point_type, 
                                       contact_index=-1)
        
        # Add processed contact markers
        for electrode_name, contacts in processed_contacts.items():
            hue = abs(hash(electrode_name)) % 360
            from PyQt6.QtGui import QColor
            contact_color = QColor()
            contact_color.setHsv(hue, 200, 255, 180)
            
            for contact_index, contact_point in enumerate(contacts):
                if self.image_controller.is_point_visible_on_slice(contact_point, orientation, current_slices):
                    pixel_coords = self.image_controller.convert_3d_to_pixel_coords(
                        contact_point, orientation, scaled_width, scaled_height
                    )
                    if pixel_coords:
                        x, y = pixel_coords
                        label.add_marker(x, y, contact_color, radius=1,
                                       electrode_name=electrode_name,
                                       coord_type='contact',
                                       contact_index=contact_index)
        
        # Add electrode tail visualization
        for electrode_name, structure in electrode_structures.items():
            if structure.has_tail and structure.tail_endpoint:
                # Get output point from electrode points (tail extends outward from output point)
                # CORRECTED: output = "End - distal part" (closer to skull surface, where tail starts)
                if electrode_name in electrode_points and 'output' in electrode_points[electrode_name]:
                    hue = abs(hash(electrode_name)) % 360
                    tail_color = QColor()
                    tail_color.setHsv(hue, 150, 200, 120)  # Slightly more transparent/muted than contacts
                    
                    output_point = electrode_points[electrode_name]['output']
                    tail_endpoint = structure.tail_endpoint
                    
                    # Check if either point is visible on this slice
                    if (self.image_controller.is_point_visible_on_slice(output_point, orientation, current_slices) or
                        self.image_controller.is_point_visible_on_slice(tail_endpoint, orientation, current_slices)):
                        
                        # Convert to pixel coordinates
                        output_point_pixel = self.image_controller.convert_3d_to_pixel_coords(
                            output_point, orientation, scaled_width, scaled_height
                        )
                        tail_endpoint_pixel = self.image_controller.convert_3d_to_pixel_coords(
                            tail_endpoint, orientation, scaled_width, scaled_height
                        )
                        
                        if output_point_pixel and tail_endpoint_pixel:
                            # Add line segment for tail (from output point outward toward skull exterior)
                            label.add_line(
                                output_point_pixel[0], output_point_pixel[1],
                                tail_endpoint_pixel[0], tail_endpoint_pixel[1],
                                tail_color, width=3,
                                electrode_name=electrode_name,
                                segment_type='tail'
                            )
    
    def remove_all_crosshairs(self):
        """Remove crosshairs from all views - called by crosshair controller."""
        for label in [self.Axial_ImagePreview, self.Sagittal_ImagePreview, self.Coronal_ImagePreview]:
            label.remove_crosshairs()

    def resizeEvent(self, event):
        """Handle window resize events to update the display."""
        super().resizeEvent(event)
        # Use debounce timer to avoid excessive refreshes during resize
        self._resize_timer.stop()
        self._resize_timer.start(100)  # 100ms delay
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self._cleanup_callback:
            self._cleanup_callback()
        super().closeEvent(event)
    
    # =============================================================================
    # IImageView Interface Implementation
    # =============================================================================
    
    def load_image_file(self, file_path: str) -> bool:
        """Load an image file for display."""
        return self.image_controller.load_image(file_path)
    
    def set_slice_range(self, orientation: str, min_slice: int, max_slice: int) -> None:
        """Set the valid slice range for an orientation."""
        if orientation == 'axial':
            slider = self.Axial_horizontalSlider
        elif orientation == 'sagittal':
            slider = self.Sagittal_horizontalSlider
        elif orientation == 'coronal':
            slider = self.Coronal_horizontalSlider
        else:
            return
        
        slider.setMinimum(min_slice)
        slider.setMaximum(max_slice)
    
    def update_overlay_opacity(self, opacity: float) -> None:
        """Update overlay opacity."""
        # Update the opacity controls if they exist
        if hasattr(self, 'opacity_slider') and self.opacity_slider:
            self.opacity_slider.setValue(int(opacity * 100))
    
    def refresh_overlay_controls(self) -> None:
        """Refresh overlay control widgets."""
        self.rebuild_all_overlay_menus()
        self.update_image_combo_boxes()
    
    def enable_electrode_controls(self, enabled: bool) -> None:
        """Enable or disable electrode control widgets."""
        self.AddElectrode_pushButton.setEnabled(enabled)
        self.SetEntryPushButton.setEnabled(enabled)
        self.SetOutputPushButton.setEnabled(enabled)
        self.ElectrodeNameLineEdit.setEnabled(enabled)
        self.ElectrodeTypeComboBox.setEnabled(enabled)
    
    def show_crosshairs(self, show: bool) -> None:
        """Show or hide crosshairs."""
        self.crosshair_controller.toggle_crosshairs(show)
    
    def update_crosshair_position(self, x: int, y: int, z: int) -> None:
        """Update crosshair position."""
        self.crosshair_controller.set_crosshair_position((x, y, z))
    
    def synchronize_crosshairs(self) -> None:
        """Synchronize crosshairs across all views."""
        self.refresh_all_views()
    
    def clear_data_tree(self) -> None:
        """Clear the data tree."""
        self.DataTreeWidget.clear()
    
    # =============================================================================
    # IBaseView Interface Implementation
    # =============================================================================
    
    def show_error_message(self, title: str, message: str) -> None:
        """Show an error message to the user."""
        QMessageBox.critical(self, title, message)
    
    def show_warning_message(self, title: str, message: str) -> None:
        """Show a warning message to the user."""
        QMessageBox.warning(self, title, message)
    
    def show_info_message(self, title: str, message: str) -> None:
        """Show an info message to the user."""
        QMessageBox.information(self, title, message)
    
    def set_busy_state(self, busy: bool) -> None:
        """Set the view to busy state (e.g., show loading cursor)."""
        if busy:
            self.setCursor(QCursor(Qt.CursorShape.WaitCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
    
    def get_widget(self) -> QWidget:
        """Get the underlying QWidget for this view."""
        return self

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    file_path = sys.argv[1] if len(sys.argv) > 1 else None
    viewer = ImagesViewer(file_path)
    viewer.show()
    sys.exit(app.exec())