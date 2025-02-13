import re
from enum import Enum
from typing import List, Dict

from .morphological_analyzers import DefaultTokenizer, Morpheme

tokenizer = DefaultTokenizer()

punctuation_tags = {'記号'}

punctuation_tags = {"記号", "補助記号", "空白"}  # auxiliary symbols (jp punctuation), "blank" (unrecognized symbols, i think?)
grammatical_word_tags = {"格助詞", "助詞", "助動詞"}  # case particles, particles, helper verbs
person_name_tags = {"人名"}
proper_noun_tags = {"固有名詞"}
latin_matcher = re.compile(r'[a-zA-Z]')

# this is a very gray category - e.g. "おく" could also be here but i think it's used more often in its literal sense
# の is only classed as lexical by mecab when its used as a nominalizer. similar idea with ない
grammaticalized_words = {"する", "ある", "いる", "やる", "の", "もの", "こと", "ない"}

hardcoded_grammar_words = {"ら", "たち"}


class WordSpeechType(Enum):
    NOT_IN_DICTIONARY = 1
    PUNCTUATION = 2
    GRAMMATICAL_WORD = 3
    PROPER_NOUN_PERSON = 4
    PROPER_NOUN_NONPERSON = 5
    LEXICAL_WORD = 6


def classify_morpheme(morpheme: Morpheme):
    # might be better to use jisho here. i don't know how large this dict is anyway
    if morpheme.is_oov or latin_matcher.search(morpheme.surface):
        return WordSpeechType.NOT_IN_DICTIONARY
    part_of_speech = morpheme.part_of_speech
    if punctuation_tags.intersection(part_of_speech):
        return WordSpeechType.PUNCTUATION
    if grammatical_word_tags.intersection(part_of_speech) \
            or morpheme.dictionary_form in hardcoded_grammar_words:
        return WordSpeechType.GRAMMATICAL_WORD
    if person_name_tags.intersection(part_of_speech):
        return WordSpeechType.PROPER_NOUN_PERSON
    if proper_noun_tags.intersection(part_of_speech):
        return WordSpeechType.PROPER_NOUN_NONPERSON
    return WordSpeechType.LEXICAL_WORD


def group_text_by_part_of_speech(text) -> Dict[WordSpeechType, List[str]]:
    morphemes = tokenizer(text)
    classified = {kind: [] for kind in WordSpeechType}
    for morpheme in morphemes:
        kind = classify_morpheme(morpheme)
        classified[kind].append(morpheme.dictionary_form)
    classified = {k: set(v) for k, v in classified.items()}

    return classified


def lexical_content(text):
    return [m.dictionary_form
            for m in tokenizer(text)
            if classify_morpheme(m) == WordSpeechType.LEXICAL_WORD]
