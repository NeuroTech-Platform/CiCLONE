"""
About dialog showing application information and version.

This dialog displays metadata from _metadata.py in a UI designed with Qt Designer.
"""

from PyQt6.QtWidgets import QDialog

from ciclone.forms.AboutDialog_ui import Ui_AboutDialog
from ciclone._metadata import (
    __version__,
    __authors__,
    __copyright__,
    __license__,
    __description__
)


class AboutDialog(QDialog, Ui_AboutDialog):
    """
    About dialog showing application information and version.

    Uses a UI file designed in Qt Designer with metadata populated from _metadata.py.
    """

    def __init__(self, parent=None):
        """
        Initialize the About dialog.

        Args:
            parent: Parent widget (typically MainWindow)
        """
        super().__init__(parent)
        self.setupUi(self)
        self._populate_metadata()

    def _populate_metadata(self):
        """
        Populate the dialog labels with metadata from _metadata.py.

        This method sets the text for all labels based on the application metadata,
        keeping the UI structure in the .ui file and data population in Python.
        """
        # Set version
        self.versionLabel.setText(f"Version {__version__}")

        # Set description
        self.descriptionLabel.setText(__description__)

        # Set copyright
        self.copyrightLabel.setText(__copyright__)

        # Set author(s) - handle single or multiple authors
        if len(__authors__) == 1:
            author_text = f"Author: {__authors__[0]}"
        else:
            author_text = f"Authors: {', '.join(__authors__)}"
        self.authorLabel.setText(author_text)

        # Set license
        self.licenseLabel.setText(f"Licensed under {__license__}")
