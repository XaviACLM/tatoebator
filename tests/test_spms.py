from tatoebator.external_download_requester import ExternalDownloadRequester
from tatoebator.sentences import SentenceProductionManager
from tatoebator.sentences.sentence_production import JParaCrawlASPM, TatoebaASPM

edr = ExternalDownloadRequester()

spm = SentenceProductionManager(edr)
f = lambda d: sum(d.values(),[])
for sentence in f(spm.find_new_sentences_with_words({"やるせない": 10,"彼": 1})):
#for sentence in f(spm.find_new_sentences_with_words({"彼": 10})):
    print(sentence.sentence)
    print(sentence.translation)
    print(sentence.source_tag, sentence.credit)
    print("")

# just testing how long the scan takes
aspm = JParaCrawlASPM(edr)
aspm = TatoebaASPM(edr)
c = 0
if 0:#for sentence in aspm.yield_sentences():
    c += 1
    if c % 10000 == 0:
        print(c)
