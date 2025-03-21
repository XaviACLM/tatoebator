from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QVBoxLayout, QPushButton

from tatoebator.gui.loading_spinner import XavoSpinner

app = QApplication([])

class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        self.spinner = XavoSpinner(self, radius=50)
        layout.addWidget(self.spinner)
        self.button = QPushButton("stop spinner")
        self.button.clicked.connect(self.spinner.stop_with_animation)
        layout.addWidget(self.button)
        self.setLayout(layout)
        self.setGeometry(100,100,300,300)


window = TestWindow()
window.show()
window.spinner.start()


app.exec()