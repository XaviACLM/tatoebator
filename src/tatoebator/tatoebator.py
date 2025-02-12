from typing import List, Optional

from .anki_db_interface import AnkiDbInterface
from .gui import MineNewWordsWidget, NewWordsTableWidget
from .db import SentenceRepository
from .language_processing import japanese_chars_ratio
from .util import get_clipboard_text

from aqt import gui_hooks


class Tatoebator:
    def __init__(self):
        self.sentence_repository = SentenceRepository()
        self.anki_db_interface = AnkiDbInterface()
        gui_hooks.main_window_did_init.append(self.update_known_counts)

    def mining_to_deck_flow(self):
        clipboard_text = get_clipboard_text()
        starting_text = clipboard_text if clipboard_text and japanese_chars_ratio(clipboard_text) > 0.7 else None

        self.mining_conductor = MiningProcessConductor(self.sentence_repository, self.anki_db_interface)
        self.mining_conductor.start(starting_text)

    def word_table_test(self, words: List[str]):
        self.table_widget = NewWordsTableWidget(words, self.sentence_repository)
        self.table_widget.show()

    def update_known_counts(self):
        self.sentence_repository.update_known(self.anki_db_interface.get_known_words())


class MiningProcessConductor:
    def __init__(self, sentence_repository: SentenceRepository, anki_db_interface: AnkiDbInterface):
        self.sentence_repository = sentence_repository
        self.anki_db_interface = anki_db_interface
        self.cached_mining_widget_data = None
        self.words_mined = []

    def start(self, starting_words: Optional[List[str]] = None):
        self.mining_widget = MineNewWordsWidget(self.anki_db_interface, starting_words or self.cached_mining_widget_data)
        self.mining_widget.continue_button_clicked.connect(self._mining_to_card_creation)
        self.mining_widget.show()

    def _mining_to_card_creation(self):
        self.cached_mining_widget_data = self.mining_widget.get_cached_fields()
        self.words_mined = self.mining_widget.get_selected_words()
        self.mining_widget.close()
        self.table_widget = NewWordsTableWidget(self.words_mined, self.sentence_repository)
        self.table_widget.back_button_clicked.connect(self._back_from_card_creation_to_mining)
        self.table_widget.continue_button_clicked.connect(self._create_cards)
        self.table_widget.show()

    def _back_from_card_creation_to_mining(self):
        self.table_widget.close()
        self.start()  # self.text_being_mined is already updated

    def _create_cards(self):
        new_words_data = self.table_widget.get_new_word_data()
        self.table_widget.close()
        from aqt.utils import showInfo
        showInfo(f"this doesn't work yet :^)\n\nhere i should create the cards for {new_words_data}")

