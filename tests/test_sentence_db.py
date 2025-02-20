
from tatoebator.db import SentenceRepository

# TODO add new sentences menu (with semi automatic translations)

# TODO interface (or manager?) logic that uses known_words and trusted fields to decide what to query

# TODO type annotations, docs, privating, eliminating "__main__" blocks...


# TODO figure out the general flow of the app. user stories or whatever. when do we actually need to use the sentence db?
#  main bits of gui
#  x the miner
#  x post-miner sentence adder
#  standalone sentence adder
#  the cards themselves (when do the notes get created? must be in the table gui, no?
#  and some config or whatever
#   particularly as relates to marking relevant fields in other notetypes in other decks
#   which will affect some kind of AnkiDbManager

# TODO make it so it doesnt crash instantly if robots requests fail. Offline mode in general


# CC-BY 2.0 : we can do anything as long as we credit properly, indicate changes, and propagate the license
# A note on propagating the license - from what I understand this doesnt' mean the whole project has to be CC-BY 2.0
# either way cc doesn't actually prohibit anything specific other than changing the license or misattribution, so fine


#maybe eventually? https://eow.alc.co.jp/search?q=%e3%81%99%e3%82%8b -> translations, usage, but ehh



#TODO create notetype, deck
#TODO note creation
#TODO card html - esp care w the logic on the sentences - separate known, discard remainder if have enough, etc
# and the random sorting, minute-based

#TODO port decks (incl. rtk to migaku... somehow?)

# TODO put all files other than temp_files in tatoebator/user_files (not in src/tatoebator/user_files!!)
# TODO help menus

# TODO option to add machine translated sentences (tag them in db + gui)

# include other corpora:
# https://www.phontron.com/japanese-translation-data.php
# https://www.kaggle.com/discussions/general/39500
# https://www.kaggle.com/code/vennaa/notebook-accessing-the-data/notebook


sentence_repository = SentenceRepository()


for word, sentences in sentence_repository.produce_sentences_for_words({"鳥":200,"空":200}, produce_new=False, ensure_audio=False, with_furigana=True).items():
    print(word)
    sentences.sort(key = lambda s:s.sentence)
    for sentence in sentences:
        print(f"\t{sentence.furigana} - {sentence.translation}")
print(jjsj)


for word, sentences in sentence_repository.produce_sentences_for_words({"鳥":200,"空":200}).items():
    print(word)
    sentences.sort(key = lambda s:s.sentence)
    for sentence in sentences:
        print(f"\t{sentence.sentence} - {sentence.translation}")
print(jjsj)



def word_test(word="煙"):
    _, sentences = sentence_repository.produce_sentences_for_word(word, 40, ensure_audio=False, produce_new=True)
    print("returned",len(sentences),"sentences")
    for s in sentences:
        print(s.sentence)
        print(s.translation)
        print(s.lexical_words)
        print(s.audio_fileid)
        print(s.source_tag)
        print(s.trusted)
        print(f"{s.n_known_words}/{s.n_lexical_words} ({s.n_unknown_words} unknown)")
        print(s.credit)
        print("")

def common_words_test():
    words = ["こんにちは","ありがとう","はい","いいえ","お願いします","すみません","ごめんなさい","おはよう","こんばんは","さようなら",
             "お休みなさい","元気","名前","友達","家族","学校","先生","学生","本","ペン","紙","水","食べ物","飲み物","お茶","コーヒー",
             "牛乳","パン","米","魚","肉","野菜","果物","りんご","バナナ","猫","犬","鳥","車","電車","バス","自転車","空","太陽",
             "月","星","雨","雪","風","山","川","海","花","木","森","家","部屋","ドア","窓","椅子","机","ベッド","服","靴","帽子",
             "時計","電話","テレビ","音楽","映画","写真","手紙","仕事","休み","旅行","お金","時間","今日","明日","昨日","今","後で",
             "ここ","そこ","あそこ","どこ","誰","何","なぜ","どうやって","いくら","大きい","小さい","新しい","古い","良い","悪い",
             "暑い","寒い","楽しい","悲しい","忙しい","簡単","難しい","近い","遠い","多い","少ない"]

    counts = sentence_repository.count_lexical_word_ocurrences(words)
    counts_50 = sentence_repository.count_lexical_word_ocurrences(words, min_comprehensibility=0.5)
    counts_80 = sentence_repository.count_lexical_word_ocurrences(words, min_comprehensibility=0.8)
    for word in counts:
        print(word, counts[word], counts_50[word], counts_80[word])


    #for word in words:
    #    _, sentences = sentence_repository.get_sentences(word, 100, produce_new=False)
    #    print(word, len(sentences))

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

"""
coso = sentence_repository.sentence_db_interface.get_sentences_by_word_batched({"煙":2,"森":5})
for word in coso:
    print(word)
    for sentence in coso[word]:
        print(sentence.sentence)
print(jjsj)
"""