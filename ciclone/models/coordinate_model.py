from typing import Dict, Tuple, Optional


class CoordinateModel:
    """Model for managing electrode coordinate data."""
    
    def __init__(self):
        self._electrode_points: Dict[str, Dict[str, Tuple[int, int, int]]] = {}
    
    def set_entry_point(self, electrode_name: str, point: Tuple[int, int, int]) -> None:
        """Set entry point for an electrode."""
        if electrode_name not in self._electrode_points:
            self._electrode_points[electrode_name] = {}
        self._electrode_points[electrode_name]['entry'] = point
    
    def set_output_point(self, electrode_name: str, point: Tuple[int, int, int]) -> None:
        """Set output point for an electrode."""
        if electrode_name not in self._electrode_points:
            self._electrode_points[electrode_name] = {}
        self._electrode_points[electrode_name]['output'] = point
    
    def get_coordinates(self, electrode_name: str) -> Dict[str, Tuple[int, int, int]]:
        """Get the coordinates for a specific electrode."""
        return self._electrode_points.get(electrode_name, {})
    
    def get_entry_point(self, electrode_name: str) -> Optional[Tuple[int, int, int]]:
        """Get entry point for an electrode."""
        coordinates = self.get_coordinates(electrode_name)
        return coordinates.get('entry')
    
    def get_output_point(self, electrode_name: str) -> Optional[Tuple[int, int, int]]:
        """Get output point for an electrode."""
        coordinates = self.get_coordinates(electrode_name)
        return coordinates.get('output')
    
    def has_entry_point(self, electrode_name: str) -> bool:
        """Check if electrode has entry point set."""
        return self.get_entry_point(electrode_name) is not None
    
    def has_output_point(self, electrode_name: str) -> bool:
        """Check if electrode has output point set."""
        return self.get_output_point(electrode_name) is not None
    
    def has_both_points(self, electrode_name: str) -> bool:
        """Check if electrode has both entry and output points set."""
        return self.has_entry_point(electrode_name) and self.has_output_point(electrode_name)
    
    def remove_electrode_coordinates(self, electrode_name: str) -> bool:
        """Remove all coordinates for an electrode."""
        if electrode_name in self._electrode_points:
            del self._electrode_points[electrode_name]
            return True
        return False

    def rename_electrode_coordinates(self, old_name: str, new_name: str) -> bool:
        """
        Rename an electrode's coordinates.
        
        Args:
            old_name: Current name of the electrode
            new_name: New name for the electrode
            
        Returns:
            bool: True if rename was successful, False otherwise
        """
        if old_name not in self._electrode_points:
            return True  # No coordinates to rename, consider it successful
        
        if new_name in self._electrode_points:
            return False  # New name already exists
        
        # Transfer coordinates to new name
        self._electrode_points[new_name] = self._electrode_points.pop(old_name)
        return True
    
    def clear_entry_point(self, electrode_name: str) -> None:
        """Clear entry point for an electrode."""
        if electrode_name in self._electrode_points and 'entry' in self._electrode_points[electrode_name]:
            del self._electrode_points[electrode_name]['entry']
    
    def clear_output_point(self, electrode_name: str) -> None:
        """Clear output point for an electrode."""
        if electrode_name in self._electrode_points and 'output' in self._electrode_points[electrode_name]:
            del self._electrode_points[electrode_name]['output']
    
    def clear_all_points(self, electrode_name: str) -> None:
        """Clear all points for an electrode."""
        if electrode_name in self._electrode_points:
            self._electrode_points[electrode_name].clear()
    
    def get_all_electrode_points(self) -> Dict[str, Dict[str, Tuple[int, int, int]]]:
        """Get all electrode points for display purposes."""
        return self._electrode_points.copy()
    
    def get_electrode_names_with_coordinates(self) -> list[str]:
        """Get names of electrodes that have coordinates set."""
        return [name for name, coords in self._electrode_points.items() if coords] 