# MainWindow Architecture Guide

This document provides a comprehensive guide to the MainWindow component architecture, covering its role as the central application interface, controller coordination patterns, and development guidelines.

## Overview

The MainWindow serves as the primary application interface for CiCLONE, orchestrating subject management, processing pipeline execution, and overall application workflow. It implements a centralized controller pattern where the MainController coordinates multiple specialized child controllers.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                   MainWindow                                    │
│                              (QMainWindow + UI)                                │
│                                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │  Subject Form   │  │  Processing     │  │  Subject Tree   │                │
│  │  - Name         │  │  - Stages       │  │  - Directory    │                │
│  │  - Schema       │  │  - Progress     │  │  - Files        │                │
│  │  - Medical      │  │  - Logs         │  │  - Context      │                │
│  │    Images       │  │                 │  │    Menus        │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
│           │                     │                     │                        │
│           └─────────────────────┼─────────────────────┘                        │
│                                 │                                              │
└─────────────────────────────────┼──────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                               MainController                                   │
│                           (Central Coordinator)                                │
│                                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │ SubjectForm     │  │ Processing      │  │ TreeView        │                │
│  │ Controller      │  │ Controller      │  │ Controller      │                │
│  │ - Validation    │  │ - Pipeline      │  │ - FileSystem    │                │
│  │ - Submission    │  │ - Workers       │  │ - Selection     │                │
│  │ - Field State   │  │ - Progress      │  │ - NIFTI Files   │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
│           │                     │                     │                        │
│           └─────────────────────┼─────────────────────┘                        │
│                                 │                                              │
│  ┌─────────────────┐            │            ┌─────────────────┐                │
│  │ Subject         │            │            │ Application     │                │
│  │ Controller      │            │            │ Model           │                │
│  │ - CRUD Ops      │            │            │ - Config        │                │
│  │ - Directory     │            │            │ - State         │                │
│  │ - Validation    │            │            │ - Workers       │                │
│  └─────────────────┘            │            └─────────────────┘                │
│           │                     │                     │                        │
│           └─────────────────────┼─────────────────────┘                        │
│                                 │                                              │
└─────────────────────────────────┼──────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Service Layer                                     │
│                                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │ DialogService   │  │ Subject File    │  │ Processing      │                │
│  │ - User Dialogs  │  │ Service         │  │ Services        │                │
│  │ - Confirmations │  │ - File I/O      │  │ - FSL           │                │
│  │ - File Browse   │  │ - Validation    │  │ - FreeSurfer    │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### MainWindow Class

**Location**: `ciclone/ui/MainWindow.py:19-553`

**Inheritance**: `QMainWindow`, `Ui_MainWindow`

#### Key Responsibilities

1. **Primary Application Interface**
   - Subject management form with real-time validation
   - Processing pipeline configuration and execution
   - Directory management and file browsing
   - User interaction coordination

2. **UI Component Management**
   - Form validation indicators with colored feedback
   - Context menus for subject operations
   - Processing progress displays
   - Log message integration

3. **Controller Coordination**
   - Centralizes all controller interactions
   - Manages application state through MainController
   - Handles view updates through interface contracts

#### Key UI Components

```python
# Form validation indicators
self.validation_indicators = {
    'name': self.validation_indicator_name,
    'schema': self.validation_indicator_schema,
    'pre_ct': self.validation_indicator_pre_ct,
    'pre_mri': self.validation_indicator_pre_mri,
    'post_ct': self.validation_indicator_post_ct,
    'post_mri': self.validation_indicator_post_mri
}

# Main controller initialization
self.main_controller = MainController(self.config_path)
```

#### Signal Connections

```python
# Form validation signals
form_controller.validation_feedback_ready.connect(self._on_field_validation_changed)
form_controller.form_state_updated.connect(self._on_form_state_changed)
form_controller.form_submission_complete.connect(self._on_form_submission_complete)

# UI interaction signals
self.pushButton_addSubject.clicked.connect(self.add_subject)
self.runAllStages_PushButton.clicked.connect(self.run_all_stages)
self.subjectTreeView.clicked.connect(self.on_tree_item_clicked)
```

### MainController Class

**Location**: `ciclone/controllers/main_controller.py`

**Role**: Central coordinator orchestrating all MainWindow operations

#### Architecture Pattern

The MainController implements a **Central Coordinator Pattern** where it:
- Manages application lifecycle and global state
- Coordinates between specialized child controllers
- Provides unified interface to the MainWindow view
- Handles cross-component communication

#### Controller Hierarchy

```python
class MainController:
    def __init__(self, config_path: str):
        # Core application state
        self.application_model = ApplicationModel(config_path)
        
        # Service layer initialization
        self.dialog_service = DialogService()
        self.view_delegate = ViewDelegate()
        
        # Child controller coordination
        self.subject_controller = SubjectController(
            self.application_model, self.dialog_service
        )
        self.processing_controller = ProcessingController(
            self.application_model, self.dialog_service
        )
        self.tree_view_controller = TreeViewController()
        self.subject_form_controller = SubjectFormController(
            self.dialog_service
        )
```

#### Key Responsibilities

1. **Application Lifecycle Management**
   - Configuration loading and validation
   - Service initialization and dependency injection
   - View coordination and state management

2. **Child Controller Coordination**
   - Delegates operations to specialized controllers
   - Coordinates cross-controller communication
   - Manages shared application state

3. **View Interface Implementation**
   - Implements IMainView contract methods
   - Handles view updates and user feedback
   - Manages ImagesViewer instance creation

4. **Service Integration**
   - Coordinates with DialogService for user interactions
   - Integrates with processing services
   - Manages file operations through services

## Child Controllers Specifications

### SubjectController

**Purpose**: Subject data management and file operations

```python
class SubjectController:
    """Manages subject CRUD operations and directory management."""
    
    # Key Methods
    def create_subject(self, subject_data: dict) -> bool
    def delete_subject(self, subject_name: str) -> bool
    def rename_subject(self, old_name: str, new_name: str) -> bool
    def validate_subject_data(self, data: dict) -> tuple[bool, list]
```

**Responsibilities**:
- Subject creation with directory structure setup
- Subject deletion with cleanup validation
- Subject renaming with file system updates
- File copying and directory management
- Integration with SubjectImporter service

### ProcessingController

**Purpose**: Medical image processing pipeline management

```python
class ProcessingController:
    """Manages processing pipeline execution and worker coordination."""
    
    # Key Methods
    def run_all_stages(self, subjects: list) -> bool
    def run_selected_stages(self, subjects: list) -> bool
    def stop_processing(self) -> None
    def update_stage_selection(self, selected_stages: list) -> None
```

**Responsibilities**:
- Pipeline stage configuration and execution
- Background worker coordination (ImageProcessingWorker)
- Progress tracking and user feedback
- Clean process termination without message spam
- Integration with FSL/FreeSurfer services

### SubjectFormController

**Purpose**: Real-time form validation and submission

```python
class SubjectFormController:
    """Manages form validation, state, and submission."""
    
    # Signal-based communication
    validation_feedback_ready = pyqtSignal(str, bool, str, str)
    form_state_updated = pyqtSignal(bool, bool)
    form_submission_complete = pyqtSignal(bool)
    
    # Key Methods
    def handle_field_change(self, field_name: str, value: str) -> None
    def submit_form(self) -> bool
    def reset_form(self) -> None
```

**Responsibilities**:
- Real-time field validation with visual feedback
- Form state management (valid/invalid, dirty/clean)
- File browsing for medical images and schemas
- Form submission coordination with other controllers
- Signal-based UI updates

### TreeViewController

**Purpose**: File system tree management and navigation

```python
class TreeViewController:
    """Manages tree view display and subject selection."""
    
    # Key Methods
    def setup_tree_view(self, tree_view: QTreeView, root_path: str) -> None
    def get_selected_subjects(self, tree_view: QTreeView) -> list
    def refresh_tree_view(self, tree_view: QTreeView) -> None
    def get_file_path_from_index(self, index: QModelIndex) -> str
```

**Responsibilities**:
- QFileSystemModel configuration and management
- Subject selection and path extraction
- File type detection (NIFTI, images, markdown)
- Tree view updates and refresh operations
- NIFTI file detection for ImagesViewer integration

## Data Flow Patterns

### Subject Creation Flow

```
User Input → MainWindow → MainController → SubjectFormController
    ↓
Form Validation → SubjectFormModel → Real-time Feedback
    ↓
Form Submission → SubjectController → Directory Creation
    ↓
File Operations → SubjectImporter → Subject Directory Structure
    ↓
Tree Update → TreeViewController → UI Refresh
```

**Detailed Example**:

1. **User Interaction**: User fills form fields in MainWindow
2. **Real-time Validation**: SubjectFormController validates each field change
3. **Visual Feedback**: Colored indicators show validation state
4. **Form Submission**: User clicks "Add Subject" button
5. **Controller Coordination**: MainController delegates to SubjectFormController
6. **Data Validation**: SubjectFormModel performs comprehensive validation
7. **Subject Creation**: SubjectController handles directory and file operations
8. **Service Integration**: SubjectImporter copies files and creates structure
9. **UI Update**: TreeViewController refreshes tree view display

### Processing Pipeline Flow

```
Stage Selection → MainWindow → MainController → ProcessingController
    ↓
Subject Selection → TreeViewController → Selected Subjects List
    ↓
Pipeline Execution → ImageProcessingWorker → Background Processing
    ↓
Progress Updates → Qt Signals → UI Progress Display
    ↓
Completion/Error → ProcessingController → User Feedback
```

**Detailed Example**:

1. **Stage Configuration**: User selects processing stages in MainWindow
2. **Subject Selection**: User selects subjects from tree view
3. **Validation**: ProcessingController validates prerequisites
4. **Worker Creation**: ImageProcessingWorker started for background processing
5. **Pipeline Execution**: FSL/FreeSurfer operations executed through services
6. **Progress Tracking**: Qt signals update progress bar and log display
7. **Completion Handling**: Results stored, UI updated, cleanup performed

### File Preview Flow

```
Tree Click → MainWindow → MainController → TreeViewController
    ↓
File Path → ViewDelegate → File Type Check
    ↓
NIFTI File → ImagesViewer Creation → Medical Image Display
    ↓
Other Files → Preview Dialog → File Content Display
```

## Interface Implementation

### IMainView Contract

The MainWindow implements the IMainView interface, providing these key methods:

```python
# Directory management
def set_output_directory_text(self, directory: str) -> None
def show_status_message(self, message: str, timeout: int = 0) -> None

# Form state management  
def enable_form_controls(self, enabled: bool) -> None
def set_field_validation_state(self, field_name: str, is_valid: bool, 
                              error_message: str = "", warning_message: str = "") -> None
def set_form_submission_state(self, can_submit: bool) -> None

# Base view operations (from IBaseView)
def show_error_message(self, title: str, message: str) -> None
def show_warning_message(self, title: str, message: str) -> None
def show_info_message(self, title: str, message: str) -> None
def set_busy_state(self, busy: bool) -> None
```

### Validation System

The MainWindow implements an elegant validation system with colored indicators:

```python
def _on_field_validation_changed(self, field: str, valid: bool, error_msg: str, warning_msg: str):
    """Handle field validation feedback using colored indicators."""
    if not valid and error_msg:
        # Red indicator for errors
        indicator.setStyleSheet("background-color: #f44336; color: #f44336;")
        indicator.setToolTip(f"Error: {error_msg}")
    elif warning_msg:
        # Orange indicator for warnings  
        indicator.setStyleSheet("background-color: #ff9800; color: #ff9800;")
        indicator.setToolTip(f"Warning: {warning_msg}")
    else:
        # Green indicator for valid fields
        indicator.setStyleSheet("background-color: #4caf50; color: #4caf50;")
        indicator.setToolTip("Valid")
```

## Development Guidelines

### Adding New Features to MainWindow

1. **Identify the Domain**
   - Subject management → SubjectController
   - Form operations → SubjectFormController  
   - Processing → ProcessingController
   - File system → TreeViewController

2. **Follow MVC Pattern**
   - Business logic in controllers and services
   - Data management in models
   - UI updates through interface methods
   - Loose coupling via Qt signals

3. **Update Interface Contract**
   - Add methods to IMainView if needed
   - Implement in MainWindow class
   - Update controller to use new interface methods

4. **Service Layer Integration**
   - Use DialogService for user interactions
   - Delegate file operations to appropriate services
   - Maintain clean separation of concerns

### Common Patterns

#### Controller Method Delegation

```python
# In MainWindow
def add_subject(self):
    """Add subject using form controller."""
    success = self.main_controller.submit_subject_form()

# In MainController  
def submit_subject_form(self) -> bool:
    """Coordinate form submission across controllers."""
    return self.subject_form_controller.submit_form()
```

#### Signal-Based UI Updates

```python
# Connect controller signals to view methods
form_controller.validation_feedback_ready.connect(
    self._on_field_validation_changed
)

# Controller emits signals for UI updates
def _update_validation_state(self, field: str, is_valid: bool):
    self.validation_feedback_ready.emit(field, is_valid, error, warning)
```

#### Service Integration

```python
# Controllers use services for operations
def browse_for_file(self, field_name: str) -> str:
    return self.dialog_service.get_open_file_name(
        parent=self.view,
        caption=f"Select {field_name}",
        filter="NIFTI Files (*.nii *.nii.gz)"
    )
```

### Best Practices

1. **Centralized Coordination**: Use MainController as single point of coordination
2. **Interface Compliance**: Always update views through interface methods
3. **Signal Communication**: Use Qt signals for loose coupling between components
4. **Service Delegation**: Delegate complex operations to service layer
5. **Error Handling**: Provide meaningful feedback through DialogService
6. **State Management**: Keep application state in ApplicationModel
7. **Validation**: Implement comprehensive validation with visual feedback

### Medical Domain Considerations

1. **Clinical Workflow**: Form design optimized for neurosurgical data entry
2. **Error Prevention**: Validation prevents invalid medical data entry
3. **Professional UX**: Non-intrusive feedback suitable for clinical environments
4. **Data Integrity**: Comprehensive validation ensures medical data quality
5. **File Organization**: Subject directory structure follows medical imaging conventions

## Integration with ImagesViewer

The MainWindow creates and manages ImagesViewer instances for medical image visualization:

```python
def open_file_preview(self, file_path: str):
    """Open file preview - delegates to ViewDelegate for type checking."""
    if self.view_delegate.is_nifti_file(file_path):
        # Create ImagesViewer for medical images
        images_viewer = ImagesViewer(file_path)
        images_viewer.show()
    else:
        # Handle other file types with preview dialogs
        self.view_delegate.show_file_preview(file_path, self.view)
```

This integration allows seamless workflow from subject management to detailed medical image analysis and electrode localization.

## Current Status

The MainWindow architecture is **production-ready** with:

- ✅ Complete MVC implementation with type-safe interfaces
- ✅ Comprehensive form validation with visual feedback  
- ✅ Robust controller coordination patterns
- ✅ Service layer integration for clean architecture
- ✅ Medical workflow optimization
- ✅ Cross-platform compatibility

The architecture provides a solid foundation for medical-grade subject management and processing pipeline execution in neurosurgical environments.