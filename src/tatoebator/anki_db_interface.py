import os
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Tuple

import anki.collection
from aqt import mw

from .constants import PATH_TO_USER_FILES
from .language_extensions import TransientSingleton
from .persistence import PossiblyEmptyPersistable


@dataclass(frozen=True)
class FieldPointer:
    deck_id: int
    notetype_id: int
    field_ord: int


class VocabFieldRegistry(List, PossiblyEmptyPersistable, TransientSingleton):
    default_filepath = os.path.join(PATH_TO_USER_FILES, "vocab_field_registry.ejson")

    def __init__(self, field_pointers: List[FieldPointer]):
        super().__init__(field_pointers)  # list.__init__
        self.field_pointers = self  # oh no

    @classmethod
    def empty(cls):
        return cls([])


class TatoebatorAnkiObjectRegistrar(PossiblyEmptyPersistable):
    default_filepath = os.path.join(PATH_TO_USER_FILES, "anki_id_registrar.ejson")

    default_tatoebator_deck_name = "Tatoebator Mined Vocab"
    default_tatoebator_notetype_name = "Tatoebator Notetype"

    recognition_cardtype_name = "Recognition"
    recognition_vocab_field_ord = 1  # TODO or is it 0?

    def __init__(self,
                 deck_id: Optional[int],
                 notetype_id: Optional[int]):
        self.deck_id = deck_id
        self.notetype_id = notetype_id

    @classmethod
    def empty(cls):
        return cls(None, None)

    @property
    def field_pointer(self):
        return FieldPointer(self.deck_id, self.notetype_id, self.recognition_vocab_field_ord)

    def ensure_objects_exist(self, col: anki.collection.Collection):
        self._ensure_deck(col)
        self._ensure_notetype(col)
        self.save()

    def _ensure_deck(self, col: anki.collection.Collection):
        id_ = self.deck_id
        if id_ is None or id_ != col.decks.get(id_)['id']:
            self._create_tatoebator_deck(col)

    def _create_tatoebator_deck(self, col: anki.collection.Collection):
        deck = col.decks.new_deck()
        deck.name = self.default_tatoebator_deck_name
        id_ = col.decks.add_deck(deck).id
        self.deck_id = id_

    def _ensure_notetype(self, col: anki.collection.Collection):
        id_ = self.notetype_id
        if id_ is None or col.models.get(id_) is None:
            self._create_tatoebator_notetype(col)

    def _create_tatoebator_notetype(self, col: anki.collection.Collection):
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
{{word_audio}} {{word_furigana}}
<hr>
<p id='definition_eng_elem'>{{definition_eng}}\n</p>
<p id='definition_jpn_elem'>{{definition_jpn}}\n</p>
{{sentence_data}}
{{other_data}}

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

        self.notetype_id = id_


class WordInLibraryType(Enum):
    NOT_IN_LIBRARY = 1
    IN_LIBRARY_KNOWN = 2
    IN_LIBRARY_NEW = 3


class AnkiDbInterface:

    def __init__(self):
        self.col = mw.col
        self.other_vocab_fields = VocabFieldRegistry.load_or_create()
        self.tatoebator_objects = TatoebatorAnkiObjectRegistrar.load_or_create()

        self.tatoebator_objects.ensure_objects_exist(self.col)

        # self.col.genCards

    def _get_deck_ids_by_name(self) -> Dict[str, int]:
        col = self.col
        return {name: id_ for id_, name in self.col.db.all("SELECT id,name FROM decks")}

    def _get_notetypes_and_fields_in_deck(self, deck_id: int) -> Tuple[Dict[str, int], Dict[str, Dict[str, int]]]:
        # notetype ids - notetype names - field names - field ords in a certain deck
        data = self.col.db.all(f"SELECT f.ntid, nt.name, f.ord, f.name AS notetype_name\
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

        notetype_ids_by_name = {name: id_ for id_, name, _, _ in data}  # some repeats - should be fine
        field_ords_by_name = {name: dict() for name in notetype_ids_by_name}
        for _, notetype_name, field_ord, field_name in data:
            field_ords_by_name[notetype_name][field_name] = field_ord

        return notetype_ids_by_name, field_ords_by_name

    def get_all_field_data(self) -> Tuple[
        Dict[str, int], Dict[str, Dict[str, int]], Dict[str, Dict[str, Dict[str, int]]]]:
        deck_ids_by_name = self._get_deck_ids_by_name()
        notetype_ids_by_names = {deck_name: dict() for deck_name in deck_ids_by_name}
        field_ords_by_names = {deck_name: dict() for deck_name in deck_ids_by_name}
        for deck_name, deck_id in deck_ids_by_name.items():
            notetype_ids_by_name, field_ords_by_name = self._get_notetypes_and_fields_in_deck(deck_id)
            notetype_ids_by_names[deck_name] = notetype_ids_by_name
            field_ords_by_names[deck_name] = field_ords_by_name
        return deck_ids_by_name, notetype_ids_by_names, field_ords_by_names

    def _search_cards_in_deck(self, field_pointer: FieldPointer, search_strings):
        col = self.col

        query = f"""
            SELECT 
                field_at_index(n.flds, {field_pointer.field_ord}) AS string, 
                c.ivl AS ivl
            FROM notes n
            JOIN cards c ON n.id = c.nid
            WHERE n.mid = {field_pointer.notetype_id} AND c.did = {field_pointer.deck_id} 
                  AND field_at_index(n.flds, {field_pointer.field_ord}) IN ({",".join((f'"s"' for s in search_strings))})
        """

        data = col.db.all(query)

        # Separate known and pending words
        known_words = {row[0] for row in data if row[1] > 0}
        pending_words = {row[0] for row in data if row[1] <= 0} - known_words  # in case there's more than one cardtype
        unknown_words = set(search_strings) - known_words - pending_words

        return {WordInLibraryType.NOT_IN_LIBRARY: unknown_words,
                WordInLibraryType.IN_LIBRARY_KNOWN: known_words,
                WordInLibraryType.IN_LIBRARY_NEW: pending_words, }

    def _get_known_words_in_deck(self, field_pointer: FieldPointer):
        col = self.col

        col.db.all(f"CREATE TEMPORARY TABLE results AS\
                    SELECT field_at_index(n.flds, {field_pointer.field_ord}) AS string, c.ivl AS ivl\
                    FROM notes n\
                    JOIN cards c ON n.id = c.nid\
                    WHERE n.mid = {field_pointer.notetype_id} AND c.did = {field_pointer.deck_id}")

        data_known = col.db.all("SELECT string FROM results WHERE ivl > 0")
        col.db.all("DROP TABLE results")

        known_words = set([row[0] for row in data_known])
        return known_words

    def group_text_by_library(self, words):
        classified = {kind: set() for kind in WordInLibraryType}
        for field_pointer in self.other_vocab_fields:
            classified_deck = self._search_cards_in_deck(field_pointer, words)
            for kind in WordInLibraryType:
                classified[kind] = classified[kind].union(classified_deck[kind])
        classified[WordInLibraryType.NOT_IN_LIBRARY] -= classified[WordInLibraryType.IN_LIBRARY_NEW]
        classified[WordInLibraryType.NOT_IN_LIBRARY] -= classified[WordInLibraryType.IN_LIBRARY_KNOWN]
        classified[WordInLibraryType.IN_LIBRARY_NEW] -= classified[WordInLibraryType.IN_LIBRARY_KNOWN]
        return classified

    def get_known_words(self):
        known_words = set()
        for field_pointer in self.other_vocab_fields:
            known_words.update(self._get_known_words_in_deck(field_pointer))
        return known_words
