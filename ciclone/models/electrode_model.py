import os
import pickle
import numpy as np
from typing import Dict, List, Tuple, Optional

from ciclone.domain.electrodes import Electrode
from ciclone.domain.electrode_element import ElectrodeElement, ElectrodeStructure
from ciclone.services.io.electrode_file_service import ElectrodeFileService


class ElectrodeModel:
    """Model for managing electrode data and business logic."""
    
    def __init__(self, electrode_file_service: ElectrodeFileService = None):
        self._electrodes: Dict[str, Electrode] = {}
        self._processed_contacts: Dict[str, List[Tuple[int, int, int]]] = {}
        self._electrode_structures: Dict[str, ElectrodeStructure] = {}
        self._electrode_file_service = electrode_file_service or ElectrodeFileService()
    
    
    def add_electrode(self, name: str, electrode_type: str) -> bool:
        """Add a new electrode to the model."""
        if name in self._electrodes:
            return False
        
        electrode = Electrode(name=name, electrode_type=electrode_type)
        self._electrodes[name] = electrode
        return True
    
    def remove_electrode(self, name: str) -> bool:
        """Remove an electrode from the model."""
        if name not in self._electrodes:
            return False
        
        del self._electrodes[name]
        if name in self._processed_contacts:
            del self._processed_contacts[name]
        if name in self._electrode_structures:
            del self._electrode_structures[name]
        
        return True

    def rename_electrode(self, old_name: str, new_name: str) -> bool:
        """
        Rename an electrode in the model.
        
        Args:
            old_name: Current name of the electrode
            new_name: New name for the electrode
            
        Returns:
            bool: True if rename was successful, False otherwise
        """
        if old_name not in self._electrodes or new_name in self._electrodes:
            return False
        
        # Get the electrode and update its name
        electrode = self._electrodes[old_name]
        electrode.name = new_name
        
        # Update the dictionary key
        self._electrodes[new_name] = self._electrodes.pop(old_name)
        
        return True
    
    def get_electrode(self, name: str) -> Optional[Electrode]:
        """Get an electrode by name."""
        return self._electrodes.get(name)
    
    def get_electrode_names(self) -> List[str]:
        """Get list of all electrode names."""
        return list(self._electrodes.keys())
    
    def get_all_electrodes(self) -> List[Electrode]:
        """Get all electrodes."""
        return list(self._electrodes.values())
    
    def electrode_exists(self, name: str) -> bool:
        """Check if an electrode with the given name exists."""
        return name in self._electrodes
    
    def get_available_electrode_types(self) -> List[str]:
        """Get list of available electrode types."""
        return self._electrode_file_service.list_available_electrode_types()
    
    def process_electrode_contacts(self, 
                                 electrode_name: str, 
                                 tip_point: Tuple[int, int, int], 
                                 entry_point: Tuple[int, int, int]) -> bool:
        """Process coordinates for an electrode and calculate contact positions with tail information.
        
        Args:
            electrode_name: Name of the electrode
            tip_point: Electrode tip (deepest point in brain)
            entry_point: Electrode entry point (where electrode enters skull)
        """
        electrode = self.get_electrode(electrode_name)
        if not electrode:
            return False
        
        try:
            # Load electrode definition
            if not self._electrode_file_service.electrode_definition_exists(electrode.electrode_type):
                return False
                
            elec_def_path = self._electrode_file_service.get_electrode_definition_path(electrode.electrode_type)
            
            with open(elec_def_path, 'rb') as f:
                elec_def = pickle.load(f)
            
            # Extract plot positions and elements
            plot_positions = []
            elements = []
            tail_element = None
            
            for key, value in elec_def.items():
                if key.startswith('Plot'):
                    position = value.get('position', [0, 0, 0])
                    plot_positions.append((key, position))
                elif key.startswith('Element'):
                    # Create ElectrodeElement from definition
                    element = ElectrodeElement(
                        diameter=value.get('diameter', 0.8),
                        length=value.get('length', 1.5),
                        vector=tuple(value.get('vector', [0, 0, 1])),
                        position=tuple(value.get('position', [0, 0, 0])),
                        type=value.get('type', 'Tube'),
                        axis=value.get('axis', 'Axe Z')
                    )
                    elements.append(element)
                    
                    # Check if this is a tail element (long tube element)
                    if element.is_tail_element():
                        tail_element = element
            
            if not plot_positions:
                return False
            
            # Sort plots by z-position
            plot_positions.sort(key=lambda x: x[1][2])
            
            # Calculate direction vector
            tip_array = np.array(tip_point)
            entry_array = np.array(entry_point)
            direction = entry_array - tip_array
            direction_norm = np.linalg.norm(direction)
            
            if direction_norm == 0:
                return False
            
            direction = direction / direction_norm
            
            # Calculate contact positions
            min_z = min(pos[1][2] for pos in plot_positions)
            max_z = max(pos[1][2] for pos in plot_positions)
            z_span = max_z - min_z
            
            if z_span == 0:
                return False
            
            tip_entry_distance = np.linalg.norm(entry_array - tip_array)
            contacts = []
            
            for plot_name, plot_pos in plot_positions:
                relative_pos = (plot_pos[2] - min_z) / z_span
                contact_pos = tip_array + relative_pos * direction * tip_entry_distance
                contacts.append(tuple(np.round(contact_pos).astype(int)))
            
            # Store contacts
            self._processed_contacts[electrode_name] = contacts
            
            # Calculate tail endpoint if tail element exists
            tail_endpoint = None
            if tail_element:
                # Electrode positioning:
                # - tip_point: Deepest point in brain (electrode tip)
                # - entry_point: Where electrode enters skull
                # - Tail extends outward from entry_point away from brain center
                
                # Insertion direction: from entry (skull) toward tip (brain center)
                insertion_direction = tip_array - entry_array
                insertion_direction = insertion_direction / np.linalg.norm(insertion_direction)
                
                # Tail direction: opposite to insertion (away from brain center)
                tail_direction = -insertion_direction
                
                # Calculate proper scaling
                # The contacts span z_span mm in the electrode definition and 
                # tip_entry_distance pixels in the image
                image_pixels_per_mm = tip_entry_distance / z_span
                
                # Scale the tail length, but cap it to a reasonable proportion
                # Medical reality: electrode tails are typically 0.5x to 1.5x the implanted portion
                # Some definitions have unrealistic tail lengths (6x contact span) that dominate the view
                tail_length_mm = tail_element.length
                max_reasonable_tail_mm = z_span * 0.8  # Cap at 0.8x the contact array span
                tail_length_capped_mm = min(tail_length_mm, max_reasonable_tail_mm)
                
                # Apply scaling to the capped length
                tail_length_scaled = tail_length_capped_mm * image_pixels_per_mm
                
                # Tail starts at entry point (skull) and extends outward
                tail_endpoint = entry_array + tail_direction * tail_length_scaled
                tail_endpoint = tuple(np.round(tail_endpoint).astype(int))
            
            # Create and store electrode structure
            electrode_structure = ElectrodeStructure(
                name=electrode_name,
                electrode_type=electrode.electrode_type,
                contact_positions=contacts,
                tail_element=tail_element,
                elements=elements
            )
            # Add calculated tail endpoint to structure
            if tail_endpoint:
                electrode_structure.tail_endpoint = tail_endpoint
            
            self._electrode_structures[electrode_name] = electrode_structure
            
            # Update electrode object
            electrode.contacts.clear()
            for i, contact_pos in enumerate(contacts):
                label = f"{electrode_name}{i+1}"
                electrode.add_contact(label, contact_pos[0], contact_pos[1], contact_pos[2])
            
            return True
        
        except Exception:
            return False
    
    def get_processed_contacts(self, electrode_name: str) -> List[Tuple[int, int, int]]:
        """Get processed contacts for a specific electrode."""
        return self._processed_contacts.get(electrode_name, [])
    
    def get_all_processed_contacts(self) -> Dict[str, List[Tuple[int, int, int]]]:
        """Get all processed contacts for display purposes."""
        contacts_dict = {}
        for electrode in self.get_all_electrodes():
            if electrode.contacts:
                contacts_dict[electrode.name] = [
                    (contact.x, contact.y, contact.z) for contact in electrode.contacts
                ]
        return contacts_dict
    
    def get_electrode_structure(self, electrode_name: str) -> Optional[ElectrodeStructure]:
        """Get the complete electrode structure including tail information."""
        return self._electrode_structures.get(electrode_name)
    
    def get_all_electrode_structures(self) -> Dict[str, ElectrodeStructure]:
        """Get all electrode structures for display purposes."""
        return self._electrode_structures.copy()
    
    def has_processed_contacts(self) -> bool:
        """Check if any electrodes have processed contacts."""
        return any(electrode.contacts for electrode in self.get_all_electrodes())
    
    def get_electrodes_with_contacts(self) -> List[Electrode]:
        """Get all electrodes that have processed contacts."""
        return [electrode for electrode in self.get_all_electrodes() if electrode.contacts]
    
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
        electrode = self.get_electrode(electrode_name)
        if not electrode or not electrode.contacts:
            return False
        
        if contact_index < 0 or contact_index >= len(electrode.contacts):
            return False
        
        # Update the contact coordinates in the electrode object
        contact = electrode.contacts[contact_index]
        contact.x, contact.y, contact.z = new_coordinates
        
        # Update the processed contacts cache
        if electrode_name in self._processed_contacts:
            if contact_index < len(self._processed_contacts[electrode_name]):
                self._processed_contacts[electrode_name][contact_index] = new_coordinates
        
        return True
    
    def get_contact_count(self, electrode_name: str) -> int:
        """Get the number of contacts for an electrode."""
        electrode = self.get_electrode(electrode_name)
        if not electrode:
            return 0
        return len(electrode.contacts)
    
    def get_contact_coordinates(self, electrode_name: str, contact_index: int) -> Optional[Tuple[int, int, int]]:
        """Get coordinates for a specific contact."""
        electrode = self.get_electrode(electrode_name)
        if not electrode or not electrode.contacts:
            return None
        
        if contact_index < 0 or contact_index >= len(electrode.contacts):
            return None
        
        contact = electrode.contacts[contact_index]
        return (contact.x, contact.y, contact.z) 