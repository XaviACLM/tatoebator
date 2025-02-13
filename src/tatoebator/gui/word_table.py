from typing import Dict

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QScrollArea, QHBoxLayout, QPushButton
)

from .process_dialog import ProgressDialog
from .util import ask_yes_no_question
from ..language_processing import grammaticalized_words, DefinitionFetcher, Definitions
from ..db import SentenceRepository


class NewWordsTableWidget(QWidget):
    backing_up_from = pyqtSignal()
    continuing_from = pyqtSignal()

    sentences_per_word_quota = 5

    # SELECTOR_ROW = 0
    # NAME_ROW = 1
    # S_ROW = 2
    # S50_ROW = 3
    # S80_ROW = 4
    # TRANSLATION_ROW = 5
    # DEFINITION_ROW = 6
    # N_ROWS = 7

    def __init__(self, words,
                 sentence_repository: SentenceRepository,
                 definition_fetcher: DefinitionFetcher):
        super().__init__()
        self.sentence_repository = sentence_repository
        self.definition_fetcher = definition_fetcher

        self.n_sentences_per_word = {word: 0 for word in words}
        self.n_sentences_per_word_50 = {word: 0 for word in words}
        self.n_sentences_per_word_80 = {word: 0 for word in words}
        self.did_search_sentences = {word: False for word in words}

        # reorder to put grammaticalized words at the end
        # funny indexing mostly to preserve order but also to count amt_grammaticalized
        amt_grammaticalized = 0
        for i in range(len(words)):
            j = i - amt_grammaticalized
            if words[j] in grammaticalized_words:
                words.append(words.pop(j))
                amt_grammaticalized += 1

        self.words = words
        self.n_rows = len(words)
        self._init_ui()

        self._uncheck_grammaticalized(amt_grammaticalized)

    def get_new_word_data(self) -> Dict[str, Definitions]:
        return {self.table.item(i, 1).text(): Definitions(self.table.item(i, 5).text(),
                                                          self.table.item(i, 6).text())
                for i in range(self.n_rows) if self._is_idx_selected(i)}

    def _init_ui(self):
        layout = QVBoxLayout()

        # Create the table
        self.table = QTableWidget(self.n_rows, 7)
        self.table.setHorizontalHeaderLabels(
            ['Include', 'Name', '# Sentences', '#S>50%', '#S>80%', 'Translation', 'Definition'])

        self.white = QColor(255, 255, 255)
        self.lightgrey = QColor(240, 240, 240)
        self.darkgrey = QColor(220, 220, 220)
        self.red = QColor(255, 230, 230)
        self.green = QColor(220, 255, 220)
        self.black = QColor(0, 0, 0)

        # some kinda progress bar during sentence/translation/definition search
        # possibly a link to a help menu
        # possibly a link to a sentence adder menu (we'll want to do that anyway)
        #   ->   include in database whether sentence was added by user
        # and card creation, w a lil popup telling you cards got created

        self.table.verticalHeader().setVisible(False)

        for row, name in enumerate(self.words):
            self.table.setItem(row, 0, QTableWidgetItem())
            self.table.item(row, 0).setFlags(self.table.item(row, 0).flags() | Qt.ItemFlag.ItemIsUserCheckable)
            self.table.item(row, 0).setCheckState(Qt.CheckState.Checked)

            self.table.setItem(row, 1, QTableWidgetItem(name))
            self.table.item(row, 1).setFlags(self.table.item(row, 0).flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.item(row, 1).setBackground(self.lightgrey)
            self.table.item(row, 1).setForeground(self.black)

            self.table.setItem(row, 2, QTableWidgetItem(""))
            self.table.item(row, 2).setFlags(self.table.item(row, 1).flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.item(row, 2).setForeground(self.black)

            self.table.setItem(row, 3, QTableWidgetItem(""))
            self.table.item(row, 3).setFlags(self.table.item(row, 2).flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.item(row, 3).setForeground(self.black)

            self.table.setItem(row, 4, QTableWidgetItem(""))
            self.table.item(row, 4).setFlags(self.table.item(row, 3).flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.item(row, 4).setForeground(self.black)

            self.table.setItem(row, 5, QTableWidgetItem(""))

            self.table.setItem(row, 6, QTableWidgetItem(""))

        # Adjust column sizes
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        # Add scrolling
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.table)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        # buttons
        buttons_bar = QHBoxLayout()
        self.button_back = QPushButton('Go back')
        self.button_sentences = QPushButton('Produce missing sentences')
        self.button_sentences.clicked.connect(self._produce_missing_sentences)
        self.button_translations = QPushButton("Generate translations")
        self.button_translations.clicked.connect(self._generate_translations)
        self.button_definitions = QPushButton("Generate definitions")
        self.button_definitions.clicked.connect(self._generate_definitions)
        self.button_remove = QPushButton("Remove unselected")
        self.button_remove.clicked.connect(self._remove_unselected)
        self.button_continue = QPushButton('Create cards')
        buttons_bar.addWidget(self.button_back)
        buttons_bar.addWidget(self.button_sentences)
        buttons_bar.addWidget(self.button_translations)
        buttons_bar.addWidget(self.button_definitions)
        buttons_bar.addWidget(self.button_remove)
        buttons_bar.addWidget(self.button_continue)

        # signals
        self.button_back.clicked.connect(self.backing_up_from.emit)
        self.button_continue.clicked.connect(self._check_before_continuing)
        self.table.itemChanged.connect(self._handle_table_change)

        layout.addLayout(buttons_bar)

        self.setLayout(layout)

        self._update_sentence_counts()

    def _uncheck_grammaticalized(self, amt_grammaticalized: int):
        for row in range(self.n_rows - amt_grammaticalized, self.n_rows):
            self.table.item(row, 0).setCheckState(Qt.CheckState.Unchecked)

    def _handle_table_change(self, item: QTableWidgetItem):
        if item.column() == 0:
            self._handle_checkbox_change(item.row(), item.checkState() == Qt.CheckState.Checked)

    def _handle_checkbox_change(self, idx: int, checked: bool):
        self._update_sentence_button_highlighting()
        if checked: self._de_greyout_row(idx)
        else: self._greyout_row(idx)

    def _greyout_row(self, row: int):
        for col in range(1, self.table.columnCount()):
            self.table.item(row, col).setBackground(self.darkgrey)

    def _de_greyout_row(self, row: int):
        self.table.item(row, 1).setBackground(self.lightgrey)
        for col in range(5, self.table.columnCount()):
            self.table.item(row, col).setBackground(self.white)
        self._update_sentence_counts_gui_at_row(row)

    def _update_sentence_counts_gui(self):
        for row in range(self.n_rows):
            if self._is_idx_selected(row):
                self._update_sentence_counts_gui_at_row(row)

    def _update_sentence_counts_gui_at_row(self, row: int):
        name = self.words[row]
        s00 = self.n_sentences_per_word[name]
        s50 = self.n_sentences_per_word_50[name]
        s80 = self.n_sentences_per_word_80[name]
        self.table.item(row, 2).setText(str(s00))
        self.table.item(row, 3).setText(str(s50))
        self.table.item(row, 4).setText(str(s80))
        # used palettes but they kind of suck... like 12 colors total and role where red fits
        self.table.item(row, 2).setBackground(self.green if s00 >= self.sentences_per_word_quota else self.red)
        self.table.item(row, 3).setBackground(self.green if s50 >= self.sentences_per_word_quota else self.red)
        self.table.item(row, 4).setBackground(self.green if s80 >= self.sentences_per_word_quota else self.red)

    def _is_idx_selected(self, idx: int) -> bool:
        return self.table.item(idx, 0).checkState() == Qt.CheckState.Checked

    def _update_sentence_counts(self):
        self.n_sentences_per_word = self.sentence_repository.count_lexical_word_ocurrences(self.words)
        self.n_sentences_per_word_50 = self.sentence_repository \
            .count_lexical_word_ocurrences(self.words, min_comprehensibility=0.5)
        self.n_sentences_per_word_80 = self.sentence_repository \
            .count_lexical_word_ocurrences(self.words, min_comprehensibility=0.8)
        self._update_sentence_counts_gui()
        self._update_sentence_button_highlighting()

    def _update_sentence_button_highlighting(self):
        for idx, word in enumerate(self.words):
            if self.n_sentences_per_word[word] < self.sentences_per_word_quota \
                    and not self.did_search_sentences[word] \
                    and self._is_idx_selected(idx):
                self.button_sentences.setStyleSheet(
                    "QPushButton { background-color: palette(highlight); color: palette(highlighted-text); }"
                )
                break
        else:
            self.button_sentences.setStyleSheet("")

    def _produce_missing_sentences(self):
        words_to_process = [word for idx, word in enumerate(self.words)
                            if self._is_idx_selected(idx) and not self.did_search_sentences[word]]
        if not words_to_process: return
        with ProgressDialog("Producing sentences...", len(words_to_process)) as progress:
            for word in words_to_process:
                self.did_search_sentences[word] = True
                progress.update_progress(f"Processing word: {word}")
                self.sentence_repository.produce_up_to_limit(word)
            self._update_sentence_counts()

    def _generate_translations(self):
        words_to_process = [(idx,word) for idx, word in enumerate(self.words)
                            if self._is_idx_selected(idx)]
        if not words_to_process: return
        with ProgressDialog("Fetching translations...", len(words_to_process)) as progress:
            for i, word in words_to_process:
                text = self.table.item(i, 5).text()
                progress.update_progress(f"Processing word: {word}")
                if not text or ask_yes_no_question(f"Overwrite the following translation with an autogenerated translation?\n\n{text}"):
                    self.table.item(i, 5).setText(self.definition_fetcher.get_en_definition(word))

    def _generate_definitions(self):
        words_to_process = [(idx,word) for idx,word in enumerate(self.words)
                            if self._is_idx_selected(idx)]
        if not words_to_process: return
        with ProgressDialog("Fetching definitions...", len(words_to_process)) as progress:
            for i, word in words_to_process:
                progress.update_progress(f"Processing word: {word}")
                text = self.table.item(i, 6).text()
                if not text or ask_yes_no_question(f"Overwrite the following definition with an autogenerated definition?\n\n{text}"):
                    self.table.item(i, 6).setText(self.definition_fetcher.get_jp_definition(word))

    def _remove_unselected(self):
        words_to_remove = []
        idxs_to_remove = []
        remaining_words = []
        for idx,word in enumerate(self.words):
            if not self._is_idx_selected(idx):
                idxs_to_remove.append(idx)
                words_to_remove.append(word)
            else:
                remaining_words.append(word)

        for word in words_to_remove:
            self.n_sentences_per_word.pop(word)
            self.n_sentences_per_word_50.pop(word)
            self.n_sentences_per_word_80.pop(word)
            self.did_search_sentences.pop(word)

        for idx in idxs_to_remove[::-1]:
            self.table.removeRow(idx)

        self.words = remaining_words
        self.n_rows = len(remaining_words)

    def _check_before_continuing(self):
        if min(self.n_sentences_per_word.values()) >= self.sentences_per_word_quota\
            or ask_yes_no_question(f"Some of the selected words have a low (<{self.sentences_per_word_quota}) amount"\
                                + " of example sentences available for them. Proceed anyway?"):
            self.continuing_from.emit()
