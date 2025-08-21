# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CiCLONE (Cico Cardinale's Localization Of Neuro-electrodes) is a production-ready Python application for medical image processing and electrode localization in neurosurgical procedures. It implements a complete MVC architecture with PyQt6 GUI and advanced medical imaging capabilities for stereotactic neurosurgery planning and analysis.

## Development Commands

### Environment Setup
```bash
# Setup Poetry environment with Python 3.10-3.13
poetry env use $(pyenv which python3.11)  # or 3.10, 3.12, 3.13

# Install dependencies
poetry install
```

### Running the Application
```bash
# GUI application
poetry run ciclone

# CLI application  
poetry run ciclone-cli --directory /path/to/output/directory [command] [options]
```

### UI Development
```bash
# Open Qt Designer for UI files
make design file=forms/MainWindow.ui
```

### Testing and Quality
```bash
# Run all unit tests
python tests/run_tests.py

# Run specific test module
python tests/run_tests.py test_subject_file_service

# Run individual test files
python -m unittest tests.test_subject_file_service
python -m unittest tests.test_electrode_view_delegate
python -m unittest tests.test_subject_data_factory
python -m unittest tests.test_subject_domain
```

## Architecture Overview

### MVC Pattern with Service Layer
- **Domain Layer** (`ciclone/domain/`): Pure business entities
  - `electrodes.py`: Electrode domain model with contacts
  - `subject.py`: Subject/patient domain model
  - `electrode_element.py`: Physical electrode structure (contacts, tail/shaft)
- **Service Layer** (`ciclone/services/`): Business logic organized by domain
  - `ui/`: Dialog service and view delegates for UI abstraction
  - `processing/`: Medical image processing operations (FSL/FreeSurfer integration)
  - `io/`: File I/O operations for medical data formats
  - `operation_metadata_parser.py`: Pipeline operation configuration
  - `config_service.py`: Application configuration management
- **Models** (`ciclone/models/`): Application state and data management with Qt signals
  - `electrode_model.py`: Electrode data management and contact processing
  - `subject_model.py`: Subject data management
  - `coordinate_model.py`: Coordinate system management
  - `image_model.py`: Medical image data management
  - `crosshair_model.py`: Crosshair state management
  - **Factories**: `subject_data_factory.py` for object creation
- **Controllers** (`ciclone/controllers/`): Coordinate between models and views
  - `main_controller.py`: Main application controller
  - `electrode_controller.py`: Electrode management and visualization
  - `image_controller.py`: Image display and manipulation
  - `processing_controller.py`: Pipeline execution management
  - `config_dialog_controller.py`: Configuration dialog management
- **Views** (`ciclone/ui/`): PyQt6 GUI components
  - `MainWindow.py`: Main application window
  - `ImagesViewer.py`: Multi-planar medical image viewer
  - `Viewer3D.py`: 3D visualization component
  - `PipelineConfigDialog.py`: Pipeline configuration UI
  - `widgets/`: Custom widgets including ClickableImageLabel
- **Interfaces** (`ciclone/interfaces/`): Type-safe Protocol-based view contracts
- **Managers** (`ciclone/managers/`): Transaction and state management
  - `config_transaction_manager.py`: Configuration change transactions
- **Workers** (`ciclone/workers/`): Background processing threads
  - `ImageProcessingWorker.py`: Async image processing

### Key Components
- **MainWindow**: Central application hub with subject/electrode management
- **ImagesViewer**: Multi-planar medical image viewer with:
  - Axial, Sagittal, Coronal views
  - Interactive electrode placement and visualization
  - Real-time crosshair synchronization
  - Electrode tail/shaft rendering with proper medical proportions
- **Viewer3D**: 3D visualization with VTK integration
- **Processing Pipeline**: Configurable YAML-based stages:
  - Dynamic parameter configuration
  - Operation metadata parsing
  - Background processing with progress tracking
- **Electrode Management**: 
  - Interactive coordinate setting (entry/output points)
  - Automatic contact position calculation
  - Support for various electrode types (DIXI series)
  - Proper tail visualization (capped at 0.8× contact array length)

### External Tool Integration
- **FSL**: Self-contained medical image analysis (no dependency conflicts)
- **FreeSurfer**: Neuroimaging analysis suite
- **3D Slicer**: File format compatibility for electrode coordinates

## Development Guidelines

### Code Style (from .cursor.json)
- Follow PEP 8 with 4 spaces indentation, 79-character line limit
- Use Google-style docstrings with comprehensive type hints
- Qt6 code follows Qt naming conventions (camelCase for methods)
- Separate UI logic from business logic maintaining MVC boundaries

### Architecture Patterns
- **Domain-Driven Design**: Pure business entities without technical dependencies
- **Service Layer**: Clean abstraction for external tool integration
- **Observer Pattern**: Qt signals/slots for loose coupling
- **Type Safety**: Protocol-based interfaces throughout

### File-Specific Guidelines
- **Domain objects**: Immutable value objects, no external dependencies
- **Services**: Single responsibility, dependency injection for testability
- **Controllers**: Coordinate only, delegate business logic to models/services
- **Models**: Manage state with Qt signals, thread-safe for shared access
- **UI components**: Focus on presentation, use layouts for responsive design

## Key Technical Details

### Dependency Management
- **Poetry** for isolated virtual environment management
- **Python**: 3.10-3.13 support
- **Core Dependencies**:
  - NumPy 2.2.0+ for numerical computations
  - PyQt6 6.8.1+ for GUI framework
  - NiBabel 5.3.2+ for medical image I/O (NIFTI format)
  - VTK 9.4.2+ for 3D visualization
  - PyYAML 6.0.1+ for configuration management
  - Pillow 10.0.0+ for image processing
- **Perfect Isolation Strategy**: FSL/FreeSurfer tools are self-contained, eliminating version conflicts

### Configuration
- `ciclone/config/config.yaml.template`: Base pipeline configuration template
- `ciclone/config/config_ct.yaml`: CT-specific pipeline configuration
- `ciclone/config/config_mri.yaml`: MRI-specific pipeline configuration
- `ciclone/config/naming_conventions.yaml`: Configurable file naming patterns for imported subjects
  - Customizable naming for CT and MRI files
  - Template variables: ${name} for subject name, ${modality} for MRI type
  - Default patterns maintain backward compatibility
- `ciclone/config/electrodes/`: Electrode definition files (.elecdef format)
  - DIXI series electrodes (D08-05AM through D08-18CM)
  - Pickled Python dictionaries with element definitions
  - Contains contact positions, spacing, and tail specifications
- Copy template to `config.yaml` and update FSL/FreeSurfer paths before first run

### Data Flow
1. Subject management through MainWindow with directory structure creation
2. Medical image loading via NIFTI format with NiBabel
3. Interactive electrode coordinate setting in ImagesViewer
4. Background processing pipeline execution with FSL/FreeSurfer
5. Results export to subject-specific directories

### MVC Compliance Improvements

The codebase has been enhanced with strict MVC compliance through the following refactoring:

#### Domain Purity
- **Subject Domain Object**: Extracted file I/O operations to `SubjectFileService`
- **Pure Business Logic**: Domain objects contain only business rules, no infrastructure concerns

#### Service Layer Enhancement
- **SubjectFileService**: Handles all Subject-related file operations with proper dependency injection
- **ElectrodeFileService**: Manages electrode definition file access with testable abstraction
- **ElectrodeViewDelegate**: Removed UI dependencies from ElectrodeModel

#### Controller Improvements
- **Dialog Service Integration**: Standardized dialog usage across controllers with dependency injection
- **Business Logic Extraction**: Moved subject data creation to `SubjectDataFactory` in model layer

#### Testing Infrastructure
- **Comprehensive Unit Tests**: All refactored components have full test coverage
- **Dependency Injection**: Services support mocking for isolated testing
- **Backward Compatibility**: All changes maintain existing functionality

## Development Principles

### Best Practices
- Every development plan MUST include updating CLAUDE.md as the final task
- Always use Qt's built-in methods when possible
- Maintain clean separation between UI and business logic
- Use dependency injection for testability
- Follow medical imaging conventions (RAS coordinates, NIFTI standards)
- Ensure thread safety for background processing 

## Important Notes

- **Production Ready Status**: Complete MVC implementation with medical-grade stability
- **Comprehensive Test Suite**: Unit tests available for all refactored MVC components
- **Medical Domain Focus**: UI and workflows optimized for stereotactic neurosurgical procedures
- **Cross-Platform**: Designed for macOS/Linux, Windows compatibility via Qt6
- **Electrode Visualization**: Accurate representation with proportional tail rendering
- **Real-time Interaction**: Responsive UI with background processing support

## Recent Improvements (2024-2025)

### Electrode Tail Rendering Fix
- **Issue**: Electrode tails appeared disproportionately large (2-6× expected size)
- **Root Cause**: Incorrect scaling factor applied to tail length from .elecdef files
- **Solution**: Proper scaling using contact array proportions, capped at 0.8× contact span
- **File**: `ciclone/models/electrode_model.py:166-198`

### Dynamic Pipeline Configuration
- Enhanced parameter configuration system with metadata parsing
- Transaction-based configuration management for atomic updates
- Dynamic UI generation based on operation requirements

### Architecture Refinements
- Improved separation of concerns across MVC layers
- Enhanced service layer abstraction
- Better dependency injection patterns
- Comprehensive error handling in background workers

### File Naming Convention System (2025)
- **Configurable File Naming**: Parametrized naming patterns for imported CT and MRI files
- **NamingService**: Clean service layer for managing file naming conventions
- **Template-Based Configuration**: YAML configuration with ${name} and ${modality} variables
- **Backward Compatibility**: Default patterns preserve existing pipeline compatibility (_CT_Bone, _CT_Electrodes)
- **Easy Customization**: Users can modify naming patterns via `naming_conventions.yaml` without code changes
- **Full Test Coverage**: Comprehensive unit tests for all naming scenarios
- **Files Added/Modified**:
  - `ciclone/config/naming_conventions.yaml`: Configuration file for naming patterns
  - `ciclone/services/naming_service.py`: Service class for naming logic
  - `ciclone/services/io/subject_importer.py`: Updated to use NamingService
  - `ciclone/controllers/subject_controller.py`: Integrated NamingService
  - `tests/test_naming_service.py`: Unit tests for naming functionality

### Configuration Transaction Management Redesign (2025)
- **Complete UX Overhaul**: Redesigned configuration editing workflow to keep all changes in memory until explicitly saved
- **Memory-Only Changes**: All modifications remain in working memory without disk I/O until main Save button is clicked
- **Visual Dirty Indicators**: Real-time asterisk (*) indicators in UI lists show exactly what has been modified at every hierarchical level
- **Intelligent Context Switching**: Smart prompting system that only asks users about unsaved changes when actually switching contexts with new modifications
- **Revert-to-Original Detection**: Automatic cleanup of dirty state when values are changed back to their original state
- **Enhanced Hierarchical State Management**: Advanced parent-child dirty state cleanup with the `_clean_parent_dirty_states` method that intelligently removes dirty indicators from parent entities when all their children have reverted to original state, providing superior UX through automatic cleanup of parent indicators
- **Improved Dialog Text**: Clear "Keep Changes" vs "Discard Changes" prompts instead of ambiguous "Save" operations
- **Session-Aware Prompting**: Only prompts when NEW changes are made in current editing session, eliminating unnecessary dialogs when navigating back to previously-modified elements
- **Files Modified**:
  - `ciclone/managers/config_transaction_manager.py`: Core transaction logic with dirty state tracking
  - `ciclone/controllers/config_dialog_controller.py`: Updated dialog handling and context switching
  - `ciclone/ui/PipelineConfigDialog.py`: Visual indicators and real-time UI updates
- **Key Benefits**: Safer experimentation, clearer visual feedback, reduced user friction, atomic saves, consistent "Save" meaning across the application