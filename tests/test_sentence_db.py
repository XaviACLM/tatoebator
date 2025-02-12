
from tatoebator.db import SentenceDbManager

# TODO stop propagating output from every cli ever


# TODO make the tanoshii searcher better: there was some old concern i don't remember
# TODO also, include too translations and definitions from "Definition and synonyms for...
# TODO tangorin definitions are also good
# TODO add new sentences menu (with semi automatic translations)
# TODO gen translation/definition is a button, fields are editable
# TODO include/don't include in table menu
# TODO warnings in table menu (low amt of sentences, not-that-lexical word...)
# TODO progress bars



# TODO decide on the logic for when to call update_known_unknown_words
# TODO interface (or manager?) logic that uses known_words and trusted fields to decide what to query
# TODO maybe aspm only inserts new sentences if MORE than one word is underrepresented in the db

# TODO type annotations, docs, privating...


# TODO figure out the general flow of the app. user stories or whatever. when do we actually need to use the sentence db?
#  main bits of gui
#  the miner
#  post-miner sentence adder
#  standalone sentence adder
#  the cards themselves (when do the notes get created? must be in the table gui, no?
#  and some config or whatever
#   particularly as relates to marking relevant fields in other notetypes in other decks
#   which will affect some kind of AnkiDbManager



# CC-BY 2.0 : we can do anything as long as we credit properly, indicate changes, and propagate the license
# A note on propagating the license - from what I understand this doesnt' mean the whole project has to be CC-BY 2.0, just the data

# include other corpora:
# https://www.phontron.com/japanese-translation-data.php
# https://www.kaggle.com/discussions/general/39500
# https://www.kaggle.com/code/vennaa/notebook-accessing-the-data/notebook




#maybe eventually? https://eow.alc.co.jp/search?q=%e3%81%99%e3%82%8b -> translations, usage, but ehh

#TODO implement a couple other sources for translations and definitions (jisho, tangorin)
#TODO - tanoshii japanese multiple block search may also match based on alternate written forms

#TODO some stuff like suru, aru, ra, tachi might be best to specifically exclude - best left to a grammar deck
#if nothing else, dake seems less complex than suru but it's a grammar word anyway

#TODO progress indicators for generation of everything on the table
#TODO "generate everything" button
#TODO ability to select/unselect words within table

#TODO hide cmd's (sudachi?) and voicevoxes

#TODO create notetype, deck
#TODO note creation
#TODO card html - esp care w the logic on the sentences - separate known, discard remainder if have enough, etc
#and the random sorting, minute-based

#TODO port decks (incl. rtk to migaku... somehow?)

#TODO furigana - in db? might be unnecessarily large, so we can take an audio-like approach




sentence_db_manager = SentenceDbManager()

def word_test(word="煙"):
    _, sentences = sentence_db_manager.get_sentences(word, 40, ensure_audio=False, produce_new=True)
    print("returned",len(sentences),"sentences")
    for example_sentence in sentences:
        print(example_sentence.sentence)
        print(example_sentence.translation)
        print(example_sentence.lexical_words)
        print(example_sentence.audio_fileid)
        print(example_sentence.source_tag)
        print(example_sentence.trusted)
        print(example_sentence.n_lexical_words)
        print(example_sentence.n_known_words)
        print(example_sentence.n_unknown_words)
        print(example_sentence.credit)
        print("")

def common_words_test():
    words = ["こんにちは","ありがとう","はい","いいえ","お願いします","すみません","ごめんなさい","おはよう","こんばんは","さようなら",
             "お休みなさい","元気","名前","友達","家族","学校","先生","学生","本","ペン","紙","水","食べ物","飲み物","お茶","コーヒー",
             "牛乳","パン","米","魚","肉","野菜","果物","りんご","バナナ","猫","犬","鳥","車","電車","バス","自転車","空","太陽",
             "月","星","雨","雪","風","山","川","海","花","木","森","家","部屋","ドア","窓","椅子","机","ベッド","服","靴","帽子",
             "時計","電話","テレビ","音楽","映画","写真","手紙","仕事","休み","旅行","お金","時間","今日","明日","昨日","今","後で",
             "ここ","そこ","あそこ","どこ","誰","何","なぜ","どうやって","いくら","大きい","小さい","新しい","古い","良い","悪い",
             "暑い","寒い","楽しい","悲しい","忙しい","簡単","難しい","近い","遠い","多い","少ない"]

    for word in words:
        _, sentences = sentence_db_manager.get_sentences(word, 100, produce_new=False)
        print(word, len(sentences))

# sentence_db_manager._produce_new_sentences_arbitrarily(1000000)

# word_test()
common_words_test()


"""
# testing known words update stuff
import pandas as pd
keywords_to_update=['火','煙']
from sqlalchemy import update
from tatoebator.db.core import Keyword
sentence_db_manager.sentence_db_interface.session.execute(
    update(Keyword).where(Keyword.keyword.in_(keywords_to_update)).values(known=True)
)
sentence_db_manager.sentence_db_interface.session.commit()

sentence_table = pd.read_sql_table(table_name='sentences',con=sentence_db_manager.sentence_db_interface.engine)
pairs_table = pd.read_sql_table(table_name='sentence_keywords',con=sentence_db_manager.sentence_db_interface.engine)
keyword_table = pd.read_sql_table(table_name='keywords',con=sentence_db_manager.sentence_db_interface.engine)
print(sentence_table.to_string())
print(pairs_table.to_string())
print(keyword_table.to_string())

sentence_db_manager.sentence_db_interface.update_known_unknown_counts()

sentence_table = pd.read_sql_table(table_name='sentences',con=sentence_db_manager.sentence_db_interface.engine)
print(sentence_table.to_string())
"""