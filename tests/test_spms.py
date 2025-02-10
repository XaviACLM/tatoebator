import regex as re

from tatoebator.sentence_production import SentenceProductionManager


kana_matcher = re.compile(r"([\p{IsHira}\p{IsKatakana}ー–—]+)", re.UNICODE)
kanji_matcher = re.compile(r"([\p{IsHan}]+)", re.UNICODE)
notkanji_matcher = re.compile(r"([^\p{IsHan}]+)", re.UNICODE)
japanese_chars = r"\p{IsHira}\p{IsKatakana}\p{IsHan}・、。ー「」『』【】〈〉《》〔〕［］｢｣〖〗【】〘〙〚〛〝〞〟〰〽〿–—‘’“”…‥･〳〴〵〶〷〼〽〾〿！？「」～"
general_chars = r"\d"
jap_text_matcher = re.compile(r"([" + japanese_chars + general_chars + "]+)", re.UNICODE)

if __name__ == "__main__":
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