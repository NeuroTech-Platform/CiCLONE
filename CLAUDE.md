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
  - `SubjectController`: Subject management (create, rename, delete)
  - `ProcessingController`: Pipeline execution
  - `ImportController`: Image import workflows
  - `SubjectFormController`: Form validation and submission
  - `TreeViewController`: Subject tree view management

### Key Architecture Principles

1. **Controller Hierarchy**: MainController coordinates all child controllers and delegates responsibilities
2. **Signal-Based Communication**: PyQt6 signals used for model-to-view updates
3. **Service Layer**: Services in `ciclone/services/` handle specialized operations
4. **Worker Pattern**: Background processing uses QThread workers with multiprocessing

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

Background processing uses a two-level worker pattern:
1. **QThread Worker** (`ImageProcessingWorker`): Runs in Qt thread
2. **Multiprocessing Process** (`ImageProcessingProcess`): Separate process for FSL/FreeSurfer tools
3. **Communication**: Pipe-based messaging for progress updates and logging

Benefits:
- True parallelism for CPU-intensive operations
- Proper isolation of external tool execution
- Clean cancellation via process termination

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

The new unified import system:
1. User adds images with session (Pre/Post), modality (CT/MRI), optional registration target
2. `ImageEntry` model tracks image metadata
3. `ImportJob` encapsulates crop + optional registration operation
4. `ImportController` executes jobs in background worker
5. Files imported to appropriate subject folders with naming conventions

## Naming Conventions

Defined in `ciclone/config/naming_conventions.yaml`:
- Pre/Post session prefixes
- CT/MRI modality patterns
- Standard suffixes (_C for cropped, _N for nudged, etc.)

`NamingService` provides consistent file naming across the application.

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

## CLI Usage

The CLI (`ciclone-cli`) supports:
- `--create-folder`: Create subject folders
- `--subjects`: Select subjects to process
- `--stages`: Run specific stages (or all if omitted)
- `--transform-coordinates`: Transform electrode coordinates to MNI

All commands require `--directory` flag for output directory.
