from tatoebator.db import SentenceRepository

sentence_repository = SentenceRepository()
print(len(sentence_repository.media_manager.get_all_audio_ids()))
sentence_repository.cleanup_orphaned_audio_files()
print(len(sentence_repository.media_manager.get_all_audio_ids()))