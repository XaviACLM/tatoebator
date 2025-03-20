import os
from pathlib import Path

SUDACHI_EXE = os.path.join(Path.home(), "AppData", "Local", "Programs", "Python", "Python310", "Scripts",
                           "sudachipy.exe")
MECAB_DIR = os.path.join("C:", os.sep, "Program Files", "MeCab")
MECAB_EXE = os.path.join(MECAB_DIR, "bin", "mecab.exe")

VOICEVOX_EXE_PATH = os.path.join(
    "C:",
    os.sep,
    "Program Files",
    "voicevox-windows-directml-0.22.3",
    "VOICEVOX",
    "vv-engine",
    "run.exe",
)

W_OKADA_TTS_DIR = os.path.join("C:", os.sep, "Program Files", "w-okada", "main")
W_OKADA_TTS_EXE = os.path.join(W_OKADA_TTS_DIR, "main.exe")

VOICEPEAK_DIR = os.path.join("C:", os.sep, "Program Files", "Voicepeak")
VOICEPEAK_EXE = os.path.join(VOICEPEAK_DIR, "voicepeak.exe")

AUDIO_BITRATE = '64k'

SENTENCES_PER_WORD = 20 # todo are we equipped to handle changes in this value, or should it be a constant?
SENTENCES_PER_CARD_FRONT = 2
SENTENCES_PER_CARD_BACK = 5
assert SENTENCES_PER_CARD_FRONT <= SENTENCES_PER_CARD_BACK
# not actually necessary to add '<= SENTENCES_PER_WORD' but best know what you're doing
