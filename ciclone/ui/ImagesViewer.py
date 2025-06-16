import os
from typing import Dict, Optional, List, Tuple
import numpy as np

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

from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QBrush, QMouseEvent

from ciclone.models.image_model import ImageModel
from ciclone.controllers.image_controller import ImageController
from ciclone.domain.electrodes import Electrode
from ciclone.controllers.electrode_controller import ElectrodeController
from ciclone.services.io.slicer_file import SlicerFile
from ciclone.ui.Viewer3D import Viewer3D
from ciclone.forms.ImagesViewer_ui import Ui_ImagesViewer

# Import new MVC components
from ciclone.models import ElectrodeModel, CoordinateModel

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

        # Track if we're in fitted mode (auto-resize) or user zoom mode
        self._is_fitted_mode = True
        
        # Timer for debouncing resize events
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self.refresh_all_views)

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

        # Configure column sizing for DataTreeWidget
        self.DataTreeWidget.setColumnCount(2)
        self.DataTreeWidget.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.DataTreeWidget.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.DataTreeWidget.setColumnWidth(1, 50)  # Width for visibility button
        
        # Setup opacity controls near image sliders
        self.setup_image_opacity_controls()
        
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
        
        # Enable context menu for DataTreeWidget
        self.DataTreeWidget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # Enable multi-selection for data tree (images)
        self.DataTreeWidget.setSelectionMode(self.DataTreeWidget.SelectionMode.ExtendedSelection)
        
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
        # Radio button signals
        self.SetEntryRadioButton.clicked.connect(lambda: self.on_coordinate_radio_clicked('entry'))
        self.SetOutputRadioButton.clicked.connect(lambda: self.on_coordinate_radio_clicked('output'))

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

        # Button signals
        self.AddElectrodePushButton.clicked.connect(self.on_add_electrode_clicked)
        self.Viewer3dButton.clicked.connect(self.on_viewer3d_clicked)
        self.ProcessCoordinatesPushButton.clicked.connect(self.on_process_coordinates_clicked)
        self.SaveFilePushButton.clicked.connect(self.on_save_file_clicked)

        # Combo box signals
        self.ElectrodesComboBox.currentTextChanged.connect(self.update_coordinate_display)

        # Context menu signals
        self.ElectrodeTreeWidget.customContextMenuRequested.connect(self.on_electrode_context_menu_requested)
        self.DataTreeWidget.customContextMenuRequested.connect(self.on_data_tree_context_menu_requested)

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

    # Old opacity methods removed - replaced with new two-image overlay system

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
        elif self.setting_output:
            self.electrode_controller.set_output_coordinate(electrode_name, coords)
        
        # Only refresh if we actually set a coordinate
        if self.setting_entry or self.setting_output:
            # Refresh all views together to avoid cascade issues
            # The slider updates above will change the slice positions,
            # and we want to show the electrode points on all affected views
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
            slice_data = self.image_controller.image_model.get_slice_data(orientation, slider.value())
            if slice_data is None:
                # No image data - clear the display
                label.clear()
                label.setText("No image loaded")
                return
                
            # Create pixmap without electrode overlays
            pixmap = self.image_controller.image_model.create_slice_pixmap_clean(
                slice_data, orientation, label.width(), label.height()
            )

            if pixmap:
                # Set the clean pixmap (this will preserve zoom due to our improved setPixmap method)
                label.setPixmap(pixmap)
                
                # Clear existing markers for this view
                label.clear_markers()
                
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
        
        # Get electrode points
        electrode_points = self.electrode_controller.get_electrode_points_for_display()
        processed_contacts = self.electrode_controller.get_processed_contacts_for_display()
        
        # Add entry/output point markers
        for electrode_name, points in electrode_points.items():
            hue = abs(hash(electrode_name)) % 360
            from PyQt6.QtGui import QColor
            electrode_color = QColor()
            electrode_color.setHsv(hue, 200, 255, 180)
            
            for point_type, point in points.items():
                if self._is_point_visible(point, orientation, current_slices):
                    pixel_coords = self._convert_3d_to_pixel_coords(
                        point, orientation, scaled_width, scaled_height
                    )
                    if pixel_coords:
                        x, y = pixel_coords
                        label.add_marker(x, y, electrode_color, radius=5)
        
        # Add processed contact markers
        for electrode_name, contacts in processed_contacts.items():
            hue = abs(hash(electrode_name)) % 360
            from PyQt6.QtGui import QColor
            contact_color = QColor()
            contact_color.setHsv(hue, 200, 255, 180)
            
            for contact_point in contacts:
                if self._is_point_visible(contact_point, orientation, current_slices):
                    pixel_coords = self._convert_3d_to_pixel_coords(
                        contact_point, orientation, scaled_width, scaled_height
                    )
                    if pixel_coords:
                        x, y = pixel_coords
                        label.add_marker(x, y, contact_color, radius=5)
    
    def _is_point_visible(self, point, orientation, current_slices):
        """Check if a 3D point is visible on the current slice."""
        x, y, z = point
        
        if orientation == 'axial' and abs(z - current_slices['axial']) <= 1:
            return True
        elif orientation == 'sagittal' and abs(x - current_slices['sagittal']) <= 1:
            return True
        elif orientation == 'coronal' and abs(y - current_slices['coronal']) <= 1:
            return True
        
        return False
    
    def _convert_3d_to_pixel_coords(self, point, orientation, scaled_width, scaled_height):
        """Convert 3D coordinates to pixel coordinates for the current view."""
        x, y, z = point
        volume_data = self.image_controller.image_model._volume_data
        
        if volume_data is None:
            return None
        
        # Use the same logic as the original _draw_point_if_visible method
        if orientation == 'axial':
            pixel_x = int(x * scaled_width / volume_data.shape[0])
            pixel_y = int((volume_data.shape[1] - 1 - y) * scaled_height / volume_data.shape[1])
        elif orientation == 'sagittal':
            pixel_x = int((volume_data.shape[1] - 1 - y) * scaled_width / volume_data.shape[1])
            pixel_y = int((volume_data.shape[2] - 1 - z) * scaled_height / volume_data.shape[2])
        elif orientation == 'coronal':
            pixel_x = int(x * scaled_width / volume_data.shape[0])
            pixel_y = int((volume_data.shape[2] - 1 - z) * scaled_height / volume_data.shape[2])
        else:
            return None
        
        return (pixel_x, pixel_y)

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
        # Use debounce timer to avoid excessive refreshes during resize
        self._resize_timer.stop()
        self._resize_timer.start(100)  # 100ms delay

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