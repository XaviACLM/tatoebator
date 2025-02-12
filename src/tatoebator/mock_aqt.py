import sys
import types

mw = None


utils = types.ModuleType('mock_aqt.utils')
utils.qconnect = None
utils.showInfo = print
sys.modules['mock_aqt.utils'] = utils


qt = types.ModuleType('mock_aqt.qt')
qt.QAction = None
sys.modules['mock_aqt.qt'] = qt
