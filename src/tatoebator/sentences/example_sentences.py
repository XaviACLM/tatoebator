from typing import Optional

from .candidate_example_sentences import CandidateExampleSentence


class ExternalFileRef(str):
    pass


class ExampleSentence(CandidateExampleSentence):
    def __init__(self,
                 sentence: str,
                 translation: str,
                 lexical_words: [str],
                 audio_file_ref: Optional[str],
                 source_tag: int,
                 trusted: bool,
                 furigana: Optional[str] = None,
                 credit: Optional[str] = None,
                 n_known_words: Optional[int] = None):
        super().__init__(sentence, translation, lexical_words, audio_file_ref, credit)
        self.source_tag = source_tag
        self.furigana = furigana
        self.trusted = trusted
        self.n_known_words = n_known_words

    @classmethod
    def from_candidate(cls, s: CandidateExampleSentence,
                       source_tag: int,
                       trusted: bool,
                       furigana: Optional[str] = None,
                       n_known_words: Optional[int] = None):
        return cls(s.sentence, s.translation, s.lexical_words,
                   None if s.audio_file_ref is None else ExternalFileRef(s.audio_file_ref),
                   source_tag, trusted, furigana, s.credit, n_known_words)

    @property
    def n_unknown_words(self):
        # return self.n_known_words and self.n_lexical_words - self.n_known_words
        if self.n_known_words is None:
            return None
        else:
            return self.n_lexical_words - self.n_known_words

    @property
    def known_ratio(self):
        return self.n_known_words/self.n_lexical_words
