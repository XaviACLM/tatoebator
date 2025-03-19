from enum import Enum
from typing import Dict, Tuple, Set

from aqt import mw

from tatoebator.anki_interfacing.card_creator import CardCreator
from tatoebator.anki_interfacing.notetype_registrar import NotetypeRegistrar
from tatoebator.anki_interfacing.vocab_field_registry import FieldPointer, VocabFieldRegistry
from tatoebator.audio import MediaManager


class WordInLibraryType(Enum):
    NOT_IN_LIBRARY = 1
    IN_LIBRARY_KNOWN = 2
    IN_LIBRARY_NEW = 3


class AnkiDbInterface:

    def __init__(self, media_manager: MediaManager):
        self.col = mw.col
        self.other_vocab_fields = VocabFieldRegistry.load_or_create()

        notetype_registrar = NotetypeRegistrar.load_or_create()
        notetype_registrar.ensure_notetype_exists()
        self.tatoebator_notetype_id = notetype_registrar.notetype_id

        self.card_creator = CardCreator(self.col, self.tatoebator_notetype_id, media_manager)

    def create_new_deck(self, deck_name: str) -> int:
        col = self.col
        deck = col.decks.new_deck()
        deck.name = deck_name
        id_ = col.decks.add_deck(deck).id
        return id_

    def get_deck_ids_by_name(self) -> Dict[str, int]:
        return {name: id_ for id_, name in self.col.db.all("SELECT id,name FROM decks")}

    def _get_notetype_ids_in_deck(self, deck_id: int) -> Set[int]:
        data = self.col.db.all(f"SELECT DISTINCT nid FROM cards WHERE did = {deck_id}")
        return set(data)

    def does_deck_contain_non_tatoebator_notetypes(self, deck_id: int):
        return len(self._get_notetype_ids_in_deck(deck_id) - {self.tatoebator_notetype_id}) > 0

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
        deck_ids_by_name = self.get_deck_ids_by_name()
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
                  AND field_at_index(n.flds, {field_pointer.field_ord}) IN ({",".join((f'"{s}"' for s in search_strings))})
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
