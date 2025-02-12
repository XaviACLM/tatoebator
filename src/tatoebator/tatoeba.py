from .gui import MineNewWordsWidget, NewWordsTableWidget
from .db import SentenceRepository


class Tatoeba:
    def __init__(self):
        self.sentence_repository = SentenceRepository()


class MiningProcessConductor:
    def __init__(self, sentence_repository: SentenceRepository):
        self.sentence_repository = sentence_repository
        self.text_being_mined = ""
        self.words_mined = []

    def start(self):
        self.mining_widget = MineNewWordsWidget(self.text_being_mined)
        self.mining_widget.continue_button_clicked.connect(self.mining_to_card_creation)
        self.mining_widget.show()

    def mining_to_card_creation(self):
        self.text_being_mined = self.mining_widget.get_mined_text()
        self.words_mined = self.mining_widget.get_selected_words()
        self.mining_widget.close()
        self.table_widget = NewWordsTableWidget(self.words_mined, self.sentence_repository)
        self.table_widget.show()
