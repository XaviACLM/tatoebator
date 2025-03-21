from typing import Dict, List

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QScrollArea, QHBoxLayout, QPushButton, QStyledItemDelegate, QPlainTextEdit, QSpacerItem, QSizePolicy
)

from .deck_select_dropdown import OutputDeckSelectionWidget
from .default_gui_elements import SpecialColors
from .gui_data_cache import GuiDataCache
from .process_dialog import ProgressDialog
from .util import ask_yes_no_question
from ..anki_interfacing import AnkiDbInterface
from ..config import SENTENCES_PER_WORD, SENTENCES_PER_CARD_BACK
from ..db import SentenceRepository
from ..language_processing import grammaticalized_words, DefinitionFetcher, Definitions


# this delegate courtesy of chatGPT
class MultiLineItemDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QPlainTextEdit(parent)
        editor.setFrameShape(QPlainTextEdit.Shape.NoFrame)
        return editor

    def setEditorData(self, editor, index):
        editor.setPlainText(index.model().data(index, Qt.ItemDataRole.DisplayRole))

    def setModelData(self, editor, model, index):
        model.setData(index, editor.toPlainText(), Qt.ItemDataRole.EditRole)


class AutoResizeTableWidget(QTableWidget):
    def __init__(self, *args, forced_resize_columns: List[int] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.setItemDelegate(MultiLineItemDelegate())

        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.original_row_height = self.rowHeight(0)
        self.forced_resize_columns = forced_resize_columns or []

        self.cellClicked.connect(self._adjust_row_height)

    def _adjust_row_height(self, row, col):
        if col in self.forced_resize_columns or self._cell_height(row, col) > self.original_row_height:
            max_height = max((self._cell_height(row, col) for col in range(self.columnCount())))
            resize_target = max(max_height, self.original_row_height + 10)
            self.setRowHeight(row, resize_target)
        else:
            self.setRowHeight(row, self.original_row_height)

        for other_row in range(self.rowCount()):
            if other_row != row:
                self.setRowHeight(other_row, self.original_row_height)

    def _cell_height(self, row, col):
        item = self.item(row, col)
        fm = QFontMetrics(item.font())
        text_rect = fm.boundingRect(self.visualItemRect(item), Qt.TextFlag.TextWordWrap, item.text())
        return text_rect.height()


class NewWordsTableWidget(QWidget):
    backing_up_from = pyqtSignal()
    continuing_from = pyqtSignal()

    sentences_per_word_quota = SENTENCES_PER_CARD_BACK
    sentences_per_word_ideally = SENTENCES_PER_WORD

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
                 definition_fetcher: DefinitionFetcher,
                 anki_db_interface: AnkiDbInterface,
                 gui_data_cache: GuiDataCache):
        super().__init__()
        self.sentence_repository = sentence_repository
        self.definition_fetcher = definition_fetcher
        self.anki_db_interface = anki_db_interface
        self.gui_data_cache = gui_data_cache

        self._n_sentences_per_word = {word: 0 for word in words}
        self._n_sentences_per_word_50 = {word: 0 for word in words}
        self._n_sentences_per_word_80 = {word: 0 for word in words}
        self._did_search_sentences = {word: False for word in words}
        self._cached_definitions = dict()

        # reorder to put grammaticalized words at the end
        # funny indexing mostly to preserve order but also to count amt_grammaticalized
        words.sort()
        amt_grammaticalized = 0
        for i in range(len(words)):
            j = i - amt_grammaticalized
            if words[j] in grammaticalized_words:
                words.append(words.pop(j))
                amt_grammaticalized += 1

        self._words = words
        self._n_rows = len(words)
        self._init_ui()

        self._uncheck_grammaticalized(amt_grammaticalized)

    def get_new_word_data(self) -> Dict[str, Definitions]:
        return {self.table.item(i, 1).text(): Definitions.from_strings(self.table.item(i, 5).text(),
                                                                       self.table.item(i, 6).text())
                for i in range(self._n_rows) if self._is_idx_selected(i)}

    def get_selected_deck_id(self) -> int:
        return self.deck_select_widget.get_selected_deck_id()

    def _init_ui(self):
        layout = QVBoxLayout()

        top_bar_layout = QHBoxLayout()

        spacer = QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.deck_select_widget = OutputDeckSelectionWidget(self.anki_db_interface,
                                                            starting_deck_id=self.gui_data_cache.last_selected_deck_id)
        top_bar_layout.addSpacerItem(spacer)
        top_bar_layout.addWidget(self.deck_select_widget)

        layout.addLayout(top_bar_layout)

        # Create the table
        self.table = AutoResizeTableWidget(self._n_rows, 7, forced_resize_columns=[5, 6])
        self.table.setHorizontalHeaderLabels(
            ['Include', 'Name', '# Sentences', '#S>50%', '#S>80%', 'Translation', 'Definition'])

        # some kinda progress bar during sentence/translation/definition search
        # possibly a link to a help menu
        # possibly a link to a sentence adder menu (we'll want to do that anyway)
        #   ->   include in database whether sentence was added by user
        # and card creation, w a lil popup telling you cards got created

        self.table.verticalHeader().setVisible(False)

        for row, name in enumerate(self._words):
            self.table.setItem(row, 0, QTableWidgetItem())
            self.table.item(row, 0).setFlags(self.table.item(row, 0).flags() | Qt.ItemFlag.ItemIsUserCheckable)
            self.table.item(row, 0).setCheckState(Qt.CheckState.Checked)

            self.table.setItem(row, 1, QTableWidgetItem(name))
            self.table.item(row, 1).setFlags(self.table.item(row, 0).flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.item(row, 1).setBackground(SpecialColors.extra_light_grey)
            self.table.item(row, 1).setForeground(SpecialColors.black)

            self.table.setItem(row, 2, QTableWidgetItem(""))
            self.table.item(row, 2).setFlags(self.table.item(row, 1).flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.item(row, 2).setForeground(SpecialColors.black)

            self.table.setItem(row, 3, QTableWidgetItem(""))
            self.table.item(row, 3).setFlags(self.table.item(row, 2).flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.item(row, 3).setForeground(SpecialColors.black)

            self.table.setItem(row, 4, QTableWidgetItem(""))
            self.table.item(row, 4).setFlags(self.table.item(row, 3).flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.item(row, 4).setForeground(SpecialColors.black)

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
        self.button_translations = QPushButton("Fill empty translations")
        self.button_translations.clicked.connect(self._generate_translations)
        self.button_definitions = QPushButton("Fill empty definitions")
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
        self.button_back.clicked.connect(self._on_go_back_clicked)
        self.button_continue.clicked.connect(self._check_before_continuing)
        self.table.itemChanged.connect(self._handle_table_change)

        layout.addLayout(buttons_bar)

        self.setLayout(layout)

        self._update_sentence_counts()

    def _on_go_back_clicked(self):
        self.gui_data_cache.last_selected_deck_id = self.get_selected_deck_id()
        self.backing_up_from.emit()

    def _uncheck_grammaticalized(self, amt_grammaticalized: int):
        for row in range(self._n_rows - amt_grammaticalized, self._n_rows):
            self.table.item(row, 0).setCheckState(Qt.CheckState.Unchecked)

    def _handle_table_change(self, item: QTableWidgetItem):
        if item.column() == 0:
            self._handle_checkbox_change(item.row(), item.checkState() == Qt.CheckState.Checked)
        # from aqt.utils import showInfo
        # showInfo(f"updated item at col/row {item.column()}/{item.row()}")

    def _handle_checkbox_change(self, idx: int, checked: bool):
        self._update_sentence_button_highlighting()
        if checked:
            self._de_greyout_row(idx)
        else:
            self._greyout_row(idx)

    def _greyout_row(self, row: int):
        for col in range(1, self.table.columnCount()):
            self.table.item(row, col).setBackground(SpecialColors.dark_grey)

    def _de_greyout_row(self, row: int):
        self.table.item(row, 1).setBackground(SpecialColors.extra_light_grey)
        for col in range(5, self.table.columnCount()):
            self.table.item(row, col).setBackground(SpecialColors.white)
        self._update_sentence_counts_gui_at_row(row)

    def _update_sentence_counts_gui(self):
        for row in range(self._n_rows):
            if self._is_idx_selected(row):
                self._update_sentence_counts_gui_at_row(row)

    def _update_sentence_counts_gui_at_row(self, row: int):
        name = self._words[row]
        s00 = self._n_sentences_per_word[name]
        s50 = self._n_sentences_per_word_50[name]
        s80 = self._n_sentences_per_word_80[name]
        self.table.item(row, 2).setText(str(s00))
        self.table.item(row, 3).setText(str(s50))
        self.table.item(row, 4).setText(str(s80))
        # used palettes but they kind of suck... like 12 colors total and no role where red fits
        self.table.item(row, 2).setBackground(SpecialColors.light_green if s00 >= self.sentences_per_word_quota
                                              else SpecialColors.light_red)
        self.table.item(row, 3).setBackground(SpecialColors.light_green if s50 >= self.sentences_per_word_quota
                                              else SpecialColors.light_red)
        self.table.item(row, 4).setBackground(SpecialColors.light_green if s80 >= self.sentences_per_word_quota
                                              else SpecialColors.light_red)

    def _is_idx_selected(self, idx: int) -> bool:
        return self.table.item(idx, 0).checkState() == Qt.CheckState.Checked

    def _update_sentence_counts(self):
        self._n_sentences_per_word = self.sentence_repository.count_lexical_word_ocurrences(self._words)
        self._n_sentences_per_word_50 = self.sentence_repository \
            .count_lexical_word_ocurrences(self._words, min_comprehensibility=0.5)
        self._n_sentences_per_word_80 = self.sentence_repository \
            .count_lexical_word_ocurrences(self._words, min_comprehensibility=0.8)
        self._update_sentence_counts_gui()
        self._update_sentence_button_highlighting()

    def _update_sentence_button_highlighting(self):
        for idx, word in enumerate(self._words):
            if self._n_sentences_per_word[word] < self.sentences_per_word_quota \
                    and not self._did_search_sentences[word] \
                    and self._is_idx_selected(idx):
                self.button_sentences.setStyleSheet(
                    "QPushButton { background-color: palette(highlight); color: palette(highlighted-text); }"
                )
                break
        else:
            self.button_sentences.setStyleSheet("")

    def _produce_missing_sentences(self):
        words_to_process = [word for idx, word in enumerate(self._words)
                            if self._is_idx_selected(idx) and not self._did_search_sentences[word]]
        if not words_to_process: return
        with ProgressDialog("Producing sentences...", 100) as progress:

            def progress_callback(aspm_name, search_ratio):
                progress.update_progress(f"Scanning {aspm_name}...", int(search_ratio * 100))

            self.sentence_repository.produce_sentences_for_words({word: self.sentences_per_word_ideally
                                                                  for word in words_to_process},
                                                                 progress_callback=progress_callback)
            for word in words_to_process:
                self._did_search_sentences[word] = True
            self._update_sentence_counts()

    def _generate_translations(self):
        words_to_process = [(idx, word) for idx, word in enumerate(self._words)
                            if self._is_idx_selected(idx)]
        if not words_to_process: return
        with ProgressDialog("Fetching translations...", len(words_to_process)) as progress:
            for i, word in words_to_process:
                text = self.table.item(i, 5).text()
                if text: continue
                progress.update_progress(f"Processing word: {word}")
                self.table.item(i, 5).setText(self._get_translation(word))

    def _generate_definitions(self):
        words_to_process = [(idx, word) for idx, word in enumerate(self._words)
                            if self._is_idx_selected(idx)]
        if not words_to_process: return
        with ProgressDialog("Fetching definitions...", len(words_to_process)) as progress:
            for i, word in words_to_process:
                text = self.table.item(i, 6).text()
                if text: continue
                progress.update_progress(f"Processing word: {word}")
                self.table.item(i, 6).setText(self._get_definition(word))

    def _get_translation(self, word):
        if word not in self._cached_definitions:
            definitions = self.definition_fetcher.get_definitions(word)
            self._cached_definitions[word] = definitions
        return self._cached_definitions[word].en_as_str

    def _get_definition(self, word):
        if word not in self._cached_definitions:
            definitions = self.definition_fetcher.get_definitions(word)
            self._cached_definitions[word] = definitions
        return self._cached_definitions[word].jp_as_str

    def _remove_unselected(self):
        words_to_remove = []
        idxs_to_remove = []
        remaining_words = []
        for idx, word in enumerate(self._words):
            if not self._is_idx_selected(idx):
                idxs_to_remove.append(idx)
                words_to_remove.append(word)
            else:
                remaining_words.append(word)

        for word in words_to_remove:
            self._n_sentences_per_word.pop(word)
            self._n_sentences_per_word_50.pop(word)
            self._n_sentences_per_word_80.pop(word)
            self._did_search_sentences.pop(word)

        for idx in idxs_to_remove[::-1]:
            self.table.removeRow(idx)

        self._words = remaining_words
        self._n_rows = len(remaining_words)

    def _check_before_continuing(self):
        if min(self._n_sentences_per_word.values()) >= self.sentences_per_word_quota \
                or ask_yes_no_question("Some of the selected words have a low (<{self.sentences_per_word_quota}) amount"
                                       " of example sentences available for them. Proceed anyway?"):
            self.gui_data_cache.last_selected_deck_id = self.get_selected_deck_id()
            self.continuing_from.emit()
