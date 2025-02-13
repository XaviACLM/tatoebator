import sys
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QProgressDialog, QApplication


class ProgressDialog:
    def __init__(self, title, n_tasks):
        self.title = title
        self.n_tasks = n_tasks
        self.dialog = None

    def __enter__(self):
        app = QApplication.instance() or QApplication(sys.argv)  # Ensure QApplication exists
        self.dialog = QProgressDialog(self.title, "Cancel", 0, 0)
        self.dialog.setMaximum(self.n_tasks)
        self.dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.dialog.setMinimumDuration(0)
        self.dialog.setAutoClose(False)
        self.dialog.setAutoReset(False)
        self.dialog.show()
        return self  # Allows calling `set_message()`

    def update_progress(self, message: Optional[str] = None):
        """Update progress message."""
        if self.dialog:
            self.dialog.setValue(self.dialog.value() + 1)
            if message: self.dialog.setLabelText(message)
            QApplication.processEvents()  # Keep UI responsive

    def __exit__(self, exc_type, exc_value, traceback):
        """Close the dialog when done."""
        if self.dialog:
            self.dialog.close()
