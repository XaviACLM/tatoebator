from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton

from ..anki_db_interface import AnkiObjectIdRegistry


class CascadingDropdown(QWidget):
    def __init__(self, choices: dict[str, dict[str, list[str]]], initial_selection: tuple[str, str, str] = None):
        super().__init__()
        self.choices = choices

        self.dropdown1 = QComboBox()
        self.dropdown2 = QComboBox()
        self.dropdown3 = QComboBox()

        self.dropdown1.addItems(choices.keys())
        self.dropdown1.setCurrentIndex(-1)
        self.dropdown2.setEnabled(False)
        self.dropdown3.setEnabled(False)

        self.dropdown1.currentTextChanged.connect(self.update_dropdown2)
        self.dropdown2.currentTextChanged.connect(self.update_dropdown3)

        layout = QHBoxLayout()
        layout.addWidget(self.dropdown1)
        layout.addWidget(self.dropdown2)
        layout.addWidget(self.dropdown3)
        self.setLayout(layout)

        if initial_selection:
            self.set_initial_selection(*initial_selection)

    def update_dropdown2(self, selection: str):
        self.dropdown2.clear()
        self.dropdown3.clear()
        self.dropdown3.setEnabled(False)

        if selection in self.choices:
            self.dropdown2.addItems(self.choices[selection].keys())
            self.dropdown2.setEnabled(True)
            self.dropdown2.setCurrentIndex(-1)

    def update_dropdown3(self, selection: str):
        self.dropdown3.clear()

        parent_selection = self.dropdown1.currentText()
        if parent_selection and selection in self.choices.get(parent_selection, {}):
            self.dropdown3.addItems(self.choices[parent_selection][selection])
            self.dropdown3.setEnabled(True)
            self.dropdown3.setCurrentIndex(-1)

    def get_selected_values(self) -> tuple[str, str, str]:
        return (
            self.dropdown1.currentText() or None,
            self.dropdown2.currentText() or None,
            self.dropdown3.currentText() or None
        )

    def set_initial_selection(self, first: str, second: str, third: str):
        if first in self.choices:
            self.dropdown1.setCurrentText(first)
            self.update_dropdown2(first)

            if second in self.choices[first]:
                self.dropdown2.setCurrentText(second)
                self.update_dropdown3(second)

                if third in self.choices[first][second]:
                    self.dropdown3.setCurrentText(third)


class AnkiRegistryEditorWidget(QWidget):
    backing_up_from = pyqtSignal()
    continuing_from = pyqtSignal()

    def __init__(self, registry: AnkiObjectIdRegistry):
        super().__init__()
        self.registry = registry

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()

        # buttons
        buttons_bar = QHBoxLayout()
        self.button_cancel = QPushButton('Cancel')
        self.button_save = QPushButton('Save')
        buttons_bar.addWidget(self.button_cancel)
        buttons_bar.addWidget(self.button_save)

        # signals
        self.button_cancel.clicked.connect(self._check_before_cancel)
        self.button_save.clicked.connect(self._save_and_continue)

        layout.addLayout(buttons_bar)

        self.setLayout(layout)

    def _check_before_cancel(self):
        raise NotImplementedError
        self.backing_up_from.emit()

    def _save_and_continue(self):
        raise NotImplementedError
        self.continuing_from.emit()