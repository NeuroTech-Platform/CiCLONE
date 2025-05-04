from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt, pyqtSignal

class ClickableImageLabel(QLabel):
    clicked = pyqtSignal(int, int)  # x, y in label coordinates

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(int(event.position().x()), int(event.position().y()))
        super().mousePressEvent(event)
