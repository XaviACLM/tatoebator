import csv
import itertools
import logging
import os
import re
import subprocess
import time
import zipfile
from typing import Optional, Iterator
from urllib import parse as parse_url

import requests

from ..config import SEVENZIP_EXE
from ..constants import CACHE_DIR, TEMP_FILES_DIR, PATH_TO_SOURCES_FILE
from .candidate_example_sentences import ExampleSentenceQualityEvaluator, QualityEvaluationResult
from .example_sentences import CandidateExampleSentence, ExampleSentence


def get_source_tag(source_name: str, license: str):
    if not os.path.exists(PATH_TO_SOURCES_FILE):
        with open(PATH_TO_SOURCES_FILE, 'w', encoding='utf-8') as sources_file:
            sources_file.write(
                "This file contains the mappings from the source_tag column in the database to the actual sources, as well as the licenses of the material in these sources.\n" \
                + "This file is updated programmatically.\n\nSOURCE_TAG;SOURCE_NAME;LICENSE\n")
    with open(PATH_TO_SOURCES_FILE, 'r', encoding='utf-8') as source_file:
        for i in range(5):
            line = next(source_file, None)
        max_tag = 0
        while line is not None:
            tag, name, _ = line.split(';')
            tag = int(tag)
            max_tag = max(max_tag, tag)
            if name == source_name:
                return tag
            line = next(source_file, None)
    # otherwise, register new source tag
    new_tag = max_tag + 1
    with open(PATH_TO_SOURCES_FILE, 'a', encoding='utf-8') as source_file:
        source_file.write(f'{new_tag};{source_name};{license}\n')
    return new_tag


class TaggedSource:
    source_name: Optional[str] = None
    license: Optional[str] = None
    source_tag: Optional[int] = None

    def __init__(self):
        self._generate_source_tag()

    def _generate_source_tag(self):
        self.source_tag = get_source_tag(self.source_name, self.license)


class SentenceProductionMethod(TaggedSource):
    def yield_sentences(self, word: str) -> Iterator[CandidateExampleSentence]:
        raise NotImplementedError()


class ArbitrarySentenceProductionMethod(TaggedSource):
    def yield_sentences(self) -> Iterator[CandidateExampleSentence]:
        raise NotImplementedError()


requests_session = requests.Session()
requests_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
})


class TatoebaSPM(SentenceProductionMethod):
    source_name = 'Tatoeba (via API)'
    license = "CC-BY 2.0 Fr"

    get_sentence_url = "https://api.tatoeba.org/unstable/sentences"
    default_params = "lang=jpn&trans%3Alang=eng&sort=created"
    stringent_params = "&is_orphan=no&is_unapproved=no&trans%3Ais_direct=yes&trans%3Ais_unapproved=no&trans%3Ais_orphan=no"
    lax_params = "&q=買&limit=10"
    block_size = 30

    def __init__(self, stringent=True):
        super().__init__()
        self.query_string = f"{self.get_sentence_url}?{self.default_params}{self.stringent_params if stringent else ''}&limit={self.block_size}"

    def yield_sentences(self, word):
        # this api is quite buggy, actually - shame, have to make the code uglier
        #  translation field is sometimes empty
        #   so we continue to the next sentence if it is
        #  for some words, searching for them seems to return random sentences
        #   so we implemented that the ProductionManager skips spms if they return too many unsuitable sentences
        #  some specific queries (seemingly for particularly high pages) return 500 consistently for no apparent reason
        #   so we check and return if so
        url = f"{self.query_string}&q={word}&page=1"
        while url:
            response = requests_session.get(url)
            if response.status_code == 500: return
            response_json = response.json()
            data = response_json['data']
            paging = response_json['paging']
            for item in data:
                jp_text = item['text']
                if item['license'] != 'CC BY 2.0 FR':
                    raise Exception(f"Something in Tatoeba has an unexpected license: {item['license']}")
                jp_owner = item['owner'] or 'unknown'
                for translation in itertools.chain(*item['translations']):
                    if translation['lang'] == 'eng':
                        break
                else:
                    continue

                en_text = translation['text']
                en_owner = translation['owner'] or 'unknown'

                yield CandidateExampleSentence(jp_text, en_text, credit=f"{jp_owner}, {en_owner} (Tatoeba)")
            url = paging and 'next' in paging and paging['next']


class TatoebaASPM(ArbitrarySentenceProductionMethod):
    source_name = 'Tatoeba (via DB download)'
    license = "CC-BY 2.0 Fr"

    def __init__(self):
        super().__init__()
        self.pairs_filepath = os.path.join(CACHE_DIR, 'tatoeba_pairs_data.tsv')
        self.en_filepath = os.path.join(CACHE_DIR, 'tatoeba_en')
        self.jp_filepath = os.path.join(CACHE_DIR, 'tatoeba_jp')
        self._ensure_data()

    def _ensure_data(self):
        if not os.path.exists(self.pairs_filepath):
            self._download_pairs_data_to_cache()
        if not os.path.exists(self.en_filepath):
            self._download_lan_data_to_cache('en')
            self._cull_lan_data('en')
        if not os.path.exists(self.jp_filepath):
            self._download_lan_data_to_cache('jp')
            self._cull_lan_data('jp')

    def _download_pairs_data_to_cache(self):
        tatoeba_session = requests.Session()
        tatoeba_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        })

        enter_url = "https://tatoeba.org/en/downloads"
        response = tatoeba_session.get(enter_url)
        if response.status_code != 200:
            raise Exception("Tatoeba session cookies GET failed")

        # this took some effort. Probably breaks TOS but I'm sure this isn't against the spirit of the project
        # i'm just trying to save them a bajillion API calls by keeping the data here locally
        post_url = "https://tatoeba.org/en/exports/add"
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-GB,en;q=0.7",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "priority": "u=1, i",
            "sec-ch-ua": "\"Not(A:Brand\";v=\"99\", \"Brave\";v=\"133\", \"Chromium\";v=\"133\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "sec-gpc": "1",
            "x-csrf-token": tatoeba_session.cookies['csrfToken'],
            "x-requested-with": "XMLHttpRequest"
        }
        post_data = {
            # "fields[]": ["id", "text", "trans_id", "trans_text"],
            # would be good if there was some owner field to access but i couldn't find it
            # instead we do this silly goofy join
            "fields[]": ["id", "trans_id"],
            "format": "tsv",
            # "from": "jpn", "to": "eng",
            # so that the ordered field is eng - more convenient to clean up the massive eng sentence file
            "from": "eng", "to": "jpn",
            "type": "pairs"
        }
        tatoeba_session.headers.update({"referrer": "https://tatoeba.org/en/downloads"})

        response = tatoeba_session.post(post_url, data=post_data, headers=headers)

        export_info = response.json().get("export")
        export_id = export_info["id"]
        status_url = f"https://tatoeba.org/en/exports/get/{export_id}"

        while True:
            status_response = tatoeba_session.get(status_url)
            status_response.raise_for_status()
            export_info = status_response.json().get("export")
            status = export_info["status"]
            if status == "online":
                break

            print(f"Waiting on tatoeba data download...")

            time.sleep(3)  # Wait before retrying

        pretty_filename = export_info["pretty_filename"]
        encoded_filename = parse_url.quote(pretty_filename)
        download_url = f"https://tatoeba.org/en/exports/download/{export_id}/{encoded_filename}"

        download_response = tatoeba_session.get(download_url)
        download_response.raise_for_status()
        with open(self.pairs_filepath, "wb") as file:
            file.write(download_response.content[3:]) # some weird characters at the start (?)

    def _download_lan_data_to_cache(self, language: str):
        if language == 'jp':
            l_tag, s_tag = 'jpn', 'jp'
        elif language == 'en':
            l_tag, s_tag = 'eng', 'en'
        else:
            raise Exception("Incorrect language in TatoebaASPM._download_lan_data_to_cache")
        zip_filepath = os.path.join(TEMP_FILES_DIR, f'tatoeba_{s_tag}.bz2')
        if not os.path.exists(zip_filepath):
            url = f'https://downloads.tatoeba.org/exports/per_language/{l_tag}/{l_tag}_sentences_detailed.tsv.bz2'
            response = requests.get(url)
            response.raise_for_status()
            with open(zip_filepath, 'wb') as file:
                file.write(response.content)
        subprocess.run(f"\"{SEVENZIP_EXE}\" e \"{zip_filepath}\" -o\"{CACHE_DIR}\"")
        os.remove(zip_filepath)

    def _cull_lan_data(self, language: str):
        if language == 'jp':
            lan_filepath = self.jp_filepath
        elif language == 'en':
            lan_filepath = self.en_filepath
        else:
            raise Exception("Incorrect language in TatoebaASPM._cull_lan_data")
        first_number_matcher = re.compile(r"(?:ï»¿)?(\d+)\t")
        second_number_matcher = re.compile(r"(?:ï»¿)?\d+\t(\d+)\n")
        with open(self.pairs_filepath, 'r') as pair_file:
            if language == 'en':
                pair_idxs = set(map(lambda line: int(first_number_matcher.match(line).group(1)), pair_file))
            if language == 'jp':
                pair_idxs = set(map(lambda line: int(second_number_matcher.match(line).group(1)), pair_file))
        with open(lan_filepath, 'r', encoding='utf-8') as lan_file:
            lan_idxs = set(map(lambda line: int(first_number_matcher.match(line).group(1)), lan_file))
        common_idx = iter(sorted(pair_idxs.intersection(lan_idxs)))

        temp_filepath = os.path.join(TEMP_FILES_DIR, f"temp_unculled_{language}_tatoeba.tsv")
        os.rename(lan_filepath, temp_filepath)

        with open(temp_filepath, 'r', encoding='utf-8') as temp_file, open(lan_filepath, 'w',
                                                                           encoding='utf-8') as lan_file:
            pair_idx = next(common_idx)
            lan_line = next(temp_file)
            lan_idx = int(first_number_matcher.match(lan_line).group(1))
            while True:
                if pair_idx == lan_idx:
                    parts = lan_line.split("\t")
                    parts[3] += "\n"
                    lan_line = "\t".join([parts[0], parts[2], parts[3]])
                    lan_file.write(lan_line)
                c1, c2 = pair_idx <= lan_idx, lan_idx <= pair_idx
                if c1:
                    pair_idx = next(common_idx, None)
                    if pair_idx is None: break
                if c2:
                    lan_line = next(temp_file, None)
                    if lan_line is None: break
                    lan_idx = int(first_number_matcher.match(lan_line).group(1))
        os.remove(temp_filepath)

    """
    # somehow slower than the alternative
    def _create_dataframe(self):
        en_df = pd.read_csv(self.en_filepath, sep='\t', names=['en_idx', 'en_text', 'en_owner'])
        pair_df = pd.read_csv(self.pairs_filepath, sep='\t', names=['en_idx', 'jp_idx'])
        jp_df = pd.read_csv(self.jp_filepath, sep='\t', names=['jp_idx', 'jp_text', 'jp_owner'])

        pair_df.drop_duplicates(subset='jp_idx', inplace=True)

        merged = jp_df.merge(pair_df, on='jp_idx', how='inner').merge(en_df, on='en_idx', how='inner')
        merged.drop(columns=['jp_idx', 'en_idx'], inplace=True)
        merged['en_owner'].replace(to_replace="\\N", value="unknown", inplace=True)
        merged['jp_owner'].replace(to_replace="\\N", value="unknown", inplace=True)
        return merged

    def yield_sentences(self):
        df = self._create_dataframe()
        for jp_text, jp_owner, en_text, en_owner in df.itertuples(index=False, name=None):
            yield CandidateExampleSentence(jp_text, en_text, credit=f"{jp_owner}, {en_owner} (Tatoeba)")
    """

    def _read_lan_file(self, language_tag: str):
        if language_tag not in ['jp','en']: raise Exception("Incorrect language tag in TatoebaASPM._read_lan_file")
        data = {}
        filepath = self.en_filepath if language_tag == 'en' else self.jp_filepath
        with open(filepath, encoding='utf-8') as file:
            reader = csv.reader(file, delimiter='\t')
            for idx, text, owner in reader:
                data[idx] = (text, owner if owner != "\\N" else "unknown")
        return data

    def _create_dataframe(self):
        en_data = self._read_lan_file('en')
        jp_data = self._read_lan_file('jp')

        merged_data = []
        seen_jp_idx = set()  # To drop duplicates
        with open(self.pairs_filepath, encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            for en_idx, jp_idx in reader:
                if jp_idx in seen_jp_idx: continue
                seen_jp_idx.add(jp_idx)
                if jp_idx not in jp_data or en_idx not in en_data: continue
                jp_text, jp_owner = jp_data[jp_idx]
                en_text, en_owner = en_data[en_idx]
                merged_data.append((jp_text, jp_owner, en_text, en_owner))

        return merged_data

    def yield_sentences(self):
        df = self._create_dataframe()
        for jp_text, jp_owner, en_text, en_owner in df:
            yield CandidateExampleSentence(jp_text, en_text, credit=f"{jp_owner}, {en_owner} (Tatoeba)")


class SentenceSearchNeocitiesASPM(ArbitrarySentenceProductionMethod):
    source_name = "sentencesearch.neocities.org"
    license = "Unknown"

    def __init__(self):
        super().__init__()
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
    source_name = "ManyThings.org Sentence Pairs"
    license = "CC-BY 2.0 Fr"

    def __init__(self):
        super().__init__()
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
        license_matcher = re.compile(r'CC-BY 2\.0 \(France\) Attribution: tatoeba\.org #\d+ \((.+)\) & #\d+ \((.+)\)\n')
        with open(self.filepath, 'r', encoding='utf-8') as file:
            for line in file:
                line_match = line_matcher.match(line)
                eng_text, jap_text, license = line_match.groups()
                en_owner, jp_owner = license_matcher.match(license).groups()
                yield CandidateExampleSentence(jap_text, eng_text, credit=f"{jp_owner}, {en_owner} (Tatoeba)")


skipped_spms_logger = logging.getLogger("tatoebator.skipped_spms")
skipped_spms_logger.setLevel(logging.INFO)
# mode 'w' because i expect this to be rerun a lot on the same sentences during testing - might change later
skipped_spms_logger.addHandler(logging.FileHandler("skipped_spms.log", mode='w', encoding='utf-8'))


class SentenceProductionManager:
    spms = [TatoebaSPM(stringent=False)]

    aspms = [
        # SentenceSearchNeocitiesASPM(), # dubious sourcing
        ManyThingsTatoebaASPM(),
        # TatoebaASPM(), # best to only ingest the more quality controlled ManyThings - we can still query the spm
    ]

    def __init__(self, generate_missing_translations=True):
        self.quality_control = ExampleSentenceQualityEvaluator(
            generate_missing_translations=generate_missing_translations)

    def yield_new_sentences(self, word=None):
        """
        if word is not None
            uses sentence production methods to produce CandidateExampleSentences containing word
            pushes them through quality control, turns them into ExampleSentences
            yields that arbitrarily or until it runs out
        if word is none
            same thing but using arbitrary sentence production methods
        """
        tagged_yielders = [(spm.source_tag, spm.yield_sentences(word)) for spm in self.spms] if word is not None \
            else [(aspm.source_tag, aspm.yield_sentences()) for aspm in self.aspms]

        for tag, yielder in tagged_yielders:
            n_bad = 0
            for n_total,s in enumerate(yielder):
                evaluation = self.quality_control.evaluate_quality(s, word=word)
                if evaluation is QualityEvaluationResult.UNSUITABLE:
                    n_bad += 1
                    if n_bad > 0.8*n_total+20+1:
                        skipped_spms_logger.info(f"{yielder.__name__} deactivated on word {word} - {n_bad}/{n_total+1} unsuitable sentences")
                        break
                    continue
                yield ExampleSentence.from_candidate(s, tag, evaluation is QualityEvaluationResult.GOOD)