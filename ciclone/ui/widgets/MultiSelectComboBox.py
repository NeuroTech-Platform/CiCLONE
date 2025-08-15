from typing import List
from PyQt6.QtWidgets import QComboBox
from PyQt6.QtCore import Qt, pyqtSignal, QModelIndex
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QKeyEvent, QFocusEvent


class MultiSelectComboBox(QComboBox):
    """
    A QComboBox that supports multiple selections with checkboxes.
    Displays selected items as comma-separated text in the combo box.
    """
    
    # Signal emitted when the selection changes
    selectionChanged = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Create and set a standard item model for proper control
        model = QStandardItemModel()
        self.setModel(model)
        
        # Make editable so we can control display text
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        
        # Connect to model changes to update display text
        model.itemChanged.connect(self._on_model_item_changed)
        
        # Connect to handle item clicks
        self.view().pressed.connect(self._on_item_pressed)
        
        # Prevent default selection behavior
        self.activated.connect(self._on_activated)
        
        # Initialize with "none" display
        self._update_display_text()
        
        # Track last emitted state to prevent duplicate signals
        self._last_emitted_state = []
    
    def _on_item_pressed(self, index: QModelIndex) -> None:
        """Handle item press to toggle checkbox state."""
        item = self.model().itemFromIndex(index)
        if item and item.isCheckable():
            current_state = item.checkState()
            new_state = (Qt.CheckState.Unchecked if current_state == Qt.CheckState.Checked 
                        else Qt.CheckState.Checked)
            item.setCheckState(new_state)
    
    def _on_model_item_changed(self, item: QStandardItem) -> None:
        """Handle model item changes (like check state changes)."""
        if item and item.isCheckable():
            self._update_display_text()
            self._emit_selection_change()
    
    def _on_activated(self, _: int) -> None:
        """Prevent default activation behavior - we handle selection via checkboxes."""
        # Intentionally empty to block default Qt selection behavior
        return
    
    def setCurrentIndex(self, _: int) -> None:
        """Override to prevent changing selection - we use checkboxes instead."""
        # Intentionally empty to prevent Qt from changing selection state
        return
    
    def setCurrentText(self, _: str) -> None:
        """Override to maintain control over display text."""
        # Intentionally empty to prevent external text changes
        return
    
    def _update_display_text(self) -> None:
        """Update the combo box display text to show selected items."""
        selected_items = self.get_selected_items()
        
        if not selected_items:
            display_text = "none"
        elif len(selected_items) == 1:
            display_text = selected_items[0]
        else:
            display_text = f"{selected_items[0]} (+{len(selected_items)-1} more)"
        
        self._set_line_edit_text(display_text)
    
    def _set_line_edit_text(self, text: str) -> None:
        """Safely update line edit text with signal blocking."""
        line_edit = self.lineEdit()
        if line_edit.text() != text:
            line_edit.blockSignals(True)
            line_edit.setText(text)
            line_edit.repaint()
            line_edit.blockSignals(False)
    
    def _emit_selection_change(self) -> None:
        """Emit selection change signal only if state actually changed."""
        current_state = self.get_selected_items()
        if current_state != self._last_emitted_state:
            self._last_emitted_state = current_state.copy()
            self.selectionChanged.emit(current_state)
    
    def add_items(self, items: List[str]) -> None:
        """Add checkable items to the combo box."""
        model = self.model()
        for item_text in items:
            if item_text != 'none':
                item = QStandardItem(item_text)
                item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                item.setData(Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
                model.appendRow(item)
        
        self._update_display_text()
    
    def clear_items(self) -> None:
        """Clear all items from the combo box."""
        self.model().clear()
        self._update_display_text()
    
    def get_selected_items(self) -> List[str]:
        """Get list of selected (checked) items."""
        selected = []
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        return selected
    
    def set_selected_items(self, items: List[str]) -> None:
        """Set which items should be selected (checked)."""
        model = self.model()
        model.blockSignals(True)
        
        items_set = set(items)
        for i in range(model.rowCount()):
            item = model.item(i)
            if item:
                check_state = (Qt.CheckState.Checked if item.text() in items_set 
                              else Qt.CheckState.Unchecked)
                item.setCheckState(check_state)
        
        model.blockSignals(False)
        self._update_display_text()
    
    def hidePopup(self) -> None:
        """Override to control when popup closes."""
        self._emit_selection_change()
        super().hidePopup()
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
            if self.view().isVisible():
                self.hidePopup()
        else:
            super().keyPressEvent(event)
    
    def focusOutEvent(self, event: QFocusEvent) -> None:
        """Handle focus loss - emit signal to ensure controller gets current state."""
        self._emit_selection_change()
        super().focusOutEvent(event)