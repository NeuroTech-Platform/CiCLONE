# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CiCLONE (Cico Cardinale's Localization Of Neuro-electrodes) is a PyQt6-based application for processing neuroimaging data (CT/MRI) to localize implanted electrodes in epilepsy patients. It provides both a GUI and CLI interface for running neuroimaging processing pipelines using FSL and FreeSurfer tools.

## Development Setup

```bash
# Setup virtual environment using Poetry (via pipx)
poetry env use $(pyenv which python3.11)  # or python3.12
poetry install

# Run GUI application
poetry run ciclone

# Run CLI application
poetry run ciclone-cli --directory /path/to/output --subjects subject1
```

## Running Tests

```bash
# Run all tests
python tests/run_tests.py

# Run specific test
python -m pytest tests/test_subject_domain.py
```

## Qt Designer Workflow

```bash
# Open Qt Designer to edit UI files
make design file=forms/MainWindow.ui

# After editing .ui files, convert them to Python using pyuic6
# The _ui.py files should NOT be manually edited
```

## Architecture

### MVC Pattern with Controllers

The application follows a strict Model-View-Controller architecture:

- **Models** (`ciclone/models/`): Business logic and data structures
  - `ApplicationModel`: Application state, configuration, output directory
  - `SubjectModel`: Subject data and operations
  - `*FormModel`: Form state and validation

- **Views** (`ciclone/ui/`): PyQt6 UI components implementing view interfaces
  - `MainWindow`: Main application window
  - View interfaces defined in `ciclone/interfaces/view_interfaces.py`

- **Controllers** (`ciclone/controllers/`): Coordinate between models and views
  - `MainController`: Main coordinator for all operations
  - `AbstractWorkerController`: Base class for worker-based controllers (template method pattern)
  - `SubjectController`: Subject management (create, rename, delete)
  - `ProcessingController`: Pipeline execution (inherits from AbstractWorkerController)
  - `ImportController`: Image import workflows (inherits from AbstractWorkerController)
  - `ConfigDialogController`: Configuration editing with transactional management
  - `SubjectFormController`: Form validation and submission
  - `TreeViewController`: Subject tree view management
  - `ElectrodeController`, `ImageController`, `CrosshairController`: ImagesViewer controllers

### Key Architecture Principles

1. **Controller Hierarchy**: MainController coordinates all child controllers and delegates responsibilities
2. **Signal-Based Communication**: PyQt6 signals used for model-to-view updates
3. **Service Layer**: Services in `ciclone/services/` handle specialized operations
4. **Abstract Worker Pattern**: Two-level background processing architecture
   - `AbstractWorkerController`: Template method pattern for controller coordination
   - `AbstractWorker`: Base QThread class managing multiprocessing.Process
   - Specialized implementations: `ProcessingController`/`ImageProcessingWorker` and `ImportController`/`ImportWorker`
5. **Template Method Pattern**: Eliminates duplication through abstract base classes
6. **Transaction Pattern**: Config editing uses `ConfigTransactionManager` for ACID-like operations

### Domain Model

- **Subject** (`ciclone/domain/subject.py`): Represents a patient with standardized folder structure
  - `images/preop/ct`, `images/preop/mri`
  - `images/postop/ct`, `images/postop/mri`
  - `processed_tmp/`: Intermediate processing files
  - `pipeline_output/`: Final results
  - `documents/`: Electrode schemas and documentation

- **Electrode** (`ciclone/domain/electrodes.py`): Represents electrode contacts with 3D coordinates
  - Used for marking electrode positions in subject space
  - Supports transformation to MNI standard space

### Multi-Configuration System

Pipeline configurations are YAML files in `ciclone/config/`:
- `config_ct.yaml`: CT-based pipeline (CTpre/CTpost)
- `config_mri.yaml`: MRI-based pipeline
- Each config defines stages with operations and dependencies

Configuration structure:
```yaml
name: Pipeline Name
stages:
  - name: stage_name
    depends_on: [prerequisite_stages]
    auto_clean: true  # Clean intermediate files after stage
    operations:
      - type: operation_name
        workdir: relative/path
        parameters:
          param1: value
```

### Processing Operations

All operations defined in `ciclone/services/processing/operations.py`:

**Core Operations**:
- `crop_image`: Remove excess background using FSL robustfov
- `coregister_images`: Register images using FSL FLIRT (6 DOF)
- `subtract_image`: Voxel-wise subtraction to isolate electrodes
- `threshold_image`: Threshold at 1600 to extract metallic artifacts
- `mask_image`: Apply binary mask using FSL fslmaths
- `extract_brain`: Brain extraction using FSL BET
- `apply_transformation`: Apply transformation matrix to images

**MNI Registration**:
- `register_mri_to_mni`: Two-stage MRI to MNI (6 DOF + 12 DOF)
- `register_ct_to_mni`: CT to MNI registration (12 DOF affine)
- `transform_coordinates`: Transform electrode coordinates to MNI space

**Advanced**:
- `cortical_reconstruction`: FreeSurfer recon-all pipeline
- `open_fsleyes`: Launch FSLeyes for visual inspection

### Variable Substitution in Configs

- `${name}`: Subject name
- `${subj_dir}`: Subject root directory path

### Worker Architecture

Background processing uses a two-level worker pattern based on template method design:

**Abstract Base Classes**:
- **`AbstractWorkerController`** (`ciclone/controllers/abstract_worker_controller.py`): Base for worker coordination
  - Template methods: `_create_worker_instance()`, `_get_operation_name()`, `_get_job_display_names()`
  - Common lifecycle: start, stop, progress tracking, cleanup
  - Subclassed by `ProcessingController` and `ImportController`
- **`AbstractWorker`** (`ciclone/workers/AbstractWorker.py`): Base QThread for background processes
  - Template methods: `_get_process_function()`, `_get_process_args()`, `_get_progress_signal_params()`
  - Manages multiprocessing.Process lifecycle
  - Subclassed by `ImageProcessingWorker` and `ImportWorker`

**Processing Pipeline Workers**:
1. **QThread Worker** (`ImageProcessingWorker`): Runs in Qt thread
2. **Multiprocessing Process** (`ImageProcessingProcess`): Separate process for FSL/FreeSurfer tools
3. **Communication**: Pipe-based messaging for progress updates and logging

**Import Workers**:
1. **QThread Worker** (`ImportWorker`): Runs in Qt thread
2. **Multiprocessing Process** (`ImportProcess`): Separate process for crop/registration operations
3. **Job Format**: `ImportJob` encapsulates crop + optional registration

Benefits:
- True parallelism for CPU-intensive operations
- Proper isolation of external tool execution
- Clean cancellation via process termination
- Code reuse through template method pattern

### Logging System

Two-level logging controlled via verbose mode (Ctrl+V):
- **Info/Warning/Error**: Always visible
- **Debug**: Only visible in verbose mode

Log callback pattern: Controllers pass `(level, message)` tuples up to MainController.

## Environment Requirements

**FSL**: Set `FSLDIR` environment variable
**FreeSurfer**: Set `FREESURFER_HOME` environment variable

The application validates these at startup via `tool_config.validate_environment()`.

## Image Import Workflow

The unified import system (introduced in commit 16a849c):

**Data Models**:
- **`ImageEntry`** (`ciclone/models/image_entry.py`): Represents individual image metadata
  - Attributes: `file_path`, `session` (Pre/Post), `modality` (CT/MRI/PET), `register_to` (optional)
  - Methods: `get_display_name()`, `get_target_directory()`
- **`ImportJob`** (`ciclone/models/import_job.py`): Unified import operation
  - Combines crop + optional registration operations
  - Serializable for multiprocessing communication
  - Validation mixin for file/directory checks

**Workflow**:
1. User adds images in MainWindow with session, modality, and optional registration target
2. `SubjectFormController` collects `ImageEntry` objects in `SubjectFormModel`
3. On submit, `MainController` creates `ImportJob` instances from `ImageEntry` list
4. **Registration Target Resolution**: `RegistrationTargetResolver` resolves target identifiers
   - Supports "[Pre] CT", "[Post] MRI #2" notation
   - Searches both newly-imported images and existing subject files
   - Prompts user for ambiguous references
5. `ImportController` creates `ImportWorker` with jobs
6. `ImportWorker` spawns `ImportProcess` in separate process
7. Each job executes: crop → optional registration → import to subject directory
8. **MRI Modality Detection**: `SubjectImporter` reads NIFTI headers for sequence type
   - Detects T1, T2, FLAIR, DWI, SWI, TOF, PDW, BOLD, ASL
   - Falls back to filename patterns if header unclear
9. Files imported with standardized naming via `NamingService`

**Key Services**:
- `RegistrationTargetResolver`: Resolves target image references
- `SubjectImporter`: Import operations with MRI modality detection
- `NamingService`: Consistent file naming conventions

## Naming Conventions

Defined in `ciclone/config/naming_conventions.yaml`:
- Pre/Post session prefixes
- CT/MRI modality patterns
- Standard suffixes (_C for cropped, _N for nudged, etc.)

`NamingService` provides consistent file naming across the application.

## Configuration Transaction Management

The pipeline configuration editing system uses a sophisticated transactional approach:

**Manager**: `ConfigTransactionManager` (`ciclone/managers/config_transaction_manager.py`)

**Key Features**:
- **Transactional Editing**: All changes remain in memory until explicit commit (Save)
- **Hierarchical Tracking**: Tracks dirty state at Pipeline/Stage/Operation levels
- **Entity Paths**: `"pipeline:0:stage:1:operation:2"` format for precise tracking
- **Change Types**: NONE, ADDED, MODIFIED, DELETED, REORDERED
- **Dirty State Indicators**: Real-time asterisk (*) markers in UI for modified entities
- **Context-Aware Prompting**: Only prompts for unsaved changes when necessary
- **Revert Detection**: Automatically cleans dirty state when values revert to original
- **Atomic Operations**: Either all changes save or none (no partial commits)

**Usage**:
```python
# In ConfigDialogController
manager = ConfigTransactionManager(config_path)
manager.begin_transaction()  # Load original configs

# Make changes (tracked automatically)
manager.update_pipeline_field(index, "name", new_value)
manager.update_stage_field(p_idx, s_idx, "name", new_value)

# Check dirty state
if manager.is_pipeline_dirty(index):
    # Show indicator

# Commit or rollback
if user_saves:
    manager.commit_transaction()  # Write to disk
else:
    manager.rollback_transaction()  # Discard all changes
```

**Visual Feedback**:
- Modified pipelines: `Pipeline Name *`
- Modified stages: `Stage Name *`
- Modified operations: `1. operation_type *`
- Window title: `Configuration Editor * (unsaved changes)`

**Integration**: See `docs/architecture/config-transaction-management.md` for complete documentation.

## Testing Strategy

Tests in `tests/` directory:
- Domain model tests (Subject, Electrode)
- Service tests (NamingService, SubjectFileService)
- Factory tests (SubjectDataFactory)
- UI delegate tests (electrode view)

## Common Workflows

### Adding New Pipeline Operation

1. Add operation function to `ciclone/services/processing/operations.py`
2. Document parameters with docstring (see existing operations)
3. Add operation type to config YAML
4. Update operation dispatch in `ciclone/main_cli.py` if needed

### Adding New UI Field

1. Edit `.ui` file in Qt Designer (`make design file=forms/MainWindow.ui`)
2. Connect signals in `MainWindow.__init__()`
3. Add validation logic to appropriate form controller
4. Update form model if state tracking needed

### Modifying Subject Structure

1. Update `Subject` class in `ciclone/domain/subject.py`
2. Update `SubjectFileService.create_subject_directories()`
3. Update any operations that depend on folder structure
4. Update naming conventions if needed

### Adding New Background Worker Operation

When adding a new operation that requires background processing:

1. **Create Data Models** (if needed):
   - Define job data structure (e.g., `ImportJob`)
   - Add validation mixin if needed (`JobValidationMixin`)

2. **Create Worker Classes**:
   - Subclass `AbstractWorker` for QThread worker
   - Implement template methods: `_get_process_function()`, `_get_process_args()`, `_get_progress_signal_params()`
   - Create process function in separate module (e.g., `ImportProcess.py`)

3. **Create Controller**:
   - Subclass `AbstractWorkerController`
   - Implement template methods: `_create_worker_instance()`, `_get_operation_name()`, `_get_job_display_names()`
   - Add public API methods (e.g., `run_operation()`, `stop_operation()`, `is_running()`)

4. **Integrate with MainController**:
   - Initialize new controller in `MainController.__init__()`
   - Connect signals for progress/completion updates
   - Add UI controls and feedback

5. **Test**:
   - Test worker lifecycle (start, progress, completion, cancellation)
   - Test error handling and cleanup
   - Verify cross-platform compatibility

## CLI Usage

The CLI (`ciclone-cli`) supports:
- `--create-folder`: Create subject folders
- `--subjects`: Select subjects to process
- `--stages`: Run specific stages (or all if omitted)
- `--transform-coordinates`: Transform electrode coordinates to MNI

All commands require `--directory` flag for output directory.
