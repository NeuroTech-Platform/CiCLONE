from typing import Optional, Tuple, Dict
from PyQt6.QtGui import QColor

from ciclone.models.crosshair_model import CrosshairModel


class CrosshairController:
    """Controller for managing crosshair operations and coordinating between model and views."""
    
    def __init__(self, crosshair_model: CrosshairModel, image_controller):
        self.crosshair_model = crosshair_model
        self.image_controller = image_controller
        self._view = None
        
        # Connect model signals to controller methods
        self.crosshair_model.crosshair_enabled_changed.connect(self._on_enabled_changed)
        self.crosshair_model.crosshair_position_changed.connect(self._on_position_changed)
        
        # Default crosshair appearance
        self._crosshair_color = QColor(255, 255, 0, 180)  # Yellow with transparency
        self._crosshair_line_width = 2
    
    def set_view(self, view):
        """Set the view reference for UI updates."""
        self._view = view
    
    def toggle_crosshairs(self, enabled: bool) -> None:
        """Toggle crosshair display on all views."""
        self.crosshair_model.set_enabled(enabled)
    
    def is_enabled(self) -> bool:
        """Check if crosshairs are currently enabled."""
        return self.crosshair_model.is_enabled()
    
    def set_crosshair_position(self, position: Tuple[int, int, int]) -> None:
        """Set the crosshair position if crosshairs are enabled."""
        if self.crosshair_model.is_enabled():
            self.crosshair_model.set_position(position)
    
    def get_crosshair_position(self) -> Optional[Tuple[int, int, int]]:
        """Get the current crosshair position."""
        return self.crosshair_model.get_position()
    
    def update_crosshairs_for_view(self, label, orientation: str, current_slices: Dict[str, int], 
                                 scaled_width: int, scaled_height: int) -> None:
        """Update crosshairs for a specific view."""
        if not self.image_controller.is_image_loaded():
            return
        
        # Only show crosshairs if enabled and position is set
        if not self.crosshair_model.is_enabled() or not self.crosshair_model.has_position():
            label.remove_crosshairs()
            return
        
        # Get crosshair position and convert to pixel coordinates
        position = self.crosshair_model.get_position()
        crosshair_coords = self.image_controller.convert_3d_to_pixel_coords(
            position, orientation, scaled_width, scaled_height
        )
        
        if crosshair_coords:
            crosshair_x, crosshair_y = crosshair_coords
            
            if label.has_crosshairs():
                # Update existing crosshairs efficiently
                label.update_crosshairs(crosshair_x, crosshair_y)
            else:
                # Create new crosshairs
                label.add_crosshairs(crosshair_x, crosshair_y, self._crosshair_color, self._crosshair_line_width)
        else:
            # Remove crosshairs if position cannot be calculated
            label.remove_crosshairs()
    
    def set_crosshair_appearance(self, color: QColor = None, line_width: int = None) -> None:
        """Set crosshair appearance properties."""
        if color is not None:
            self._crosshair_color = color
        if line_width is not None:
            self._crosshair_line_width = line_width
        
        # Refresh views if there are crosshairs to update
        if self.crosshair_model.is_enabled() and self.crosshair_model.has_position() and self._view:
            self._view.refresh_all_views()
    
    def _on_enabled_changed(self, enabled: bool) -> None:
        """Handle crosshair enabled state change."""
        if self._view:
            if not enabled:
                # Remove crosshairs from all views when disabled
                self._view.remove_all_crosshairs()
            else:
                # Refresh views when enabled (in case position was already set)
                self._view.refresh_all_views()
    
    def _on_position_changed(self, position: Optional[Tuple[int, int, int]]) -> None:
        """Handle crosshair position change."""
        if self._view and self.crosshair_model.is_enabled():
            self._view.refresh_all_views() 