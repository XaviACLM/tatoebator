import functools
from typing import Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QComboBox, QLabel, QLineEdit, QInputDialog, QStyledItemDelegate
from PyQt6.QtGui import QColor, QPalette

from .default_gui_elements import Colors
from ..anki_interfacing import AnkiDbInterface


class OutputDeckSelectionWidget(QWidget):

    _create_new_deck_text = "-- Create new deck --"

    def __init__(self, anki_db_interface: AnkiDbInterface, starting_deck_id: Optional[int] = None):
        super().__init__()
        self.anki_db_interface = anki_db_interface

        self._init_ui(starting_deck_id)

    def _init_ui(self, starting_deck_id: Optional[int]):
        self.layout = QVBoxLayout()

        self.dropdown = QComboBox()
        # todo figure out how to style this and the last item properly, someday
        self.dropdown.setPlaceholderText("-- Select output deck --")
        self.warning_label = QLabel()
        self.warning_label.setStyleSheet(f"color: {Colors.warning_red.name()};")
        self.warning_label.setText("Selected deck contains non-tatoebator cards.")
        f = self.warning_label.font()
        f.setItalic(True)
        self.warning_label.setFont(f)
        sp_retain = self.warning_label.sizePolicy()
        sp_retain.setRetainSizeWhenHidden(True)
        self.warning_label.setSizePolicy(sp_retain)
        self.warning_label.hide()

        self._populate_dropdown()
        self._select_starting_dropdown_index(starting_deck_id)
        self.dropdown.currentIndexChanged.connect(self._on_selection_changed)

        self.layout.addWidget(self.dropdown)
        self.layout.addWidget(self.warning_label)
        self.setLayout(self.layout)

        self._creating_new_deck = False

    def _populate_dropdown(self):
        self.dropdown.clear()
        self.decks = self.anki_db_interface.get_deck_ids_by_name()  # {name: id}

        for name in self.decks:
            self.dropdown.addItem(name)

        # Add "Create New Deck" option
        self.dropdown.addItem(self._create_new_deck_text)
        last_index = self.dropdown.count() - 1

        # Make the last option grey
        palette = self.dropdown.view().palette()
        palette.setColor(QPalette.ColorRole.Text, QColor("gray"))
        self.dropdown.view().setPalette(palette)

    def _on_selection_changed(self):
        selected_text = self.dropdown.currentText()

        if selected_text == self._create_new_deck_text:
            self._create_new_deck()
        else:
            deck_id = self.decks[selected_text]
            self._update_notetype_warning(deck_id)

    def _update_notetype_warning(self, deck_id: int):
        if self._does_deck_contain_non_tatoebator_notetypes(deck_id):
            self.warning_label.show()
        else:
            self.warning_label.hide()

    def _create_new_deck(self):
        # todo created deck doesn't show up on the dashboard until you hit sync
        if self._creating_new_deck:
            # if we don't have this lock, the dropdown updates during deck creation trip another deck creation prompt
            return
        new_deck_name, accepted = QInputDialog.getText(self, "New Deck", "Enter new deck name:",
                                                       QLineEdit.EchoMode.Normal, "")
        if accepted and new_deck_name:
            new_id = self.anki_db_interface.create_new_deck(new_deck_name, refresh_deck_browser=True)
            self.decks[new_deck_name] = new_id

            self._creating_new_deck = True
            self.dropdown.insertItem(self.dropdown.count() - 1, new_deck_name)  # Insert before "Create New Deck"
            self._creating_new_deck = False

            self.dropdown.setCurrentText(new_deck_name)
            self.warning_label.hide()

    def get_selected_deck_id(self) -> int:
        selected_text = self.dropdown.currentText()
        return self.decks.get(selected_text, None)

    def does_selected_deck_contain_non_tatoebator_notetypes(self) -> bool:
        deck_id = self.get_selected_deck_id()
        return self._does_deck_contain_non_tatoebator_notetypes(deck_id) if deck_id else False

    @functools.lru_cache()
    def _does_deck_contain_non_tatoebator_notetypes(self, deck_id: int) -> bool:
        return self.anki_db_interface.does_deck_contain_non_tatoebator_notetypes(deck_id)

    def _select_starting_dropdown_index(self, starting_deck_id: Optional[int]):
        if starting_deck_id is not None:
            starting_deck_name = next((name for name, id in self.decks.items() if id == starting_deck_id), None)
            if starting_deck_name is not None:
                self.dropdown.setCurrentText(starting_deck_name)
                self._update_notetype_warning(starting_deck_id)
                return
        self.dropdown.setCurrentIndex(-1)
