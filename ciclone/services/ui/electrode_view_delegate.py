"""
Electrode View Delegate for CiCLONE Application

This delegate handles UI-specific operations for electrode display,
maintaining proper MVC separation by removing UI dependencies from models.
"""

from typing import Optional
from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtCore import Qt

from ciclone.domain.electrodes import Electrode


class ElectrodeViewDelegate:
    """Delegate for handling electrode UI operations while maintaining MVC architecture."""
    
    def create_tree_item(self, electrode: Electrode) -> QTreeWidgetItem:
        """Create a tree widget item for an electrode."""
        item = QTreeWidgetItem()
        item.setText(0, electrode.name)
        item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
        
        # Add contact sub-items
        for contact in electrode.contacts:
            contact_item = QTreeWidgetItem(item)
            contact_item.setText(0, contact.label)
            contact_item.setText(1, str(int(contact.x)))
            contact_item.setText(2, str(int(contact.y)))
            contact_item.setText(3, str(int(contact.z)))
            contact_item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
            contact_item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
            contact_item.setTextAlignment(2, Qt.AlignmentFlag.AlignCenter)
            contact_item.setTextAlignment(3, Qt.AlignmentFlag.AlignCenter)
        
        return item