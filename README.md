# CiCLONE: Cico Cardinale's Localization Of Neuro-electrodes

![CiCLONE Logo](docs/images/ciclone_banner.png)

A PyQt6-based neuroimaging application for localizing implanted electrodes in epilepsy patients. CiCLONE provides automated CT/MRI processing pipelines using FSL and FreeSurfer, with an intuitive graphical interface for electrode marking and coordinate transformation.

## Features

- **User-Friendly GUI** - Intuitive interface for subject management and image processing
- **Automated Pipelines** - CT and MRI-based workflows for electrode localization
- **Image Import** - Automatic cropping and registration of medical images
- **Built-in Image Viewer** - Multi-planar visualization with electrode marking tools
- **MNI Transformation** - Convert electrode coordinates to standard MNI space

## Installation

### Prerequisites

- **Python**: 3.10, 3.11, 3.12, or 3.13
- **Poetry**: Package manager (install via `pipx install poetry`)
- **FSL**: Medical image analysis toolkit
- **FreeSurfer**: (optional) For cortical reconstruction

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd CiCLONE

# Create virtual environment with Poetry
poetry env use $(pyenv which python3.12)  # or any Python 3.10-3.13

# Install dependencies
poetry install
```

### Environment Variables

Set up the required environment variables before running CiCLONE:

```bash
export FSLDIR=/path/to/fsl
export FREESURFER_HOME=/path/to/freesurfer  # optional
```

## Getting Started

Launch CiCLONE:

```bash
poetry run ciclone
```

The application provides:
- Subject creation and file import
- Interactive pipeline execution
- Built-in image viewer with electrode marking
- Real-time processing feedback

For detailed usage instructions, see the [User Guide](docs/users/userdoc.md).

## Documentation

- **[User Guide](docs/users/userdoc.md)** - Complete guide for using CiCLONE's GUI and features
- **[Architecture Documentation](docs/architecture/)** - Technical architecture and design patterns
- **[Developer Guide](CLAUDE.md)** - Development setup and contribution guidelines

## Acknowledgments

This project has received funding from the Swiss State Secretariat for Education, Research and Innovation (SERI) under contract number 23.00638, as part of the Horizon Europe project "EBRAINS 2.0".
