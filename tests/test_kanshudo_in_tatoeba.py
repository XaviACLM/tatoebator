from tatoebator.sentence_production import SentenceProductionManager

"""
sp_manager = SentenceProductionManager(generate_missing_translations=False)

word = "処理"
from_kanshudo = {s.sentence for s in sp_manager.spms_by_tag[1].yield_sentences(word)}
from_tatoeba = {s.sentence for s in sp_manager.spms_by_tag[4].yield_sentences(word)}

print("t",len(from_tatoeba))
print("k",len(from_kanshudo))
print("t-k",len(from_tatoeba-from_kanshudo))
print("k-t",len(from_kanshudo-from_tatoeba))

print(sorted(list(from_tatoeba)))

print(sorted(list(from_kanshudo)))
"""

# looking through the results on the webpage, searching for the translation of kanshudo sentence on tatoeba
# out of 29 - 20 came up on tatoeba
# and this is while i was searching with the approved no-orphan, so who knows if the real difference is higher
# but now i'm getting k-t = 25, as opposed to 9, which confuses me

# ok i just ran the search without the orphan or acceptance restrictions
# out of 29 kanshudo sentences: 26 have their japanese in tatoeba, 23 their english
# so very roughly maybe 10% of their content is original japanese - possibly just modified sentences

# now let's test ss-neocities against ManyThings-Tatoeba (we'll test against full tatoeba later mb)

sp_manager = SentenceProductionManager(generate_missing_translations=False)

ssn = {s.translation for s in sp_manager.aspms_by_tag[101].yield_sentences()}
mtt = {s.translation for s in sp_manager.aspms_by_tag[102].yield_sentences()}

print(len(ssn))
print(len(mtt))
print(len(ssn.intersection(mtt)))