from tatoebator.language_processing.lexical_analysis import group_text_by_part_of_speech, WordSpeechType
from tatoebator.language_processing import DefaultTokenizer

tokenizer = DefaultTokenizer()
text = """散々な思い出は悲しみを穿つほど
やるせない恨みはアイツのために
置いてきたのさ
あんたらわかっちゃないだろ
本当に傷む孤独を
今だけ箍外してきて
怒りよ今 悪党ぶっ飛ばして
そりゃあ愛ある罰だ
もう眠くはないや ないやないや
もう悲しくないさ ないさ
そう 怒りよ今 悪党蹴り飛ばして
そりゃあ愛への罰だ
もう眠くはないな ないなないな
もう寂しくないさ ないさ"""
text = """火のない所に煙は立たないということは、誰も否定することはできません。
エレベーターから煙の臭いがします。
あの山は昔煙を吐いていた。"""
texts=["自由になるのは大変だろう",
       "自由になるのは大変だろう\n",
       "\n自由になるのは大変だろう",
       "\n自由になるのは大変だろう\n",
       ]
for text in texts:
    for morpheme in tokenizer(text):
        print(morpheme)
    print("")
print(jjsj)
for type, words in group_text_by_part_of_speech(text).items():
    print(type)
    print(words)
    print("")

grammatical_word_sentences = [
    ("する","勉強するのが好きです。","彼はいつも変なことをする。"),
    ("ある","ここに名前を書いてある。","机の上に本がある。"),
    ("いる","ずっと日本にいるつもりです。","そこに猫がいる！"),
    ("おく","明日のために準備しておく。","本を机の上におく。"),
    ("の","日本語を勉強するのは楽しい。","このカバンは私ののです。"),
    ("こと","本を読むことが好きです。","大事なことを忘れた。"),
    ("もの","勉強しないとダメなものだよ。","これは大切なものです。"),
]

for word, sentence_1, sentence_2 in grammatical_word_sentences:
    print(word,
          word in group_text_by_part_of_speech(sentence_1)[WordSpeechType.LEXICAL_WORD],
          word in group_text_by_part_of_speech(sentence_2)[WordSpeechType.LEXICAL_WORD])
    print(group_text_by_part_of_speech(sentence_1)[WordSpeechType.LEXICAL_WORD])
    print(group_text_by_part_of_speech(sentence_2)[WordSpeechType.LEXICAL_WORD])
    print("")

# this seems like a common topic - unidic being overly fine-grained
# it will be a lot less of a headache to stick with ipadic, probably, but we might need to do a lot of bookkeeping

# mecab reads antara as amu tara (if you weave)

# we could use the neologism dictionary but it looks a bit hacked together to be honest. i don't really need a
# neologism _dictionary_, just like a few common contractions. hopefully we can build this up over time.