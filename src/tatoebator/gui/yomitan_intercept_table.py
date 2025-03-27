import re
from typing import List, Dict, Optional, Callable

from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRectF
from PyQt6.QtGui import QFontMetrics, QPainter, QTextDocument
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QSpacerItem, QSizePolicy, QTableWidget, QTableWidgetItem, \
    QPushButton, QWidget, QHeaderView, QAbstractItemView, QStyledItemDelegate
from anki import hooks
from anki.collection import Collection
from anki.decks import DeckId
from anki.notes import Note
from bs4 import BeautifulSoup

from .default_gui_elements import Colors, SpecialColors
from .toggle_switch import QToggle
from .util import ask_yes_no_question
from ..anki_interfacing import TatoebatorFields, AnkiDbInterface
from ..config import SENTENCES_PER_CARD_BACK, SENTENCES_PER_WORD
from ..constants import INTER_FIELD_SEPARATOR
from ..db import SentenceRepository
from ..util import subclass_must_define_attributes


# this delegate courtesy of chatgpt
class HTMLDelegate(QStyledItemDelegate):
    """Delegate to render HTML in QTableWidget cells while respecting boundaries."""

    def paint(self, painter: QPainter, option, index):
        """Custom paint method to render HTML correctly and prevent overflow."""
        painter.save()

        doc = QTextDocument()
        doc.setHtml(index.data(Qt.ItemDataRole.DisplayRole))  # Get cell text as HTML

        # Set the document width to match the column width
        doc.setTextWidth(option.rect.width())

        # Ensure text does not overflow outside the cell
        painter.setClipRect(option.rect)  # Clip drawing to the cell's boundaries
        painter.translate(option.rect.topLeft())  # Position the text correctly
        doc.drawContents(painter, QRectF(0, 0, option.rect.width(), option.rect.height()))

        painter.restore()

    def sizeHint(self, option, index):
        """Return the correct size of the cell based on HTML content."""
        doc = QTextDocument()
        doc.setHtml(index.data(Qt.ItemDataRole.DisplayRole))
        doc.setTextWidth(option.rect.width())  # Match column width

        # Ensure the height does not exceed available space
        ideal_height = doc.size().height()
        return QSize(doc.idealWidth(), ideal_height)


class AutoResizeTableWidget(QTableWidget):
    def __init__(self, *args, forced_resize_columns: List[int] = None, default_row_height: int = 30, **kwargs):
        super().__init__(*args, **kwargs)

        self._default_row_height = default_row_height
        self._forced_resize_columns = forced_resize_columns or list(range(self.columnCount()))

        self.cellClicked.connect(self._adjust_row_height)

    def _adjust_row_height(self, row, col):
        if col in self._forced_resize_columns:
            max_height = max((self._cell_height(row, col) for col in self._forced_resize_columns))
            resize_target = max(self._default_row_height, max_height + self._default_row_height // 2)
            self.setRowHeight(row, resize_target)
        else:
            self.setRowHeight(row, self._default_row_height)

        for other_row in range(self.rowCount()):
            if other_row != row:
                self.setRowHeight(other_row, self._default_row_height)

    def _cell_height(self, row, col):
        item = self.item(row, col)
        if item is None: return self._default_row_height
        fm = QFontMetrics(item.font())
        text_rect = fm.boundingRect(self.visualItemRect(item), Qt.TextFlag.TextWordWrap, item.text())
        return text_rect.height()

    def _cell_height(self, row, col):
        item = self.item(row, col)
        if not item: return self._default_row_height
        text = item.text()
        doc = QTextDocument()
        doc.setHtml(text)
        doc.setDefaultFont(item.font())
        return doc.size().height()


@subclass_must_define_attributes(['_control_row_name'])
class WordTableWidget(AutoResizeTableWidget):
    sentence_search_required_change = pyqtSignal(bool)
    found_new_sentences_for_word = pyqtSignal(str)
    word_selected_definition_changed = pyqtSignal(object)  # (word, selected_definition)

    table_height = 500
    _n_cols = 7

    _control_row_name: str

    # 0 control
    # 1 name
    # 2 n sentences
    # 3 n sentences w c>50
    # 4 c>80
    # 5 definition
    # 6 manage definitions button

    _sentences_per_word_quota = SENTENCES_PER_CARD_BACK
    _sentences_per_word_ideally = SENTENCES_PER_WORD

    def __init__(self,
                 starting_words: List[str],
                 definitions: Dict[str, List[str]],
                 selected_definition_idxs: Dict[str, Optional[int]],
                 sentence_repository: SentenceRepository):
        self.sentence_repository = sentence_repository

        self._words = starting_words
        self._definitions = definitions
        self._selected_definition_idxs = selected_definition_idxs
        super().__init__(self._n_words, self._n_cols, forced_resize_columns=[5, 6]) # 6 is also autoresize

        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        self._last_sentence_search_required_value = None

        self._did_search_sentences = {word: False for word in starting_words}
        self._update_sentence_counts()

        self._init_ui()

        self._maybe_signal_sentence_search_required_change()

    def add_word(self, word: str, definitions: List[str], selected_definition_idx: int, at_index=0):
        row_idx = at_index if at_index >= 0 else self._n_words + 1 - at_index

        self._words = self._words[:row_idx] + [word] + self._words[row_idx:]
        self._did_search_sentences[word] = False
        self._add_new_word_to_sentence_counts(word)
        self._definitions[word] = definitions
        self._selected_definition_idxs[word] = selected_definition_idx

        self.insertRow(row_idx)

        self._init_ui_row(row_idx)

    # todo getter functions for finishing up

    def search_sentences_then_update_counts_and_gui(self,
                                                    progress_callback: Optional[Callable[..., None]] = None):
        self._produce_missing_sentences(progress_callback=progress_callback)
        self.update_sentence_counts_and_gui()

    def update_sentence_counts_and_gui(self):
        self._update_sentence_counts()
        self._update_sentence_counts_gui()

    def is_quota_satisfied(self) -> bool:
        return min(self._n_sentences_per_word.values()) >= self._sentences_per_word_quota

    def _is_idx_selected(self, idx: int) -> bool:
        raise NotImplementedError

    def _init_ui_control_column_at_row(self, idx: int):
        raise NotImplementedError

    def _init_ui(self):
        self.setMinimumHeight(self.table_height)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.verticalHeader().setVisible(False)
        self.setHorizontalHeaderLabels(
            [self._control_row_name, 'Word', '# Sentences', '#S>50%', '#S>80%', 'Definition', '']
        )

        for i in range(self._n_cols):
            self.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        for row_idx in range(self._n_words):
            self._init_ui_row(row_idx)

        self.setItemDelegateForColumn(5, HTMLDelegate())

    def _produce_missing_sentences(self, progress_callback: Optional[Callable[..., None]]):
        words_to_process = [word for idx, word in enumerate(self._words)
                            if self._is_idx_selected(idx) and not self._did_search_sentences[word]]
        if not words_to_process: return
        self.sentence_repository.produce_sentences_for_words({word: self._sentences_per_word_ideally
                                                              for word in words_to_process},
                                                             progress_callback=progress_callback)
        for word in words_to_process:
            self.found_new_sentences_for_word.emit(word)
            self._did_search_sentences[word] = True

    def _maybe_signal_sentence_search_required_change(self):
        last_val = self._last_sentence_search_required_value
        new_val = self._does_any_selected_word_require_sentence_search()
        if new_val is not last_val:
            self._last_sentence_search_required_value = new_val
            self.sentence_search_required_change.emit(new_val)

    def _does_any_selected_word_require_sentence_search(self) -> bool:
        for idx, word in enumerate(self._words):
            if self._n_sentences_per_word[word] < self._sentences_per_word_quota \
                    and not self._did_search_sentences[word] \
                    and self._is_idx_selected(idx):
                return True
        return False

    def _init_ui_row(self, row_idx: int):
        self._init_ui_row_noninteractive_cells(row_idx)

        word = self._words[row_idx]
        self.item(row_idx, 1).setText(word)
        self._update_sentence_counts_gui_at_row(row_idx)
        self._update_definition_at_row(row_idx)

        self._init_ui_control_column_at_row(row_idx)
        self._init_ui_definitions_button_at_row(row_idx)

    def _init_ui_definitions_button_at_row(self, row_idx: int):
        button = QPushButton("Manage definitions")
        self.setCellWidget(row_idx, 6, button)
        word = self._words[row_idx]

        def cycle_definition():
            if not self._definitions[word]:
                return
            self._selected_definition_idxs[word] = (
                    (self._selected_definition_idxs[word] + 1) % len(self._definitions[word])
            )
            self._update_definition_at_row(row_idx)
            self.word_selected_definition_changed.emit((word, self._get_definition(word)))

        button.clicked.connect(cycle_definition)

    def _update_definition_at_row(self, row_idx: int):
        self.item(row_idx, 5).setText(self._get_definition(self._words[row_idx]) or "")

    @property
    def _n_words(self) -> int:
        return len(self._words)

    def _get_definition(self, word: str) -> Optional[str]:
        idx = self._selected_definition_idxs[word]
        if idx is None: return None
        return self._definitions[word][idx]

    def _init_ui_row_noninteractive_cells(self, row_idx: int):
        for col_idx in range(1, 6):
            self.setItem(row_idx, col_idx, QTableWidgetItem(""))
            self.item(row_idx, col_idx).setFlags(self.item(row_idx, col_idx).flags()
                                                 & ~Qt.ItemFlag.ItemIsEditable)
            self.item(row_idx, col_idx).setForeground(SpecialColors.black)

        self.item(row_idx, 1).setBackground(SpecialColors.extra_light_grey)

    def _remove_word_at_idx(self, idx: int):
        word = self._words.pop(idx)
        self._did_search_sentences.pop(word)
        self._n_sentences_per_word.pop(word)
        self._n_sentences_per_word_50.pop(word)
        self._n_sentences_per_word_80.pop(word)
        self._definitions.pop(word)
        self._selected_definition_idxs.pop(word)
        self.removeRow(idx)

    def _greyout_row(self, row: int):
        for col in range(1, self._n_cols):
            self.item(row, col).setBackground(SpecialColors.dark_grey)

    def _de_greyout_row(self, row: int):
        self.item(row, 1).setBackground(SpecialColors.extra_light_grey)
        for col in range(5, self._n_cols):
            self.item(row, col).setBackground(SpecialColors.white)
        self._update_sentence_counts_gui_at_row(row)

    def _update_sentence_counts_gui(self):
        for row in range(self._n_words):
            if self._is_idx_selected(row):
                self._update_sentence_counts_gui_at_row(row)

    def _update_sentence_counts_gui_at_row(self, row: int):
        name = self._words[row]
        s00 = self._n_sentences_per_word[name]
        s50 = self._n_sentences_per_word_50[name]
        s80 = self._n_sentences_per_word_80[name]
        self.item(row, 2).setText(str(s00))
        self.item(row, 3).setText(str(s50))
        self.item(row, 4).setText(str(s80))
        self.item(row, 2).setBackground(SpecialColors.light_green if s00 >= self._sentences_per_word_quota
                                        else SpecialColors.light_red)
        self.item(row, 3).setBackground(SpecialColors.light_green if s50 >= self._sentences_per_word_quota
                                        else SpecialColors.light_red)
        self.item(row, 4).setBackground(SpecialColors.light_green if s80 >= self._sentences_per_word_quota
                                        else SpecialColors.light_red)

    def _update_sentence_counts(self):
        self._n_sentences_per_word = self.sentence_repository.count_lexical_word_ocurrences(self._words)
        self._n_sentences_per_word_50 = self.sentence_repository \
            .count_lexical_word_ocurrences(self._words, min_comprehensibility=0.5)
        self._n_sentences_per_word_80 = self.sentence_repository \
            .count_lexical_word_ocurrences(self._words, min_comprehensibility=0.8)
        self._maybe_signal_sentence_search_required_change()

    def _add_new_word_to_sentence_counts(self, word: str):
        self._n_sentences_per_word.update(self.sentence_repository.count_lexical_word_ocurrences([word]))
        self._n_sentences_per_word_50.update(self.sentence_repository \
                                             .count_lexical_word_ocurrences([word], min_comprehensibility=0.5))
        self._n_sentences_per_word_80.update(self.sentence_repository \
                                             .count_lexical_word_ocurrences([word], min_comprehensibility=0.8))
        self._maybe_signal_sentence_search_required_change()


class MinedWordsTableWidget(WordTableWidget):
    _control_row_name = "Include"

    def __init__(self,
                 starting_selected_words: List[str],
                 starting_unselected_words: List[str],
                 sentence_repository: SentenceRepository):

        starting_words = starting_selected_words + starting_unselected_words
        self._n_starting_selected_words = len(starting_selected_words)
        super().__init__(starting_words,
                         {word: [] for word in starting_words},
                         {word: None for word in starting_words},
                         sentence_repository)
        self.itemChanged.connect(self._handle_table_change)

    def _is_idx_selected(self, idx: int) -> bool:
        return self.item(idx, 0).checkState() == Qt.CheckState.Checked

    def _init_ui_control_column_at_row(self, row_idx: int):
        self.setItem(row_idx, 0, QTableWidgetItem())
        self.item(row_idx, 0).setFlags(self.item(row_idx, 0).flags() | Qt.ItemFlag.ItemIsUserCheckable)
        self.item(row_idx, 0).setCheckState(Qt.CheckState.Checked if row_idx < self._n_starting_selected_words
                                            else Qt.CheckState.Unchecked)

    def _handle_table_change(self, item: QTableWidgetItem):
        if item.column() == 0:
            self._handle_checkbox_change(item.row(), item.checkState() == Qt.CheckState.Checked)

    def _handle_checkbox_change(self, idx: int, checked: bool):
        self._maybe_signal_sentence_search_required_change()
        if checked:
            self._de_greyout_row(idx)
        else:
            self._greyout_row(idx)


class WordsFromCollectionTableWidget(WordTableWidget):
    _control_row_name = ""

    word_deleted = pyqtSignal(str)

    @classmethod
    def empty(cls, sentence_repository: SentenceRepository):
        return cls([], dict(), dict(), sentence_repository)

    def _is_idx_selected(self, idx: int) -> bool:
        return True

    def _init_ui_control_column_at_row(self, row_idx: int):
        button = QPushButton("Delete")
        self.setCellWidget(row_idx, 0, button)

        word = self._words[row_idx]

        def delete_word():
            latest_idx = self._words.index(word)
            self._remove_word_at_idx(latest_idx)
            self.word_deleted.emit(word)

        button.clicked.connect(delete_word)


# todo
#  removing data-sc-content="example-sentence" from definitions
#  undo would be nice

# todo probably go back to the expanding table idea to show definition decently
# todo a "going to this or that deck" label on top, oppposite side of intercept toggle

# todo: card says it is for shin (furigana and audio both are shin, both are from yomitan), but example stcs use kokoro
#  i think this might be quite painful, actually. can it be fixed?
#  it's not impossible in the mecab setting, because mecab does provide a reading. will need yet another rework of the search though
#  but also we need to be able to combine this with a search that can still work, albeit possibly worse, for oov words

# todo gui progress callback

class YomichanInterceptTable(QWidget):
    backing_up_from = pyqtSignal()
    continuing_from = pyqtSignal()

    def __init__(self,
                 sentence_repository: SentenceRepository,
                 anki_db_interface: AnkiDbInterface):
        super().__init__()

        self.sentence_repository = sentence_repository
        self.anki_db_interface = anki_db_interface

        self._intercept_enabled = True
        self._notes_by_word: Dict[str, Note] = dict()

        self._init_ui()

        hooks.note_will_be_added.append(self._note_created_callback)

    def _init_ui(self):
        layout = QVBoxLayout()

        top_layout = QHBoxLayout()

        self.intercept_toggle = QToggle()
        self.intercept_toggle.setText('Yomitan note creation intercept enabled')
        self.intercept_toggle.setFixedHeight(24)
        self.intercept_toggle.setStyleSheet(f"QToggle{{"
                                            f"qproperty-bg_color:{Colors.emph_bg.name()};"
                                            f"qproperty-circle_color:{Colors.std_bg.name()};"
                                            f"qproperty-active_color:{Colors.tatoebator_blue.name()};"
                                            f"qproperty-disabled_color:{Colors.emph_bg.name()};}}")
        # f"qproperty-text_color:#A0F;}")
        self.intercept_toggle.setChecked(self._intercept_enabled)
        self.intercept_toggle.stateChanged.connect(self._update_intercept_enabled)

        spacer = QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        top_layout.addWidget(self.intercept_toggle)
        top_layout.addSpacerItem(spacer)

        # todo yomichan is sending these cards to <deck>, override button, deck selector

        layout.addLayout(top_layout)

        self.table = WordsFromCollectionTableWidget.empty(self.sentence_repository)
        self.table.word_deleted.connect(self._delete_note_by_word)
        self.table.sentence_search_required_change.connect(self._update_button_sentences)
        self.table.found_new_sentences_for_word.connect(self._update_sentences_for_note_by_word)
        self.table.word_selected_definition_changed.connect(self._update_selected_definition_for_note_by_word)

        layout.addWidget(self.table)

        bottom_layout = QHBoxLayout()

        self.button_back = QPushButton('Go back')
        self.button_sentences = QPushButton('Produce missing sentences')
        self.button_continue = QPushButton('Create cards')

        # todo delete all sentences if exiting backwards? maybe ask?
        #  can do this with an onClose. set some flag so it doesn't get triggered on continue
        self.button_back.clicked.connect(self.backing_up_from.emit)
        self.button_sentences.clicked.connect(self.table.search_sentences_then_update_counts_and_gui)
        self.button_continue.clicked.connect(self._check_before_continuing)

        bottom_layout.addWidget(self.button_back)
        bottom_layout.addWidget(self.button_sentences)
        bottom_layout.addWidget(self.button_continue)

        layout.addLayout(bottom_layout)

        self.setLayout(layout)

    def _note_created_callback(self, col: Collection, note: Note, deck_id: DeckId):
        try:
            self._note_created_callback_2(col, note, deck_id)
        except:
            import traceback
            print(traceback.format_exc())
            raise Exception("hmhmmgmmh")

    def _note_created_callback_2(self, col: Collection, note: Note, deck_id: DeckId):
        if not self._intercept_enabled:
            return

        # todo there's a lot of stuff here that isn't even that related to this class
        #  maybe there should be some kind of yomichan_note_intake/interception_manager
        #  manager bad word. seems like a good opportunity to pick a nice name - this class acts as a sort of gatekeeper
        #  that's a bad name, but something along those lines

        word_field_ord = TatoebatorFields.index(TatoebatorFields.WORD)
        word = note.fields[word_field_ord]
        # unsure why this is necessary, but data from yomitan often arrives with extra newlines at the end
        word = word.strip()
        note.fields[word_field_ord] = word

        all_definitions_data = note.fields[TatoebatorFields.index(TatoebatorFields.ALL_DEFINITIONS)]
        all_definitions_data = all_definitions_data.strip()  # again random trailing newlines/spaces
        soup = BeautifulSoup(all_definitions_data, 'html.parser').find()
        assert soup.name == 'div' and soup['class'] == ['yomitan-glossary']
        # todo will have to see that this works for yomichan, too
        ol_elem, = soup.children
        assert ol_elem.name == 'ol'
        all_definitions = [f"<ol>{item}</ol>" for item in ol_elem.children]
        note.fields[TatoebatorFields.index(TatoebatorFields.ALL_DEFINITIONS)] = "".join(all_definitions)

        # remove sound tag from audio
        audio = note.fields[TatoebatorFields.index(TatoebatorFields.WORD_AUDIO)].strip()
        if audio:
            audio, = re.fullmatch(r"\[sound:(.+?)]", audio).groups()
            note.fields[TatoebatorFields.index(TatoebatorFields.WORD_AUDIO)] = audio

        self.table.add_word(word, all_definitions, 0)
        self._notes_by_word[word] = note

        # todo ehh might have to do some work in seeing how much the above has to be adapted (if at all) for absent defs
        self._update_selected_definition_for_note_by_word((word, all_definitions[0] if all_definitions else ""))
        self._update_sentences_for_note_by_word(word)

    def _update_selected_definition_for_note_by_word(self, args):
        word, selected_definition = args
        note = self._notes_by_word[word]
        note.fields[TatoebatorFields.index(TatoebatorFields.DEFINITION_EN)] = selected_definition

    def _update_sentences_for_note_by_word(self, word: str):
        note = self._notes_by_word[word]
        sentences = self.sentence_repository.produce_sentences_for_word(word, SENTENCES_PER_WORD,
                                                                        produce_new=False,
                                                                        ensure_audio=True,
                                                                        with_furigana=True)

        # repeated code with card creator
        sentence_data = INTER_FIELD_SEPARATOR.join(
            (INTER_FIELD_SEPARATOR.join(
                [sentence.sentence, sentence.furigana, sentence.translation, sentence.audio_file_ref, sentence.credit]
            )
                for sentence in sentences)
        )

        # todo something here doesn't work right when this is called from the signal
        #  cards all had 0-4 sentences
        #  whereas after deleting the notes and re-intercepting their re-creation (while sentences were still in db)
        #  now the sentences were correctly input in the notes. but how does that make sense? this is the same function
        #  and also the sentences were very complicated and long, too
        note.fields[TatoebatorFields.index(TatoebatorFields.SENTENCE_DATA)] = sentence_data

    def _check_before_continuing(self):
        if self.table.is_quota_satisfied() or ask_yes_no_question(
                "Some of the selected words have a low (<{self.sentences_per_word_quota}) amount"
                " of example sentences available for them. Proceed anyway?"
        ):
            self.continuing_from.emit()

    def _update_button_sentences(self, search_required: bool):
        if search_required:
            self.button_sentences.setStyleSheet("QPushButton {"
                                                f"background-color:{Colors.highlight_blue.name()};"
                                                f"color:{SpecialColors.white.name()};"
                                                "}")
        else:
            self.button_sentences.setStyleSheet("")

    def _update_intercept_enabled(self, state: bool):
        # old function. see https://doc.qt.io/qt-6/qcheckbox.html
        self._intercept_enabled = state == 2  # Qt.CheckState.Checked
        print(self._intercept_enabled)

    def _delete_note_by_word(self, word: str):
        id_ = self._notes_by_word.pop(word).id
        self.anki_db_interface.remove_notes_by_ids([id_])
