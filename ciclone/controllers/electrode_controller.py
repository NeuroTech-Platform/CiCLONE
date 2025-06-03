from typing import Optional, List, Tuple, Dict
from PyQt6.QtWidgets import QMessageBox, QTreeWidgetItem
from PyQt6.QtCore import QObject, pyqtSignal

from ciclone.models.electrode_model import ElectrodeModel
from ciclone.models.coordinate_model import CoordinateModel
from ciclone.domain.electrodes import Electrode


class ElectrodeController:
    """Controller for managing electrode operations and coordinating between models and views."""
    
    def __init__(self, electrode_model: ElectrodeModel, coordinate_model: CoordinateModel):
        self.electrode_model = electrode_model
        self.coordinate_model = coordinate_model
        self._view = None
    
    def set_view(self, view):
        """Set the view reference for UI updates."""
        self._view = view
    
    def create_electrode(self, name: str, electrode_type: str) -> bool:
        """Create a new electrode with validation."""
        if not name.strip():
            self._show_error("Please enter an electrode name.")
            return False
        
        if self.electrode_model.electrode_exists(name):
            self._show_error("An electrode with this name already exists.")
            return False
        
        success = self.electrode_model.add_electrode(name, electrode_type)
        if success and self._view:
            self._view.refresh_electrode_list()
            self._view.clear_electrode_input()
        
        return success
    
    def delete_electrode(self, electrode_name: str) -> bool:
        """Delete an electrode with confirmation."""
        if not self._confirm_deletion(electrode_name):
            return False
        
        success = self.electrode_model.remove_electrode(electrode_name)
        if success:
            self.coordinate_model.remove_electrode_coordinates(electrode_name)
            if self._view:
                self._view.refresh_electrode_list()
                self._view.refresh_coordinate_display()
                self._view.refresh_image_display()
        
        return success
    
    def delete_multiple_electrodes(self, electrode_names: List[str]) -> bool:
        """Delete multiple electrodes with confirmation."""
        if not electrode_names:
            return False
            
        if not self._confirm_multiple_deletion(electrode_names):
            return False
        
        success_count = 0
        for electrode_name in electrode_names:
            if self.electrode_model.remove_electrode(electrode_name):
                self.coordinate_model.remove_electrode_coordinates(electrode_name)
                success_count += 1
        
        if success_count > 0 and self._view:
            self._view.refresh_electrode_list()
            self._view.refresh_coordinate_display()
            self._view.refresh_image_display()
        
        return success_count == len(electrode_names)
    
    def set_entry_coordinate(self, electrode_name: str, coordinates: Tuple[int, int, int]) -> bool:
        """Set entry coordinates for an electrode."""
        if not electrode_name:
            self._show_warning("Please select an electrode first.")
            return False
        
        self.coordinate_model.set_entry_point(electrode_name, coordinates)
        if self._view:
            self._view.update_coordinate_display(electrode_name)
        
        return True
    
    def set_output_coordinate(self, electrode_name: str, coordinates: Tuple[int, int, int]) -> bool:
        """Set output coordinates for an electrode."""
        if not electrode_name:
            self._show_warning("Please select an electrode first.")
            return False
        
        self.coordinate_model.set_output_point(electrode_name, coordinates)
        if self._view:
            self._view.update_coordinate_display(electrode_name)
        
        return True
    
    def process_electrode_coordinates(self, electrode_name: str) -> bool:
        """Process coordinates to generate electrode contacts."""
        if not electrode_name:
            self._show_warning("Please select an electrode first.")
            return False
        
        electrode = self.electrode_model.get_electrode(electrode_name)
        if not electrode:
            self._show_warning(f"Electrode {electrode_name} not found.")
            return False
        
        coordinates = self.coordinate_model.get_coordinates(electrode_name)
        if not coordinates or 'entry' not in coordinates or 'output' not in coordinates:
            self._show_warning("Please set both entry and output coordinates first.")
            return False
        
        # Process coordinates using the electrode model
        success = self.electrode_model.process_electrode_contacts(
            electrode_name, 
            coordinates['entry'], 
            coordinates['output']
        )
        
        if success:
            if self._view:
                self._view.refresh_electrode_tree()
                self._view.refresh_image_display()
            self._show_info(f"Successfully processed contacts for electrode {electrode_name}.")
        else:
            self._show_warning(f"Failed to process coordinates for electrode {electrode_name}.")
        
        return success
    
    def get_electrode_names(self) -> List[str]:
        """Get list of all electrode names."""
        return self.electrode_model.get_electrode_names()
    
    def get_electrode(self, name: str) -> Optional[Electrode]:
        """Get electrode by name."""
        return self.electrode_model.get_electrode(name)
    
    def get_coordinates(self, electrode_name: str) -> Dict[str, Tuple[int, int, int]]:
        """Get coordinates for an electrode."""
        return self.coordinate_model.get_coordinates(electrode_name)
    
    def get_electrode_points_for_display(self) -> Dict[str, Dict[str, Tuple[int, int, int]]]:
        """Get all electrode points for display purposes."""
        return self.coordinate_model.get_all_electrode_points()
    
    def get_processed_contacts_for_display(self) -> Dict[str, List[Tuple[int, int, int]]]:
        """Get all processed contacts for display purposes."""
        return self.electrode_model.get_all_processed_contacts()
    
    def create_tree_item(self, electrode: Electrode) -> QTreeWidgetItem:
        """Create a tree widget item for an electrode."""
        return self.electrode_model.create_tree_item(electrode)
    
    def get_electrode_types(self) -> List[str]:
        """Get available electrode types."""
        return self.electrode_model.get_available_electrode_types()
    
    def _show_error(self, message: str):
        """Show error message to user."""
        if self._view:
            QMessageBox.critical(self._view, "Error", message)
    
    def _show_warning(self, message: str):
        """Show warning message to user."""
        if self._view:
            QMessageBox.warning(self._view, "Warning", message)
    
    def _show_info(self, message: str):
        """Show info message to user."""
        if self._view:
            QMessageBox.information(self._view, "Success", message)
    
    def _confirm_deletion(self, electrode_name: str) -> bool:
        """Confirm electrode deletion with user."""
        if not self._view:
            return False
        
        reply = QMessageBox.question(
            self._view,
            "Confirm Deletion",
            f"Are you sure you want to delete electrode '{electrode_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        return reply == QMessageBox.StandardButton.Yes
    
    def _confirm_multiple_deletion(self, electrode_names: List[str]) -> bool:
        """Confirm multiple electrode deletion with user."""
        if not self._view:
            return False
        
        if len(electrode_names) == 1:
            return self._confirm_deletion(electrode_names[0])
        
        electrode_list = '\n'.join([f"  • {name}" for name in electrode_names])
        reply = QMessageBox.question(
            self._view,
            "Confirm Multiple Deletion",
            f"Are you sure you want to delete the following {len(electrode_names)} electrodes?\n\n{electrode_list}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        return reply == QMessageBox.StandardButton.Yes 