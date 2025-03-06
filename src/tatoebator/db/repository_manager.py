from typing import List, Dict, Set, Optional, Callable
from wsgiref.validate import header_re

from ..audio import MediaManager
from ..constants import SENTENCES_PER_CARD
from ..db.core import SentenceDbInterface
from ..language_processing import add_furigana_html
from ..sentences import ExampleSentence
from ..sentences import SentenceProductionManager


class SentenceRepository:
    def __init__(self, media_manager: MediaManager):
        self.media_manager = media_manager
        self.sentence_production_manager = SentenceProductionManager()
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
        if ensure_audio: self._ensure_sentences_have_audio(sum(sentences.values(), []))
        if with_furigana: self._add_furigana(sum(sentences.values(),[]))

        missing_sentences_by_word = {word: word_desired_amts[word]-len(sentences[word]) for word in words}
        produced_all_desired = max(missing_sentences_by_word.values()) <= 0
        if not produce_new or produced_all_desired:
            return sentences

        new_sentences = self._produce_new_sentences_for_words(missing_sentences_by_word,
                                                              ensure_audio=ensure_audio,
                                                              progress_callback=progress_callback)
        if ensure_audio: self._ensure_sentences_have_audio(sum(new_sentences.values(), []))
        if with_furigana: self._add_furigana(sum(new_sentences.values(),[]))
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

        orphaned_file_ids = existing_audio_ids - referenced_audio_ids
        for orphaned_id in orphaned_file_ids:
            self.media_manager.remove_by_id(orphaned_id)

    def regenerate_missing_audio_files(self):
        # TODO yeah this doesn't make that much sense. will conflict with anki orphaned file cleanup
        #  need to devise a way to do this but only w sentences that actually appear in decks
        #  and moreover cleanup_orphaned_audio_files is likewise bad b/c it will delete word audios
        #  perhaps that one should just never be called. let anki cleanup handle it
        #  but what of this one?
        #  ---
        #  we will need info from anki_db_interface too
        #  guessing a midway object held by Tatoebator that worries about media cleanliness
        #  moreover i think we will take audido out of the db altogether
        #  media_manager is held by the repository and responsible for populating the audio of ExampleSentence objects
        #  internally knows whether they exist, can be passed by arg to relevant functions whether it will create more
        sentences_by_audio_id = self.sentence_db_interface.get_sentence_texts_by_audio_fileid()
        referenced_audio_ids = set(sentences_by_audio_id.keys())
        existing_audio_ids = self.media_manager.get_all_audio_ids()
        orphaned_ids = referenced_audio_ids - existing_audio_ids
        for audio_id in orphaned_ids:
            self.media_manager.create_audio_file(sentences_by_audio_id[audio_id], 0.8, audio_id)

    def update_known(self, known_words: Set[str]):
        self.sentence_db_interface.update_known_field(known_words)
        self.sentence_db_interface.update_known_unknown_counts()

    def _ensure_sentences_have_audio(self, sentences: List[ExampleSentence]):
        updated_sentences = []
        for sentence in sentences:
            if sentence.audio_fileid is None:
                updated_sentences.append(sentence)
                self._add_audio_file_to_sentence(sentence)
        if updated_sentences:
            self.sentence_db_interface.update_audio_file_ids(updated_sentences)

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
        sentences = {word: [] for word in word_desired_amts}
        for word, sentence in self.sentence_production_manager \
                .yield_new_sentences_with_words(word_desired_amts,
                                                filtering_fun=is_not_in_db,
                                                progress_callback=progress_callback):

            if ensure_audio and sentence.audio_fileid is None:
                self._add_audio_file_to_sentence(sentence)

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

    def _add_furigana(self, sentences):
        for sentence in sentences:
            sentence.furigana = add_furigana_html(sentence.sentence, ignore_unknown_words=True)

    def _add_audio_file_to_sentence(self, sentence: ExampleSentence, speed=0.8, desired_id=None):
        sentence.audio_fileid = self.media_manager.create_audio_file(sentence.sentence, speed, desired_id)
