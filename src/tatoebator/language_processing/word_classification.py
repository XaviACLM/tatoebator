from enum import Enum

from aqt import mw

from .lexical_analysis import WordSpeechType, group_text_by_part_of_speech


##### ANKI DB SEARCH CLASSIFICATION

def find_relevant_ids():
    # not a real function, just keeping code that will be useful when we make a menu for this
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


class WordInLibraryType(Enum):
    NOT_IN_LIBRARY = 1
    IN_LIBRARY_KNOWN = 2
    IN_LIBRARY_NEW = 3


def search_cards_in_deck(deck_id, notetype_id, field_num, search_strings):
    col = mw.col  # Access the Anki collection

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


# this will have to be read from somewhere later on, with a fancy menu built from the functions in find_relevant_ids
# for now it's just hardcoded.
where_to_search = [(1699173573926, 1437620882055, 1),  # deck_id, notetype_id, field_num
                   (1704665226577, 1629856136563, 0)]


def group_text_by_library(words):
    classified = {kind: set() for kind in WordInLibraryType}
    for where in where_to_search:
        classified_deck = search_cards_in_deck(*where, words)
        for kind in WordInLibraryType:
            classified[kind] = classified[kind].union(classified_deck[kind])
    classified[WordInLibraryType.NOT_IN_LIBRARY] -= classified[WordInLibraryType.IN_LIBRARY_NEW]
    classified[WordInLibraryType.NOT_IN_LIBRARY] -= classified[WordInLibraryType.IN_LIBRARY_KNOWN]
    classified[WordInLibraryType.IN_LIBRARY_NEW] -= classified[WordInLibraryType.IN_LIBRARY_KNOWN]
    return classified


##### FINAL CLASSIFICATION

class WordLearnableType(Enum):
    NEW_WORD = 1
    IN_LIBRARY_KNOWN = 2
    IN_LIBRARY_PENDING = 3
    PROPER_NOUN_NONPERSON = 4
    GRAMMATICAL_WORD = 5
    NOT_IN_DICTIONARY = 6


def group_text_by_learnability(text):
    classified_speech = group_text_by_part_of_speech(text)

    classified = {kind: set() for kind in WordLearnableType}

    classified[WordLearnableType.NOT_IN_DICTIONARY] = classified_speech[WordSpeechType.NOT_IN_DICTIONARY]
    # punctuation is discarded
    classified[WordLearnableType.GRAMMATICAL_WORD] = classified_speech[WordSpeechType.GRAMMATICAL_WORD]
    classified[WordLearnableType.NOT_IN_DICTIONARY] = classified[WordLearnableType.NOT_IN_DICTIONARY].union(
        classified_speech[
            WordSpeechType.PROPER_NOUN_PERSON])
    classified[WordLearnableType.PROPER_NOUN_NONPERSON] = classified_speech[WordSpeechType.PROPER_NOUN_NONPERSON]

    # lexical words are split acc to whether we know them already
    lexical_words = classified_speech[WordSpeechType.LEXICAL_WORD]
    classified_library = group_text_by_library(list(lexical_words))

    classified[WordLearnableType.NEW_WORD] = classified_library[WordInLibraryType.NOT_IN_LIBRARY]
    classified[WordLearnableType.IN_LIBRARY_KNOWN] = classified_library[WordInLibraryType.IN_LIBRARY_KNOWN]
    classified[WordLearnableType.IN_LIBRARY_PENDING] = classified_library[WordInLibraryType.IN_LIBRARY_NEW]

    return classified
