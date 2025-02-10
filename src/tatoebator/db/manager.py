import os
from typing import List, Tuple, Dict

from ..audio.media_manager import MediaManager
from ..example_sentences import ExampleSentence
from ..sentence_production import SentenceProductionManager
from ..db.core import SentenceDbInterface
from ..constants import SENTENCES_PER_CARD


class SentenceDbManager:
    def __init__(self):
        self.sentence_db_interface = SentenceDbInterface()
        self.sentence_production_manager = SentenceProductionManager(generate_missing_translations=True)
        self.media_manager = MediaManager()

        # not really necessary since we already check w/ the db but using this should be faster than that
        # (or not? sql is supposed to be fast ... but i really doubt this can hurt)
        # note that this will (unlike the db) reset each execution
        self.seen_sentences = set()

        # same idea, also resets for each execution
        # TODO wait, that's dumb
        # following that thread it kinda seems like this class shouldn't own the sentence production manager, instead having it passed?
        # or the sentence production manage should have some logic integrated with this to figure out where to start from its 'databanks'
        self.arbitrary_yielder = self.sentence_production_manager.yield_new_sentences()

    def get_sentences(self, word, amt_desired, produce_new=True, ensure_audio=False) -> Tuple[bool, List[ExampleSentence]]:
        """
        gets amt_desired sentences from the database. if there are not enough sentences and produce_new is true, produces some new sentences
        returns a bool (indicating whether it managed to get the desired amount - it might not, even if produce_new=True)
                and the sentences.
        """
        sentences = self.sentence_db_interface.get_sentences_by_word(word, max_desired_amt=amt_desired)
        sentences = sentences[:amt_desired]
        if ensure_audio: self._ensure_audio(sentences)
        if len(sentences) == amt_desired:
            return True, sentences
        if not produce_new:
            return False, sentences
        reached_desired_amt, produced_sentences = self._produce_new_sentences(word, amt_desired-len(sentences), ensure_audio=ensure_audio)
        return reached_desired_amt, sentences+produced_sentences

    def produce_up_to_limit(self, word, max_amt_desired=SENTENCES_PER_CARD, ensure_audio=False) -> None:
        # essentially the same as calling get_sentences and then discarding the return
        # but i don't know, that would feel  like bad design somehow
        sentences = self.sentence_db_interface.get_sentences_by_word(word, max_amt_desired=max_amt_desired)
        if ensure_audio: self._ensure_audio(sentences)
        amt_desired = max_amt_desired-len(sentences)
        if amt_desired > 0:
            self._produce_new_sentences(word, amt_desired, ensure_audio=ensure_audio)

    def _ensure_audio(self, sentences: List[ExampleSentence]):
        updated_sentences = []
        for sentence in sentences:
            if sentence.audio_fileid is None:
                updated_sentences.append(sentence)
                self.media_manager.add_audio_file_to_sentence(sentence)
        if updated_sentences:
            self.sentence_db_interface.update_audio_file_ids(updated_sentences)

    def _produce_new_sentences(self, word, amt_desired, ensure_audio=False) -> Tuple[bool, List[ExampleSentence]]:
        """
        does what it says on the tin
        only creates up to amt_desired sentences
        saves them all to the db
        takes care not to insert any repeats or create any unnecessary audio files
        returns bool (indicating whether it managed to create amt_desired, False if it fell short), and created sentences
        """
        sentences = []
        for sentence in self.sentence_production_manager.yield_new_sentences(word=word):

            # avoid duplicates
            if sentence.sentence in self.seen_sentences:
                continue
            self.seen_sentences.add(sentence.sentence)
            if self.sentence_db_interface.check_sentence(sentence.sentence, commit=False) is not None:
                continue

            if ensure_audio and sentence.audio_fileid is None:
                self.media_manager.add_audio_file_to_sentence(sentence)

            sentences.append(sentence)
            amt_desired -= 1
            if amt_desired == 0:
                break

        self.sentence_db_interface.insert_sentences_batched(sentences, verify_not_repeated=False)
        return amt_desired == 0, sentences

    def _produce_new_sentences_arbitrarily(self, desired_amt, max_desired_sentences_per_word=SENTENCES_PER_CARD, block_size=50) -> bool:
        block = []
        for sentence in self.arbitrary_yielder:

            # avoid duplicates
            if sentence.sentence in self.seen_sentences:
                continue
            self.seen_sentences.add(sentence.sentence)
            if self.sentence_db_interface.check_sentence(sentence.sentence, commit=False) is not None:
                continue

            # check there is at least one lexical word which doesn't already exist a lot within the db
            least_present_lexical_word = min(self.sentence_db_interface.count_keywords(sentence.lexical_words).values())
            if least_present_lexical_word >= max_desired_sentences_per_word: continue

            block.append(sentence)
            if len(block) == min(block_size, desired_amt):
                self.sentence_db_interface.insert_sentences_batched(block, verify_not_repeated=False)
                block = []
                desired_amt -= block_size
                if desired_amt <= 0:
                    return True
        return False

    def count_lexical_word_ocurrences(self, lexical_words) -> Dict[str, int]:
        return self.sentence_db_interface.count_keywords(lexical_words)

    def cleanup_orphaned_audio_files(self):
        referenced_audio_ids = self.sentence_db_interface.get_all_audio_ids()
        existing_audio_ids = self.media_manager.get_all_audio_ids()

        orphaned_ids = existing_audio_ids-referenced_audio_ids
        for orphaned_id in orphaned_ids:
            self.media_manager.remove_by_id(orphaned_id)

    def update_known(self):
        # TODO insert some info from the anki db to get the Keywords.known data
        # and then we call...
        self.sentence_db_interface.update_known_unknown_counts()
