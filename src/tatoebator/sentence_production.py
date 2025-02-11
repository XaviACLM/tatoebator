import itertools
import os
import re
import zipfile
from typing import Iterator, Dict

import requests

from .candidate_example_sentences import ExampleSentenceQualityEvaluator, QualityEvaluationResult
from .constants import CACHE_DIR, TEMP_FILES_DIR
from .example_sentences import CandidateExampleSentence, ExampleSentence


class SentenceProductionMethod:
    def yield_sentences(self, word: str) -> Iterator[CandidateExampleSentence]:
        raise NotImplementedError()

class ArbitrarySentenceProductionMethod():
    def yield_sentences(self) -> Iterator[CandidateExampleSentence]:
        raise NotImplementedError()


requests_session = requests.Session()
requests_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
})


class TatoebaSPM(SentenceProductionMethod):
    get_sentence_url = "https://api.tatoeba.org/unstable/sentences"
    default_params = "lang=jpn&trans%3Alang=eng&sort=created"
    stringent_params = "&is_orphan=no&is_unapproved=no&trans%3Ais_direct=yes&trans%3Ais_unapproved=no&trans%3Ais_orphan=no"
    lax_params = "&q=買&limit=10"
    block_size = 30

    def __init__(self, stringent=True):
        self.query_string = f"{self.get_sentence_url}?{self.default_params}{self.stringent_params if stringent else ''}&limit={self.block_size}"

    def yield_sentences(self, word):
        for page in itertools.count(1):
            url = f"{self.query_string}&q={word}&page={page}"
            data = requests_session.get(url).json()['data']
            for item in data:
                jp_text = item['text']
                if item['license'] != 'CC BY 2.0 FR':
                    raise Exception(f"Something in Tatoeba has an unexpected license: {item['license']}")
                jp_owner = item['owner']
                for translation in itertools.chain(*item['translations']):
                    if translation['lang']=='eng':
                        break
                else:
                    # sometimes the return doesn't have a translation in the language we want
                    # why? that's weird. filed a big report
                    continue
                en_text = translation['text']
                en_owner = translation['owner']
                yield CandidateExampleSentence(jp_text, en_text, credit=f"{jp_owner}, {en_owner} (Tatoeba)")


class TatoebaASPM(ArbitrarySentenceProductionMethod):
    def __init__(self):
        self.filepath = os.path.join(CACHE_DIR, 'ssneocities_data.json')
        if not os.path.exists(self.filepath):
            self._download_data_to_cache()


class SentenceSearchNeocitiesASPM(ArbitrarySentenceProductionMethod):
    def __init__(self):
        self.filepath = os.path.join(CACHE_DIR, 'ssneocities_data.json')
        if not os.path.exists(self.filepath):
            self._download_data_to_cache()

    def _download_data_to_cache(self):
        url = 'https://sentencesearch.neocities.org/data/all_v11.json'
        response = requests.get(url)
        response.raise_for_status()
        with open(self.filepath, 'wb') as file:
            file.write(response.content)

    def yield_sentences(self):
        # sometimes a space precedes the newline (?)
        jap_pattern = re.compile(r'^    "jap":\s"(.*?)", ?$')
        eng_pattern = re.compile(r'^    "eng":\s"(.*?)"$')
        with open(self.filepath, 'r', encoding='utf-8') as file:
            results = []  # Store results as tuples (jap, eng)
            line_number = 0
            for line in file:
                # some empty lines?
                if line == "\n": continue
                line_number += 1
                if (line_number - 5) % 6 == 0:
                    jap_match = jap_pattern.match(line)
                    jap_text = jap_match.group(1)
                elif (line_number - 6) % 6 == 0:
                    eng_match = eng_pattern.match(line)
                    eng_text = eng_match.group(1)
                    # some are empty
                    if jap_text == "": continue
                    yield CandidateExampleSentence(jap_text, translation=eng_text)


class ManyThingsTatoebaASPM(ArbitrarySentenceProductionMethod):
    def __init__(self):
        self.filepath = os.path.join(CACHE_DIR, 'manythings_tatoeba.txt')
        if not os.path.exists(self.filepath):
            self._download_data_to_cache()

    def _download_data_to_cache(self):
        zip_filepath = os.path.join(TEMP_FILES_DIR, 'jpn-eng.zip')
        if not os.path.exists(zip_filepath):
            url = 'https://www.manythings.org/anki/jpn-eng.zip'
            response = requests_session.get(url)
            with open(zip_filepath, 'wb') as file:
                file.write(response.content)
        with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
            with zip_ref.open('jpn.txt') as orig, open(self.filepath, 'wb') as dest:
                dest.write(orig.read())
        os.remove(zip_filepath)

    def yield_sentences(self):
        line_matcher = re.compile(r'([^\t]+)\t([^\t]+)\t([^\t]+)')
        license_matcher = re.compile(r'CC-BY 2\.0 \(France\) Attribution: tatoeba\.org #\d+ \(.+\) & #\d+ \(.+\)\n')
        with open(self.filepath, 'r', encoding='utf-8') as file:
            for line in file:
                line_match = line_matcher.match(line)
                eng_text, jap_text, license = line_match.groups()
                license_match = license_matcher.match(license)
                # TODO license license license
                yield CandidateExampleSentence(jap_text, translation=eng_text)


class SentenceProductionManager:

    spms_by_tag: Dict[int, SentenceProductionMethod] = {
        4: TatoebaSPM(),
    }

    aspms_by_tag: Dict[int, ArbitrarySentenceProductionMethod] = {
        101: SentenceSearchNeocitiesASPM(),
        102: ManyThingsTatoebaASPM(),
    }

    # TODO trust score from source

    def __init__(self, generate_missing_translations=True):
        self.quality_control = ExampleSentenceQualityEvaluator(generate_missing_translations=generate_missing_translations)

    def yield_new_sentences(self, word=None):
        """
        if word is not None
            uses sentence production methods to produce CandidateExampleSentences containing word
            pushes them through quality control, turns them into ExampleSentences
            yields that arbitrarily or until it runs out
        if word is none
            same thing but using arbitrary sentence production methods
        """
        yielders_by_tag = {tag:spm.yield_sentences() for tag, spm in self.aspms_by_tag.items()} if word is None\
            else {tag:spm.yield_sentences(word) for tag, spm in self.spms_by_tag.items()}

        for tag, yielder in yielders_by_tag.items():
            for s in yielder:
                evaluation = self.quality_control.evaluate_quality(s, word=word)
                if evaluation is QualityEvaluationResult.UNSUITABLE:
                    continue
                yield ExampleSentence.from_candidate(s, tag, evaluation is QualityEvaluationResult.GOOD)
