from .gui import MineNewWordsWidget, NewWordsTableWidget
from .db import SentenceRepository


class Tatoeba:
    def __init__(self):
        self.sentence_repository = SentenceRepository()


class MiningProcessConductor:
    def __init__(self, sentence_repository: SentenceRepository):
        self.sentence_repository = sentence_repository
        self.cached_mining_widget_data = None
        self.words_mined = []

    def start(self):
        self.mining_widget = MineNewWordsWidget(self.cached_mining_widget_data)
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

