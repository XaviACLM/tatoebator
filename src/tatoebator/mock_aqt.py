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


gui_hooks = types.ModuleType('aqt.gui_hooks')
gui_hooks.main_window_did_init = []
sys.modules['aqt.gui_hooks'] = gui_hooks
