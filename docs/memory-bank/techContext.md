# CiCLONE Technical Context

## Technology Stack

### Core Technologies

#### Python 3.12+
- **Primary Language**: Modern Python with type hints and advanced features
- **Minimum Version**: Python 3.10 (development on 3.12)
- **Key Features Used**: Dataclasses, type annotations, pathlib, async/await

#### PyQt6
- **GUI Framework**: Modern Qt6 bindings for Python
- **Version**: ^6.8.1
- **Key Components**: 
  - QMainWindow, QTreeView, QTabWidget for UI structure
  - QSlider, QComboBox, QPushButton for controls
  - QPixmap, QImage for image display
  - QThread, QTimer for background processing
  - Signal/slot system for event handling

#### Medical Imaging Libraries

**NiBabel (^5.3.2)**
- **Purpose**: NIFTI medical image format support
- **Usage**: Loading, processing, and saving neuroimaging data
- **Integration**: Primary interface for medical image I/O

**VTK (^9.4.2)** 
- **Purpose**: 3D visualization and processing
- **Usage**: 3D electrode visualization, volume rendering
- **Integration**: 3D viewer component support

#### Numerical Computing

**NumPy (^2.2.0)**
- **Purpose**: Numerical operations, array processing
- **Usage**: Image data manipulation, coordinate transformations
- **Critical For**: Slice extraction, overlay blending, coordinate calculations

#### Configuration and Data

**PyYAML (^6.0.1)**
- **Purpose**: Configuration file parsing
- **Usage**: Processing pipeline configuration, stage definitions
- **Files**: `config.yaml` for pipeline stages and operations

**Argcomplete (^3.2.2)**
- **Purpose**: Command-line interface enhancements
- **Usage**: CLI auto-completion for pipeline operations

#### Additional Libraries

**Pillow (^10.0.0)**
- **Purpose**: Image processing utilities
- **Usage**: Image format conversions, basic image operations

**Docling (^2.37.0) + Markdown (^3.6)**
- **Purpose**: Documentation processing
- **Usage**: File preview capabilities, documentation rendering

### External Tool Dependencies

#### FSL (FMRIB Software Library)
- **Purpose**: Medical image analysis toolkit
- **Operations**: 
  - Image registration and coregistration
  - Brain extraction
  - Coordinate transformations
- **Integration**: Command-line tool execution via subprocess
- **Environment**: Requires FSL installation and environment setup

#### FreeSurfer
- **Purpose**: Neuroimaging analysis and visualization
- **Operations**:
  - Cortical reconstruction 
  - Anatomical processing
  - Surface-based analysis
- **Integration**: Pipeline execution through subprocess calls
- **Environment**: Requires FreeSurfer installation and licensing

#### ANTs (Advanced Normalization Tools)
- **Purpose**: Image registration and normalization
- **Operations**:
  - Non-linear registration
  - Template-based normalization
  - Coordinate transformations
- **Integration**: Subprocess execution for registration operations

#### 3D Slicer (File Format Compatibility)
- **Purpose**: Medical image visualization and analysis
- **Integration**: File format compatibility for electrode coordinates
- **Usage**: Import/export of coordinate data in Slicer JSON format

## Development Environment

### Package Management

#### Poetry
- **Tool**: Modern Python package management
- **Configuration**: `pyproject.toml`
- **Benefits**: 
  - Dependency resolution and locking
  - Virtual environment management
  - Build system integration
  - Script execution (`ciclone`, `ciclone-cli`)

**Setup Commands:**
```bash
# Environment setup
poetry env use $(pyenv which python3.12)
poetry install

# Running application
poetry run ciclone          # GUI application
poetry run ciclone-cli      # CLI interface
```

### Development Tools

#### Qt Designer Integration
- **Purpose**: UI design and layout
- **Files**: `.ui` files in `ciclone/forms/`
- **Workflow**: Design → Convert to Python → Import in views
- **Auto-generation**: `*_ui.py` files generated from `.ui` files

#### Version Control
- **Tool**: Git with feature branch workflow
- **Current Branch**: `feat/UI` (UI improvements and MVC refactoring)
- **Strategy**: Feature branches for major developments

## Architecture Dependencies

### Layer Dependencies
```
┌─────────────────────────────────────────────────────────────────┐
│                        External Tools                          │
│              FSL • FreeSurfer • ANTs • 3D Slicer              │
└─────────────────────────────────────────────────────────────────┘
                                   ↑
┌─────────────────────────────────────────────────────────────────┐
│                    Python Application                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │   PyQt6     │  │   NiBabel   │  │   NumPy     │           │
│  │  (GUI)      │  │ (Medical    │  │ (Compute)   │           │
│  │             │  │  Imaging)   │  │             │           │
│  └─────────────┘  └─────────────┘  └─────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                                   ↑
┌─────────────────────────────────────────────────────────────────┐
│                    Python 3.12+ Runtime                       │
└─────────────────────────────────────────────────────────────────┘
```

### Critical Path Dependencies

**Image Processing Chain:**
```
NIFTI Files → NiBabel → NumPy Arrays → Qt Display Pipeline
```

**External Processing:**
```
Configuration → YAML Parser → Subprocess Management → FSL/FreeSurfer
```

**UI Rendering:**
```
Medical Images → NumPy → QImage → QPixmap → QLabel Display
```

## Configuration Management

### Application Configuration

#### config.yaml Structure
```yaml
stages:
  - name: preprocessing
    operations:
      - type: crop
        workdir: preop/ct
        files: ["${name}_CT_Bone", "${name}_CT_Bone_C"]
      - type: coregister
        workdir: postop/ct
        files: [input, reference, output]
```

#### Electrode Definitions
- **Location**: `ciclone/config/electrodes/`
- **Format**: `.elecdef` files
- **Examples**: 
  - `Dixi-D08-05AM.elecdef` (5-contact electrode)
  - `Dixi-D08-15AM.elecdef` (15-contact electrode)
- **Content**: Electrode specifications, contact spacing, geometric properties

### Environment Configuration

#### Required Environment Variables
- **FSL Setup**: `FSLDIR`, `FSLOUTPUTTYPE`
- **FreeSurfer Setup**: `FREESURFER_HOME`, `SUBJECTS_DIR`
- **ANTs Setup**: `ANTSPATH`

#### Application Settings
- **Output Directory**: User-configurable base directory for subjects
- **Processing Configuration**: Pipeline stages and operations
- **Electrode Libraries**: Available electrode types and definitions

## Performance Considerations

### Memory Management
- **Large Medical Images**: NIFTI files can be several GB
- **Strategy**: Lazy loading, slice-based access
- **Optimization**: Efficient NumPy array operations

### Background Processing
- **Threading**: Qt QThread for UI responsiveness
- **Process Management**: Subprocess execution for external tools
- **Progress Tracking**: Real-time feedback on long operations

### UI Responsiveness
- **Image Display**: Efficient pixmap caching and scaling
- **Overlay Blending**: Real-time opacity adjustments
- **Event Handling**: Debounced resize events, optimized redraws

## Platform Support

### Target Platforms
- **macOS**: Primary development platform (darwin 24.5.0)
- **Linux**: Scientific computing environments
- **Windows**: Clinical workstation support

### Platform-Specific Considerations
- **External Tool Paths**: Platform-specific FSL/FreeSurfer installations
- **File Paths**: Cross-platform path handling with pathlib
- **Process Execution**: Platform-aware subprocess management

## Security and Compliance

### Medical Data Handling
- **Data Privacy**: Local processing, no cloud dependencies
- **File Permissions**: Secure subject directory management
- **Data Integrity**: Validation of coordinate transformations

### Tool Integration Security
- **Subprocess Execution**: Controlled external tool invocation
- **Input Validation**: Sanitized parameters for external commands
- **Error Handling**: Safe failure modes for external tool errors

## Deployment Considerations

### Installation Requirements
1. **Python Environment**: Python 3.12+ with poetry
2. **External Tools**: FSL, FreeSurfer, ANTs installations
3. **System Libraries**: Qt6 system dependencies
4. **Medical Data**: Access to NIFTI medical imaging files

### Runtime Dependencies
- **Environment Setup**: Proper FSL/FreeSurfer environment configuration
- **File Access**: Read/write permissions for subject directories
- **Network**: Optional for documentation and updates (local operation capable)

### Development Setup
```bash
# 1. Python environment
poetry env use $(pyenv which python3.12)
poetry install

# 2. Configuration
cp ciclone/config/config.yaml.template ciclone/config/config.yaml

# 3. External tools (platform-specific)
# Install FSL, FreeSurfer, ANTs according to platform instructions

# 4. Run application
poetry run ciclone
``` 