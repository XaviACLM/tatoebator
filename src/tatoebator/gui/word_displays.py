from typing import List

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QTextOption, QTextCharFormat, QColor, QTextCursor, QFont
from PyQt6.QtWidgets import QTextEdit, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton


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

    def set_selected_words(self, selected_words: List[str]):
        count = 0
        for word in self.words:
            if word in selected_words:
                count += 1
                self.word_states[word] = True
            else:
                self.word_states[word] = False
        self._update_text()
        self.num_highlighted_words = count

    def _update_text(self):
        """Update the text with current words and states."""
        self.clear()
        cursor = self.textCursor()

        normal_fmt = QTextCharFormat()
        highlight_fmt = QTextCharFormat()
        highlight_fmt.setBackground(QColor("black"))
        highlight_fmt.setForeground(QColor("white"))

        words = iter(self.words)
        word = next(words)
        cursor.insertText(word, highlight_fmt if self.word_states[word] else normal_fmt)
        for word in words:
            cursor.insertText(" " * 3, normal_fmt)
            cursor.insertText(word, highlight_fmt if self.word_states[word] else normal_fmt)

    def mousePressEvent(self, event):
        """Toggle highlighting when a word is clicked."""
        cursor = self.cursorForPosition(event.pos())
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        word = cursor.selectedText()
        if not word: return
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

    def get_words(self):
        text = self.text_edit.toPlainText()
        if text: return text.split(" "*3)
        else: return []


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

    def set_selected_words(self, selected_words: List[str]):
        self.text_edit.set_selected_words(selected_words)
        self._update_highlight_count()