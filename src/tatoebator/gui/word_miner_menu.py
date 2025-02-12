from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QTextEdit, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QSpacerItem, QSizePolicy

from ..language_processing import group_text_by_learnability, WordLearnableType
from .word_displays import QWordDisplay, QSelectableWordDisplay


class MineNewWordsWidget(QWidget):

    continue_button_clicked = pyqtSignal()

    def __init__(self, text_to_mine=""):
        super().__init__()

        self.initUI()
        self.text_edit.insertPlainText(text_to_mine)

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
        self.continue_button.clicked.connect(self.continue_button_clicked.emit)

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
        text = self.text_edit.toPlainText()
        classified = group_text_by_learnability(text)

        for kind in WordLearnableType:
            self.word_displays[kind].set_words(classified[kind])

    def get_mined_text(self):
        return self.text_edit.toPlainText()

    def get_selected_words(self):
        return self.word_displays[WordLearnableType.NEW_WORD].get_selected_words()
