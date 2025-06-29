# CiCLONE System Patterns

## Architectural Overview

CiCLONE follows a **Model-View-Controller (MVC)** architecture with **Domain-Driven Design** principles, providing clear separation of concerns and maintainable code organization.

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Domain      │    │    Services     │    │   Controllers   │
│  (Pure Logic)   │    │ (Business Logic)│    │  (Coordination) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
         │     Models      │    │      Views      │    │    Workers      │
         │  (Data/State)   │    │   (UI/Display)  │    │ (Background)    │
         └─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Core Architectural Patterns

### 1. Model-View-Controller (MVC)

#### Controllers Layer (`ciclone/controllers/`)
Central coordination layer that manages interactions between models and views.

**Key Controllers:**
- **`MainController`**: Orchestrates all application operations
- **`ElectrodeController`**: Manages electrode-related operations  
- **`ImageController`**: Handles image loading and display coordination
- **`ProcessingController`**: Manages pipeline execution
- **`CrosshairController`**: Coordinates crosshair display across views

**Pattern Benefits:**
- Clear separation of concerns
- Testable business logic
- Loose coupling between components
- Coordinated state management

#### Models Layer (`ciclone/models/`)
Data management and business state.

**Key Models:**
- **`ApplicationModel`**: Global application state
- **`ElectrodeModel`**: Electrode data and operations
- **`ImageModel`**: Image data and overlay management
- **`CoordinateModel`**: Coordinate storage and validation
- **`SubjectModel`**: Subject data management

#### Views Layer (`ciclone/ui/`)
User interface and presentation logic.

**Key Views:**
- **`MainWindow`**: Primary application interface
- **`ImagesViewer`**: Multi-planar image display with electrode interaction
- **`Viewer3D`**: 3D visualization component

### 2. Domain-Driven Design (DDD)

#### Domain Layer (`ciclone/domain/`)
Pure business entities without technical dependencies.

**Core Entities:**
```python
# Contact: Single electrode contact point
class Contact:
    - coordinates: (x, y, z)
    - index: contact number
    
# Electrode: Collection of contacts
class Electrode:
    - name: identifier
    - contacts: List[Contact]
    - electrode_type: configuration
    
# Electrodes: Management collection
class Electrodes:
    - electrodes: Dict[name, Electrode]
    - operations: add, remove, find
```

**Value Objects:**
- **`ElectrodeElement`**: Immutable electrode definition components
- **`Subject`**: Patient/study representation

#### Services Layer (`ciclone/services/`)
Business logic organized by functional domain.

**Processing Services (`services/processing/`):**
- **`operations.py`**: Medical image operations (FSL/FreeSurfer integration)
- **`stages.py`**: Pipeline orchestration and workflow management
- **`tool_config.py`**: External tool configuration

**I/O Services (`services/io/`):**
- **`electrode_reader.py`**: Electrode definition file parsing
- **`slicer_file.py`**: 3D Slicer format handling
- **`subject_importer.py`**: Subject data import and directory management

**UI Services (`services/ui/`):**
- **`dialog_service.py`**: Clean abstraction for all user dialogs, removing MVC violations
- **`view_delegate.py`**: UI business logic delegate handling tree operations and file classification

### 3. Observer Pattern

#### Qt Signal/Slot System
Leverages PyQt6's signal/slot mechanism for loose coupling.

**Key Connections:**
```python
# Model state changes trigger view updates
application_model.output_directory_changed.connect(controller.refresh_views)
application_model.worker_state_changed.connect(view.update_processing_ui)

# User interactions delegate to controllers
view.button_clicked.connect(controller.handle_action)
view.image_clicked.connect(controller.set_coordinates)
```

**Benefits:**
- Decoupled communication between components
- Event-driven architecture
- Automatic UI synchronization with model state

### 4. Strategy Pattern

#### Configurable Processing Operations
Different image processing operations implemented as pluggable strategies.

**Operations Strategy:**
```python
# Each operation type is a strategy
operations = {
    'crop': crop_image_operation,
    'coregister': coregister_operation, 
    'threshold': threshold_operation,
    'register_ct_to_mni': mni_registration_operation
}

# Pipeline executes strategies based on configuration
for operation in stage.operations:
    strategy = operations[operation.type]
    strategy.execute(operation.parameters)
```

#### Electrode Type Strategy
Different electrode configurations handled through definition files.

```
config/electrodes/
├── Dixi-D08-05AM.elecdef    # 5-contact electrode
├── Dixi-D08-08AM.elecdef    # 8-contact electrode
├── Dixi-D08-15AM.elecdef    # 15-contact electrode
└── ...                      # Additional electrode types
```

### 5. Factory Pattern

#### UI Component Creation
Controllers act as factories for creating UI components.

```python
# ElectrodeController creates tree items
def create_tree_item(self, electrode: Electrode) -> QTreeWidgetItem:
    item = QTreeWidgetItem()
    # Configure item based on electrode data
    return item

# ImageController creates pixmaps for display
def create_clean_pixmap_for_display(self, slice_data, orientation, width, height):
    # Factory method for creating display-ready pixmaps
```

## Data Flow Patterns

### 1. Image Loading and Display
```
User Action → ImageController → ImageModel → Data Storage
     ↓              ↓              ↓
View Update ← Controller ← Model State Change
```

**Detailed Flow:**
1. User selects image file
2. `ImageController.load_image()` validates and delegates
3. `ImageModel.load_nifti_file()` processes and stores data
4. Model triggers state change signals
5. Controller updates view components
6. Views refresh display with new image data

### 2. Electrode Management
```
User Input → ElectrodeController → ElectrodeModel → Domain Objects
     ↓              ↓                    ↓
UI Updates ← Coordinate Model ← Business Logic
```

**Detailed Flow:**
1. User creates electrode or sets coordinates
2. Controller validates input and coordinates operations
3. Model stores electrode data and triggers state changes
4. Views update to reflect new electrode information

### 3. Coordinate Transformation Pipeline
```
Voxel Coordinates → Physical Coordinates → Center-Relative Coordinates → Export Format
      ↓                    ↓                        ↓                    ↓
Image Clicking → Affine Transform → Image Center Subtraction → Slicer JSON
```

**Coordinate System Flow:**
1. **Voxel Space**: User clicks on image, generates voxel coordinates (array indices)
2. **Physical Space**: NIFTI affine matrix transforms voxel to physical coordinates
3. **Center-Relative Space**: Subtract image center for anatomical centering
4. **Export Format**: Generate standardized output (Slicer JSON, research formats)

**Key Pattern**: **Center-Relative Coordinate System**
- **Problem**: NIFTI origins can be far from anatomical center (scanner coordinate system)
- **Solution**: Transform to center-relative coordinates for proper 3D visualization
- **Implementation**: `get_image_center_physical()` calculates anatomical center, coordinates adjusted relative to center
- **Benefit**: Electrodes properly centered around (0,0,0) in 3D Slicer and other visualization tools

### 4. Processing Pipeline Pattern

## Key Design Principles

### 1. Separation of Concerns
- **Domain**: Pure business logic, no technical dependencies
- **Services**: Technical business logic with external integrations
- **Controllers**: Coordination and workflow management
- **Models**: Data and state management
- **Views**: User interface and presentation

### 2. Dependency Inversion
- High-level modules don't depend on low-level modules
- Controllers depend on abstractions (model interfaces)
- Views receive data through controller interfaces
- Domain objects have no dependencies on infrastructure

### 3. Single Responsibility
- Each class has one reason to change
- Models focus on data management
- Controllers focus on coordination
- Views focus on presentation
- Services focus on specific business operations

### 4. Interface Segregation
- Components depend only on interfaces they use
- Controllers provide specific view interfaces
- Models expose focused data access methods
- Clean boundaries between architectural layers

## Benefits of Current Architecture

### Maintainability
- Clear code organization and boundaries
- Easy to locate and modify specific functionality
- Minimal coupling between components
- Well-defined responsibilities

### Testability
- Controllers can be tested with mock models/views
- Domain logic can be tested in isolation
- Services can be tested with controlled dependencies
- Clear interfaces enable effective mocking

### Extensibility
- New electrode types added through configuration
- New processing operations added through strategy pattern
- New views can integrate through controller interfaces
- Additional image formats supported through model extensions

### User Experience
- Responsive UI through proper separation of concerns
- Background processing doesn't block interface
- Real-time updates through observer pattern
- Consistent behavior across all components 