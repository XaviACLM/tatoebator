from enum import Enum

from aqt import mw
from aqt.utils import showInfo


class WordInLibraryType(Enum):
    NOT_IN_LIBRARY = 1
    IN_LIBRARY_KNOWN = 2
    IN_LIBRARY_NEW = 3


class AnkiDbInterface:
    def __init__(self):
        # TODO
        #  this will have to be read from somewhere later, with a fancy menu built from the functions in find_relevant_ids
        #  for now it's just hardcoded.
        self.other_vocabulary_decks = [(1699173573926, 1437620882055, 1),  # deck_id, notetype_id, field_num
                                       (1704665226577, 1629856136563, 0)]

    # not a real function, just keeping code that will be useful when we make a menu for this
    def find_relevant_ids(self):
        col = mw.col

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
    @staticmethod
    def _search_cards_in_deck(deck_id, notetype_id, field_num, search_strings):
        col = mw.col

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

    @staticmethod
    def _get_known_words_in_deck(deck_id, notetype_id, field_num):
        col = mw.col

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
        for deck_id, notetype_id, field_num in self.other_vocabulary_decks:
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


