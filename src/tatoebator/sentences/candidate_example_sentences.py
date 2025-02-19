import logging
from enum import Enum
from functools import cached_property
from typing import Optional, List

import re

from ..language_processing import lexical_content, estimate_jp_sentence_distance
from ..language_processing import Translator
from ..language_processing import UnicodeRange as ur


class CandidateExampleSentence:
    """
    class holding a (japanese) example sentence w/ translation that has not yet gone through quality control
     ( quality control will make it into a different class b/c this process also appends some new data )

    about the fields

    sentence is the sentence in japanese. This is the only necessary field on instantiation

    translation is the english translation. This may be None and can be generated (google) with generate_translation()

    lexical content is a list of the dictionary form of lexical words in the sentence.
    may or may not be passed to the constructor (usually not passed). is generated on the spot

    audio_fileid points to a file containing a readout of the sentence.
    will usually be created later (in ExampleSentence, not here), but might be found while crawling
    """

    def __init__(self,
                 sentence: str,
                 translation: Optional[str] = None,
                 lexical_words: Optional[List[str]] = None,
                 audio_fileid: Optional[str] = None,
                 credit: Optional[str] = None
                 ):
        self.sentence = sentence

        self._lexical_words = lexical_words
        self.translation = translation
        self.audio_fileid = audio_fileid
        self.credit = credit

    # the performance loss computing this on init would be minimal
    # but it might save us trouble from calling mecab/sudachi on jumbled up sentences
    @cached_property
    def lexical_words(self):
        return self._lexical_words or lexical_content(self.sentence)

    def generate_translation(self):
        # TODO this shouldn't be here. using google translate to generate a translation is a decision,
        #  no need to 'canonize' it by baking in a function for it much less with this name
        self.translation = Translator.eng_to_jp(self.sentence)

    # these used to be cached
    # (in fact they used to be in an entirely different class that served only to hold caches on Candidates
    # but surely the overhead is insignificant
    @property
    def sentence_len(self):
        return len(self.sentence)

    @property
    def n_lexical_words(self):
        return len(self.lexical_words)


discarded_sentences_logger = logging.getLogger("tatoebator.discarded_sentences")
discarded_sentences_logger.setLevel(logging.INFO)
# mode 'w' because i expect this to be rerun a lot on the same sentences during testing - might change later
discarded_sentences_logger.addHandler(logging.FileHandler("discarded_sentences.log", mode='w', encoding='utf-8'))

strictly_japanese_chars_matcher = re.compile(fr"[{ur.hiragana}{ur.katakana}{ur.kanji}ー]")
format_tags_matcher = re.compile(
    r"nbsp|&quot;|<(?:html|head|body|div|span|h\d|p|br|hr|strong|em|b|i|u|ul|ol|li|a|img|label|tr|td)")
# english_punctuation = ".,!?;:()[]{}'\"“”‘’@#$%^&*-_/+=<>|\\~–—"
english_punctuation = r" .,!?;:()\[\]%'\"“”‘’#$%&-/~–—"
# full width characters here - incl the first space and the numbers
japanese_punctuation = "　。、！？・：％「」『』（）〔〕［］《》【】…‥ー〜〃／―０１２３４５６７８９々"
other_full_width_chars = "０１２３４５６７８９　ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ！＂＇：；～"
newline_or_tab_matcher = re.compile(r"[\n\t]")
known_characters_text_matcher = re.compile(
    fr"[a-zA-Z0-9{ur.hiragana}{ur.katakana}{ur.kanji}" + english_punctuation + japanese_punctuation + other_full_width_chars + "]+")
known_japanese_text_matcher = re.compile(
    fr"[{ur.hiragana}{ur.katakana}{ur.kanji}" + japanese_punctuation + other_full_width_chars + "]+")
known_english_text_matcher = re.compile(r"[a-zA-Z0-9" + english_punctuation + "]+")


class QualityEvaluationResult(Enum):
    UNSUITABLE = -1
    SUITABLE = 0
    GOOD = 1


class ExampleSentenceQualityEvaluator:
    pre_translation_filters = {
        "Not too short": lambda s: s.sentence_len > 5,
        "Not too long": lambda s: s.sentence_len <= 140,
        "Sufficient japanese characters": lambda s: (len(
            re.findall(strictly_japanese_chars_matcher, s.sentence)) / s.sentence_len) > 0.7,
        "No weird format tags": lambda s: re.search(format_tags_matcher, s.sentence) is None,
        "No linebreaks or tabs": lambda s: re.search(newline_or_tab_matcher, s.sentence) is None,
        "No unknown characters": lambda s: re.fullmatch(known_characters_text_matcher, s.sentence) is not None,
    }

    post_translation_filters = {
        "No japanese in translation": lambda s: re.search(strictly_japanese_chars_matcher, s.translation) is None,
        "No weird format tags in translation": lambda s: re.search(format_tags_matcher, s.translation) is None,
        "No linebreaks or tabs in translation": lambda s: re.search(newline_or_tab_matcher, s.translation) is None,
        "No unknown characters in translation": lambda s: re.fullmatch(known_characters_text_matcher,
                                                                       s.translation) is not None,
        "At least two lexical words": lambda s: s.n_lexical_words >= 2,
    }

    extra_quality_filters = {
        "Not too many lexical words": lambda s: s.n_lexical_words <= 20,
        "No english characters": lambda s: re.fullmatch(known_japanese_text_matcher, s.sentence) is not None,
        "No japanese characters in translation": lambda s: re.fullmatch(known_english_text_matcher,
                                                                        s.translation) is not None,
    }

    @classmethod
    def evaluate_quality(cls, example_sentence: CandidateExampleSentence, word: str = None) -> QualityEvaluationResult:

        for filter_name, filter_fun in cls.pre_translation_filters.items():
            if not filter_fun(example_sentence):
                discarded_sentences_logger.info(f'{filter_name} :: {example_sentence.sentence}')
                return QualityEvaluationResult.UNSUITABLE

        if word is not None and word not in example_sentence.lexical_words:
            discarded_sentences_logger.info(f'Requested word must be in lexical content :: {example_sentence.sentence}')
            return QualityEvaluationResult.UNSUITABLE

        # meant to cover translation being empty, but also might be "-" or something like that
        has_translation = example_sentence.translation is not None and len(example_sentence.translation) > 5
        if not has_translation:
            discarded_sentences_logger.info(
                f'Translation must be present :: {example_sentence.sentence} / {example_sentence.translation}'
            )
            return QualityEvaluationResult.UNSUITABLE

        for filter_name, filter_fun in cls.post_translation_filters.items():
            if not filter_fun(example_sentence):
                discarded_sentences_logger.info(
                    f'{filter_name} :: {example_sentence.sentence} / {example_sentence.translation}')
                return QualityEvaluationResult.UNSUITABLE

        # we now know the sentence is good enough. now to see if it goes through the extra checks to be called good

        if not has_translation: return QualityEvaluationResult.SUITABLE
        for filter_name, filter_fun in cls.extra_quality_filters.items():
            if not filter_fun(example_sentence):
                return QualityEvaluationResult.SUITABLE

        return QualityEvaluationResult.GOOD

    @staticmethod
    async def evaluate_translation_quality(example_sentence: CandidateExampleSentence,
                                           machine_translation: Optional[str] = None) -> QualityEvaluationResult:
        # careful! translation, and so this filter, is not deterministic
        # this is fine - the filter's design accepts having a significant amount of false negatives
        # as long as we get very little false positives that's fine
        # TODO would be good to execute this check two or three times for sentences where we don't have enough examples
        #  complicated to pass that signal all the way down here, though
        if machine_translation is None:
            machine_translation = await Translator.async_eng_to_jp(example_sentence.translation)
        if estimate_jp_sentence_distance(example_sentence.sentence, machine_translation) >= 0.15:
            discarded_sentences_logger.info(
                f'Sentence must reasonably match machine translation of translation :: {example_sentence.sentence} / {example_sentence.translation}'
            )
            return QualityEvaluationResult.UNSUITABLE
        return QualityEvaluationResult.SUITABLE
