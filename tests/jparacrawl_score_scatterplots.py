from tatoebator.sentences.sentence_production import TatoebaASPM, TatoebaSPM, JParaCrawlASPM

"""
    def get_distance_vs_score_scatterplot(self, qt:int) -> List[Tuple[float, float]]:
        estimate_score_pairs = []

        from ..language_processing import estimate_jp_sentence_distance, Translator
        def estimated_sentence_distance(jp, en):
            return estimate_jp_sentence_distance(jp, Translator.eng_to_jp(en))

        line_matcher = re.compile(r"([^\t]+)\t([^\t]+)\t([^\t]+)\t([^\t]+)\t([^\t]+)\n")
        with open(self.filepath, 'r', encoding='utf-8') as file:
            for _ in range(100): next(file)
            for i,line in enumerate(file):
                if qt%10==0: print(qt)
                _, _, score, en_text, jp_text = line_matcher.fullmatch(line).groups()
                estimate = estimated_sentence_distance(jp_text, en_text)
                estimate_score_pairs.append((estimate, float(score)))
                qt -= 1
                if qt==0:
                    break
        return estimate_score_pairs

    def get_scores(self, qt:int) -> List[Tuple[float, float]]:
        scores = []
        line_matcher = re.compile(r"([^\t]+)\t([^\t]+)\t([^\t]+)\t([^\t]+)\t([^\t]+)\n")
        with open(self.filepath, 'r', encoding='utf-8') as file:
            for i,line in enumerate(file):
                if qt%10==0: print(qt)
                _, _, score, _, _ = line_matcher.fullmatch(line).groups()
                scores.append(float(score))
                qt -= 1
                if qt==0:
                    break
        return scores

    def show_good_score_distance_disparity(self, qt:int):
        estimate_score_pairs = []

        from ..language_processing import estimate_jp_sentence_distance, Translator
        def estimated_sentence_distance(jp, en):
            return estimate_jp_sentence_distance(jp, Translator.eng_to_jp(en))

        line_matcher = re.compile(r"([^\t]+)\t([^\t]+)\t([^\t]+)\t([^\t]+)\t([^\t]+)\n")
        with open(self.filepath, 'r', encoding='utf-8') as file:
            for _ in range(100): next(file)
            for i,line in enumerate(file):
                if qt%10==0: print(qt)
                _, _, score, en_text, jp_text = line_matcher.fullmatch(line).groups()
                score = float(score)
                estimate = estimated_sentence_distance(jp_text, en_text)
                if score > 0.67 and estimate > 0.15:
                    print(en_text)
                    print(jp_text)
                    print(score, estimate)
                qt -= 1
                if qt==0:
                    break
"""

# that investigation was a bit unconclusive in all
# bad sentences do seem to have low score but it's very much a toss-up with the higher scores
# clearly better in general but not that reliable as a prediction

aspm = JParaCrawlASPM()

aspm.show_good_score_distance_disparity(1000)
print(jjsj)

#scores = aspm.get_scores(10000)
#from matplotlib import pyplot as plt
#plt.hist(scores)
#plt.show()
#print(jjsj)

pairs = aspm.get_distance_vs_score_scatterplot(100)
from matplotlib import pyplot as plt
plt.scatter(*zip(*pairs))
plt.xlabel("distance")
plt.ylabel("score")
plt.show()