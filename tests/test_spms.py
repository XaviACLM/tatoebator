from tatoebator.sentences import SentenceProductionManager
from tatoebator.sentences.sentence_production import JParaCrawlASPM

spm = SentenceProductionManager()
for word, sentence in spm.yield_new_sentences_with_words({"やるせない": 10}):
    print(sentence.sentence)
    print(sentence.translation)
    print(sentence.source_tag, sentence.credit)
    print("")

# just testing how long the scan takes
aspm = JParaCrawlASPM()
c = 0
for sentence in aspm.yield_sentences():
    c += 1
    if c % 100000 == 0:
        print(c)
