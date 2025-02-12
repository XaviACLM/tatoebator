import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..\\..\\lib"))

from .util import running_as_anki_addon, ensure_aqt

ensure_aqt()

from .tatoebator import Tatoebator

# if not running in anki, insert mock_aqt module into sys.modules['aqt']


# introduces import hook that replaces unless with if not
# commented out b/c it messes with tracebacks (most likely this is b/c i didn't do it right)
# from .language_extensions.ast_transformers import install_unless
# install_unless()

if running_as_anki_addon():

    from aqt import mw
    from aqt.utils import qconnect, showInfo
    from aqt.qt import QAction

    from .gui import MineNewWordsWidget
    from .gui import NewWordsTableWidget
    from .db import SentenceRepository

    mw.tatoebator = Tatoebator()


    def testfun1() -> None:
        mw.tatoebator.mining_to_deck_flow()

    def testfun2() -> None:
        mw.tatoebator.word_table_test(["煙", "母親", "彼", "恩人", "する"])

    def testfun3() -> None:
        mw.tatoebator.update_known_counts()

    for idx, testfun in enumerate([testfun1, testfun2, testfun3]):
        action = QAction(f"test{idx + 1}", mw)
        qconnect(action.triggered, testfun)
        mw.form.menuTools.addAction(action)
