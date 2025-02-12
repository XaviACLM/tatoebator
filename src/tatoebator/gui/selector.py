from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor, QTextCharFormat, QColor, QTextOption
from PyQt6.QtWidgets import QLabel, QTextEdit, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QSpacerItem, QSizePolicy

from ..language_processing import group_text_by_learnability, WordLearnableType
from .word_table import NewWordsTableWidget


class QSelectableTextEdit(QTextEdit):
    state_changed = pyqtSignal()

    def __init__(self, parent=None, all_selected=False):
        super().__init__(parent)
        self.num_words = 0
        self.num_highlighted_words = 0
        self.setReadOnly(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setStyleSheet("background-color: transparent; font-size: 20px;")
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self.words = []
        self.word_states = {}
        self.all_selected = all_selected

    def set_words(self, word_list):
        """Sets the list of words, overwriting existing ones."""
        self.words = word_list
        self.num_words = len(word_list)
        self.num_highlighted_words = self.num_words if self.all_selected else 0
        self.word_states = {word: self.all_selected for word in self.words}  # Track highlighted state
        self._update_text()

    def get_selected_words(self):
        return [word for word, val in self.word_states.items() if val]

    def _update_text(self):
        """Update the text with current words and states."""
        self.clear()
        cursor = self.textCursor()

        normal_fmt = QTextCharFormat()
        highlight_fmt = QTextCharFormat()
        highlight_fmt.setBackground(QColor("black"))
        highlight_fmt.setForeground(QColor("white"))

        for word in self.words:
            fmt = QTextCharFormat()
            if self.word_states[word]:
                cursor.insertText(word, highlight_fmt)
            else:
                cursor.insertText(word, normal_fmt)
            cursor.insertText(" " * 3, normal_fmt)

    def mousePressEvent(self, event):
        """Toggle highlighting when a word is clicked."""
        cursor = self.cursorForPosition(event.pos())
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        word = cursor.selectedText()
        if word and word in self.word_states:
            word_state = self.word_states[word]
            self.word_states[word] = not word_state
            self.num_highlighted_words += -1 if word_state else +1
            self._update_text()
            self.state_changed.emit()

    def select_all(self):
        self.word_states = {word: True for word in self.words}
        self._update_text()
        self.num_highlighted_words = self.num_words
        self.state_changed.emit()

    def deselect_all(self):
        self.word_states = {word: False for word in self.words}
        self._update_text()
        self.num_highlighted_words = 0
        self.state_changed.emit()

    def flip_selection(self):
        self.word_states = {word: not state for word, state in self.word_states.items()}
        self._update_text()
        self.num_highlighted_words = self.num_words - self.num_highlighted_words
        self.state_changed.emit()


class QWordDisplay(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title_label = QLabel()
        self.title_label.setFont(QFont("Arial", weight=QFont.Weight.Bold))
        self.title = title
        self.title_label.setText(self.title)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("background-color: transparent; font-size: 20px;")
        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.text_edit.setWordWrapMode(QTextOption.WrapMode.WordWrap)

        self.layout = QVBoxLayout()
        self.header_layout = QHBoxLayout()
        self.header_layout.addWidget(self.title_label)
        self.layout.insertLayout(0, self.header_layout)
        self.layout.addWidget(self.text_edit)
        self.setLayout(self.layout)

    def _update_title(self, extra_info=None):
        if extra_info is None:
            self.title_label.setText(f"{self.title}")
        else:
            self.title_label.setText(f"{self.title} ({extra_info})")

    def set_words(self, word_list):
        self.text_edit.setPlainText((" " * 3).join(word_list))
        self._update_title(len(word_list))


class QSelectableWordDisplay(QWordDisplay):
    def __init__(self, title, all_selected=False, parent=None):
        super().__init__(title, parent)

        # Replace the text_edit with QSelectableTextEdit
        self.layout.removeWidget(self.text_edit)
        self.text_edit.deleteLater()
        self.text_edit = QSelectableTextEdit(all_selected=all_selected)
        self.layout.addWidget(self.text_edit)
        self.text_edit.state_changed.connect(self._update_highlight_count)

        # Add buttons for select all, deselect all, flip selection
        self.button_layout = QHBoxLayout()

        self.select_all_button = QPushButton()
        self.select_all_button.setText("All")
        self.select_all_button.clicked.connect(self.text_edit.select_all)

        self.deselect_all_button = QPushButton()
        self.deselect_all_button.setText("None")
        self.deselect_all_button.clicked.connect(self.text_edit.deselect_all)

        self.flip_selection_button = QPushButton()
        self.flip_selection_button.setText("Flip")
        self.flip_selection_button.clicked.connect(self.text_edit.flip_selection)

        self.button_layout.addWidget(self.select_all_button)
        self.button_layout.addWidget(self.deselect_all_button)
        self.button_layout.addWidget(self.flip_selection_button)

        self.header_layout.insertLayout(1, self.button_layout)  # Add button layout below the title

        self.all_selected = all_selected

    def _update_highlight_count(self):
        self._update_title(f" {self.text_edit.num_highlighted_words} / {self.text_edit.num_words} ")

    def set_words(self, word_list):
        self.text_edit.set_words(word_list)
        self._update_highlight_count()

    def get_selected_words(self):
        return self.text_edit.get_selected_words()

    def mousePressEvent(self, event):
        self.text_edit.mousePressEvent(event)
        self._update_title()


class MineNewWordsWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        main_layout = QHBoxLayout()

        left_column = QVBoxLayout()

        label = QLabel('Text to be mined:')
        left_column.addWidget(label)

        self.text_edit = QTextEdit()
        left_column.addWidget(self.text_edit)

        main_layout.addLayout(left_column)

        mid_column = QVBoxLayout()
        self.mine_button = QPushButton('--->')
        self.mine_button.clicked.connect(self.mine_into_boxes)
        mid_column.addWidget(self.mine_button)
        main_layout.addLayout(mid_column)

        right_column = QVBoxLayout()
        boxes = QHBoxLayout()
        boxes_left = QVBoxLayout()
        boxes_right = QVBoxLayout()

        self.word_displays = {WordLearnableType.NEW_WORD: QSelectableWordDisplay("New words", all_selected=True),
                              WordLearnableType.IN_LIBRARY_PENDING: QWordDisplay("In library (upcoming)"),
                              WordLearnableType.IN_LIBRARY_KNOWN: QWordDisplay("In library (known)"),
                              WordLearnableType.PROPER_NOUN_NONPERSON: QWordDisplay("Proper (non-person) nouns"),
                              WordLearnableType.GRAMMATICAL_WORD: QWordDisplay("Grammatical particles"),
                              WordLearnableType.NOT_IN_DICTIONARY: QWordDisplay("Not in dictionary")
                              }

        # Create the first text element
        boxes_left.addWidget(self.word_displays[WordLearnableType.NEW_WORD])
        boxes_left.addWidget(self.word_displays[WordLearnableType.IN_LIBRARY_PENDING])
        boxes_left.addWidget(self.word_displays[WordLearnableType.IN_LIBRARY_KNOWN])

        boxes_right.addWidget(self.word_displays[WordLearnableType.PROPER_NOUN_NONPERSON])
        boxes_right.addWidget(self.word_displays[WordLearnableType.GRAMMATICAL_WORD])
        boxes_right.addWidget(self.word_displays[WordLearnableType.NOT_IN_DICTIONARY])

        boxes.addLayout(boxes_left)
        boxes.addLayout(boxes_right)

        right_column.addLayout(boxes)

        spacer = QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.continue_button = QPushButton('Add selected new words to deck')
        self.continue_button.clicked.connect(self.continue_to_card_creation)

        hbox = QHBoxLayout()
        hbox.addSpacerItem(spacer)
        hbox.addWidget(self.continue_button)

        right_column.addLayout(hbox)

        # Add the right column layout to the main layout
        main_layout.addLayout(right_column)

        main_layout.setStretch(0, 1)  # left stretches a bit
        main_layout.setStretch(1, 0)  # mid nothing
        main_layout.setStretch(2, 2)  # right double

        # Set the layout to the QWidget
        self.setLayout(main_layout)

        # Set window title and size
        self.setWindowTitle('Mine New Words')
        self.setGeometry(100, 100, 1400, 800)

    def mine_into_boxes(self):
        # fairly serious problem
        # i request through the table creation of sentences for tosho
        # a bunch for toshokan get through
        # but the table seems to believe we only got 3 sentences
        # only possible explanation is that kanshudo or tangorin gave us toshokan sentences when we looked for tosho
        # need to do lexical check for those too? pain in the ass
        # yes, kanshudo has a bunch of toshokans
        # tangorin does not seem to? but maybe it's best not to risk it
        # this certainly makes the sudachi-powershell issue all that much more irritating. maybe try mecab?

        # it has been weeks since i wrote the above comment and forget what it means exactly
        # although we did both fix the sudachi issue and implement mecab
        text = self.text_edit.toPlainText()
        classified = group_text_by_learnability(text)

        for kind in WordLearnableType:
            self.word_displays[kind].set_words(classified[kind])

    def continue_to_card_creation(self):
        words = self.word_displays[WordLearnableType.NEW_WORD].get_selected_words()
        self.new_window = NewWordsTableWidget(words)
        self.new_window.show()
        self.close()
