# TODO this is a bit a mess for now, gotta clean up this interface

from .word_classification import group_text_by_learnability, WordLearnableType
from .online_dictionaries import get_definition_from_weblio, get_meaning_from_tanoshii
from .lexical_analysis import lexical_content
from .translator import translate
from .unicode_ranges import UnicodeRange