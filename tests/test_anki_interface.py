# needs to be actually run from inside anki - (i.e. paste this as a function in Tatoebator
# mb eventually we'll figure out a more elegant way to run these kinds of tests

def anki_db_test(self):
    fp = self.anki_db_interface.registry.other_vocab_fields[0]

    print(self.anki_db_interface._search_cards_in_deck(fp.deck_id, fp.notetype_id, fp.field_ord,
                                                       ["こんにちは", "ありがとう", "はい", "いいえ", "お願いします",
                                                        "すみません", "ごめんなさい", "おはよう", "こんばんは",
                                                        "さようなら"]))
    print(self.anki_db_interface._search_cards_in_deck_2(fp.deck_id, fp.notetype_id, fp.field_ord,
                                                         ["こんにちは", "ありがとう", "はい", "いいえ", "お願いします",
                                                          "すみません", "ごめんなさい", "おはよう", "こんばんは",
                                                          "さようなら"]))