import os
import sys
from hashlib import sha256


def deterministic_hash(string: str) -> str:
    m = sha256()
    m.update(string.encode(encoding="utf-16"))
    return m.hexdigest()


def running_as_anki_addon() -> bool:
    _, exec_name = os.path.split(sys.executable)
    return exec_name == "anki.exe"


def ensure_aqt():
    if running_as_anki_addon(): return
    from . import mock_aqt
    sys.modules['aqt'] = mock_aqt


try:

    # from Mark Tolonen, https://stackoverflow.com/questions/46132401/read-text-from-clipboard-in-windows-using-ctypes
    import ctypes
    import ctypes.wintypes as wt

    class ClipboardGetter:
        CF_UNICODETEXT = 13

        u32 = ctypes.WinDLL('user32')
        k32 = ctypes.WinDLL('kernel32')

        OpenClipboard = u32.OpenClipboard
        OpenClipboard.argtypes = wt.HWND,
        OpenClipboard.restype = wt.BOOL
        GetClipboardData = u32.GetClipboardData
        GetClipboardData.argtypes = wt.UINT,
        GetClipboardData.restype = wt.HANDLE
        GlobalLock = k32.GlobalLock
        GlobalLock.argtypes = wt.HGLOBAL,
        GlobalLock.restype = wt.LPVOID
        GlobalUnlock = k32.GlobalUnlock
        GlobalUnlock.argtypes = wt.HGLOBAL,
        GlobalUnlock.restype = wt.BOOL
        CloseClipboard = u32.CloseClipboard
        CloseClipboard.argtypes = None
        CloseClipboard.restype = wt.BOOL

        @classmethod
        def get_clipboard_text(cls):
            text = ""
            if cls.OpenClipboard(None):
                h_clip_mem = cls.GetClipboardData(cls.CF_UNICODETEXT)
                text = ctypes.wstring_at(cls.GlobalLock(h_clip_mem))
                cls.GlobalUnlock(h_clip_mem)
                cls.CloseClipboard()
            return text


    get_clipboard_text = ClipboardGetter.get_clipboard_text

except ModuleNotFoundError:

    get_clipboard_text = lambda: ""


class CircularBuffer:
    def __init__(self, size, initial_value):
        self.buffer = [initial_value] * size
        self.index = 0
        self.size = size

    def peek(self):
        return self.buffer[self.index]

    def push(self, value):
        self.buffer[self.index] = value
        self.index = (self.index + 1) % self.size
