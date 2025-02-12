from enum import Enum

from .lexical_analysis import WordSpeechType, group_text_by_part_of_speech
from ..anki_db_interface import AnkiDbInterface, WordInLibraryType


class WordLearnableType(Enum):
    NEW_WORD = 1
    IN_LIBRARY_KNOWN = 2
    IN_LIBRARY_PENDING = 3
    PROPER_NOUN_NONPERSON = 4
    GRAMMATICAL_WORD = 5
    NOT_IN_DICTIONARY = 6


def group_text_by_learnability(text, anki_db_interface: AnkiDbInterface):
    classified_speech = group_text_by_part_of_speech(text)

    classified = {kind: set() for kind in WordLearnableType}

    classified[WordLearnableType.NOT_IN_DICTIONARY] = classified_speech[WordSpeechType.NOT_IN_DICTIONARY]
    # punctuation is discarded
    classified[WordLearnableType.GRAMMATICAL_WORD] = classified_speech[WordSpeechType.GRAMMATICAL_WORD]
    classified[WordLearnableType.NOT_IN_DICTIONARY] = classified[WordLearnableType.NOT_IN_DICTIONARY].union(
        classified_speech[
            WordSpeechType.PROPER_NOUN_PERSON])
    classified[WordLearnableType.PROPER_NOUN_NONPERSON] = classified_speech[WordSpeechType.PROPER_NOUN_NONPERSON]

    # lexical words are split acc to whether we know them already
    lexical_words = classified_speech[WordSpeechType.LEXICAL_WORD]
    classified_library = anki_db_interface.group_text_by_library(list(lexical_words))

    classified[WordLearnableType.NEW_WORD] = classified_library[WordInLibraryType.NOT_IN_LIBRARY]
    classified[WordLearnableType.IN_LIBRARY_KNOWN] = classified_library[WordInLibraryType.IN_LIBRARY_KNOWN]
    classified[WordLearnableType.IN_LIBRARY_PENDING] = classified_library[WordInLibraryType.IN_LIBRARY_NEW]

    return classified
