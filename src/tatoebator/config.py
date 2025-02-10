from pathlib import Path
import os

SUDACHI_EXE = os.path.join(Path.home(), "AppData", "Local", "Programs", "Python", "Python310", "Scripts", "sudachipy.exe")
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
