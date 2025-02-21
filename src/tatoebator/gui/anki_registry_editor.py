from typing import Optional, Tuple, Dict, List, Iterable

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QSpacerItem, QSizePolicy, QFrame

from ..anki_db_interface import AnkiDbInterface


class CascadingDropdownWidget(QWidget):
    def __init__(self, options: Dict[str, Dict[str, Iterable[str]]], initial_selection: Optional[Tuple[str, str, str]] = None):
        super().__init__()
        self.options = options

        self._init_ui(options)

        if initial_selection is not None:
            self._set_initial_selection(*initial_selection)

    def _init_ui(self, options):
        self._dropdown1 = QComboBox()
        self._dropdown2 = QComboBox()
        self._dropdown3 = QComboBox()
        self._dropdown1.addItems(options.keys())
        self._dropdown1.setCurrentIndex(-1)
        self._dropdown2.setEnabled(False)
        self._dropdown3.setEnabled(False)
        self._dropdown1.currentTextChanged.connect(self._update_dropdowns23)
        self._dropdown2.currentTextChanged.connect(self._update_dropdown3)
        layout = QHBoxLayout()
        layout.addWidget(self._dropdown1, stretch=2)
        layout.addWidget(self._dropdown2, stretch=1)
        layout.addWidget(self._dropdown3, stretch=1)
        self.setLayout(layout)

    def _update_dropdowns23(self, selection: str):
        self._dropdown2.clear()
        self._dropdown2.addItems(self.options[selection].keys())
        self._dropdown2.setEnabled(True)
        self._dropdown2.setCurrentIndex(-1)

        self._dropdown3.clear()
        self._dropdown3.setEnabled(False)

    def _update_dropdown3(self, selection: str):
        self._dropdown3.clear()
        parent_selection = self._dropdown1.currentText()
        if selection not in self.options[parent_selection]:
            return  # ugh
        self._dropdown3.addItems(self.options[parent_selection][selection])
        self._dropdown3.setEnabled(True)
        self._dropdown3.setCurrentIndex(-1)

    def get_selected_values(self) -> Tuple[str, str, str]:
        return (
            self._dropdown1.currentText() or None,
            self._dropdown2.currentText() or None,
            self._dropdown3.currentText() or None
        )

    def _set_initial_selection(self, selected_1: str, selected_2: str, selected_3: str):
        exception = KeyError("One of the initial selections passed to CascadingMenu was not in the options")
        if selected_1 not in self.options:
            raise exception
        self._dropdown1.setCurrentText(selected_1)
        self._update_dropdowns23(selected_1)
        if selected_2 not in self.options[selected_1]:
            raise exception
        self._dropdown2.setCurrentText(selected_2)
        self._update_dropdown3(selected_2)
        if selected_3 not in self.options[selected_1][selected_2]:
            raise exception
        self._dropdown3.setCurrentText(selected_3)


class FieldSelectorWidget(QFrame):
    def __init__(self, anki_db_interface: AnkiDbInterface):
        super().__init__()
        self.anki_db_interface = anki_db_interface

        self.decks_by_name, self.notetypes_by_names, self.fields_by_names = self.anki_db_interface.get_all_field_data()

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()

        self.dropdown_container = QVBoxLayout()

        self.dropdowns = []
        for starting_choice in self._starting_choices():
            dropdown = CascadingDropdownWidget(self.fields_by_names, starting_choice)
            self.dropdowns.append(dropdown)
            self.dropdown_container.addWidget(dropdown)
        self.dropdown_container.setContentsMargins(10,10,10,10)
        layout.addLayout(self.dropdown_container)

        self.button_bar = QHBoxLayout()
        spacer_left = QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.add_button = QPushButton("Add new")
        self.remove_button = QPushButton("Remove last")
        self.button_bar.addSpacerItem(spacer_left)
        self.button_bar.addWidget(self.add_button)
        self.button_bar.addWidget(self.remove_button)
        self.button_bar.setContentsMargins(10,10,10,10)
        layout.addLayout(self.button_bar)

        self.add_button.clicked.connect(self._add_selector)
        self.remove_button.clicked.connect(self._remove_selector)

        self.setLayout(layout)

    def _add_selector(self):
        dropdown = CascadingDropdownWidget(self.fields_by_names)
        self.dropdowns.append(dropdown)
        self.dropdown_container.addWidget(dropdown)

    def _remove_selector(self):
        dropdown = self.dropdowns.pop(-1)
        self.dropdown_container.removeWidget(dropdown)

    def _starting_choices(self) -> List[Tuple[str, str, str]]:
        # this could be in util but let's keep it local to avoid using it any more than necessary - obv hacky and bad
        get_key_from_value = lambda value, dictionary: next(filter(lambda k: dictionary[k]==value, dictionary), None)
        res = []
        for field_pointer in self.anki_db_interface.registry.other_vocab_fields:
            deck_name = get_key_from_value(field_pointer.deck_id, self.decks_by_name)
            notetype_name = get_key_from_value(field_pointer.notetype_id, self.notetypes_by_names[deck_name])
            field_name = get_key_from_value(field_pointer.field_ord, self.fields_by_names[deck_name][notetype_name])
            res.append((deck_name, notetype_name, field_name))
        return res


class AnkiRegistryEditorWidget(QWidget):
    backing_up_from = pyqtSignal()
    continuing_from = pyqtSignal()

    def __init__(self, anki_db_interface: AnkiDbInterface):
        super().__init__()
        self.anki_db_interface = anki_db_interface

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()

        self.field_selector = FieldSelectorWidget(self.anki_db_interface)
        layout.addWidget(self.field_selector)
        self.field_selector.setObjectName("field_selector")
        self.field_selector.setStyleSheet('QFrame#field_selector {background-color: lightgray; border-radius: 10px;}')
        self.field_selector.setContentsMargins(10,10,10,10)

        # buttons
        self._buttons_bar = QHBoxLayout()
        spacer_left = QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._button_cancel = QPushButton('Cancel')
        self._button_save = QPushButton('Save changes')
        self._buttons_bar.addSpacerItem(spacer_left)
        self._buttons_bar.addWidget(self._button_cancel)
        self._buttons_bar.addWidget(self._button_save)

        # signals
        self._button_cancel.clicked.connect(self._check_before_cancel)
        self._button_save.clicked.connect(self._save_and_continue)

        layout.addLayout(self._buttons_bar)
        self._buttons_bar.setContentsMargins(10,10,10,10)

        self.setLayout(layout)
        self.setGeometry(100, 100, 700, 500)

    def _check_before_cancel(self):
        raise NotImplementedError
        self.backing_up_from.emit()

    def _save_and_continue(self):
        raise NotImplementedError
        self.continuing_from.emit()