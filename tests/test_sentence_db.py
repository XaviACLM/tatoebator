from tatoebator.audio import MediaManager
from tatoebator.db import SentenceRepository


sentence_repository = SentenceRepository(MediaManager())


for word, sentences in sentence_repository.produce_sentences_for_words({"鳥":200,"空":200}, produce_new=False, ensure_audio=False, with_furigana=True).items():
    print(word)
    sentences.sort(key = lambda s:s.sentence)
    for sentence in sentences:
        print(f"\t{sentence.sentence} - {sentence.translation}")
        print(f"\t{sentence.furigana}")
        print("")


def word_test(word="煙"):
    _, sentences = sentence_repository.produce_sentences_for_word(word, 40, ensure_audio=False, produce_new=True)
    print("returned",len(sentences),"sentences")
    for s in sentences:
        print(s.sentence)
        print(s.translation)
        print(s.lexical_words)
        print(s.audio_file_ref)
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


word_test()
common_words_test()
