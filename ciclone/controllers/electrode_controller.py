from typing import Optional, List, Tuple, Dict
from PyQt6.QtWidgets import QMessageBox, QTreeWidgetItem
from PyQt6.QtCore import QObject, pyqtSignal
import numpy as np

from ciclone.models.electrode_model import ElectrodeModel
from ciclone.models.coordinate_model import CoordinateModel
from ciclone.domain.electrodes import Electrode
from ciclone.domain.electrode_element import ElectrodeStructure
from ciclone.interfaces.view_interfaces import IImageView
from ciclone.services.io.slicer_file import SlicerFile
from ciclone.services.ui.electrode_view_delegate import ElectrodeViewDelegate
from ciclone.services.ui.dialog_service import DialogService


class ElectrodeController:
    """Controller for managing electrode operations and coordinating between models and views."""
    
    def __init__(self, electrode_model: ElectrodeModel, coordinate_model: CoordinateModel, dialog_service: DialogService = None):
        self.electrode_model = electrode_model
        self.coordinate_model = coordinate_model
        self._view = None
        self._electrode_view_delegate = ElectrodeViewDelegate()
        self._dialog_service = dialog_service
    
    def set_view(self, view: IImageView):
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

    def rename_electrode(self, old_name: str, new_name: str) -> bool:
        """
        Rename an electrode and update all associated data.
        
        Args:
            old_name: Current name of the electrode
            new_name: New name for the electrode
            
        Returns:
            bool: True if rename was successful, False otherwise
        """
        # Validate inputs
        if not old_name or not new_name:
            self._show_error("Electrode names cannot be empty.")
            return False
        
        # Check if old electrode exists
        if not self.electrode_model.electrode_exists(old_name):
            self._show_error(f"Electrode '{old_name}' does not exist.")
            return False
        
        # Check if new name already exists
        if self.electrode_model.electrode_exists(new_name):
            self._show_error(f"Electrode '{new_name}' already exists.")
            return False
        
        try:
            # Get the electrode object before renaming
            electrode = self.electrode_model.get_electrode(old_name)
            if not electrode:
                return False
            
            # Rename in electrode model
            if not self.electrode_model.rename_electrode(old_name, new_name):
                return False
            
            # Update coordinates in coordinate model
            self.coordinate_model.rename_electrode_coordinates(old_name, new_name)
            
            # Update contact labels within the electrode to match new name
            for i, contact in enumerate(electrode.contacts):
                contact.label = f"{new_name}{i+1}"
            
            # Update processed contacts if they exist
            if old_name in self.electrode_model._processed_contacts:
                self.electrode_model._processed_contacts[new_name] = self.electrode_model._processed_contacts.pop(old_name)
            
            # Update UI if view is available
            if self._view:
                self._view.refresh_electrode_list()
                self._view.refresh_coordinate_display()
                self._view.refresh_image_display()
            
            self._show_info(f"Successfully renamed electrode '{old_name}' to '{new_name}'.")
            return True
            
        except Exception as e:
            self._show_error(f"Failed to rename electrode: {str(e)}")
            return False
    
    def load_electrodes_from_file(self, file_path: str, 
                                image_center: Optional[np.ndarray] = None,
                                affine_transform: Optional[np.ndarray] = None) -> bool:
        """
        Load electrodes from a Slicer JSON file and integrate them into the current session.
        
        Args:
            file_path: Path to the Slicer JSON file
            image_center: Image center for coordinate transformation
            affine_transform: Affine transformation matrix
            
        Returns:
            bool: True if loading was successful, False otherwise
        """
        try:
            # Initialize the SlicerFile parser
            slicer_file = SlicerFile()
            
            # Load and parse the file
            markup_data = slicer_file.load_from_file(file_path)
            electrodes_data = slicer_file.parse_markup_to_electrodes(
                markup_data, image_center, affine_transform
            )
            
            if not electrodes_data:
                self._show_warning("No valid electrodes found in the file.")
                return False
            
            # Handle electrode name conflicts by automatically renaming
            conflicts = self._check_electrode_conflicts(electrodes_data)
            if conflicts:
                electrodes_data = self._rename_conflicting_electrodes(electrodes_data, conflicts)
            
            # Import the electrodes
            imported_count = 0
            skipped_count = 0
            
            for electrode_data in electrodes_data:
                success = self._import_single_electrode(electrode_data)
                if success:
                    imported_count += 1
                else:
                    skipped_count += 1
            
            # Update the UI
            if imported_count > 0:
                if self._view:
                    self._view.refresh_electrode_list()
                    self._view.rebuild_electrode_tree()  # Use rebuild to add all new electrodes
                    self._view.refresh_coordinate_display()  # Update coordinate display
                    self._view.refresh_image_display()
                
                # Show success message
                message = f"Successfully imported {imported_count} electrode(s)"
                if skipped_count > 0:
                    message += f" ({skipped_count} skipped due to errors)"
                self._show_info(message)
                
                return True
            else:
                self._show_warning("No electrodes could be imported.")
                return False
                
        except ValueError as e:
            self._show_error(f"File format error: {str(e)}")
            return False
        except Exception as e:
            self._show_error(f"Failed to load electrodes: {str(e)}")
            return False

    def _check_electrode_conflicts(self, electrodes_data: List[Dict]) -> List[str]:
        """Check for electrode name conflicts with existing electrodes."""
        conflicts = []
        for electrode_data in electrodes_data:
            if self.electrode_model.electrode_exists(electrode_data['name']):
                conflicts.append(electrode_data['name'])
        return conflicts


    def _rename_conflicting_electrodes(self, electrodes_data: List[Dict], 
                                     conflicts: List[str]) -> List[Dict]:
        """Rename conflicting electrodes using pattern ElecName(1), ElecName(2), etc."""
        resolved_data = []
        
        for electrode_data in electrodes_data:
            if electrode_data['name'] in conflicts:
                # Find a unique name using pattern ElecName(1), ElecName(2), etc.
                base_name = electrode_data['name']
                counter = 1
                new_name = f"{base_name}({counter})"
                
                while self.electrode_model.electrode_exists(new_name):
                    counter += 1
                    new_name = f"{base_name}({counter})"
                
                # Create new electrode data with renamed electrode
                new_electrode_data = electrode_data.copy()
                new_electrode_data['name'] = new_name
                resolved_data.append(new_electrode_data)
            else:
                resolved_data.append(electrode_data)
        
        return resolved_data

    def _import_single_electrode(self, electrode_data: Dict) -> bool:
        """
        Import a single electrode with its processed contacts.
        
        Args:
            electrode_data: Dictionary with 'name', 'type', and 'contacts' keys
            
        Returns:
            bool: True if import was successful
        """
        try:
            name = electrode_data['name']
            electrode_type = electrode_data['type']
            contacts = electrode_data['contacts']
            
            # Validate electrode type (use first available type if unknown)
            available_types = self.electrode_model.get_available_electrode_types()
            if electrode_type not in available_types:
                if available_types:
                    electrode_type = available_types[0]  # Use first available type
                else:
                    electrode_type = "Unknown"
            
            # Create the electrode in the model
            if not self.electrode_model.add_electrode(name, electrode_type):
                return False
            
            # Add the processed contacts directly to the electrode
            electrode = self.electrode_model.get_electrode(name)
            if not electrode:
                return False
            
            # Clear any existing contacts and add the imported ones
            electrode.contacts.clear()
            for i, contact_coords in enumerate(contacts):
                contact_label = f"{name}{i+1}"
                electrode.add_contact(
                    contact_label, 
                    float(contact_coords[0]), 
                    float(contact_coords[1]), 
                    float(contact_coords[2])
                )
            
            # Store the processed contacts in the model
            self.electrode_model._processed_contacts[name] = contacts
            
            # Derive tip and entry coordinates from the contacts
            if len(contacts) >= 2:
                # First contact is the electrode tip (deepest in brain)
                # Last contact is the skull entry point
                tip_point = tuple(int(coord) for coord in contacts[0])
                entry_point = tuple(int(coord) for coord in contacts[-1])
                
                # Set the derived coordinates in the coordinate model
                self.coordinate_model.set_tip_point(name, tip_point)
                self.coordinate_model.set_entry_point(name, entry_point)
            elif len(contacts) == 1:
                # Single contact electrode - use the same point for both tip and entry
                single_point = tuple(int(coord) for coord in contacts[0])
                self.coordinate_model.set_tip_point(name, single_point)
                self.coordinate_model.set_entry_point(name, single_point)
            
            # Tree widget will be updated by the view's refresh methods
            
            return True
            
        except Exception as e:
            print(f"Failed to import electrode {electrode_data.get('name', 'Unknown')}: {str(e)}")
            return False
    
    def set_entry_coordinate(self, electrode_name: str, coordinates: Tuple[int, int, int]) -> bool:
        """Set tip coordinates for an electrode."""
        if not electrode_name:
            self._show_warning("Please select an electrode first.")
            return False
        
        self.coordinate_model.set_tip_point(electrode_name, coordinates)
        if self._view:
            self._view.update_coordinate_display(electrode_name)
        
        return True
    
    def set_output_coordinate(self, electrode_name: str, coordinates: Tuple[int, int, int]) -> bool:
        """Set entry coordinates for an electrode."""
        if not electrode_name:
            self._show_warning("Please select an electrode first.")
            return False
        
        self.coordinate_model.set_entry_point(electrode_name, coordinates)
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
        if not coordinates or 'tip' not in coordinates or 'entry' not in coordinates:
            self._show_warning("Please set both tip and entry coordinates first.")
            return False
        
        # Process coordinates using the electrode model
        success = self.electrode_model.process_electrode_contacts(
            electrode_name, 
            coordinates['tip'], 
            coordinates['entry']
        )
        
        if success:
            if self._view:
                self._view.refresh_electrode_tree(electrode_name)
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
    
    def get_electrode_structures_for_display(self) -> Dict[str, ElectrodeStructure]:
        """Get all electrode structures including tail information for display purposes."""
        return self.electrode_model.get_all_electrode_structures()
    
    def create_tree_item(self, electrode: Electrode) -> QTreeWidgetItem:
        """Create a tree widget item for an electrode."""
        return self._electrode_view_delegate.create_tree_item(electrode)
    
    def get_electrode_types(self) -> List[str]:
        """Get available electrode types."""
        return self.electrode_model.get_available_electrode_types()
    
    def has_processed_contacts(self) -> bool:
        """Check if any electrodes have processed contacts."""
        return self.electrode_model.has_processed_contacts()
    
    def get_electrodes_with_contacts(self) -> List:
        """Get all electrodes that have processed contacts."""
        return self.electrode_model.get_electrodes_with_contacts()
    
    def toggle_electrode_movement(self, electrode_name: str, enabled: bool) -> bool:
        """Toggle movement enabled state for an electrode."""
        if not electrode_name:
            return False
        
        self.coordinate_model.set_movement_enabled(electrode_name, enabled)
        if self._view:
            self._view.update_electrode_movement_state(electrode_name, enabled)
        
        return True
    
    def is_electrode_movement_enabled(self, electrode_name: str) -> bool:
        """Check if movement is enabled for an electrode."""
        return self.coordinate_model.is_movement_enabled(electrode_name)
    
    def move_electrode_coordinate(self, electrode_name: str, coord_type: str, new_coordinates: Tuple[int, int, int]) -> bool:
        """
        Move an electrode coordinate (entry or output point).
        
        Args:
            electrode_name: Name of the electrode
            coord_type: Type of coordinate ('tip' or 'entry')
            new_coordinates: New coordinates
            
        Returns:
            bool: True if move was successful, False otherwise
        """
        if not electrode_name:
            return False
        
        success = False
        # Map coord_type to the correct method
        # After refactoring: 'tip' = electrode tip, 'entry' = skull entry point
        if coord_type == 'tip':
            success = self.coordinate_model.move_tip_point(electrode_name, new_coordinates)
        elif coord_type == 'entry':
            success = self.coordinate_model.move_entry_point(electrode_name, new_coordinates)
        
        if success:
            # If both tip and entry points exist, reprocess contacts
            coordinates = self.coordinate_model.get_coordinates(electrode_name)
            if 'tip' in coordinates and 'entry' in coordinates:
                self.electrode_model.process_electrode_contacts(
                    electrode_name, 
                    coordinates['tip'], 
                    coordinates['entry']
                )
            
            if self._view:
                self._view.refresh_coordinate_display()
                self._view.refresh_electrode_tree(electrode_name)  # Update tree widget to show new contacts
                self._view.refresh_image_display()
        
        return success
    
    def move_contact_coordinate(self, electrode_name: str, contact_index: int, new_coordinates: Tuple[int, int, int]) -> bool:
        """
        Move a specific contact coordinate for an electrode.
        
        Args:
            electrode_name: Name of the electrode
            contact_index: Index of the contact to move (0-based)
            new_coordinates: New coordinates for the contact
            
        Returns:
            bool: True if move was successful, False otherwise
        """
        if not electrode_name or not self.is_electrode_movement_enabled(electrode_name):
            return False
        
        success = self.electrode_model.move_contact_coordinate(electrode_name, contact_index, new_coordinates)
        
        if success and self._view:
            self._view.refresh_coordinate_display()
            self._view.refresh_electrode_tree(electrode_name)  # Update tree widget to show new contact coordinates
            self._view.refresh_image_display()
        
        return success
    
    def _show_error(self, message: str):
        """Show error message to user."""
        if self._dialog_service:
            self._dialog_service.show_error("Error", message)
        elif self._view:
            QMessageBox.critical(self._view, "Error", message)
    
    def _show_warning(self, message: str):
        """Show warning message to user."""
        if self._dialog_service:
            self._dialog_service.show_warning("Warning", message)
        elif self._view:
            QMessageBox.warning(self._view, "Warning", message)
    
    def _show_info(self, message: str):
        """Show info message to user."""
        if self._dialog_service:
            self._dialog_service.show_information("Success", message)
        elif self._view:
            QMessageBox.information(self._view, "Success", message)
    
    def _confirm_deletion(self, electrode_name: str) -> bool:
        """Confirm electrode deletion with user."""
        if self._dialog_service:
            return self._dialog_service.show_confirmation(
                "Confirm Deletion",
                f"Are you sure you want to delete electrode '{electrode_name}'?",
                default_no=True
            )
        elif self._view:
            reply = QMessageBox.question(
                self._view,
                "Confirm Deletion",
                f"Are you sure you want to delete electrode '{electrode_name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            return reply == QMessageBox.StandardButton.Yes
        return False
    
    def _confirm_multiple_deletion(self, electrode_names: List[str]) -> bool:
        """Confirm multiple electrode deletion with user."""
        if len(electrode_names) == 1:
            return self._confirm_deletion(electrode_names[0])
        
        electrode_list = '\n'.join([f"  • {name}" for name in electrode_names])
        message = f"Are you sure you want to delete the following {len(electrode_names)} electrodes?\n\n{electrode_list}"
        
        if self._dialog_service:
            return self._dialog_service.show_confirmation(
                "Confirm Multiple Deletion",
                message,
                default_no=True
            )
        elif self._view:
            reply = QMessageBox.question(
                self._view,
                "Confirm Multiple Deletion",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            return reply == QMessageBox.StandardButton.Yes
        return False 