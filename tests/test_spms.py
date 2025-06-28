from tatoebator.external_download_requester import ExternalDownloadRequester
from tatoebator.sentences import SentenceProducer
from tatoebator.sentences.sentence_production import JParaCrawlASPM, TatoebaASPM, SentenceSearchConfig, \
    SentenceScoringRequirements

edr = ExternalDownloadRequester()

scoring_requirements = SentenceScoringRequirements(20,10,lambda s: len(s.sentence))
search_config = SentenceSearchConfig(#scoring_requirements=scoring_requirements,
                                     scoring_requirements=None,
                                     #filtering_callback=lambda s: s.sentence[-1] != "。",
                                     filtering_callback=lambda s: True,
                                     generate_machine_translations=True)

spm = SentenceProducer(edr, search_config)
f = lambda d: sum(d.values(),[])
for sentence in f(spm.find_new_sentences_with_words({"やるせない": 10,"彼": 1})):
#for sentence in f(spm.find_new_sentences_with_words({"彼": 10})):
    print(sentence.sentence)
    print(sentence.translation)
    print(sentence.source_tag, sentence.credit)
    print("")

print(jjsj)

# just testing how long the scan takes
aspm = JParaCrawlASPM(edr)
aspm = TatoebaASPM(edr)
c = 0
if 0:#for sentence in aspm.yield_sentences():
    c += 1
    if c % 10000 == 0:
        print(c)
