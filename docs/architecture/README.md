# CiCLONE Architecture Documentation

Welcome to the CiCLONE architecture documentation. This directory contains comprehensive documentation about the application's architecture, design patterns, and component relationships.

## 📚 Documentation Structure

### Core Architecture
- **[architecture.md](./architecture.md)** - Complete architectural overview, patterns, and development guidelines
- **[mainwindow.md](./mainwindow.md)** - MainWindow component architecture and controller relationships
- **[imagesviewer.md](./imagesviewer.md)** - ImagesViewer component architecture and MVC coordination

### Feature Documentation
- **[electrode-auto-detection.md](./electrode-auto-detection.md)** - Automatic electrode detection algorithm and implementation

### Quick Navigation

#### 🏗️ For New Developers
1. **Start Here**: [architecture.md](./architecture.md) - Overview and quick start guide
2. **UI Components**: [mainwindow.md](./mainwindow.md) and [imagesviewer.md](./imagesviewer.md)
3. **Project Structure**: See architecture.md project structure section

#### 🔧 For Component Development
- **MainWindow Features**: See [mainwindow.md](./mainwindow.md) for subject management and processing pipeline
- **Image Viewer Features**: See [imagesviewer.md](./imagesviewer.md) for medical image display and electrode management
- **MVC Patterns**: Both component docs include detailed MVC implementation patterns

#### 📋 For Architecture Understanding
- **Overall Design**: [architecture.md](./architecture.md) - Complete architectural patterns and philosophy
- **Component Relationships**: Diagrams and flow charts in individual component docs
- **Data Flow**: Detailed examples in each component documentation

## 🎯 Quick Reference

### Component Responsibilities

| Component | Primary Purpose | Key Controllers | Documentation |
|-----------|----------------|-----------------|---------------|
| **MainWindow** | Application entry point, subject management, processing pipeline | MainController, SubjectController, ProcessingController | [mainwindow.md](./mainwindow.md) |
| **ImagesViewer** | Medical image display, electrode localization, coordinate management | ImageController, ElectrodeController, CrosshairController | [imagesviewer.md](./imagesviewer.md) |
| **Auto-Detection** | Automatic electrode contact detection from CT images | CTElectrodeDetector, DetectionService | [electrode-auto-detection.md](./electrode-auto-detection.md) |

### Architecture Patterns

- **🏛️ MVC Architecture**: Strict separation with type-safe interfaces
- **🎯 Domain-Driven Design**: Pure business entities in domain layer
- **🔧 Service Layer**: Clean abstraction for business operations
- **👁️ Observer Pattern**: Qt signals/slots for component communication
- **🔗 Interface Contracts**: Protocol-based type safety throughout

### Technology Stack

- **Backend**: Python 3.11/3.12, NumPy 2.x, NiBabel
- **UI Framework**: PyQt6 with Qt Designer integration
- **Medical Tools**: FSL, FreeSurfer (perfectly isolated dependencies)
- **Architecture**: Complete MVC with service layer and type-safe interfaces

## 📖 Reading Guide

### For First-Time Contributors
```
1. architecture.md (Overview and setup)
   ↓
2. mainwindow.md (Primary UI understanding)
   ↓  
3. imagesviewer.md (Medical image processing understanding)
   ↓
4. Choose specific component for your work
```

### For Specific Tasks

#### Adding MainWindow Features
- Read [mainwindow.md](./mainwindow.md) controller specifications
- Focus on MainController coordination patterns
- Follow form validation and processing pipeline examples

#### Adding ImagesViewer Features  
- Read [imagesviewer.md](./imagesviewer.md) MVC coordination
- Understand image display and electrode management
- Follow coordinate transformation examples

#### Understanding Data Flow
- Both component docs include detailed data flow examples
- See architecture.md for overall application data flow patterns
- Follow signal-based communication examples

## 🚀 Development Best Practices

### Architecture Compliance
- **Interface First**: Use type-safe Protocol interfaces
- **Service Layer**: Business logic belongs in services, not controllers
- **Domain Purity**: Keep domain objects free of technical dependencies
- **Signal Communication**: Use Qt signals for loose coupling

### Code Organization
- **MVC Boundaries**: Maintain strict separation of concerns
- **Single Responsibility**: Each component has one clear purpose
- **Dependency Injection**: Services support testable interfaces
- **Type Safety**: Comprehensive type hints throughout

### Medical Domain Focus
- **Clinical Workflows**: UI optimized for neurosurgical procedures
- **Error Prevention**: Interface design prevents common mistakes
- **Professional UX**: Elegant, non-intrusive feedback for medical environments
- **Data Integrity**: Comprehensive validation for medical data

## 🎯 Current Status: Production Ready

CiCLONE has achieved production-ready status with complete MVC architecture, perfect dependency isolation, and medical-grade user experience. The documentation reflects this mature, stable codebase ready for clinical deployment.

---

**Next Steps**: Choose the appropriate documentation file based on your development needs and refer back to this guide for navigation between different architectural concerns.