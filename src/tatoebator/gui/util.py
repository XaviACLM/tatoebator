from PyQt6.QtWidgets import QMessageBox


def ask_yes_no_question(question: str) -> bool:
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Question)
    msg_box.setText(question)
    yes_button = msg_box.addButton("Yes", QMessageBox.ButtonRole.YesRole)
    no_button = msg_box.addButton("No", QMessageBox.ButtonRole.NoRole)
    msg_box.exec()
    return msg_box.clickedButton() == yes_button
