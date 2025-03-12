import json
import os
import re
from functools import cached_property

from .unicode_ranges import UnicodeRange as ur, UnicodeRange
from ..constants import PATH_TO_OTHER_DATA

_strictly_japanese_chars_matcher = re.compile(fr"[{ur.hiragana}{ur.katakana}{ur.kanji}ー]")


def japanese_chars_ratio(text: str) -> float:
    return len(re.findall(_strictly_japanese_chars_matcher, text)) / len(text)


def approximate_jp_root_form(word: str) -> str:
    return word[:-1] if word[-1] in "いうくすつぬふむゆるぐずづぶぷ" else word


class _JpSentenceSimilarityEstimator:
    kanji_matcher = re.compile(fr"[{UnicodeRange.kanji}]")

    def __init__(self):
        self.path = os.path.join(PATH_TO_OTHER_DATA, "dembeddings.json")

    @cached_property
    def related_pairs(self):
        with open(self.path, "r") as f:
            distances = json.load(f)["nearest"]
        return {kanji: list(close_kanji.keys()) for kanji, close_kanji in distances.items()}

    def distance(self, k1, k2):
        if k1 == k2: return 0
        neighbors = self.related_pairs.get(k1, None)
        if neighbors is None: return 0  # ignore unknown kanji (obs. this dist is not symmetric)
        return int(k2 not in neighbors)

    def distance_one_to_many(self, k, ks):
        return min((self.distance(k, k2) for k2 in ks))

    def distance_many_to_many(self, ks1, ks2):
        return (sum((self.distance_one_to_many(k1, ks2) for k1 in ks1))
                + sum((self.distance_one_to_many(k2, ks1) for k2 in ks2)))

    def distance_sentences(self, jp_text_1, jp_text_2):
        kanji_1 = self.kanji_matcher.findall(jp_text_1)
        kanji_2 = self.kanji_matcher.findall(jp_text_2)
        if not (kanji_1 and kanji_2):
            return 1  # will catch a lot of good sentences but cannot be helped
        return self.distance_many_to_many(kanji_1, kanji_2) / max(10, len(kanji_1) + len(kanji_2))


estimate_jp_sentence_distance = _JpSentenceSimilarityEstimator().distance_sentences
