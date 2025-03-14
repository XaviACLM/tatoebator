import sys
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QProgressDialog, QApplication


class ProgressDialog:
    def __init__(self, title, n_tasks):
        self._title = title
        self._n_tasks = n_tasks
        self._dialog = None

    def __enter__(self):
        app = QApplication.instance() or QApplication(sys.argv)  # Ensure QApplication exists
        self._dialog = QProgressDialog(self._title, "Cancel", 0, 100)
        self._dialog.setMaximum(self._n_tasks)
        self._dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._dialog.setMinimumDuration(0)
        self._dialog.setAutoClose(False)
        self._dialog.setAutoReset(False)
        self._dialog.show()
        return self  # Allows calling `set_message()`

    def update_progress(self, message: Optional[str] = None, value: Optional[int] = None):
        """Update progress message."""
        if self._dialog:
            value = value if value is not None else self._dialog.value() + 1
            self._dialog.setValue(value)
            if message: self._dialog.setLabelText(message)
            QApplication.processEvents()  # Keep UI responsive

    def __exit__(self, exc_type, exc_value, traceback):
        """Close the dialog when done."""
        if self._dialog:
            self._dialog.close()
