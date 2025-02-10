import os, sys
from .language_extensions.ast_transformers import install_unless

# introduces import hook that replaces unless with if not
# commented out b/c it messes with tracebacks (most likely this is b/c i didn't do it right)
# install_unless()

from .util import running_as_anki_addon
from .util import showInfo

if running_as_anki_addon():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..\\..\\lib"))

    from aqt import mw
    from aqt.utils import qconnect
    from aqt.qt import *

    from .gui.selector import MineNewWordsWidget
    from .gui.word_table import TableWidget
    from .db.manager import SentenceDbManager

    def testfun1() -> None:
        mw.myWidget = MineNewWordsWidget()
        mw.myWidget.show()

    def testfun2() -> None:
        showInfo(str(sys.executable))
        sentence_db_manager = SentenceDbManager()
        _, sentences = sentence_db_manager.get_sentences("煙", 10)

        showInfo("\n".join((f"{sentence.sentence} / {sentence.translation}" for sentence in sentences)))

    def testfun3() -> None:
        mw.myWidget = TableWidget(["煙","母親","彼","恩人","する"])
        mw.myWidget.show()

    for idx, testfun in enumerate([testfun1, testfun2, testfun3]):
        action = QAction(f"test{idx+1}", mw)
        qconnect(action.triggered, testfun)
        mw.form.menuTools.addAction(action)