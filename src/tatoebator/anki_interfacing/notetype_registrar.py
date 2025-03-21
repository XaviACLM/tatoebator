import os
from typing import Optional

import anki.collection

from ..config import SENTENCES_PER_CARD_FRONT, SENTENCES_PER_CARD_BACK
from ..constants import PATH_TO_USER_FILES
from ..persistence import PossiblyEmptyPersistable


class NotetypeRegistrar(PossiblyEmptyPersistable):
    default_filepath = os.path.join(PATH_TO_USER_FILES, "notetype_id.ejson")

    default_tatoebator_notetype_name = "Tatoebator Notetype"

    recognition_cardtype_name = "Recognition"

    def __init__(self, notetype_id: Optional[int]):
        self.notetype_id = notetype_id

    @classmethod
    def empty(cls):
        return cls(None)

    def ensure_notetype_exists(self, col: anki.collection.Collection):
        id_ = self.notetype_id
        if id_ is None or col.models.get(id_) is None:
            self._create_notetype(col)
            self.save()

    def _create_notetype(self, col: anki.collection.Collection):
        mm = col.models
        m = mm.new(self.default_tatoebator_notetype_name)

        mm.addField(m, mm.new_field("word"))
        mm.addField(m, mm.new_field("word_audio"))
        mm.addField(m, mm.new_field("word_furigana"))
        mm.addField(m, mm.new_field("definition_eng"))
        mm.addField(m, mm.new_field("definition_jpn"))
        mm.addField(m, mm.new_field("sentence_data"))
        mm.addField(m, mm.new_field("other_data"))

        t = mm.new_template(self.recognition_cardtype_name)

        local_dir, _ = os.path.split(__file__)

        with open(os.path.join(local_dir, 'card_template/style.css'), 'r') as f:
            m["css"] = f.read()
        with open(os.path.join(local_dir, 'card_template/front.html'), 'r') as f:
            front_html = f.read()
        front_html = front_html.replace("<<REPLACE_TAG:max_amt_sentences_front>>", str(SENTENCES_PER_CARD_FRONT))
        front_html = front_html.replace("<<REPLACE_TAG:max_amt_sentences_back>>", str(SENTENCES_PER_CARD_BACK))
        t["qfmt"] = front_html
        with open(os.path.join(local_dir, 'card_template/back.html'), 'r') as f:
            t["afmt"] = f.read()

        mm.addTemplate(m, t)
        id_ = mm.add(m).id

        self.notetype_id = id_
