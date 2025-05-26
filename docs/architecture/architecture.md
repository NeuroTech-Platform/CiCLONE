# CiCLONE Architecture Documentation

## Overview

CiCLONE (Cico Cardinale's Localization Of Neuro-electrodes) is a Python application for medical image processing and electrode localization in neurosurgical procedures. The application follows a modern MVC (Model-View-Controller) architecture with domain-driven design principles.

## Project Structure

```
CiCLONE/
├── ciclone/                    # Main application package
│   ├── domain/                 # Domain models and entities
│   ├── services/               # Business logic services
│   ├── controllers/            # MVC controllers
│   ├── models/                 # MVC models
│   ├── ui/                     # Views and UI components
│   ├── forms/                  # Auto-generated UI forms
│   ├── workers/                # Background processing
│   ├── utils/                  # General utilities
│   ├── config/                 # Configuration files
│   ├── main.py                 # GUI application entry point
│   └── main_cli.py             # CLI application entry point
├── docs/                       # Documentation
├── pyproject.toml              # Project configuration
├── poetry.lock                 # Dependency lock file
└── README.md                   # Project overview
```

## Architecture Layers

### 1. Domain Layer (`ciclone/domain/`)

Contains pure business entities and value objects that represent the core concepts of the application.

#### Components:
- **`electrodes.py`**: Core electrode entities
  - `Contact`: Represents a single electrode contact with 3D coordinates
  - `Electrode`: Represents an electrode with multiple contacts
  - `Electrodes`: Collection of multiple electrodes
- **`electrode_element.py`**: Value object for electrode definition elements
- **`subject.py`**: Subject domain model representing a patient/study

#### Characteristics:
- No external dependencies except basic Python libraries
- Pure business logic without technical concerns
- Immutable value objects where appropriate

### 2. Services Layer (`ciclone/services/`)

Contains business logic services organized by functional domain.

#### Processing Services (`services/processing/`)
- **`operations.py`**: Medical image processing operations
  - FSL/FreeSurfer integration functions
  - Image registration, transformation, and analysis
  - Coordinate transformation utilities
- **`stages.py`**: Pipeline stage management
  - Orchestrates multiple operations into processing stages
  - Handles workflow execution

#### I/O Services (`services/io/`)
- **`electrode_reader.py`**: Reads electrode definition files (.elecdef)
- **`slicer_file.py`**: Handles 3D Slicer file format operations
- **`subject_importer.py`**: Imports subject data and creates directory structures

### 3. MVC Architecture

#### Models (`ciclone/models/`)
Manage data and business logic for the application state.

- **`electrode_model.py`**: Manages electrode data and operations
  - Electrode creation, deletion, and retrieval
  - Contact processing and coordinate calculations
  - Tree widget item creation for UI
- **`coordinate_model.py`**: Manages coordinate data for electrodes
  - Entry and output point storage
  - Coordinate validation and retrieval
- **`image_model.py`**: Manages medical image data
  - NIFTI file loading and processing
  - Volume data management and slice extraction

#### Controllers (`ciclone/controllers/`)
Coordinate between models and views, handling user interactions.

- **`electrode_controller.py`**: Manages electrode-related operations
  - Electrode CRUD operations
  - Coordinate setting and processing
  - UI state management for electrode operations
- **`image_controller.py`**: Manages image-related operations
  - Image loading and display
  - Slice navigation and visualization
  - Coordinate mapping between views

#### Views (`ciclone/ui/`)
Handle user interface and presentation logic.

- **`MainWindow.py`**: Main application window
  - Subject management and directory browsing
  - Processing pipeline execution
  - Integration with ImagesViewer
- **`ImagesViewer.py`**: Medical image viewer with electrode placement
  - Multi-planar reconstruction (axial, sagittal, coronal)
  - Interactive electrode coordinate setting
  - 3D visualization integration
- **`Viewer3D.py`**: 3D visualization component
- **`ClickableImageLabel.py`**: Custom widget for image interaction

### 4. Supporting Components

#### Forms (`ciclone/forms/`)
Auto-generated UI forms from Qt Designer files.
- `MainWindow_ui.py`
- `ImagesViewer_ui.py`
- `Viewer3D_ui.py`

#### Workers (`ciclone/workers/`)
Background processing components for long-running operations.
- **`ImageProcessingWorker.py`**: Qt thread worker for image processing
- **`ImageProcessingProcess.py`**: Multiprocessing support for pipeline execution

#### Utils (`ciclone/utils/`)
General-purpose utility functions.
- **`utility.py`**: Command execution, configuration reading, file utilities

#### Config (`ciclone/config/`)
Configuration files and electrode definitions.
- `config.yaml`: Processing pipeline configuration
- `electrodes/`: Electrode definition files (.elecdef)

## Key Design Patterns

### 1. Model-View-Controller (MVC)
- **Separation of Concerns**: Clear boundaries between data, business logic, and presentation
- **Loose Coupling**: Components communicate through well-defined interfaces
- **Testability**: Each layer can be tested independently

### 2. Domain-Driven Design (DDD)
- **Domain Layer**: Pure business entities without technical dependencies
- **Service Layer**: Business logic organized by functional domains
- **Clear Boundaries**: Technical concerns separated from business logic

### 3. Observer Pattern
- Controllers observe model changes and update views accordingly
- Qt signals/slots for loose coupling between components

### 4. Strategy Pattern
- Different image processing operations implemented as separate functions
- Pluggable electrode types through definition files

## Data Flow

### Image Loading and Display
1. User selects image file in MainWindow or ImagesViewer
2. ImageController.load_image() called
3. ImageModel loads and processes NIFTI data
4. ImageController updates view with new image data
5. Views refresh to display updated slices

### Electrode Management
1. User creates electrode through ImagesViewer UI
2. ElectrodeController.create_electrode() validates and delegates to model
3. ElectrodeModel stores electrode data
4. ElectrodeController updates view (combo box, tree widget)
5. User sets coordinates by clicking on images
6. CoordinateModel stores coordinate data
7. Processing generates contact positions
8. Views refresh to display electrode contacts

### Processing Pipeline
1. User selects subjects and stages in MainWindow
2. ImageProcessingWorker executes in background thread
3. Processing services execute FSL/FreeSurfer operations
4. Progress updates sent to UI through Qt signals
5. Results stored in subject directory structure

## Technology Stack

### Core Technologies
- **Python 3.12+**: Primary programming language
- **PyQt6**: GUI framework for desktop application
- **NumPy**: Numerical computing for image processing
- **NiBabel**: NIFTI medical image format support
- **Poetry**: Dependency management and packaging

### External Tools Integration
- **FSL**: Medical image analysis toolkit
- **FreeSurfer**: Neuroimaging analysis suite
- **ANTs**: Advanced normalization tools
- **3D Slicer**: Medical image visualization (file format compatibility)

### Development Tools
- **Poetry**: Package management
- **Git**: Version control
- **Qt Designer**: UI design tool
