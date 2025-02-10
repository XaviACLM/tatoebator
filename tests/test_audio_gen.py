from tatoebator.audio.tts2 import DefaultTTSManager


lines = """散々な思い出は悲しみを穿つほど
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
もう寂しくないさ ないさ""".split("\n")
manager = DefaultTTSManager()
for voice in range(manager.amt_voices):
    for i, line in enumerate(lines[:2]):
        manager.create_audio(
            line, voice_idx=voice, file_name=str(100 * voice + i + 1)
        )
