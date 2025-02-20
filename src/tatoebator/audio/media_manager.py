import os
from typing import Set

from .ffmpeg_interface import convert_bitrate
from .tts2 import DefaultTTSManager
from ..config import AUDIO_BITRATE
from ..constants import TEMP_FILES_DIR, ADDON_NAME, MEDIA_DIR
from ..sentences import ExampleSentence
from ..util import deterministic_hash


class MediaManager:
    def __init__(self, temp_file_name: str = 'temp_audio_file.mp3'):
        self.temp_file_name = temp_file_name
        self.temp_path = os.path.join(TEMP_FILES_DIR, self.temp_file_name)
        self.tts_manager = DefaultTTSManager()

    def _filename_from_id(self, sentence_id: str):
        return f"{ADDON_NAME}.{sentence_id}.mp3"

    def create_audio_file(self, sentence: str, speed=0.8, desired_id=None):
        sentence_id = desired_id or deterministic_hash(sentence)[:32]
        sentence_filename = self._filename_from_id(sentence_id)
        sentence_path = os.path.join(MEDIA_DIR, sentence_filename)
        if not os.path.exists(sentence_path):
            self.tts_manager.create_audio(sentence, speed=speed, file_dir=TEMP_FILES_DIR, file_name=self.temp_file_name)
            convert_bitrate(self.temp_path, sentence_path, AUDIO_BITRATE)
            os.remove(self.temp_path)
        return sentence_id

    def add_audio_file_to_sentence(self, sentence: ExampleSentence, speed=0.8, desired_id=None):
        sentence.audio_fileid = self.create_audio_file(sentence.sentence, speed, desired_id)

    def get_all_audio_ids(self) -> Set[str]:
        return set(
            (filename[len(ADDON_NAME) + 1:-4] for filename in os.listdir(MEDIA_DIR) if filename.endswith(".mp3")))

    def remove_by_id(self, sentence_id: str):
        os.remove(os.path.join(MEDIA_DIR, self._filename_from_id(sentence_id)))
