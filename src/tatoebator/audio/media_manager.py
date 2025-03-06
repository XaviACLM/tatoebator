import os
from typing import Set

from .ffmpeg_interface import convert_bitrate
from .tts2 import DefaultTTSManager, TTSManager
from ..config import AUDIO_BITRATE
from ..constants import TEMP_FILES_DIR, ADDON_NAME, MEDIA_DIR, PATH_TO_AUDIO_GENERATION_QUEUE
from ..subprocesses import BackgroundProcessor
from ..util import deterministic_hash


class TTSBackgroundProcessor(BackgroundProcessor):
    # task format: tuple - sentence to speak, speed at which to speak, path to which to save
    def __init__(self, tts_manager: TTSManager, temp_file_name: str = 'temp_audio_file.mp3'):
        super().__init__(PATH_TO_AUDIO_GENERATION_QUEUE)
        self.tts_manager = tts_manager
        self._temp_file_name = temp_file_name
        self._temp_path = os.path.join(TEMP_FILES_DIR, self._temp_file_name)

    def process_task(self, task):
        sentence, speed, sentence_path = task

        print("generating sentence in background...")
        if not os.path.exists(sentence_path):
            self.tts_manager.create_audio(sentence, speed=speed, file_dir=TEMP_FILES_DIR, file_name=self._temp_file_name)
            convert_bitrate(self._temp_path, sentence_path, AUDIO_BITRATE)
            os.remove(self._temp_path)


class MediaManager:
    def __init__(self):
        self.tts_manager = DefaultTTSManager()
        self.background_processor = TTSBackgroundProcessor(self.tts_manager)

    def filename_from_id(self, sentence_id: str):
        return f"{ADDON_NAME}.{sentence_id}.mp3"

    def create_audio_file(self, sentence: str, speed=0.8, desired_id=None):
        print("create audio file called w sentence",sentence)
        sentence_id = desired_id or deterministic_hash(sentence)[:32]
        sentence_filename = self.filename_from_id(sentence_id)
        sentence_path = os.path.join(MEDIA_DIR, sentence_filename)

        self.background_processor.enqueue_task((sentence, speed, sentence_path))

        return sentence_id

    def get_all_audio_ids(self) -> Set[str]:
        return set(
            (filename[len(ADDON_NAME) + 1:-4] for filename in os.listdir(MEDIA_DIR)
             if filename.endswith(".mp3") and filename.startswith(ADDON_NAME)))

    def remove_by_id(self, sentence_id: str):
        os.remove(os.path.join(MEDIA_DIR, self.filename_from_id(sentence_id)))