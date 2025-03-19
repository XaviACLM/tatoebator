from typing import List, Dict, Set, Optional, Callable
from wsgiref.validate import header_re

from ..audio import MediaManager
from ..constants import SENTENCES_PER_WORD
from ..db.core import SentenceDbInterface
from ..external_download_requester import ExternalDownloadRequester
from ..language_processing import add_furigana_html
from ..sentences import ExampleSentence
from ..sentences import SentenceProductionManager
from ..sentences.example_sentences import ExternalFileRef


class SentenceRepository:
    def __init__(self, media_manager: MediaManager, external_download_requester: ExternalDownloadRequester):
        self.media_manager = media_manager
        self.sentence_production_manager = SentenceProductionManager(external_download_requester)
        self.sentence_db_interface = SentenceDbInterface()
        self._ensure_starter_sentences()

    def _ensure_starter_sentences(self):
        if self.sentence_db_interface.count_n_sentences() < self.sentence_production_manager.amt_starter_sentences*0.5:
            self._ingest_starter_sentences()

    def produce_sentences_for_word(self, word: str, desired_amt: int,
                                   produce_new=True, ensure_audio=False, with_furigana=False,
                                   progress_callback: Optional[Callable[..., None]] = None)\
            -> List[ExampleSentence]:
        """
        gets amt_desired sentences from the database. if there are not enough sentences and produce_new is true,
        produces some new sentences. this might still not hit the quota.
        returns the sentences that have been found, up to the specified amount.
        """
        sentences = self.sentence_db_interface.get_sentences_by_word(word, desired_amt=desired_amt)
        if ensure_audio: self._ensure_sentences_have_audio(sentences)
        if with_furigana: self._add_furigana(sentences)
        if len(sentences) == desired_amt or not produce_new:
            return sentences
        produced_sentences = self._produce_new_sentences_for_word(word,
                                                                  desired_amt - len(sentences),
                                                                  ensure_audio=ensure_audio,
                                                                  progress_callback=progress_callback)
        if ensure_audio: self._ensure_sentences_have_audio(produced_sentences)
        if with_furigana: self._add_furigana(produced_sentences)
        return sentences + produced_sentences

    def produce_sentences_for_words(self, word_desired_amts: Dict[str, int],
                                    produce_new=True, ensure_audio=False, with_furigana=False,
                                    progress_callback: Optional[Callable[..., None]] = None)\
            -> Dict[str, List[ExampleSentence]]:
        words = list(word_desired_amts.keys())
        sentences = self.sentence_db_interface.get_sentences_by_word_batched(word_desired_amts)

        missing_sentences_by_word = {word: word_desired_amts[word]-len(sentences[word]) for word in words}
        produced_all_desired = max(missing_sentences_by_word.values()) <= 0
        if not produced_all_desired and produce_new:
            new_sentences = self._produce_new_sentences_for_words(missing_sentences_by_word,
                                                                  ensure_audio=ensure_audio,
                                                                  progress_callback=progress_callback)
            sentences = {word: sentences[word]+new_sentences[word] for word in words}

        for sentence in sum(sentences.values(), []):
            media_file_ref = self.media_manager.get_ref_for_sentence(sentence.sentence)
            if self.media_manager.check_ref_exists(media_file_ref):
                sentence.audio_file_ref = media_file_ref
            elif ensure_audio:
                sentence.audio_file_ref = self.media_manager.create_audio_file(sentence.sentence)

        if with_furigana: self._add_furigana(sum(sentences.values(),[]))

        return sentences

    def count_lexical_word_ocurrences(self, lexical_words: List[str],
                                      min_comprehensibility: Optional[float] = None) -> Dict[str, int]:
        if min_comprehensibility is not None:
            return self.sentence_db_interface \
                .count_keywords_by_sentence_comprehensibility(lexical_words, min_comprehensibility)
        return self.sentence_db_interface.count_keywords(lexical_words)

    def update_known(self, known_words: Set[str]):
        self.sentence_db_interface.update_known_field(known_words)
        self.sentence_db_interface.update_known_unknown_counts()

    def _produce_new_sentences_for_word(self, word: str, desired_amt: int, ensure_audio=False,
                                        progress_callback: Optional[Callable[..., None]] = None)\
            -> List[ExampleSentence]:
        return self._produce_new_sentences_for_words({word: desired_amt},
                                                     ensure_audio=ensure_audio,
                                                     progress_callback=progress_callback
                                                     )[word]

    def _produce_new_sentences_for_words(self, word_desired_amts: Dict[str, int], ensure_audio=False,
                                         progress_callback: Optional[Callable[..., None]] = None) \
            -> Dict[str, List[ExampleSentence]]:
        """
        does what it says on the tin
        only creates up to amt_desired sentences
        saves them all to the db
        takes care not to insert any repeats or create any unnecessary audio files
        returns created sentences
        """
        is_not_in_db = lambda s: self.sentence_db_interface.check_sentence(s.sentence, commit=False) is None
        sentences = self.sentence_production_manager\
            .find_new_sentences_with_words(word_desired_amts,
                                           filtering_fun=is_not_in_db,
                                           progress_callback=progress_callback)
        for sentence_group in sentences.values():
            for sentence in sentence_group:
                if sentence.audio_file_ref is not None:
                    sentence.audio_file_ref = self.media_manager.intake_external_audio_file(sentence.sentence,
                                                                                            sentence.audio_file_ref)
                elif ensure_audio:
                    sentence.audio_file_ref = self.media_manager.create_audio_file(sentence.sentence)

        all_sentences = sum(sentences.values(), [])
        self.sentence_db_interface.insert_sentences_batched(all_sentences, verify_not_repeated=False)
        return sentences

    def _ingest_starter_sentences(self, max_desired_sentences_per_word: int = SENTENCES_PER_WORD, block_size: int = 50):
        print("SentenceRepository ingesting base corpora...")
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

            if sentence.audio_file_ref is not None:
                sentence.audio_file_ref = self.media_manager.intake_external_audio_file(sentence.sentence,
                                                                                        sentence.audio_file_ref)

            if len(block) == block_size:
                self.sentence_db_interface.insert_sentences_batched(block, verify_not_repeated=False)
                block = []
                sentence_text = set()
        self.sentence_db_interface.insert_sentences_batched(block, verify_not_repeated=False)

    def _add_furigana(self, sentences):
        for sentence in sentences:
            sentence.furigana = add_furigana_html(sentence.sentence, ignore_unknown_words=True)

    def _compute_comprehensibility_of_sentence_outside_repository(self, sentence_text: str):
