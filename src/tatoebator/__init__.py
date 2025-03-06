import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..\\..\\lib"))

from .util import running_as_anki_addon, ensure_aqt

# if not running in anki, insert mock_aqt module into sys.modules['aqt']
ensure_aqt()

from .tatoebator import Tatoebator


# introduces import hook that replaces unless with if not
# commented out b/c it messes with tracebacks (because we were lazy about it)
# from .language_extensions.ast_transformers import install_unless
# install_unless()

if running_as_anki_addon():

    from aqt import mw
    from aqt.utils import qconnect
    from aqt.qt import QAction

    from .gui import MineNewWordsWidget
    from .gui import NewWordsTableWidget
    from .db import SentenceRepository

    mw.tatoebator = Tatoebator()

    action = QAction("T: Mine words", mw)
    qconnect(action.triggered, mw.tatoebator.mining_to_deck_flow)
    mw.form.menuTools.addAction(action)

    action = QAction("T: Edit searchable fields", mw)
    qconnect(action.triggered, mw.tatoebator.open_registry_editor)
    mw.form.menuTools.addAction(action)

    action = QAction("T: Ensure data health", mw)
    qconnect(action.triggered, mw.tatoebator.ensure_data_health)
    mw.form.menuTools.addAction(action)


    def testfun1() -> None:
        mw.tatoebator.anki_db_test()

    def testfun2() -> None:
        mw.tatoebator.note_creation_test()

    def testfun3() -> None:
        print("uuuh")

    for idx, testfun in enumerate([testfun1, testfun2, testfun3]):
        action = QAction(f"test{idx + 1}", mw)
        qconnect(action.triggered, testfun)
        mw.form.menuTools.addAction(action)
