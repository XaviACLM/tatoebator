from typing import List, Optional

from aqt import gui_hooks

from .anki_db_interface import AnkiDbInterface
from .db import SentenceRepository
from .gui import MineNewWordsWidget, NewWordsTableWidget
from .gui.anki_registry_editor import AnkiRegistryEditorWidget
from .gui.word_miner_menu import MinerFieldDataCache
from .language_processing import japanese_chars_ratio, DefinitionFetcher
from .util import get_clipboard_text


class Tatoebator:
    def __init__(self):
        self.sentence_repository = SentenceRepository()
        self.definition_fetcher = DefinitionFetcher()
        self.anki_db_interface: Optional[AnkiDbInterface] = None

        gui_hooks.main_window_did_init.append(self._init_anki_inteface)
        gui_hooks.main_window_did_init.append(self._update_known_counts)
        gui_hooks.reviewer_will_end.append(self._update_known_counts)

    def mining_to_deck_flow(self):
        clipboard_text = get_clipboard_text()
        starting_text = clipboard_text if clipboard_text and japanese_chars_ratio(clipboard_text) > 0.7 else None

        self.mining_conductor = MiningProcessConductor(self.sentence_repository,
                                                       self.anki_db_interface,
                                                       self.definition_fetcher)
        self.mining_conductor.start(starting_text)

    def word_table_test(self, words: List[str]):
        self.table_widget = NewWordsTableWidget(words, self.sentence_repository, self.definition_fetcher)
        self.table_widget.show()

    def open_registry_editor(self):
        self.registry_editor = AnkiRegistryEditorWidget(self.anki_db_interface)
        close = lambda: self.registry_editor.close()
        self.registry_editor.backing_up_from.connect(close)
        self.registry_editor.continuing_from.connect(close)
        self.registry_editor.continuing_from.connect(self._update_known_counts)
        self.registry_editor.show()

    def _update_known_counts(self):
        self.sentence_repository.update_known(self.anki_db_interface.get_known_words())

    def _init_anki_inteface(self):
        self.anki_db_interface = AnkiDbInterface()



class MiningProcessConductor:
    def __init__(self, sentence_repository: SentenceRepository,
                 anki_db_interface: AnkiDbInterface,
                 definition_fetcher: DefinitionFetcher):
        self.sentence_repository = sentence_repository
        self.definition_fetcher = definition_fetcher
        self.anki_db_interface = anki_db_interface
        self.cached_mining_widget_data = None
        self.words_mined = []

    def start(self, starting_text: Optional[str] = None):
        if starting_text is not None:
            self.cached_mining_widget_data = MinerFieldDataCache.from_text(starting_text)
        self.mining_widget = MineNewWordsWidget(self.anki_db_interface, self.cached_mining_widget_data)
        self.mining_widget.continuing_from.connect(self._mining_to_card_creation)
        self.mining_widget.show()

    def _mining_to_card_creation(self):
        self.cached_mining_widget_data = self.mining_widget.get_cached_fields()
        self.words_mined = self.mining_widget.get_selected_words()
        self.mining_widget.close()
        self.table_widget = NewWordsTableWidget(self.words_mined, self.sentence_repository, self.definition_fetcher)
        self.table_widget.backing_up_from.connect(self._back_from_card_creation_to_mining)
        self.table_widget.continuing_from.connect(self._create_cards)
        self.table_widget.show()

    def _back_from_card_creation_to_mining(self):
        self.table_widget.close()
        self.start()  # self.text_being_mined is already updated

    def _create_cards(self):
        new_words_data = self.table_widget.get_new_word_data()
        self.table_widget.close()

        from aqt.utils import showInfo
        message = ["this doesn't work yet :^)\nhere i should create the cards for:"]
        for word, definition in new_words_data.items():
            message.append(f"{word}  -  {definition.en} / {definition.jp}")
        showInfo("\n\n".join(message))

