# CiCLONE Project Brief

## Project Name
**CiCLONE** - Cico Cardinale's Localization Of Neuro-electrodes

## Core Purpose
CiCLONE is a specialized medical imaging application designed for neurosurgical electrode localization and analysis. The application provides a comprehensive pipeline for processing medical images (CT, MRI) and precisely localizing electrode positions in 3D space, transforming coordinates between subject and standard (MNI) spaces.

## Primary Goals

### Medical Imaging Pipeline
- Process preoperative and postoperative medical images (CT/MRI)
- Integrate with industry-standard neuroimaging tools (FSL, FreeSurfer, ANTs)
- Provide automated and manual processing stages for image registration, coregistration, and transformation

### Electrode Localization
- Enable precise 3D localization of neuro-electrodes from medical images
- Support various electrode types with configurable definitions
- Transform electrode coordinates from subject space to standardized MNI space
- Integration with 3D Slicer workflow for electrode marking

### User Interface
- Provide intuitive desktop application for medical professionals
- Multi-planar image visualization (axial, sagittal, coronal views)
- Interactive electrode placement and coordinate setting
- Real-time visualization with overlay capabilities
- Subject and data management interface

### Processing Automation
- Configurable multi-stage processing pipeline
- Background processing with progress tracking
- Batch processing capabilities for multiple subjects
- Integration with external neuroimaging toolkits

## Target Users
- Neurosurgeons and neuroscientists
- Medical imaging technicians
- Researchers working with electrode localization
- Clinical teams requiring precise electrode coordinate analysis

## Key Requirements

### Functional Requirements
1. Load and display NIFTI medical images
2. Support multi-image overlay with opacity controls
3. Enable precise coordinate setting through image interaction
4. Process images through configurable pipeline stages
5. Transform coordinates between coordinate systems
6. Export results in standard formats (JSON)
7. Manage subject data and directory structures

### Technical Requirements
1. Cross-platform desktop application (macOS, Linux, Windows)
2. Integration with FSL, FreeSurfer, and ANTs toolkits
3. PyQt6-based modern GUI interface
4. NIFTI image format support via NiBabel
5. Processing pipeline configuration via YAML
6. Background processing with Qt threading

### Quality Requirements
1. Precise coordinate calculations and transformations
2. Reliable processing pipeline execution
3. Intuitive and responsive user interface
4. Proper error handling and user feedback
5. Maintainable codebase with clean architecture

## Success Criteria
- Accurate electrode localization with sub-millimeter precision
- Seamless integration with existing clinical workflows
- Reliable processing of standard neuroimaging datasets
- User-friendly interface requiring minimal training
- Robust handling of various image formats and electrode types

## Constraints
- Dependent on external neuroimaging toolkits (FSL, FreeSurfer)
- Medical-grade precision requirements
- NIFTI format standardization
- Clinical workflow integration needs
- Performance requirements for real-time image display and interaction 