from typing import List, Tuple, Dict, Set, Optional

from ..sentences import ExampleSentence
from ..sentences import SentenceProductionManager
from ..audio import MediaManager
from ..constants import SENTENCES_PER_CARD
from ..db.core import SentenceDbInterface


class SentenceRepository:
    def __init__(self):
        self.sentence_production_manager = SentenceProductionManager()
        self.sentence_db_interface = SentenceDbInterface()
        self.media_manager = MediaManager()
        self._ensure_starter_sentences()

    def _ensure_starter_sentences(self):
        if self.sentence_db_interface.count_n_sentences() < self.sentence_production_manager.amt_starter_sentences*0.5:
            self._ingest_starter_sentences()

    def produce_sentences_for_word(self, word: str, desired_amt: int,
                                   produce_new=True, ensure_audio=False) -> List[ExampleSentence]:
        """
        gets amt_desired sentences from the database. if there are not enough sentences and produce_new is true, produces some new sentences
        returns a bool (indicating whether it managed to get the desired amount - it might not, even if produce_new=True)
                and the sentences.
        """
        sentences = self.sentence_db_interface.get_sentences_by_word(word, desired_amt=desired_amt)
        if ensure_audio: self._ensure_audio(sentences)
        if len(sentences) == desired_amt or not produce_new:
            return sentences
        reached_desired_amt, produced_sentences = self._produce_new_sentences_for_word(word,
                                                                                       desired_amt - len(sentences),
                                                                                       ensure_audio=ensure_audio)
        return sentences + produced_sentences

    def produce_sentences_for_words(self, word_desired_amts: Dict[str, int],
                                   produce_new=True, ensure_audio=False) -> Dict[str, List[ExampleSentence]]:
        words = list(word_desired_amts.keys())
        sentences = self.sentence_db_interface.get_sentences_by_word_batched(word_desired_amts)
        if ensure_audio: self._ensure_audio(sum(sentences.values(),[]))

        missing_sentences_by_word = {word: word_desired_amts[word]-len(sentences[word]) for word in words}
        produced_all_desired = max(missing_sentences_by_word.values()) <= 0
        if not produce_new or produced_all_desired:
            return sentences

        new_sentences = self._produce_new_sentences_for_words(missing_sentences_by_word, ensure_audio=ensure_audio)
        aggregated_sentences = {word: sentences[word]+new_sentences[word] for word in words}

        return aggregated_sentences

    def count_lexical_word_ocurrences(self, lexical_words: List[str],
                                      min_comprehensibility: Optional[float] = None) -> Dict[str, int]:
        if min_comprehensibility is not None:
            return self.sentence_db_interface \
                .count_keywords_by_sentence_comprehensibility(lexical_words, min_comprehensibility)
        return self.sentence_db_interface.count_keywords(lexical_words)

    def cleanup_orphaned_audio_files(self):
        referenced_audio_ids = self.sentence_db_interface.get_all_audio_ids()
        existing_audio_ids = self.media_manager.get_all_audio_ids()

        orphaned_ids = existing_audio_ids - referenced_audio_ids
        for orphaned_id in orphaned_ids:
            self.media_manager.remove_by_id(orphaned_id)

    def update_known(self, known_words: Set[str]):
        self.sentence_db_interface.update_known_field(known_words)
        self.sentence_db_interface.update_known_unknown_counts()

    def _ensure_audio(self, sentences: List[ExampleSentence]):
        updated_sentences = []
        for sentence in sentences:
            if sentence.audio_fileid is None:
                updated_sentences.append(sentence)
                self.media_manager.add_audio_file_to_sentence(sentence)
        if updated_sentences:
            self.sentence_db_interface.update_audio_file_ids(updated_sentences)

    def _produce_new_sentences_for_word(self, word: str, desired_amt: int, ensure_audio=False) -> List[ExampleSentence]:
        return self._produce_new_sentences_for_words({word: desired_amt}, ensure_audio=ensure_audio)[word]

    def _produce_new_sentences_for_words(self, word_desired_amts: Dict[str, int], ensure_audio=False) \
            -> Dict[str, List[ExampleSentence]]:
        """
        does what it says on the tin
        only creates up to amt_desired sentences
        saves them all to the db
        takes care not to insert any repeats or create any unnecessary audio files
        returns created sentences
        """
        is_not_in_db = lambda s: self.sentence_db_interface.check_sentence(s.sentence, commit=False) is None
        sentences = {word: [] for word in word_desired_amts}
        for word, sentence in self.sentence_production_manager \
                .yield_new_sentences_with_words(word_desired_amts, filtering_fun=is_not_in_db):

            if ensure_audio and sentence.audio_fileid is None:
                self.media_manager.add_audio_file_to_sentence(sentence)

            sentences[word].append(sentence)

        all_sentences = sum(sentences.values(), [])
        self.sentence_db_interface.insert_sentences_batched(all_sentences, verify_not_repeated=False)
        return sentences

    def _ingest_starter_sentences(self, max_desired_sentences_per_word: int = SENTENCES_PER_CARD, block_size: int = 50):
        is_not_in_db = lambda s: self.sentence_db_interface.check_sentence(s.sentence, commit=False) is None
        block = []
        sentence_text = set()
        for sentence in self.sentence_production_manager.yield_starter_sentences(filtering_fun=is_not_in_db):

            # check there is at least one lexical word which doesn't already exist a lot within the db
            least_present_lexical_word = min(self.sentence_db_interface.count_keywords(sentence.lexical_words).values())
            if least_present_lexical_word >= max_desired_sentences_per_word: continue

            if sentence.sentence in sentence_text:
                continue
            sentence_text.add(sentence.sentence)
            block.append(sentence)
            if len(block) == block_size:
                self.sentence_db_interface.insert_sentences_batched(block, verify_not_repeated=False)
                block = []
                sentence_text = set()
        self.sentence_db_interface.insert_sentences_batched(block, verify_not_repeated=False)
