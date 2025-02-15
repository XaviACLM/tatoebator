import regex as re

from tatoebator.sentences import SentenceProductionManager
from tatoebator.sentences.sentence_production import TatoebaASPM, TatoebaSPM

kana_matcher = re.compile(r"([\p{IsHira}\p{IsKatakana}ー–—]+)", re.UNICODE)
kanji_matcher = re.compile(r"([\p{IsHan}]+)", re.UNICODE)
notkanji_matcher = re.compile(r"([^\p{IsHan}]+)", re.UNICODE)
japanese_chars = r"\p{IsHira}\p{IsKatakana}\p{IsHan}・、。ー「」『』【】〈〉《》〔〕［］｢｣〖〗【】〘〙〚〛〝〞〟〰〽〿–—‘’“”…‥･〳〴〵〶〷〼〽〾〿！？「」～"
general_chars = r"\d"
jap_text_matcher = re.compile(r"([" + japanese_chars + general_chars + "]+)", re.UNICODE)

"""
sp_manager = SentenceProductionManager(generate_missing_translations=False)
for sentence in sp_manager.yield_new_sentences():
    pass#print(sentence.sentence)
print(jjsj)
for sentence in aspm.yield_sentences():
    if not re.fullmatch(jap_text_matcher, sentence.sentence):
        print(sentence.sentence)
    continue
    print(sentence.sentence)
    print(sentence.translation)
    print(sentence.lexical_words)
    print(sentence.audio_fileid)
    print("")
"""

"""
mtt = ManyThingsTatoebaASPM()
for sentence in mtt.yield_sentences():
    print(sentence)
"""

"""
sp_manager = SentenceProductionManager(generate_missing_translations=False)
c=0
for sentence in sp_manager.yield_new_sentences():
    c+=1
print(c)
"""

"""
spm = TatoebaSPM(stringent=False)
for item in spm.yield_sentences("買う"):
    print(item.sentence)
"""


#aspm = TatoebaASPM()
aspm = TatoebaSPM()
#aspm = ManyThingsTatoebaASPM()
for sentence in aspm.yield_sentences('アイツ'):
    print(sentence.sentence, sentence.credit)


"""
sp_manager = SentenceProductionManager(generate_missing_translations=False)
for sentence in sp_manager.yield_new_sentences():
    print(sentence.sentence)
    print(sentence.credit)
"""