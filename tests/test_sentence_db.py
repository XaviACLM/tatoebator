
from tatoebator.db.manager import SentenceDbManager

# TODO stop propagating output from yumekey + ffmpeg


# TODO make the tanoshii searcher better: there was some old concern i don't remember
# TODO also, include too translations and definitions from "Definition and synonyms for...
# TODO tangorin definitions are also good
# TODO add new sentences menu (with semi automatic translations)
# TODO gen translation/definition is a button, fields are editable
# TODO include/don't include in table menu
# TODO warnings in table menu (low amt of sentences, not-that-lexical word...)
# TODO progress bars

# TODO reinsert audio data when generated upon taking it out of the db
# so we can ingest a TON of data from corpuses and stop depending on kanshudo/tangorin/etc
# TODO stuff from parallel corpuses:
# https://www.phontron.com/japanese-translation-data.php
# https://www.manythings.org/bilingual/jpn/ <- amazing! also warns against tatoeba
# https://www.kaggle.com/discussions/general/39500
# https://www.kaggle.com/code/vennaa/notebook-accessing-the-data/notebook

# maybe other sentence sources too:
# https://context.reverso.net/%E7%BF%BB%E8%A8%B3/%E6%97%A5%E6%9C%AC%E8%AA%9E-%E8%8B%B1%E8%AA%9E/%E3%82%84%E3%82%8B%E3%81%9B%E3%81%AA%E3%81%84
# https://ejje.weblio.jp/content/%E3%82%84%E3%82%8B%E3%81%9B%E3%81%AA%E3%81%84

# TODO decide on the logic for when to call update_known_unknown_words
# TODO switch to regular SQL queries?
# TODO interface (or manager?) logic that uses known_words and trusted fields to decide what to query
# TODO maybe aspm only inserts new sentences if MORE than one word is underrepresented in the db

# TODO be a good boy:
# ManyThings-Tatoeba is CC-BY 2.0 : we can do anything as long as we credit properly, indicate changes, and propagate the license
# A note on propagating the license - from what I understand this doesnt' mean the whole project has to be CC-BY 2.0, just the data
# kanshudo and tangorin robots.txt place no restrictions on us
# sentence search seems dubious in its sourcing, actually

# tangorin says all its example sentences are from tatoeba? tatoeba will be CC-BY 2.0 too
# this seems true. Considering tangorin data is tatoeba and robots.txt allows us to crawl, tangorin is just a nicer interface to tatoeba
# but is it complete? I don't really think so, meaning we will waste the same amount of time crawling through tatoeba later to drop all examples
# hmmm... but obviously we can just read all of them from our db if we push them in earlier. man!
# actually tangorin... well first of all their page system doesn't work but you can do the normal query with &offset= a multiple of 50
# doing this it looks like tangorin has almost everything in tatoeba, missing maybe 5% - possibly they have an older copy of the database?
# importantly this is with tangorin eating EVERYTHING, orphaned and unapproved sentences all the same. note that they also say:
sentence_db_manager = SentenceDbManager()

#ok a lot of things end up going back to tatoeba actually. how big is tatoeba? maybe its practical to just keep it locally
#its 28.2MB, very reasonable. But - how many sentences are there in there actually?

# ManyThings-Tatoeba is just tatoeba (but quality controlled, let's somehow tell the db we like it more)
# tatoeba-OA means tatoeba but accepting orphans and non-accepted sentences. our tatoeba is not this (but it can be)
# tangorin is just tatoeba-OA
# kanshudo is almost entirely (~90%) tatoeba-OA, possibly more w/ modified tatoeba sentences.
# jisho also says "most example sentences in jisho come from the tatoeba project). only other sentence source listed is jreibun and only 407 of its sentences come from there
# about jreibun - website says '2,797 items, 4,892 example sentences created (with English translation)', but nowhere to download them
# ss-neocities is the only one that might be more complex, actually. however it lists a ton of sources and it really seems like it made no effort to check whether they had a license
# let's test how much stuff in it is not in tatoeba. We'll check against ManyThings-Tatoeba bc it's what we got right now
# wow, only 5% of ss-neocities is in manythings-tatoeba. Shame about the license - we'll see if it's necessary or not, but better not touch it i suppose

# ok so here's the plan
# spms: all of them out the window. forget tangorin, kanshudo, jisho - and instead of the tatoeba website we'll use the tatoeba api (duh)
# https://api.dev.tatoeba.org/unstable#?route=get-/unstable/sentences

# aspms: keep the neocities one just in case but don't use it. Have manythings-tatoeba and all of tatoeba - figure out how
# to introduce logic (and more stuff in the DB) to figure out which one to use. later on also include other corpora:
# https://www.phontron.com/japanese-translation-data.php
# https://www.kaggle.com/discussions/general/39500
# https://www.kaggle.com/code/vennaa/notebook-accessing-the-data/notebook
# further extend ExampleSentence to CreditedExampleSentence - this will carry license and credit info (one string each)
# spms/aspms now return creditedExampleSentences. DB has two new fields to store this data. DB getter methods however
# return only ExampleSentences, no credit into - the credit info is never used, only kept there because it's nice
# there will also be an option (---> a method in the manager) to delete the credit info, in case...
# well i don't really know why you'd be that pressed for space, but in case.
# and actually maybe it might not be a bad idea to use CreditedExampleSentences everywhere - would be nice to put a small semitransparent credit on sentences in the UI
# hm... but if this is the case, do we just add new fields to ExampleSentence, instead of extending it? i'm a bit afraid to do that
# seems like you might want to do operations on them without caring about the license data at times
# actually that probably makes sense...
# i don't know, we'll consider it

def word_test(word="煙"):
    _, sentences = sentence_db_manager.get_sentences(word, 5, ensure_audio=False)
    print("returned",len(sentences),"sentences")
    for example_sentence in sentences:
        print(example_sentence.sentence)
        print(example_sentence.translation)
        print(example_sentence.lexical_words)
        print(example_sentence.audio_fileid)
        print(example_sentence.source_tag)
        print(example_sentence.trusted)
        print(example_sentence.n_unknown_words)
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

# sentence_db_manager._produce_new_sentences_arbitrarily(10000)
word_test()
# common_words_test()

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