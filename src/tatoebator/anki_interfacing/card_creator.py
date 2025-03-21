from typing import List

import anki.collection

from ..audio import MediaManager
from ..constants import INTER_FIELD_SEPARATOR
from ..language_processing import Definitions, add_furigana_html
from ..sentences import ExampleSentence


class CardCreator:
    def __init__(self, col: anki.collection.Collection, notetype_id: int, media_manager: MediaManager):
        self.col = col
        self.notetype_id = notetype_id
        self.media_manager = media_manager

    def create_note_in_deck(self, deck_id: int, word: str, definitions: Definitions, sentences: List[ExampleSentence]):
        note = self.col.new_note(self.notetype_id)

        word_audio_file_ref = self.media_manager.create_audio_file(word, 0.8, None)

        note['word'] = word
        note['word_audio'] = f'[sound:{word_audio_file_ref}]'
        #note['word_audio'] = word_audio_file_ref'
        note['word_furigana'] = add_furigana_html(word, ignore_unknown_words=True)
        note['definition_eng'] = "\n- ".join(definitions.en)
        note['definition_jpn'] = "\n- ".join(definitions.jp)
        note['sentence_data'] = INTER_FIELD_SEPARATOR.join((INTER_FIELD_SEPARATOR.join([sentence.sentence,
                                                                                        sentence.furigana,
                                                                                        sentence.translation,
                                                                                        #f"[sound:{sentence.audio_file_ref}]",
                                                                                        sentence.audio_file_ref,
                                                                                        sentence.credit])
                                                            for sentence in sentences))
        note['other_data'] = ''

        self.col.add_note(note, deck_id)
