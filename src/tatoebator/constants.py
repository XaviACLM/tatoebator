import os
from pathlib import Path

# TODO: an actually reliable way to know where the addon is installed - start this from __init__ with __file__, maybe
ADDON_NAME = 'tatoebator'
ADDON_DIR = os.path.join(Path.home(), "AppData", "Roaming", "Anki2", "addons21", ADDON_NAME)
PACKAGE_DIR = os.path.join(ADDON_DIR, "src", ADDON_NAME)

USER_AGENT = f"{ADDON_NAME} example sentence searcher"
TEMP_FILES_DIR = os.path.join(ADDON_DIR, "temp_files")
SENTENCES_PER_CARD = 20
VOICEVOX_VOICES = [0, 13, 14, 30, 81]
MEDIA_DIR = os.path.join(ADDON_DIR, "fake_media_dir")
LIB_DIR = os.path.join(ADDON_DIR, "lib")
PATH_TO_USER_FILES = os.path.join(ADDON_DIR, "user_files")
PATH_TO_SOURCES_FILE = os.path.join(PATH_TO_USER_FILES, "annotated_data_sources.txt")
PATH_TO_DATABASE = os.path.join(PATH_TO_USER_FILES, "sentences.db")
DATABASE_URL = f'sqlite:///{PATH_TO_DATABASE}'
PATH_TO_CACHED_DOWNLOADS = os.path.join(PATH_TO_USER_FILES, "cached_downloads")
PATH_TO_MANUAL_DOWNLOADS = os.path.join(PATH_TO_USER_FILES, "manual_downloads")
