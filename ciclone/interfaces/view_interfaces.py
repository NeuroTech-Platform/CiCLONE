"""
View Interfaces for CiCLONE Application

This module defines the contracts between controllers and views, ensuring proper
separation of concerns and enabling testable, maintainable code.

These interfaces represent the final step in our MVC architecture implementation.

Note: We use Protocol instead of ABC to avoid metaclass conflicts with Qt classes.
"""

from typing import Protocol, List, Dict, Any, Optional, Tuple
from PyQt6.QtWidgets import QWidget


class IMainView(Protocol):
    """Interface for the main application view."""
    
    # =============================================================================
    # Subject Management Interface
    # =============================================================================
    
    def refresh_subject_tree(self) -> None:
        """Refresh the subject tree view with current subjects."""
        ...
    
    def update_schema_field(self, schema_text: str) -> None:
        """Update the schema field with provided text."""
        ...
    
    def update_field(self, field_name: str, file_path: str) -> None:
        """Update a specific form field with a file path."""
        ...
    
    def on_form_reset(self) -> None:
        """Handle form reset operations."""
        ...
    
    # =============================================================================
    # Processing Interface
    # =============================================================================
    
    def update_processing_ui(self, is_running: bool, progress: int) -> None:
        """Update processing UI state and progress."""
        ...
    
    def clear_processing_log(self) -> None:
        """Clear the processing log display."""
        ...
    
    def add_log_message(self, level: str, message: str) -> None:
        """Add a log message to the display."""
        ...
    
    # =============================================================================
    # UI State Management Interface  
    # =============================================================================
    
    def set_output_directory_text(self, directory: str) -> None:
        """Set the output directory text field."""
        ...
    
    def enable_form_controls(self, enabled: bool) -> None:
        """Enable or disable form controls."""
        ...
    
    def show_status_message(self, message: str, timeout: int = 0) -> None:
        """Show a status message."""
        ...
    
    # =============================================================================
    # Validation Feedback Interface
    # =============================================================================
    
    def set_field_validation_state(self, field_name: str, is_valid: bool, 
                                 error_message: str = "", warning_message: str = "") -> None:
        """Set validation state for a form field."""
        ...
    
    def set_form_submission_state(self, can_submit: bool) -> None:
        """Set whether the form can be submitted."""
        ...


class IImageView(Protocol):
    """Interface for image viewing components."""
    
    # =============================================================================
    # Image Loading and Display Interface
    # =============================================================================
    
    def load_image_file(self, file_path: str) -> bool:
        """Load an image file for display."""
        ...
    
    def refresh_all_views(self) -> None:
        """Refresh all image views (axial, sagittal, coronal)."""
        ...
    
    def update_slice_display(self, orientation: str, slice_index: int) -> None:
        """Update slice display for a specific orientation."""
        ...
    
    def set_slice_range(self, orientation: str, min_slice: int, max_slice: int) -> None:
        """Set the valid slice range for an orientation."""
        ...
    
    # =============================================================================
    # Image Controls Interface
    # =============================================================================
    
    def enable_image_controls(self, enabled: bool = True) -> None:
        """Enable or disable image control widgets."""
        ...
    
    def update_slider_ranges(self) -> None:
        """Update slider ranges based on loaded images."""
        ...
    
    def show_default_display(self) -> None:
        """Show default display when no image is loaded."""
        ...
    
    # =============================================================================
    # Overlay Management Interface
    # =============================================================================
    
    def set_overlay_visibility(self, visible: bool) -> None:
        """Set overlay visibility."""
        ...
    
    def update_overlay_opacity(self, opacity: float) -> None:
        """Update overlay opacity."""
        ...
    
    def refresh_overlay_controls(self) -> None:
        """Refresh overlay control widgets."""
        ...
    
    # =============================================================================
    # Electrode Management Interface
    # =============================================================================
    
    def refresh_electrode_list(self) -> None:
        """Refresh the electrode list display."""
        ...
    
    def clear_electrode_input(self) -> None:
        """Clear electrode input fields."""
        ...
    
    def update_coordinate_display(self) -> None:
        """Update coordinate display."""
        ...
    
    def enable_electrode_controls(self, enabled: bool) -> None:
        """Enable or disable electrode control widgets."""
        ...
    
    # =============================================================================
    # Crosshair Interface
    # =============================================================================
    
    def show_crosshairs(self, show: bool) -> None:
        """Show or hide crosshairs."""
        ...
    
    def update_crosshair_position(self, x: int, y: int, z: int) -> None:
        """Update crosshair position."""
        ...
    
    def synchronize_crosshairs(self) -> None:
        """Synchronize crosshairs across all views."""
        ...
    
    # =============================================================================
    # Data Tree Interface
    # =============================================================================
    
    def add_file_to_data_tree(self, file_path: str) -> None:
        """Add a file to the data tree widget."""
        ...
    
    def refresh_data_tree(self) -> None:
        """Refresh the data tree display."""
        ...
    
    def clear_data_tree(self) -> None:
        """Clear the data tree."""
        ...


class IViewer3D(Protocol):
    """Interface for 3D viewing components."""
    
    # =============================================================================
    # 3D Rendering Interface
    # =============================================================================
    
    def load_volume_data(self, volume_data: Any) -> bool:
        """Load volume data for 3D rendering."""
        ...
    
    def update_rendering(self) -> None:
        """Update the 3D rendering."""
        ...
    
    def reset_camera(self) -> None:
        """Reset camera to default position."""
        ...
    
    # =============================================================================
    # Electrode Visualization Interface
    # =============================================================================
    
    def add_electrode_to_scene(self, electrode_data: Dict[str, Any]) -> None:
        """Add electrode visualization to the 3D scene."""
        ...
    
    def remove_electrode_from_scene(self, electrode_name: str) -> None:
        """Remove electrode from the 3D scene."""
        ...
    
    def update_electrode_visibility(self, electrode_name: str, visible: bool) -> None:
        """Update electrode visibility in 3D scene."""
        ...
    
    # =============================================================================
    # View Controls Interface
    # =============================================================================
    
    def set_rendering_quality(self, quality: str) -> None:
        """Set rendering quality (low, medium, high)."""
        ...
    
    def enable_interaction(self, enabled: bool) -> None:
        """Enable or disable 3D interaction."""
        ...
    
    def export_screenshot(self, file_path: str) -> bool:
        """Export 3D view as screenshot."""
        ...


class IBaseView(Protocol):
    """Base interface for all views providing common functionality."""
    
    # =============================================================================
    # Message Display Interface
    # =============================================================================
    
    def show_error_message(self, title: str, message: str) -> None:
        """Show error message dialog."""
        ...
    
    def show_warning_message(self, title: str, message: str) -> None:
        """Show warning message dialog."""
        ...
    
    def show_info_message(self, title: str, message: str) -> None:
        """Show info message dialog."""
        ...
    
    # =============================================================================
    # State Management Interface
    # =============================================================================
    
    def set_busy_state(self, busy: bool) -> None:
        """Set view busy state (e.g., loading cursor)."""
        ...
    
    def get_widget(self) -> QWidget:
        """Get the underlying QWidget."""
        ... 