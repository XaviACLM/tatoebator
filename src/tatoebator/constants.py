import os

ADDON_NAME = 'tatoebator'

PATH_TO_PACKAGE = os.path.split(__file__)[0]
PATH_TO_ADDON = PATH_TO_PACKAGE.removesuffix(f"\\src\\{ADDON_NAME}")
PATH_TO_ANKI = PATH_TO_ADDON.removesuffix(f"\\addons21\\{ADDON_NAME}") # TODO this will have to be the addon id later

# TODO this will have to work some other way
ANKI_USER_NAME = "User 1"
MEDIA_DIR = os.path.join(PATH_TO_ANKI, ANKI_USER_NAME, 'collection.media')
# MEDIA_DIR = os.path.join(PATH_TO_ADDON, "fake_media_dir")

SENTENCES_PER_CARD = 20
USER_AGENT = f"{ADDON_NAME} example sentence searcher"
INTER_FIELD_SEPARATOR = '##SEP##'

TEMP_FILES_DIR = os.path.join(PATH_TO_ADDON, "temp_files")
LIB_DIR = os.path.join(PATH_TO_ADDON, "lib")
PATH_TO_USER_FILES = os.path.join(PATH_TO_ADDON, "user_files")
PATH_TO_SOURCES_FILE = os.path.join(PATH_TO_USER_FILES, "annotated_data_sources.txt")
PATH_TO_DATABASE = os.path.join(PATH_TO_USER_FILES, "sentences.db")
PATH_TO_CACHED_DOWNLOADS = os.path.join(PATH_TO_USER_FILES, "cached_downloads")
PATH_TO_MANUAL_DOWNLOADS = os.path.join(PATH_TO_USER_FILES, "manual_downloads")
PATH_TO_AUDIO_GENERATION_QUEUE = os.path.join(PATH_TO_USER_FILES, "audio_generation_queue.json")