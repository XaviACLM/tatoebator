import itertools
import re
import json

from accelerate.utils.modeling import compute_module_total_buffer_size

from tatoebator.language_processing import lexical_content, Translator, UnicodeRange
from tatoebator.sentences.candidate_example_sentences import ExampleSentenceQualityEvaluator, QualityEvaluationResult
from tatoebator.sentences.sentence_production import ManyThingsTatoebaASPM, TatoebaASPM, JParaCrawlASPM, \
    JapaneseEnglishSubtitleCorpusASPM, ImmersionKitSPM

# first, how many words are there?

# < counted words/sentences in ManyThingsTatoebaASPM

# 15000. Would take almost 2Gb to store a distance matrix. have to take some kind of sparse approach, so:
# how many concurrently appearing pairs of words even are there?

# < tried to compute list of all appearing kanji pairs >

# far too slow. cannot work.
# so i think we can get sth for the joyo kanji from that website



# defining distances

path = r"C:\Users\xavia\AppData\Roaming\Anki2\addons21\tatoebator\src\tatoebator\external_datasets\dembeddings.json"
with open(path,"r") as f:
    distances = json.load(f)["nearest"]
def distance(k1, k2):
    if k1==k2: return 0
    neighbors = distances.get(k1, None)
    if neighbors is None: return 0
    return int(k2 not in neighbors)
    # return neighbors.get(k2, 10)
def distance_one_to_many(k, ks):
    return min((distance(k, k2) for k2 in ks))
def distance_many_to_many(ks1, ks2):
    return sum((distance_one_to_many(k1, ks2) for k1 in ks1)) + sum((distance_one_to_many(k2, ks1) for k2 in ks2))
kanji_matcher = re.compile(fr"[{UnicodeRange.kanji}]")
def distance_sentences(jp_text_1, jp_text_2):
    kanji_1 = kanji_matcher.findall(jp_text_1)
    kanji_2 = kanji_matcher.findall(jp_text_2)
    if not (kanji_1 and kanji_2):
        return 1  # will catch a lot of good sentences but cannot be helped
    return distance_many_to_many(kanji_1, kanji_2)/max(5, len(kanji_1), len(kanji_2))
    return distance_many_to_many(kanji_1, kanji_2)/max(5, len(kanji_1) + len(kanji_2))




evaluator = ExampleSentenceQualityEvaluator(generate_missing_translations=False)
def manythings_1000samples(skip=50):
    # sentences = JapaneseEnglishSubtitleCorpusASPM().yield_sentences()

    spm = ImmersionKitSPM()
    sentences = itertools.chain(*(spm.yield_sentences(word) for word in ["月","星","雨","雪","風","山","川","海","花","木","森","家","部屋","ドア","窓","椅子","机","ベッド","服","靴","帽子",
             "時計","電話","テレビ","音楽","映画","写真","手紙","仕事","休み","旅行","お金","時間","今日","明日","昨日","今","後で",
             "ここ","そこ","あそこ","どこ","誰","何","なぜ","どうやって","いくら","大きい","小さい","新しい","古い","良い","悪い",
             "暑い","寒い","楽しい","悲しい","忙しい","簡単","難しい","近い","遠い","多い","少ない"]))

    c_seen = 0
    c_yielded = 0
    for sentence in sentences:
        c_seen += 1
        if c_seen < skip:
            continue
        else:
            c_seen = 0
        if evaluator.evaluate_quality(sentence) == QualityEvaluationResult.UNSUITABLE:
            continue
        c_yielded += 1
        if c_yielded%10==0:
            print(c_yielded)
        if c_yielded>1000:
            return
        yield sentence

c_passed = 0
c_total = 0
for sentence in manythings_1000samples():
    c_total += 1
    real_text = sentence.sentence
    machine_text = Translator.eng_to_jp(sentence.translation)
    d = distance_sentences(real_text, machine_text)
    if d>=0.3: continue
    c_passed += 1
print(f"{c_passed} / {c_total}, {int(100*c_passed/c_total)}%")

# there are a lot of false negatives - that's to be expecte.
# mtt is here for calibration - could adjust the results so mtt is 95%-ish

# manythingstatoeba: 560 / 1000
# straight tatoeba: 367 / 1000
# jparacrawl: 218 / 1000
# parallel subtitles: 216 / 1000
# immersionkit: 58 / 237, 24%