from typing import Optional, Tuple
from PyQt6.QtCore import QObject, pyqtSignal


class CrosshairModel(QObject):
    """Model for managing crosshair state and business logic."""
    
    # Signals for state changes
    crosshair_enabled_changed = pyqtSignal(bool)
    crosshair_position_changed = pyqtSignal(object)  # Optional[Tuple[int, int, int]]
    
    def __init__(self):
        super().__init__()
        self._enabled = False
        self._position = None  # (x, y, z) coordinates in 3D space
    
    def is_enabled(self) -> bool:
        """Check if crosshairs are currently enabled."""
        return self._enabled
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable crosshairs."""
        if self._enabled != enabled:
            self._enabled = enabled
            self.crosshair_enabled_changed.emit(enabled)
            
            # Clear position when disabling
            if not enabled:
                self.clear_position()
    
    def get_position(self) -> Optional[Tuple[int, int, int]]:
        """Get the current crosshair position in 3D space."""
        return self._position
    
    def set_position(self, position: Optional[Tuple[int, int, int]]) -> None:
        """Set the crosshair position in 3D space."""
        if self._position != position:
            self._position = position
            self.crosshair_position_changed.emit(position)
    
    def clear_position(self) -> None:
        """Clear the crosshair position."""
        self.set_position(None)
    
    def has_position(self) -> bool:
        """Check if a crosshair position is set."""
        return self._position is not None 