"""
Electrode View Delegate for CiCLONE Application

This delegate handles UI-specific operations for electrode display,
maintaining proper MVC separation by removing UI dependencies from models.
"""

from typing import Optional
from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPixmap, QPainter, QIcon

from ciclone.domain.electrodes import Electrode


class ElectrodeViewDelegate:
    """Delegate for handling electrode UI operations while maintaining MVC architecture."""
    
    def _get_electrode_color(self, electrode_name: str) -> QColor:
        """
        Generate electrode color using the same algorithm as image markers.
        
        Args:
            electrode_name: Name of the electrode
            
        Returns:
            QColor with HSV(hue, 200, 255, 180) matching image markers
        """
        hue = abs(hash(electrode_name)) % 360
        electrode_color = QColor()
        electrode_color.setHsv(hue, 200, 255, 180)
        return electrode_color
    
    def _create_colored_dot_icon(self, electrode_name: str, size: int = 12) -> QIcon:
        """
        Create a colored circular icon for the electrode.
        
        Args:
            electrode_name: Name of the electrode
            size: Size of the icon in pixels (default 12x12)
            
        Returns:
            QIcon with colored circle matching electrode markers
        """
        color = self._get_electrode_color(electrode_name)
        
        # Create pixmap
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        # Draw colored circle
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Draw circle with 1px margin
        circle_size = size - 2
        painter.drawEllipse(1, 1, circle_size, circle_size)
        painter.end()
        
        return QIcon(pixmap)
    
    def create_tree_item(self, electrode: Electrode) -> QTreeWidgetItem:
        """Create a tree widget item for an electrode."""
        item = QTreeWidgetItem()
        item.setText(0, electrode.name)
        item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
        
        # Add colored dot icon matching electrode markers in image slices
        colored_icon = self._create_colored_dot_icon(electrode.name)
        item.setIcon(0, colored_icon)
        
        # Add contact sub-items
        for contact_index, contact in enumerate(electrode.contacts):
            contact_item = QTreeWidgetItem(item)
            contact_item.setText(0, contact.label)
            contact_item.setText(1, str(int(contact.x)))
            contact_item.setText(2, str(int(contact.y)))
            contact_item.setText(3, str(int(contact.z)))
            contact_item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
            contact_item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
            contact_item.setTextAlignment(2, Qt.AlignmentFlag.AlignCenter)
            contact_item.setTextAlignment(3, Qt.AlignmentFlag.AlignCenter)
            
            # Store metadata for click navigation (electrode_name, contact_index)
            contact_item.setData(0, Qt.ItemDataRole.UserRole, (electrode.name, contact_index))
        
        return item