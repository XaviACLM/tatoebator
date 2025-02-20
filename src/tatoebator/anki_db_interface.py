import os
from dataclasses import dataclass
import time
from enum import Enum
from typing import List, Optional

from aqt import mw
from aqt.utils import showInfo

from .constants import PATH_TO_USER_FILES
from .persistence import Persistable


@dataclass
class FieldPointer:
    deck_id: int
    notetype_id: int
    field_num: int


class AnkiObjectIdRegistry(Persistable):

    default_filepath = os.path.join(PATH_TO_USER_FILES, "anki_object_id_registry.ejson")

    def __init__(self,
                 tatoebator_deck_id: Optional[int],
                 tatoebator_deck_name: Optional[str],
                 tatoebator_notetype_id: Optional[int],
                 tatoebator_notetype_name: Optional[str],
                 other_vocab_fields: List[FieldPointer]):
        self.tatoebator_deck_id = tatoebator_deck_id
        self.tatoebator_deck_name = tatoebator_deck_name
        self.tatoebator_notetype_id = tatoebator_notetype_id
        self.tatoebator_notetype_name = tatoebator_notetype_name
        self.other_vocab_fields = other_vocab_fields

    @classmethod
    def my_default(cls):
        # TODO
        #  this will have to be read from somewhere later, with a fancy menu built from the functions in find_relevant_ids
        #  for now it's just hardcoded.
        return cls(None, None, None, None,
                   [FieldPointer(1699173573926, 1437620882055, 1),
                    FieldPointer(1704665226577, 1629856136563, 0)])
        # return cls(1740128400011, "Tatoebator Mined Vocab", 1740128400012, "Tatoebator Notetype",


class WordInLibraryType(Enum):
    NOT_IN_LIBRARY = 1
    IN_LIBRARY_KNOWN = 2
    IN_LIBRARY_NEW = 3


class AnkiDbInterface:

    default_tatoebator_deck_name = "Tatoebator Mined Vocab"
    default_tatoebator_notetype_name = "Tatoebator Notetype"

    recognition_cardtype_name = "Recognition"

    def __init__(self):
        self.col = mw.col
        self.registry = AnkiObjectIdRegistry.load()
        self.other_vocabulary_decks = [(1699173573926, 1437620882055, 1),  # deck_id, notetype_id, field_num
                                       (1704665226577, 1629856136563, 0)]
        self._ensure_tatoebator_deck()
        self._ensure_tatoebator_nonetype()

    def _ensure_tatoebator_deck(self):
        id_ = self.registry.tatoebator_deck_id
        if id_ is None or id_ != self.col.decks.get(id_)['id']:
            self._create_tatoebator_deck()

    def _create_tatoebator_deck(self):
        deck = self.col.decks.new_deck()
        deck.name = self.default_tatoebator_deck_name
        id_ = self.col.decks.add_deck(deck).id
        self.registry.tatoebator_deck_id = id_
        self.registry.tatoebator_deck_name = deck.name
        self.registry.save()

    def _ensure_tatoebator_nonetype(self):
        id_ = self.registry.tatoebator_notetype_id
        if id_ is None or self.col.models.get(id_) is None:
            self._create_tatoebator_nonetype()

    def _create_tatoebator_nonetype(self):
        col = self.col

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

        # css
        '''
        m[
            "css"
        ] += """\
    .jp { font-size: 30px }
    .win .jp { font-family: "MS Mincho", "ＭＳ 明朝"; }
    .mac .jp { font-family: "Hiragino Mincho Pro", "ヒラギノ明朝 Pro"; }
    .linux .jp { font-family: "Kochi Mincho", "東風明朝"; }
    .mobile .jp { font-family: "Hiragino Mincho ProN"; }"""
        '''

        t["qfmt"] = "{{word_audio}} {{word_furigana}}"

        t["afmt"] = """\
{{word_audio}} {{word_furigana}}\n\n<hr>\n
<p id='definition_eng_elem'>{{definition_eng}}\n</p>
<p id='definition_jpn_elem'>{{definition_jpn}}\n</p>
\n\n{{sentence_data}}
\n\n{{other_data}}

<script>
    function hideIfEmpty(elem_id) {
        const elem = document.getElementById(elem_id);
        const content = elem.textContent.trim(); // Trim newlines
        if (content === "") {
            elem.style.display = 'none';
        }
    }
    hideIfEmpty("definition_eng_elem");
    hideIfEmpty("definition_jpn_elem");
</script>
"""
        mm.addTemplate(m, t)
        id_ = mm.add(m).id

        self.registry.tatoebator_notetype_id = id_
        self.registry.tatoebator_notetype_name = self.default_tatoebator_notetype_name
        self.registry.save()


    # not a real function, just keeping code that will be useful when we make a menu for this
    def find_relevant_ids(self):
        col = self.col

        # get all deck names
        deck_name_ids = col.db.all("SELECT id,name FROM decks")

        # id corresponding to a deck name
        (deck_id,), = col.db.all("SELECT id FROM decks WHERE name = 'Japanese\x1fCore2.3k Version 3'")
        showInfo(f"{deck_id}")

        # notetype ids - notetype names - field names - field ords in a certain deck

        data = col.db.all(f"SELECT f.ntid, f.ord, f.name, nt.name AS notetype_name\
                    FROM fields f\
                    JOIN notetypes nt ON f.ntid = nt.id\
                    WHERE nt.id IN (\
                        SELECT mid\
                        FROM notes\
                        WHERE id IN (\
                            SELECT nid\
                            FROM cards\
                            WHERE did = {deck_id}\
                        )\
                    );")
        showInfo(f"{data}")

    # eventually this kind of thing will probably be segregated
    # when we need to do things like get specific cards to suspend them or change the random sentence fields
    # but we won't know the requirements until then so let's keep it as is
    def _search_cards_in_deck(self, deck_id, notetype_id, field_num, search_strings):
        col = self.col

        col.db.all("DROP TABLE IF EXISTS search_strings")
        col.db.all("DROP TABLE IF EXISTS string_ntid")
        col.db.all("DROP TABLE IF EXISTS results")

        # and now for the muxing business

        col.db.all("CREATE TEMPORARY TABLE search_strings (search_string TEXT)")
        for search_string in search_strings:
            col.db.all(f"INSERT INTO search_strings (search_string) VALUES ('{search_string}')")

        col.db.all(f"CREATE TEMPORARY TABLE string_ntid AS\
                    SELECT ss.search_string AS string, n.id AS nid\
                    FROM search_strings ss\
                    JOIN notes n ON field_at_index(n.flds, {field_num}) = ss.search_string\
                    WHERE n.mid = {notetype_id};")
        col.db.all("DROP TABLE search_strings")

        data = col.db.all(f"CREATE TEMPORARY TABLE results AS\
                    SELECT sn.string AS string, c.ivl AS ivl\
                    FROM string_ntid sn JOIN cards c ON sn.nid = c.nid\
                    WHERE c.did = {deck_id}")
        col.db.all("DROP TABLE string_ntid")

        data_known = col.db.all("SELECT string FROM results WHERE ivl > 0")
        data_pending = col.db.all("SELECT string FROM results WHERE ivl <= 0")
        col.db.all("DROP TABLE results")

        known_words = set([row[0] for row in data_known])
        pending_words = set([row[0] for row in data_pending])
        unknown_words = set(search_strings) - known_words - pending_words

        return {WordInLibraryType.NOT_IN_LIBRARY: unknown_words,
                WordInLibraryType.IN_LIBRARY_KNOWN: known_words,
                WordInLibraryType.IN_LIBRARY_NEW: pending_words, }

    def _get_known_words_in_deck(self, deck_id, notetype_id, field_num):
        col = self.col

        col.db.all(f"CREATE TEMPORARY TABLE results AS\
                    SELECT field_at_index(n.flds, {field_num}) AS string, c.ivl AS ivl\
                    FROM notes n\
                    JOIN cards c ON n.id = c.nid\
                    WHERE n.mid = {notetype_id} AND c.did = {deck_id}")

        data_known = col.db.all("SELECT string FROM results WHERE ivl > 0")
        col.db.all("DROP TABLE results")

        known_words = set([row[0] for row in data_known])
        return known_words

    def group_text_by_library(self, words):
        classified = {kind: set() for kind in WordInLibraryType}
        for deck_id, notetype_id, field_num in self.tracker.registry.other_vocab_fields:
            classified_deck = self._search_cards_in_deck(deck_id, notetype_id, field_num, words)
            for kind in WordInLibraryType:
                classified[kind] = classified[kind].union(classified_deck[kind])
        classified[WordInLibraryType.NOT_IN_LIBRARY] -= classified[WordInLibraryType.IN_LIBRARY_NEW]
        classified[WordInLibraryType.NOT_IN_LIBRARY] -= classified[WordInLibraryType.IN_LIBRARY_KNOWN]
        classified[WordInLibraryType.IN_LIBRARY_NEW] -= classified[WordInLibraryType.IN_LIBRARY_KNOWN]
        return classified

    def get_known_words(self):
        known_words = set()
        for deck_id, notetype_id, field_num in self.other_vocabulary_decks:
            known_words.update(self._get_known_words_in_deck(deck_id, notetype_id, field_num))
        return known_words


