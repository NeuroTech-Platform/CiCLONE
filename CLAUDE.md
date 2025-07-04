# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CiCLONE (Cico Cardinale's Localization Of Neuro-electrodes) is a production-ready Python application for medical image processing and electrode localization in neurosurgical procedures. It implements a complete MVC architecture with PyQt6 GUI and advanced medical imaging capabilities.

## Development Commands

### Environment Setup
```bash
# Setup Poetry environment with Python 3.11 or 3.12
poetry env use $(pyenv which python3.11)
# or
poetry env use $(pyenv which python3.12)

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
No specific test/lint commands found in project configuration. Check with maintainers for preferred testing approach.

## Architecture Overview

### MVC Pattern with Service Layer
- **Domain Layer** (`ciclone/domain/`): Pure business entities (electrodes, subjects)
- **Service Layer** (`ciclone/services/`): Business logic organized by domain
  - `ui/`: Dialog service and view delegates for UI abstraction
  - `processing/`: Medical image processing operations (FSL/FreeSurfer integration)
  - `io/`: File I/O operations for medical data formats
- **Models** (`ciclone/models/`): Application state and data management with Qt signals
- **Controllers** (`ciclone/controllers/`): Coordinate between models and views
- **Views** (`ciclone/ui/`): PyQt6 GUI components with professional medical UI
- **Interfaces** (`ciclone/interfaces/`): Type-safe Protocol-based view contracts

### Key Components
- **MainWindow**: Central application with subject management and processing pipeline
- **ImagesViewer**: Multi-planar medical image viewer with overlay controls
- **Viewer3D**: 3D visualization component
- **Processing Pipeline**: Configurable YAML-based stages for FSL/FreeSurfer operations
- **Electrode Management**: Interactive coordinate setting with validation

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
- **Perfect Isolation Strategy**: FSL tools are self-contained, eliminating NumPy version conflicts
- **Modern Stack**: NumPy 2.x, PyQt6, NiBabel for medical imaging

### Configuration
- `config/config.yaml`: Processing pipeline configuration
- `config/electrodes/`: Electrode definition files (.elecdef format)
- Copy `config.yaml.template` to `config.yaml` and update paths before first run

### Data Flow
1. Subject management through MainWindow with directory structure creation
2. Medical image loading via NIFTI format with NiBabel
3. Interactive electrode coordinate setting in ImagesViewer
4. Background processing pipeline execution with FSL/FreeSurfer
5. Results export to subject-specific directories

## Important Notes

- **Production Ready Status**: Complete MVC implementation with medical-grade stability
- **No Test Framework Discovered**: Verify testing approach with maintainers before adding tests
- **Medical Domain Focus**: UI and workflows optimized for neurosurgical procedures
- **Cross-Platform**: Designed for macOS/Linux, Windows compatibility via Qt6