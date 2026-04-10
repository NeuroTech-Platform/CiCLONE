"""
Electrode View Delegate for CiCLONE Application

This delegate handles UI-specific operations for electrode display,
maintaining proper MVC separation by removing UI dependencies from models.
"""

from typing import Optional, List
from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPixmap, QPainter, QIcon

from ciclone.domain.electrodes import Electrode


class ElectrodeViewDelegate:
    """Delegate for handling electrode UI operations while maintaining MVC architecture."""

    # Default atlas type to display in the tree widget
    DEFAULT_ATLAS_TYPE = "aparc+aseg"

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

    def _format_atlas_tooltip(self, atlas_labels: dict) -> str:
        """
        Format atlas labels as a tooltip string.

        Args:
            atlas_labels: Dictionary mapping atlas type to label name

        Returns:
            Formatted tooltip string with all atlas labels
        """
        if not atlas_labels:
            return ""

        # Sort atlas types for consistent display
        lines = []
        for atlas_type in sorted(atlas_labels.keys()):
            label_name = atlas_labels[atlas_type]
            # Format atlas type for display
            display_type = atlas_type.replace('+', ' + ').replace('.', ' ')
            lines.append(f"{display_type}: {label_name}")

        return "\n".join(lines)

    def create_tree_item(self, electrode: Electrode,
                         show_atlas_labels: bool = True,
                         atlas_type: str = None) -> QTreeWidgetItem:
        """
        Create a tree widget item for an electrode.

        Args:
            electrode: Electrode object to create item for
            show_atlas_labels: Whether to show atlas labels in a separate column
            atlas_type: Which atlas type to display (default: aparc+aseg)

        Returns:
            QTreeWidgetItem configured for the electrode
        """
        if atlas_type is None:
            atlas_type = self.DEFAULT_ATLAS_TYPE

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

            # Add atlas label column if available and requested
            if show_atlas_labels and contact.atlas_labels:
                # Get label for the selected atlas type
                label_text = contact.atlas_labels.get(atlas_type, "")

                # If the requested atlas type isn't available, try to use any available label
                if not label_text and contact.atlas_labels:
                    # Use the first available label
                    label_text = next(iter(contact.atlas_labels.values()), "")

                contact_item.setText(4, label_text)
                contact_item.setTextAlignment(4, Qt.AlignmentFlag.AlignLeft)

                # Add tooltip with all atlas labels
                tooltip = self._format_atlas_tooltip(contact.atlas_labels)
                if tooltip:
                    contact_item.setToolTip(4, tooltip)

            # Store metadata for click navigation (electrode_name, contact_index)
            contact_item.setData(0, Qt.ItemDataRole.UserRole, (electrode.name, contact_index))

        return item

    def get_tree_headers(self, show_atlas_labels: bool = True) -> List[str]:
        """
        Get the column headers for the electrode tree widget.

        Args:
            show_atlas_labels: Whether to include atlas label column

        Returns:
            List of header strings
        """
        headers = ["Contact", "X", "Y", "Z"]
        if show_atlas_labels:
            headers.append("Atlas Label")
        return headers