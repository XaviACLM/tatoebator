from pathlib import Path
import os

#TODO: an actually reliable way to know where the addon is installed - start this from __init__ with __file__, maybe
ADDON_NAME = 'tatoebator'
TEMP_FILES_DIR = os.path.join(Path.home(),"AppData","Roaming","Anki2","addons21",ADDON_NAME,"src",ADDON_NAME, "temp_files")
PATH_TO_DATABASE = os.path.join(Path.home(),"AppData","Roaming","Anki2","addons21", ADDON_NAME,"sentences.db")
DATABASE_URL = f'sqlite:///{PATH_TO_DATABASE}'
SENTENCES_PER_CARD = 20
VOICEVOX_VOICES = [0,13,14,30,81]
MEDIA_DIR = os.path.join(Path.home(),"AppData","Roaming","Anki2","addons21", ADDON_NAME,"fake_media_dir")
LIB_DIR = os.path.join(Path.home(),"AppData","Roaming","Anki2","addons21", ADDON_NAME,"lib")
SRC_DIR = os.path.join(Path.home(),"AppData","Roaming","Anki2","addons21", ADDON_NAME,"src",ADDON_NAME)