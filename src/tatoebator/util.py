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
