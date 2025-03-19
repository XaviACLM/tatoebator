from __future__ import annotations

import os
import subprocess
import sys
import traceback
import webbrowser
from typing import List, Dict

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QWidget, QHBoxLayout, QSpacerItem, \
    QSizePolicy, QFrame, QMessageBox

from .default_gui_elements import Colors, Pixmaps
from .loading_spinner import XavoSpinner
from ..external_download_requester import Downloadable, AutomaticallyDownloadable, ManualDownloadInstructions, \
    mdit


class FileExistenceWidget(QWidget):
    def __init__(self, filepaths, show_dir_buttons=True):
        super().__init__()
        self.filepaths = filepaths
        self._show_dir_buttons = show_dir_buttons

        self._init_ui()

    def _init_ui(self):

        layout = QHBoxLayout()

        left_layout = QVBoxLayout()

        self._check_button = QPushButton("Check files exist")
        self._check_button.clicked.connect(self._check_files)
        spacer_item = QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        left_layout.addWidget(self._check_button)
        left_layout.addSpacerItem(spacer_item)

        layout.addLayout(left_layout)

        right_layout = QVBoxLayout()

        self._icons = []
        for path in self.filepaths:
            item_layout = QHBoxLayout()

            icon = self.style().standardIcon(Pixmaps.q_mark)
            icon_label = QLabel()
            icon_label.setPixmap(icon.pixmap(16))
            self._icons.append(icon_label)
            item_layout.addWidget(icon_label)

            if self._show_dir_buttons:
                button = QPushButton("Open dir")
                button.setMaximumWidth(60)
                button.clicked.connect(lambda: self._try_open_directory(path))
                item_layout.addWidget(button)

            label = QLabel(path)
            item_layout.addWidget(label)

            spacer = QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            item_layout.addSpacerItem(spacer)

            right_layout.addLayout(item_layout)

        right_frame = QFrame()
        right_frame.setLayout(right_layout)
        right_frame.setObjectName("right_frame")
        right_frame.setStyleSheet(
            f'QFrame#right_frame {{background-color: {Colors.light_grey.name()}; border-radius: 10px;}}')

        frame_holder_layout = QVBoxLayout()
        frame_holder_layout.addWidget(right_frame)
        layout.addLayout(frame_holder_layout)
        # layout.addWidget(right_frame)

        self.setLayout(layout)
        layout.setStretch(0, 0)
        layout.setStretch(1, 1)

    def _check_files(self):
        for icon_label, filepath in zip(self._icons, self.filepaths):
            if os.path.exists(filepath):
                icon = self.style().standardIcon(Pixmaps.tick)
                icon_label.setPixmap(icon.pixmap(16))
            else:
                icon = self.style().standardIcon(Pixmaps.cross)
                icon_label.setPixmap(icon.pixmap(16))

    def _try_open_directory(self, filepath):
        directory = os.path.dirname(filepath)
        if not os.path.exists(directory):
            directory = self._find_existing_parent(directory)
            QMessageBox.warning(self, "Directory Not Found",
                                f"Original directory does not exist. Opening nearest existing path: {directory}")

        if sys.platform == "win32":
            subprocess.run(["explorer", directory])
        elif sys.platform == "darwin":
            subprocess.run(["open", directory])
        else:
            subprocess.run(["xdg-open", directory])

    def _find_existing_parent(self, path):
        while path and not os.path.exists(path):
            path = os.path.dirname(path)
        return path


class ManualDownloadInstructionsDialog(QDialog):
    def __init__(self, instructions: ManualDownloadInstructions):
        super().__init__()
        self._init_ui(instructions)
        self.setWindowTitle("Manual download instructions")

    def _init_ui(self, instructions: ManualDownloadInstructions):
        layout = QVBoxLayout()

        self._widgets = []
        for instruction_type, *args in instructions:
            if instruction_type is mdit.TEXT:
                text, = args
                label = QLabel(text)
                label.setWordWrap(True)
                self._widgets.append(label)
            elif instruction_type is mdit.URL_BUTTON:
                url, = args
                url_button = QPushButton(url)
                # ignore first argument passed by qt on clicked signals
                url_button.clicked.connect(lambda _, captured_url=url: webbrowser.open(captured_url))
                self._widgets.append(url_button)
            elif instruction_type is mdit.BUTTON:
                button_text, func = args
                button = QPushButton(button_text)
                button.clicked.connect(func)
                self._widgets.append(button)
            elif instruction_type is mdit.FILE_CHECK_WIDGET:
                paths_to_check, = args
                checker_widget = FileExistenceWidget(paths_to_check)
                self._widgets.append(checker_widget)

        for widget in self._widgets:
            layout.addWidget(widget)

        self.setLayout(layout)


class DownloadWorker(QThread):
    success = pyqtSignal()
    failure = pyqtSignal(str)

    def __init__(self, downloadable):
        super().__init__()
        self.downloadable = downloadable

    def run(self):
        try:
            self.downloadable.attempt_automatic_download()
            if self.downloadable.are_files_downloaded():
                self.success.emit()
            else:
                self.failure.emit("No exception ocurred, but files did not get downloaded.")
        except Exception as e:
            self.failure.emit(traceback.format_exc())


class DownloadDialog(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Attempting automatic download...")
        self.setModal(True)  # Block other UI interactions

        self.layout = QVBoxLayout()

        self.spinner = XavoSpinner(self, radius=50)
        self.spinner.start()

        self.label = QLabel("")
        self.label.setVisible(False)
        self.layout.addWidget(self.label)

        # Scrollable text box for errors
        self.error_box = QTextEdit()
        self.error_box.setReadOnly(True)
        self.error_box.setVisible(False)  # Initially hidden
        self.layout.addWidget(self.error_box)

        self.button = QPushButton("Continue")
        self.button.setVisible(False)  # Initially hidden
        self.button.clicked.connect(self.close)
        self.layout.addWidget(self.button)

        self.setLayout(self.layout)
        self.setGeometry(300, 300, 400, 400)

    def show_error_after_spinner(self, error: str):
        self.spinner.stop_with_animation(callback=lambda: self.show_error(error))

    def close_after_spinner(self):
        self.spinner.stop_with_animation(self.accept)

    def show_error(self, error: str):
        self.label.setText(f"Automatic download failed. Sorry about that :(\n\nDiagnostic information:")
        self.label.setVisible(True)

        self.error_box.setPlainText(error)
        self.error_box.setVisible(True)

        self.button.setVisible(True)


class DownloadableMenuItemWidget(QWidget):
    def __init__(self, downloadable: Downloadable, user_refused_download: bool):
        super().__init__()
        self.downloadable = downloadable
        self.user_refused_download = user_refused_download

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()

        info_bar = QHBoxLayout()

        self._name_label = QLabel(self.downloadable.name)
        self._labels_spacer = QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._size_label = QLabel(self.downloadable.size + ('' if self.downloadable.processed_size is None
                                                            else f' ({self.downloadable.processed_size} processed)'))
        self._state_label = QLabel("")
        f = self._state_label.font()
        f.setItalic(True)
        self._state_label.setFont(f)

        info_bar.addWidget(self._name_label)
        info_bar.addSpacerItem(self._labels_spacer)
        info_bar.addWidget(self._size_label)
        info_bar.addWidget(self._state_label)

        layout.addLayout(info_bar)

        buttons_bar = QHBoxLayout()

        self._buttons_spacer = QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        buttons_bar.addSpacerItem(self._buttons_spacer)

        self._refuse_download_button = QPushButton()
        self._refuse_download_button.clicked.connect(self._switch_download_refusal_state)

        self._automatic_download_button = QPushButton("Attempt automatic download")
        if isinstance(self.downloadable, AutomaticallyDownloadable):
            self._automatic_download_button.clicked.connect(self._attempt_automatic_download)
        else:
            self._automatic_download_button.setHidden(True)

        self._manual_download_button = QPushButton("Manual download instructions")
        self._manual_download_button.clicked.connect(self._manual_download_instructions)

        buttons_bar.addWidget(self._refuse_download_button)
        buttons_bar.addWidget(self._automatic_download_button)
        buttons_bar.addWidget(self._manual_download_button)

        layout.addLayout(buttons_bar)

        self.setLayout(layout)

        self._update_download_refusal_state(self.user_refused_download)
        if self.downloadable.are_files_downloaded():
            self._mark_download_as_unnecessary()

    def _switch_download_refusal_state(self):
        self._update_download_refusal_state(not self.user_refused_download)

    def _update_download_refusal_state(self, new_download_refusal_state: bool):
        self.user_refused_download = new_download_refusal_state

        self._refuse_download_button.setText("Unrefuse download" if self.user_refused_download
                                             else "Refuse download")

        self._automatic_download_button.setDisabled(new_download_refusal_state)
        self._manual_download_button.setDisabled(new_download_refusal_state)
        self._size_label.setHidden(new_download_refusal_state)
        self._state_label.setText("(User refused download)" if new_download_refusal_state else "")

    def _attempt_automatic_download(self):
        self.dialog = DownloadDialog()
        self.worker = DownloadWorker(self.downloadable)

        self.worker.success.connect(self.dialog.close_after_spinner)
        self.worker.success.connect(self._mark_download_as_unnecessary)

        self.worker.failure.connect(self.dialog.show_error_after_spinner)

        self.worker.start()
        self.dialog.exec()  # Show the dialog (blocks until it's closed)

    def _manual_download_instructions(self):
        self.dialog = ManualDownloadInstructionsDialog(self.downloadable.get_manual_download_instructions())
        self.dialog.exec()
        if self.downloadable.are_files_downloaded():
            self._mark_download_as_unnecessary()

    def _mark_download_as_unnecessary(self):
        self._refuse_download_button.setDisabled(True)
        self._automatic_download_button.setDisabled(True)
        self._manual_download_button.setDisabled(True)
        self._size_label.setHidden(True)
        self._state_label.setText(
            f"(Item{'s' if len(self.downloadable.item_filepaths) > 1 else ''} already downloaded)")


class ExternalDownloadDialog(QDialog):
    def __init__(self,
                 sentence_corpus_downloadables: List[Downloadable],
                 japanese_dictionary_downloadables: List[Downloadable],
                 english_dictionary_downloadables: List[Downloadable],
                 user_has_refused_to_download: Dict[str, bool]):
        super().__init__()
        self.sentence_corpus_downloadables = sentence_corpus_downloadables
        self.japanese_dictionary_downloadables = japanese_dictionary_downloadables
        self.english_dictionary_downloadables = english_dictionary_downloadables

        self._user_has_refused_to_download = user_has_refused_to_download
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        self._downloadable_widgets = []

        self._textbox = QLabel("Sentence corpora downloads\n"
                               "blah blah blah\n"
                               "something about JESC and JParaCrawl")
        layout.addWidget(self._textbox)

        for downloadable in self.sentence_corpus_downloadables:
            _downloadable_widget = DownloadableMenuItemWidget(
                downloadable, self._user_has_refused_to_download[downloadable.name])
            self._downloadable_widgets.append(_downloadable_widget)
            layout.addWidget(_downloadable_widget)

        self.setLayout(layout)

    def closeEvent(self, event):
        for downloadable_widget in self._downloadable_widgets:
            downloadable = downloadable_widget.downloadable
            self._user_has_refused_to_download[downloadable.name] = downloadable_widget.user_refused_download
