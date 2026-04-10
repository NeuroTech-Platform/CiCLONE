import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional


@dataclass
class Contact:
    """
    Represents a single electrode contact with 3D coordinates.

    Attributes:
        label: Contact label (e.g., "LA1", "LA2")
        x: X coordinate in voxel space
        y: Y coordinate in voxel space
        z: Z coordinate in voxel space
        atlas_labels: Dictionary mapping atlas type to anatomical label name
                     (e.g., {"aparc+aseg": "Left-Hippocampus", "aseg": "Left-Hippocampus"})
    """
    label: str
    x: float
    y: float
    z: float
    atlas_labels: Dict[str, str] = field(default_factory=dict)

    @property
    def coordinates(self) -> Tuple[float, float, float]:
        """Return the coordinates as a tuple."""
        return (self.x, self.y, self.z)

    def get_atlas_label(self, atlas_type: str = "aparc+aseg") -> str:
        """
        Get the anatomical label for a specific atlas type.

        Args:
            atlas_type: Atlas type string (e.g., "aparc+aseg", "aseg")

        Returns:
            Anatomical label name, or empty string if not available
        """
        return self.atlas_labels.get(atlas_type, "")

    def set_atlas_label(self, atlas_type: str, label_name: str) -> None:
        """
        Set the anatomical label for a specific atlas type.

        Args:
            atlas_type: Atlas type string (e.g., "aparc+aseg", "aseg")
            label_name: Anatomical label name
        """
        self.atlas_labels[atlas_type] = label_name

    def clear_atlas_labels(self) -> None:
        """Clear all atlas labels."""
        self.atlas_labels.clear()


class Electrode:
    """
    Represents an electrode with one or more contacts.
    """
    def __init__(self, name: str, electrode_type: str = ""):
        """
        Initialize an electrode with a name and type.
        
        Args:
            name (str): Name of the electrode
            electrode_type (str): Type of the electrode
        """
        self.name = name
        self.electrode_type = electrode_type
        self.contacts: List[Contact] = []
    
    def add_contact(self, label: str, x: float, y: float, z: float,
                    atlas_labels: Optional[Dict[str, str]] = None) -> None:
        """
        Add a contact to the electrode.

        Args:
            label: Label for the contact
            x: X coordinate
            y: Y coordinate
            z: Z coordinate
            atlas_labels: Optional dictionary mapping atlas types to label names
        """
        contact = Contact(label=label, x=x, y=y, z=z)
        if atlas_labels:
            contact.atlas_labels = atlas_labels
        self.contacts.append(contact)
    
    def get_contact(self, index: int) -> Optional[Contact]:
        """
        Get a contact by index.
        
        Args:
            index (int): Index of the contact
            
        Returns:
            Contact or None: The contact at the specified index, or None if not found
        """
        if 0 <= index < len(self.contacts):
            return self.contacts[index]
        return None
    
    def get_all_contacts(self) -> List[Contact]:
        """
        Get all contacts for this electrode.
        
        Returns:
            List[Contact]: List of all contacts
        """
        return self.contacts
    
    def get_coordinates_array(self) -> np.ndarray:
        """
        Get all contact coordinates as a numpy array.
        
        Returns:
            np.ndarray: Array of shape (n_contacts, 3) containing all coordinates
        """
        return np.array([contact.coordinates for contact in self.contacts])


class Electrodes:
    """
    Collection of multiple electrodes.
    """
    def __init__(self):
        """Initialize an empty collection of electrodes."""
        self.electrodes: Dict[str, Electrode] = {}
    
    def add_electrode(self, electrode: Electrode) -> None:
        """
        Add an electrode to the collection.
        
        Args:
            electrode (Electrode): The electrode to add
        """
        self.electrodes[electrode.name] = electrode
    
    def create_electrode(self, name: str, electrode_type: str = "") -> Electrode:
        """
        Create and add a new electrode to the collection.
        
        Args:
            name (str): Name of the electrode
            electrode_type (str): Type of the electrode
            
        Returns:
            Electrode: The newly created electrode
        """
        electrode = Electrode(name=name, electrode_type=electrode_type)
        self.electrodes[name] = electrode
        return electrode
    
    def get_electrode(self, name: str) -> Optional[Electrode]:
        """
        Get an electrode by name.
        
        Args:
            name (str): Name of the electrode
            
        Returns:
            Electrode or None: The electrode with the specified name, or None if not found
        """
        return self.electrodes.get(name)
    
    def get_all_electrodes(self) -> Dict[str, Electrode]:
        """
        Get all electrodes in the collection.
        
        Returns:
            Dict[str, Electrode]: Dictionary of all electrodes, keyed by name
        """
        return self.electrodes
    
    def get_all_contacts(self) -> List[Tuple[str, Contact]]:
        """
        Get all contacts from all electrodes.
        
        Returns:
            List[Tuple[str, Contact]]: List of tuples containing (electrode_name, contact)
        """
        all_contacts = []
        for name, electrode in self.electrodes.items():
            for contact in electrode.contacts:
                all_contacts.append((name, contact))
        return all_contacts
