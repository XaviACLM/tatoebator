import time

from tatoebator.language_processing.translator import Translator

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
もう寂しくないさ ないさ
"""*100
#print(tokenizer(text))
now = time.time()
for line in text.splitlines():
    then = now
    print(line)
    print(Translator.jp_to_eng(line))
    now = time.time()
    print(now-then)
    print("")
