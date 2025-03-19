from typing import Optional, Tuple, Dict, List, Iterable

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QSpacerItem, QSizePolicy, QFrame

from .default_gui_elements import Colors
from .util import ask_yes_no_question
from tatoebator.anki_interfacing.anki_db_interface import AnkiDbInterface
from ..anki_interfacing.vocab_field_registry import FieldPointer


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

    def get_selected_fields(self) -> List[FieldPointer]:
        name_data = [dropdown.get_selected_values() for dropdown in self._dropdowns]
        return [FieldPointer(self.decks_by_name[deck_name],
                             self.notetypes_by_names[deck_name][notetype_name],
                             self.fields_by_names[deck_name][notetype_name][field_name])
                for deck_name, notetype_name, field_name in name_data
                if (deck_name and notetype_name and field_name) is not None]

    def _init_ui(self):
        layout = QVBoxLayout()

        self._dropdown_container = QVBoxLayout()

        self._dropdowns = []
        for starting_choice in self._starting_choices():
            dropdown = CascadingDropdownWidget(self.fields_by_names, starting_choice)
            self._dropdowns.append(dropdown)
            self._dropdown_container.addWidget(dropdown)
        self._dropdown_container.setContentsMargins(10, 10, 10, 10)
        self._dropdown_container_container = QVBoxLayout()
        self._dropdown_container_container.addLayout(self._dropdown_container)
        self._spacer_bottom = QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self._dropdown_container_container.addSpacerItem(self._spacer_bottom)
        layout.addLayout(self._dropdown_container_container)

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
        self._dropdowns.append(dropdown)
        self._dropdown_container.addWidget(dropdown)

    def _remove_selector(self):
        dropdown = self._dropdowns.pop(-1)
        self._dropdown_container.removeWidget(dropdown)

    def _starting_choices(self) -> List[Tuple[str, str, str]]:
        # this could be in util but let's keep it local to avoid using it any more than necessary - obv hacky and bad
        get_key_from_value = lambda value, dictionary: next(filter(lambda k: dictionary[k]==value, dictionary), None)
        res = []
        for field_pointer in self.anki_db_interface.other_vocab_fields:
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

        self._field_selector = FieldSelectorWidget(self.anki_db_interface)
        layout.addWidget(self._field_selector)
        self._field_selector.setObjectName("field_selector")
        self._field_selector.setStyleSheet(f'QFrame#field_selector {{background-color: {Colors.light_grey.name()}; border-radius: 10px;}}')
        self._field_selector.setContentsMargins(10, 10, 10, 10)

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

    def _data_has_changed(self):
        return set(self.anki_db_interface.other_vocab_fields) != set(self._field_selector.get_selected_fields())

    def _check_before_cancel(self):
        if self._data_has_changed() and not ask_yes_no_question("Cancel changes to config?"):
            return
        self.backing_up_from.emit()

    def _save_and_continue(self):
        self.anki_db_interface.other_vocab_fields.clear()
        self.anki_db_interface.other_vocab_fields.extend(self._field_selector.get_selected_fields())
        self.anki_db_interface.other_vocab_fields.save()
        self.continuing_from.emit()