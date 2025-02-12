import sys

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QScrollArea, QHBoxLayout, QPushButton
)

from ..language_processing import get_meaning_from_tanoshii, get_definition_from_weblio
from ..constants import SENTENCES_PER_CARD
from ..db import SentenceDbManager


class NewWordsTableWidget(QWidget):
    def __init__(self, words):
        # maybe the db manager should be passed by constructor?
        self.sentence_db_manager = SentenceDbManager()
        super().__init__()

        self.words = words
        self._translations = None
        self._definitions = None
        self.n_rows = len(words)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # Create the table
        self.table = QTableWidget(self.n_rows, 5)
        self.table.setHorizontalHeaderLabels(['Name', '# Sentences', '# Missing', 'Translation', 'Definition'])

        # Populate the table
        for row, name in enumerate(self.words):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(""))
            self.table.setItem(row, 2, QTableWidgetItem(""))
            self.table.setItem(row, 3, QTableWidgetItem(""))
            self.table.setItem(row, 4, QTableWidgetItem(""))
        self.update_sentence_counts()

        # Adjust column sizes
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        # Add scrolling
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.table)
        scroll_area.setWidgetResizable(True)

        layout.addWidget(scroll_area)

        buttons_bar = QHBoxLayout()
        self.button_sentences = QPushButton('Produce missing example sentences')
        self.button_sentences.clicked.connect(self.produce_missing_sentences)
        self.checkbox_translations = QCheckBox("Generate translations")
        self.checkbox_translations.stateChanged.connect(self.cb_translations_updated)
        self.checkbox_definitions = QCheckBox("Generate definitions")
        self.checkbox_definitions.stateChanged.connect(self.cb_definitions_updated)
        self.button_continue = QPushButton('Create cards')
        buttons_bar.addWidget(self.button_sentences)
        buttons_bar.addWidget(self.checkbox_translations)
        buttons_bar.addWidget(self.checkbox_definitions)
        buttons_bar.addWidget(self.button_continue)

        layout.addLayout(buttons_bar)

        self.setLayout(layout)

    def update_sentence_counts(self):
        sentences_per_word = self.sentence_db_manager.count_lexical_word_ocurrences(self.words)
        for row, name in enumerate(self.words):
            self.table.item(row, 1).setText(str(sentences_per_word[name]))
            self.table.item(row, 2).setText(str(max(0, SENTENCES_PER_CARD - sentences_per_word[name])))

    def cb_translations_updated(self, state):
        """
        # from translator import translate
        if state:
            #this is such a stupid hack. we should at least batch it
            #...or get the translations from an actual dictionary, probably
            translation = translate(str(self.words)[1:-1])
            translation = translation.replace('"','').replace(',','').replace('\'','')
            translations = translation.split(' ')
        """
        for i in range(self.n_rows):
            self.table.item(i, 3).setText(self.get_translations()[i] if state else "")

    def cb_definitions_updated(self, state):
        for i in range(self.n_rows):
            self.table.item(i, 4).setText(self.get_definitions()[i] if state else "")

    def produce_missing_sentences(self):
        for word in self.words:
            self.sentence_db_manager.produce_up_to_limit(word)
        self.update_sentence_counts()

    # these should be @cached_property but it doesn't work for some reason - something about qt?
    def get_translations(self):
        if self._translations is None:
            self._translations = list(map(get_meaning_from_tanoshii, self.words))
        return self._translations

    def get_definitions(self):
        if self._definitions is None:
            self._definitions = list(map(get_definition_from_weblio, self.words))
        return self._definitions


if __name__ == '__main__':
    app = QApplication(sys.argv)
    names = ['Row 1', 'Row 2', 'Row 3', 'Row 4', 'Row 5']
    ex = NewWordsTableWidget(names)
    ex.show()
    sys.exit(app.exec())
