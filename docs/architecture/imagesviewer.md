# ImagesViewer Architecture Guide

This document provides a comprehensive guide to the ImagesViewer component architecture, covering its role as a specialized medical image viewer, MVC coordination patterns, and electrode localization capabilities.

## Overview

The ImagesViewer serves as CiCLONE's specialized medical image viewer, designed specifically for neurosurgical electrode localization. It implements a distributed controller pattern where multiple specialized controllers coordinate to provide seamless medical image interaction, electrode management, and coordinate system handling.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                 ImagesViewer                                   │
│                            (QMainWindow + UI)                                  │
│                                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │ Image Display   │  │ Electrode       │  │ Data Tree       │                │
│  │ - Axial View    │  │ Controls        │  │ - Loaded Files  │                │
│  │ - Sagittal View │  │ - Entry/Output  │  │ - Visibility    │                │
│  │ - Coronal View  │  │ - Coordinates   │  │ - Overlay       │                │
│  │ - Crosshairs    │  │ - Tree View     │  │ - Context Menu  │                │
│  │ - Sliders       │  │ - Processing    │  │                 │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
│           │                     │                     │                        │
│           └─────────────────────┼─────────────────────┘                        │
│                                 │                                              │
└─────────────────────────────────┼──────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          Controller Coordination                               │
│                                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │ Image           │  │ Electrode       │  │ Crosshair       │                │
│  │ Controller      │  │ Controller      │  │ Controller      │                │
│  │ - Load Images   │  │ - CRUD Ops      │  │ - Toggle        │                │
│  │ - Slice Nav     │  │ - Coordinates   │  │ - Position      │                │
│  │ - Overlays      │  │ - Contacts      │  │ - Sync Views    │                │
│  │ - Coords        │  │ - Import/Export │  │ - Display       │                │
│  │ - Pixmaps       │  │ - Tree Updates  │  │                 │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
│           │                     │                     │                        │
│           └─────────────────────┼─────────────────────┘                        │
│                                 │                                              │
└─────────────────────────────────┼──────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                               Model Layer                                      │
│                                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │ ImageModel      │  │ ElectrodeModel  │  │ CrosshairModel  │                │
│  │ - NIFTI Data    │  │ - Electrode     │  │ - Position      │                │
│  │ - Affine        │  │   Definitions   │  │ - Enabled State │                │
│  │ - Slices        │  │ - Coordinates   │  │ - Appearance    │                │
│  │ - Overlay       │  │ - Contacts      │  │                 │                │
│  │ - Pixmaps       │  │ - Validation    │  │                 │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
│           │                     │                     │                        │
│           └─────────────────────┼─────────────────────┘                        │
│                                 │                                              │
│  ┌─────────────────┐            │            ┌─────────────────┐                │
│  │ CoordinateModel │            │            │ Services        │                │
│  │ - 3D Coords     │            │            │ - Slicer Files  │                │
│  │ - Transforms    │            │            │ - Electrode     │                │
│  │ - Validation    │            │            │   Definitions   │                │
│  └─────────────────┘            │            └─────────────────┘                │
│           │                     │                     │                        │
│           └─────────────────────┼─────────────────────┘                        │
│                                 │                                              │
└─────────────────────────────────┼──────────────────────────────────────────────┘
```

## Core Components

### ImagesViewer Class

**Location**: `ciclone/ui/ImagesViewer.py:43-1615`

**Inheritance**: `QMainWindow`, `Ui_ImagesViewer`

#### Key Responsibilities

1. **Medical Image Display**
   - Multi-planar reconstruction (axial, sagittal, coronal views)
   - Advanced overlay system with opacity control
   - Real-time slice navigation with synchronized views
   - Professional medical imaging interface

2. **Electrode Management**
   - Interactive electrode placement and visualization
   - Entry/output coordinate setting with push-button workflow
   - Electrode contact processing and display
   - Import/export electrode data in 3D Slicer format

3. **Coordinate System Management**
   - 3D coordinate transformation between views
   - Click-to-coordinate conversion for precise positioning
   - Crosshair synchronization across all views
   - Medical-grade coordinate accuracy

4. **Advanced UI Features**
   - Gear button overlay control system
   - Visibility toggles for multiple images
   - Context menus for file and electrode management
   - Professional UX optimized for neurosurgical workflows

#### MVC Initialization

```python
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
```

## Controller Specifications

### ImageController

**Location**: `ciclone/controllers/image_controller.py`

**Purpose**: Medical image management and display coordination

#### Key Responsibilities

1. **Image Loading and Validation**
   ```python
   def load_image(self, file_path: str) -> bool:
       """Load NIFTI medical image with validation and error handling."""
       # Validate file format and accessibility
       # Load through ImageModel with NiBabel
       # Update view with new image data
       # Configure slice ranges and initial display
   ```

2. **Slice Management and Navigation**
   ```python
   def get_slice_data_for_display(self, orientation: str, slice_index: int):
       """Extract slice data for specific orientation and index."""
       # Extract 2D slice from 3D volume
       # Apply overlay blending if configured
       # Return processed slice data for display
   
   def get_slice_range(self, orientation: str) -> tuple[int, int]:
       """Get valid slice range for orientation."""
       # Calculate min/max slice indices based on volume dimensions
   ```

3. **Coordinate Transformation**
   ```python
   def get_3d_coordinates_from_click(self, orientation: str, x: int, y: int, 
                                   label_width: int, label_height: int,
                                   pixmap_width: int, pixmap_height: int,
                                   current_slices: dict) -> tuple[float, float, float]:
       """Convert 2D click coordinates to 3D volume coordinates."""
       # Account for label scaling and positioning
       # Apply orientation-specific coordinate mapping
       # Return precise 3D coordinates for medical use
   ```

4. **Advanced Overlay System**
   ```python
   def set_overlay_images(self, base_name: str, overlay_name: str, opacity: float):
       """Configure base/overlay image combination with opacity."""
       # Validate image compatibility
       # Configure overlay blending parameters
       # Update all views with new overlay configuration
   
   def clear_overlay_state(self):
       """Clear overlay configuration and return to single image display."""
   ```

5. **Pixmap Generation and Caching**
   ```python
   def create_clean_pixmap_for_display(self, slice_data, orientation: str, 
                                     display_width: int, display_height: int):
       """Create optimized pixmap for display with proper scaling."""
       # Apply medical image windowing and scaling
       # Optimize for display performance
       # Cache frequently accessed slices
   ```

#### Integration with View

The ImageController updates the ImagesViewer through well-defined interface methods:

```python
# View interface methods called by controller
def refresh_image_display(self) -> None
def update_slider_ranges(self) -> None
def enable_image_controls(self) -> None
def add_file_to_data_tree(self, file_path: str) -> None
def remove_file_from_data_tree(self, file_path: str) -> None
```

### ElectrodeController

**Location**: `ciclone/controllers/electrode_controller.py`

**Purpose**: Electrode management and coordinate processing

#### Key Responsibilities

1. **Electrode CRUD Operations**
   ```python
   def create_electrode(self, name: str, electrode_type: str) -> bool:
       """Create new electrode with validation and conflict checking."""
       # Validate electrode name uniqueness
       # Load electrode definition from .elecdef files
       # Create electrode instance in model
       # Update view with new electrode
   
   def delete_multiple_electrodes(self, electrode_names: list) -> bool:
       """Delete multiple electrodes with proper cleanup."""
   
   def rename_electrode(self, old_name: str, new_name: str) -> bool:
       """Rename electrode with data integrity preservation."""
   ```

2. **Coordinate Management**
   ```python
   def set_entry_coordinate(self, electrode_name: str, coordinates: tuple):
       """Set entry (proximal) coordinate for electrode."""
       # Validate coordinate format and range
       # Store in CoordinateModel
       # Update view coordinate display
       # Trigger image refresh for visual feedback
   
   def set_output_coordinate(self, electrode_name: str, coordinates: tuple):
       """Set output (distal) coordinate for electrode."""
   ```

3. **Contact Processing**
   ```python
   def process_electrode_coordinates(self, electrode_name: str):
       """Generate electrode contacts from entry/output coordinates."""
       # Retrieve electrode definition and coordinates
       # Calculate contact positions along electrode trajectory
       # Apply electrode-specific spacing and configuration
       # Update model with processed contacts
       # Refresh view to display contacts
   ```

4. **File Import/Export with Conflict Resolution**
   ```python
   def load_electrodes_from_file(self, file_path: str, image_center, affine_transform):
       """Load electrodes from 3D Slicer JSON with intelligent conflict handling."""
       # Parse Slicer markup file format
       # Apply coordinate transformations (center-relative to absolute)
       # Detect and resolve naming conflicts
       # Preserve existing electrode data when appropriate
       # Provide user feedback on import results
   ```

5. **UI Integration and State Management**
   ```python
   def get_electrode_types(self) -> list:
       """Get available electrode types from definition files."""
   
   def create_tree_item(self, electrode) -> QTreeWidgetItem:
       """Create UI tree item for electrode with contacts."""
   
   def get_electrode_points_for_display(self) -> dict:
       """Get electrode entry/output points for view overlay."""
   
   def get_processed_contacts_for_display(self) -> dict:
       """Get processed contact coordinates for view overlay."""
   ```

#### Integration with Models

The ElectrodeController coordinates between multiple models:

```python
# ElectrodeModel integration
self.electrode_model.add_electrode(electrode)
self.electrode_model.delete_electrode(name)

# CoordinateModel integration  
self.coordinate_model.set_entry_coordinate(electrode_name, coordinates)
self.coordinate_model.set_output_coordinate(electrode_name, coordinates)

# Cross-model coordination for contact processing
coordinates = self.coordinate_model.get_coordinates(electrode_name)
electrode = self.electrode_model.get_electrode(electrode_name)
# Process contacts using both sources
```

### CrosshairController

**Location**: `ciclone/controllers/crosshair_controller.py`

**Purpose**: Crosshair display and synchronization across views

#### Key Responsibilities

1. **Crosshair State Management**
   ```python
   def toggle_crosshairs(self, enabled: bool):
       """Enable or disable crosshair display across all views."""
       # Update CrosshairModel state
       # Coordinate with all image views
       # Handle toolbar button state
   
   def is_enabled(self) -> bool:
       """Check if crosshairs are currently enabled."""
   ```

2. **Position Coordination**
   ```python
   def set_crosshair_position(self, position: tuple[float, float, float]):
       """Set crosshair position and update all views."""
       # Store position in CrosshairModel
       # Calculate view-specific crosshair positions
       # Update all orientation views simultaneously
   
   def get_crosshair_position(self) -> tuple[float, float, float]:
       """Get current crosshair position in 3D space."""
   ```

3. **View Synchronization**
   ```python
   def update_crosshairs_for_view(self, label, orientation: str, 
                                current_slices: dict, scaled_width: int, scaled_height: int):
       """Update crosshairs for specific view with efficient rendering."""
       # Calculate crosshair position for orientation
       # Convert 3D position to 2D pixel coordinates
       # Update view-specific crosshair display
       # Optimize for performance (no unnecessary redraws)
   ```

4. **Integration with ImageController**
   ```python
   def __init__(self, crosshair_model: CrosshairModel, image_controller: ImageController):
       """Initialize with dependency on ImageController for coordinate conversion."""
       # Use ImageController for coordinate transformations
       # Leverage existing image display infrastructure
       # Maintain loose coupling through well-defined interfaces
   ```

#### Crosshair Rendering System

The CrosshairController implements an efficient rendering system:

```python
# Crosshair display on ClickableImageLabel
def add_crosshair(self, x: int, y: int, color=QColor(255, 255, 0), line_width=2):
    """Add crosshair overlay to image label."""
    # Use QPainter for efficient crosshair rendering
    # Optimize for real-time updates during interaction
    # Maintain visual quality at all zoom levels

def remove_crosshairs(self):
    """Remove all crosshairs from view."""
    # Clean crosshair state
    # Trigger efficient view refresh
```

## Data Flow Patterns

### Image Loading and Display Flow

```
File Selection → ImagesViewer → ImageController → ImageModel
    ↓
NIFTI Loading → NiBabel Processing → Volume Data Storage
    ↓
Slice Extraction → Pixmap Generation → View Updates
    ↓
UI Updates → Slider Configuration → Data Tree Update
```

**Detailed Example**:

1. **File Selection**: User selects NIFTI file through file dialog or drag-drop
2. **Controller Delegation**: ImagesViewer delegates to ImageController.load_image()
3. **Model Processing**: ImageModel loads file with NiBabel, validates format
4. **Affine Processing**: Extract affine transformation matrix for coordinate conversion
5. **Slice Range Calculation**: Determine valid slice ranges for each orientation
6. **View Updates**: Update sliders, enable controls, refresh displays
7. **Data Tree Integration**: Add file to data tree with visibility controls

### Electrode Coordinate Setting Flow

```
Image Click → ImagesViewer → ImageController → 3D Coordinates
    ↓
Coordinate Storage → last_clicked_coordinates → User Button Press
    ↓
Set Entry/Output → ElectrodeController → CoordinateModel
    ↓
Coordinate Display Update → View Refresh → Visual Feedback
```

**Detailed Example**:

1. **Image Interaction**: User clicks on image view (axial, sagittal, or coronal)
2. **Coordinate Conversion**: ImageController converts click to 3D coordinates
3. **Coordinate Storage**: Store coordinates in `last_clicked_coordinates`
4. **Button Interaction**: User clicks "Set Entry" or "Set Output" button
5. **Controller Processing**: ElectrodeController validates and stores coordinates
6. **Model Updates**: CoordinateModel stores coordinate data
7. **View Updates**: Coordinate display updated, image views refreshed
8. **Visual Feedback**: Electrode markers displayed on all relevant views

### Advanced Overlay System Flow

```
Gear Button Click → Overlay Menu → Image Selection → Opacity Control
    ↓
ImageController → Base/Overlay Configuration → Blend Processing
    ↓
All Views Update → Synchronized Display → Real-time Feedback
```

**Detailed Example**:

1. **Menu Activation**: User clicks gear button next to image slider
2. **Menu Population**: Populate dropdowns with currently loaded images
3. **Image Selection**: User selects base and overlay images
4. **Opacity Control**: User adjusts opacity slider with real-time feedback
5. **Controller Coordination**: ImageController configures overlay blending
6. **Processing**: Apply overlay blending with specified opacity
7. **View Synchronization**: All three views (axial, sagittal, coronal) update simultaneously
8. **Visual Feedback**: Real-time preview with percentage display

### Crosshair Synchronization Flow

```
Image Click → Crosshair Position → CrosshairController → All Views Update
    ↓
3D Coordinate → View-Specific Conversion → Crosshair Rendering
    ↓
Synchronized Display → Medical-Grade Precision → User Feedback
```

## Advanced Features

### Gear Button Overlay System

The ImagesViewer implements a sophisticated overlay control system:

```python
def setup_image_opacity_controls(self):
    """Setup gear buttons near image sliders that open overlay control panels."""
    # Create gear buttons for each orientation (axial, sagittal, coronal)
    # Position buttons next to existing slice sliders
    # Create popup menus with overlay controls
    # Integrate with existing UI layout seamlessly

def rebuild_all_overlay_menus(self):
    """Rebuild all overlay control menus with current two-image system."""
    # Populate base/overlay image dropdowns
    # Configure opacity slider with real-time feedback
    # Set up signal connections for immediate updates
    # Optimize for smooth user interaction
```

**Features**:
- **Intuitive Interface**: Gear buttons provide discoverable overlay controls
- **Real-time Feedback**: Opacity changes update immediately across all views
- **Professional UX**: Non-intrusive design suitable for clinical environments
- **Synchronized Updates**: All three views update simultaneously

### Push-Button Coordinate Workflow

Optimized for medical professionals:

```python
def on_set_entry_clicked(self):
    """Handle set entry button click with medical workflow optimization."""
    # Validate electrode selection
    # Check for stored coordinates from image click
    # Provide clear user feedback if prerequisites not met
    # Set coordinates with immediate visual confirmation
    # Clear coordinate storage after successful operation

def on_set_output_clicked(self):
    """Handle set output button click with same workflow."""
```

**Workflow Design**:
1. **Click Image**: User clicks on desired location in any view
2. **Visual Feedback**: Crosshairs update if enabled
3. **Coordinate Storage**: System stores precise 3D coordinates
4. **Button Press**: User clicks "Set Entry" or "Set Output"
5. **Confirmation**: Immediate visual feedback with coordinate display
6. **Professional UX**: Clear, mistake-proof workflow for clinical use

### Multi-Image Visibility System

Advanced image management for complex cases:

```python
def on_visibility_toggle(self, file_path: str, checked: bool):
    """Handle visibility button toggle with intelligent image management."""
    # Determine current overlay configuration
    # Add/remove images from display based on priority
    # Maintain logical base/overlay relationships
    # Update all UI elements consistently

def update_all_visibility_buttons(self):
    """Update visibility button states to reflect current overlay configuration."""
    # Sync button states with actual display
    # Provide visual feedback for displayed images
    # Maintain consistency across all UI elements
```

**Features**:
- **Eye Icon Toggles**: Intuitive visibility controls for each loaded image
- **Smart Management**: Automatic base/overlay assignment based on user intent
- **Consistent State**: UI always reflects actual display configuration
- **Professional Appearance**: Green icons for visible, gray for hidden

## Interface Implementation

### IImageView Contract

The ImagesViewer implements the IImageView interface:

```python
# Image management
def load_image_file(self, file_path: str) -> bool
def set_slice_range(self, orientation: str, min_slice: int, max_slice: int) -> None

# Overlay controls
def set_overlay_visibility(self, visible: bool) -> None
def update_overlay_opacity(self, opacity: float) -> None
def refresh_overlay_controls(self) -> None

# Electrode management
def refresh_electrode_list(self) -> None
def refresh_electrode_tree(self) -> None
def update_coordinate_display(self, electrode_name: str = None) -> None
def enable_electrode_controls(self, enabled: bool) -> None

# Crosshair coordination
def show_crosshairs(self, show: bool) -> None
def update_crosshair_position(self, x: int, y: int, z: int) -> None
def synchronize_crosshairs(self) -> None

# Data management
def add_file_to_data_tree(self, file_path: str) -> None
def remove_file_from_data_tree(self, file_path: str) -> None
def clear_data_tree(self) -> None
```

### IBaseView Implementation

Common interface methods for error handling and state management:

```python
def show_error_message(self, title: str, message: str) -> None
def show_warning_message(self, title: str, message: str) -> None
def show_info_message(self, title: str, message: str) -> None
def set_busy_state(self, busy: bool) -> None
def get_widget(self) -> QWidget
```

## Development Guidelines

### Adding New Features to ImagesViewer

1. **Identify the Controller Domain**
   - Image display → ImageController
   - Electrode operations → ElectrodeController
   - Crosshair functionality → CrosshairController

2. **Follow MVC Patterns**
   - Business logic in controllers and models
   - View updates through interface methods
   - Loose coupling via well-defined interfaces

3. **Coordinate System Considerations**
   - Use ImageController for coordinate transformations
   - Maintain medical-grade precision
   - Test coordinate accuracy with known reference points

4. **Medical Workflow Optimization**
   - Design for neurosurgical procedures
   - Minimize clicks and cognitive load
   - Provide clear visual feedback
   - Prevent common user errors

### Common Development Patterns

#### Controller Coordination

```python
# Multiple controllers working together
def on_image_clicked(self, orientation, x, y):
    # ImageController handles coordinate conversion
    coords = self.image_controller.get_3d_coordinates_from_click(...)
    
    # CrosshairController handles crosshair updates
    if self.crosshair_controller.is_enabled():
        self.crosshair_controller.set_crosshair_position(coords)
    
    # Store for ElectrodeController use
    self.last_clicked_coordinates = coords
```

#### Model State Synchronization

```python
# Keep models synchronized across operations
def update_electrode_data(self, electrode_name: str):
    # Update multiple models consistently
    self.electrode_model.update_electrode(electrode_name, data)
    self.coordinate_model.update_coordinates(electrode_name, coords)
    
    # Trigger view updates
    self.refresh_electrode_tree()
    self.refresh_coordinate_display()
    self.refresh_image_display()
```

#### Signal-Based Updates

```python
# Connect UI signals to controller methods
self.Axial_horizontalSlider.valueChanged.connect(
    lambda: self.update_slice_display('axial')
)
self.SetEntryPushButton.clicked.connect(self.on_set_entry_clicked)
```

### Best Practices

1. **Coordinate Precision**: Maintain medical-grade coordinate accuracy
2. **Performance Optimization**: Cache pixmaps and optimize rendering
3. **User Feedback**: Provide immediate visual confirmation of actions
4. **Error Prevention**: Validate user input and provide clear guidance
5. **Professional UX**: Design for clinical environments and workflows
6. **Cross-View Consistency**: Ensure all views stay synchronized
7. **Memory Management**: Properly handle large medical image datasets

### Medical Domain Considerations

1. **Neurosurgical Workflow**: Interface optimized for electrode placement procedures
2. **Coordinate Accuracy**: Sub-millimeter precision for medical applications
3. **Visual Standards**: High contrast, professional medical imaging appearance
4. **Error Prevention**: Workflow design prevents coordinate placement mistakes
5. **Data Integrity**: Comprehensive validation ensures medical data quality
6. **Clinical Compatibility**: 3D Slicer format support for clinical integration

## Integration with Processing Pipeline

The ImagesViewer integrates with the broader CiCLONE processing pipeline:

```python
def on_export_mni_clicked(self):
    """Export electrode coordinates to MNI space with automatic subject detection."""
    # Auto-detect subject directory from loaded images
    # Create Subject instance for transformation matrix access
    # Export coordinates using existing processing services
    # Provide seamless integration with processing pipeline
```

This integration enables seamless workflow from image viewing and electrode placement to coordinate transformation and clinical data export.

## Current Status

The ImagesViewer architecture is **production-ready** with:

- ✅ Complete MVC implementation with distributed controller coordination
- ✅ Advanced overlay system with gear button controls
- ✅ Medical-grade coordinate precision and transformation
- ✅ Professional neurosurgical workflow optimization
- ✅ Comprehensive electrode management with 3D Slicer integration
- ✅ Real-time crosshair synchronization across all views
- ✅ Robust error handling and user feedback systems

The architecture provides a sophisticated foundation for medical image visualization and electrode localization in neurosurgical environments, with the flexibility to extend for advanced clinical requirements.