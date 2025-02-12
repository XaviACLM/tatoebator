from tatoebator.db import SentenceDbManager

sentence_db_manager = SentenceDbManager()
print(len(sentence_db_manager.media_manager.get_all_audio_ids()))
sentence_db_manager.cleanup_orphaned_audio_files()