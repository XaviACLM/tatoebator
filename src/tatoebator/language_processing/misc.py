import re

from .unicode_ranges import UnicodeRange as ur

strictly_japanese_chars_matcher = re.compile(fr"[{ur.hiragana}{ur.katakana}{ur.kanji}ー]")


def japanese_chars_ratio(text: str):
    return len(re.findall(strictly_japanese_chars_matcher, text)) / len(text)