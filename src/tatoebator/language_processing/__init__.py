from .furigana import add_furigana_plaintext, add_furigana_html
from .lexical_analysis import lexical_content, grammaticalized_words, WordSpeechType, group_text_by_part_of_speech
from .misc import japanese_chars_ratio, approximate_jp_root_form, estimate_jp_sentence_distance
from .morphological_analyzers import dictionary_form, DefaultTokenizer
from .online_dictionaries import DefinitionFetcher, Definitions
from .translator import Translator
from .unicode_ranges import UnicodeRange
