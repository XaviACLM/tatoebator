import sys
import types

mw = None


utils = types.ModuleType('aqt.utils')
utils.qconnect = None
utils.showInfo = print
sys.modules['aqt.utils'] = utils


qt = types.ModuleType('aqt.qt')
qt.QAction = None
sys.modules['aqt.qt'] = qt
