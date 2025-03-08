import os
from typing import Set

from .ffmpeg_interface import convert_bitrate
from .tts2 import DefaultTTSManager, TTSManager
from ..config import AUDIO_BITRATE
from ..constants import TEMP_FILES_DIR, ADDON_NAME, MEDIA_DIR
from ..language_extensions import TransientSingleton
from ..sentences.example_sentences import ExternalFileRef
from ..subprocesses import BackgroundProcessor
from ..util import deterministic_hash


class TTSBackgroundProcessor(BackgroundProcessor, TransientSingleton):
    # task format: tuple - sentence to speak, speed at which to speak, path to which to save
    def __init__(self, tts_manager: TTSManager,
                 queue_file_name: str = 'audio_generation_queue.json',
                 temp_file_name: str = 'temp_audio_file.mp3'):
        queue_filepath = os.path.join(TEMP_FILES_DIR, queue_file_name)
        super().__init__(queue_filepath)
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


class BitrateConversionBackgroundProcessor(BackgroundProcessor, TransientSingleton):
    # task format: tuple - input file path, output file path
    def __init__(self, queue_file_name: str = 'bitrate_conversion_queue.json'):
        queue_filepath = os.path.join(TEMP_FILES_DIR, queue_file_name)
        super().__init__(queue_filepath)

    def process_task(self, task):
        input_filepath, output_filepath = task

        convert_bitrate(input_filepath, output_filepath, AUDIO_BITRATE)


class MediaManager:
    def __init__(self):
        self.tts_manager = DefaultTTSManager()
        self.tts_background_processor = TTSBackgroundProcessor(self.tts_manager)
        self.bitrate_background_processor = BitrateConversionBackgroundProcessor()

    def _filename_from_id(self, sentence_id: str):
        return f"{ADDON_NAME}.{sentence_id}.mp3"

    def create_audio_file(self, sentence_text: str, speed=0.8, desired_id=None):
        sentence_id = desired_id or deterministic_hash(sentence_text)[:32]
        sentence_filename = self._filename_from_id(sentence_id)
        sentence_path = os.path.join(MEDIA_DIR, sentence_filename)

        self.tts_background_processor.enqueue_task((sentence_text, speed, sentence_path))

        return sentence_filename

    def intake_external_audio_file(self, sentence_text: str, external_filepath: ExternalFileRef):
        sentence_id = deterministic_hash(sentence_text)[:32]
        sentence_filename = self._filename_from_id(sentence_id)
        sentence_path = os.path.join(MEDIA_DIR, sentence_filename)

        self.bitrate_background_processor.enqueue_task((external_filepath, sentence_path))

        return sentence_filename

    def get_all_audio_ids(self) -> Set[str]:
        return set(
            (filename[len(ADDON_NAME) + 1:-4] for filename in os.listdir(MEDIA_DIR)
             if filename.endswith(".mp3") and filename.startswith(ADDON_NAME)))

    def get_ref_for_sentence(self, sentence_text: str):
        sentence_id = deterministic_hash(sentence_text)[:32]
        sentence_filename = self._filename_from_id(sentence_id)
        return sentence_filename

    def check_ref_exists(self, media_file_ref: str):
        media_file_path = os.path.join(MEDIA_DIR, media_file_ref)
        return os.path.exists(media_file_path)
