from typing import List, Optional

from aqt import gui_hooks

from .anki_db_interface import AnkiDbInterface
from .audio import MediaManager
from .constants import SENTENCES_PER_CARD
from .db import SentenceRepository
from .gui import MineNewWordsWidget, NewWordsTableWidget
from .gui.anki_registry_editor import AnkiRegistryEditorWidget
from .gui.word_miner_menu import MinerFieldDataCache
from .language_processing import japanese_chars_ratio, DefinitionFetcher
from .util import get_clipboard_text


class Tatoebator:
    def __init__(self):
        self.media_manager = MediaManager()
        self.sentence_repository = SentenceRepository(self.media_manager)
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
        self.anki_db_interface = AnkiDbInterface(self.media_manager)

    def word_table_test(self, words: List[str]):
        self.table_widget = NewWordsTableWidget(words, self.sentence_repository, self.definition_fetcher)
        self.table_widget.show()

    def anki_db_test(self):
        fp = self.anki_db_interface.other_vocab_fields[0]

        from aqt.utils import showInfo

        showInfo(str(self.anki_db_interface._search_cards_in_deck(fp,
                                                                  ["時計", "電話", "テレビ", "音楽", "映画", "写真",
                                                                   "手紙", "仕事", "休み", "旅行", "お金", "時間",
                                                                   "今日", "明日", "昨日", "今", "後で"])))

    def note_creation_test(self):
        self.anki_db_interface.card_creator.create_note("balls", None, None)

    def ensure_data_health(self):
        self.sentence_repository.update_known(self.anki_db_interface.get_known_words())
        self.sentence_repository.cleanup_orphaned_audio_files()
        self.sentence_repository.regenerate_missing_audio_files()


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

        sentences_per_word_ideally = SENTENCES_PER_CARD
        request = {word: sentences_per_word_ideally for word in new_words_data}
        sentences = self.sentence_repository.produce_sentences_for_words(request,
                                                                         produce_new=False,
                                                                         ensure_audio=True,
                                                                         with_furigana=True)

        for word, definitions in new_words_data.items():
            self.anki_db_interface.card_creator.create_note(word, definitions, sentences[word])
