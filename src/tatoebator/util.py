import os
import sys
import bisect
from hashlib import sha256
import threading
from typing import Callable, Any, Tuple, Dict, Set, List


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


    class _ClipboardGetter:
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
        def get_clipboard_text(cls) -> str:
            text = ""
            try:
                if cls.OpenClipboard(None):
                    h_clip_mem = cls.GetClipboardData(cls.CF_UNICODETEXT)
                    text = ctypes.wstring_at(cls.GlobalLock(h_clip_mem))
                    cls.GlobalUnlock(h_clip_mem)
                    cls.CloseClipboard()
                return text
            except OSError:
                # clipboard just stops working randomly?
                # man i don't know. whatever.
                print("OSError trying to read clipboard")
                return ""


    get_clipboard_text = _ClipboardGetter.get_clipboard_text

except ModuleNotFoundError:

    get_clipboard_text = lambda: ""


class CircularBuffer:
    def __init__(self, size: int, initial_value):
        self.buffer = [initial_value] * size
        self.index = 0
        self.size = size

    def peek(self):
        return self.buffer[self.index]

    def push(self, value):
        self.buffer[self.index] = value
        self.index = (self.index + 1) % self.size


class AutoRemovingThread(threading.Thread):
    def __init__(self, thread_set: Set,
                 target: Callable[..., Any],
                 args: Tuple[Any],
                 kwargs: Dict[str, any] = None):
        kwargs = kwargs or {}
        super().__init__(target=self._run_and_cleanup, args=args, kwargs=kwargs)
        self.target_func = target
        self.thread_set = thread_set
        self.thread_set.add(self)

    def _run_and_cleanup(self, *args, **kwargs):
        try:
            self.target_func(*args, **kwargs)
        finally:
            self.thread_set.discard(self)


class RankedItem:
    def __init__(self, value, item):
        self.value = value
        self.item = item

    def __lt__(self, other):
        return self.value < other.value  # Compare only values


class RankedBuffer:
    def __init__(self, max_size: int):
        self.max_size = max_size
        self._items: List[RankedItem] = []  # Stores (value, item) tuples

    def insert(self, value, item):
        bisect.insort(self._items, RankedItem(value, item))

        if len(self._items) > self.max_size:
            self._items.pop(0)

    def is_full(self):
        return self.amt_items() == self.max_size

    def amt_items(self):
        return len(self._items)

    def get_items(self):
        return [ranked_item.item for ranked_item in self._items]

    def lowest_value(self, default_value=None):
        return self._items[0].value if self._items else default_value
