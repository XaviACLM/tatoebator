import asyncio
import csv
import itertools
import os
import re
import subprocess
import zipfile
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Optional, Iterator, List, Dict, Callable, Tuple
from urllib import parse as parse_url

import requests
from titlecase import titlecase

from ..config import SEVENZIP_EXE
from ..constants import CACHE_DIR, TEMP_FILES_DIR, PATH_TO_SOURCES_FILE, USER_AGENT, EXTERNAL_DATASETS_DIR
from .candidate_example_sentences import ExampleSentenceQualityEvaluator, QualityEvaluationResult
from .example_sentences import CandidateExampleSentence, ExampleSentence
from ..language_processing import approximate_jp_root_form, Translator
from ..robots import RobotsAwareSession
from ..util import sync_from_async


def get_source_tag(source_name: str, license: str):
    if ";" in source_name: raise Exception(f"Names passed to get_source_tag cannot contain ';' ({source_name})")
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

    last_seen_index = 0
    translations_reliable = False

    def yield_sentences(self, start_at: int = 0) -> Iterator[CandidateExampleSentence]:
        raise NotImplementedError()


class TatoebaSPM(SentenceProductionMethod):
    source_name = 'Tatoeba (via API)'
    license = "CC-BY 2.0 Fr"

    base_url = "https://api.tatoeba.org"
    get_sentence_url = "https://api.tatoeba.org/unstable/sentences"
    default_params = "lang=jpn&trans%3Alang=eng&sort=created"
    stringent_params = "&is_orphan=no&is_unapproved=no&trans%3Ais_direct=yes&trans%3Ais_unapproved=no&trans%3Ais_orphan=no"
    block_size = 30

    def __init__(self, stringent=True):
        super().__init__()
        self.query_string = f"{self.get_sentence_url}?{self.default_params}{self.stringent_params if stringent else ''}&limit={self.block_size}"
        self.session = RobotsAwareSession(self.base_url, USER_AGENT)

    def yield_sentences(self, word):
        # this api is quite buggy, actually - shame, have to make the code uglier
        #  translation field is sometimes empty
        #   so we continue to the next sentence if it is
        #  for some words, searching for them seems to return random sentences
        #   so we implemented that the ProductionManager skips spms if they return too many unsuitable sentences
        #  some specific queries (seemingly for particularly high pages) return 500 consistently for no apparent reason
        #   so we check and return if so
        #  will sometimes hit you with "unknown parameter: page" (??????????????)
        #   so we start w/o page param (defaults to 1) and navigate via "paging"
        #   which is also weird and inconsistent but you can reliably just check whether it has a 'next' key
        #   no, the 'has_next' key does not always appear
        url = f"{self.query_string}&q={word}"
        while url:
            try:  # ugh
                response = self.session.get(url)
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
            except Exception as e:
                from aqt.utils import showInfo
                showInfo(f"tatoeba hit a snag on {url}")
                raise e


class ImmersionKitSPM(SentenceProductionMethod):

    # just investigating tl quality. DON'T use this in production, we haven't asked for permission

    source_name = 'ImmersionKit'
    license = 'Unknown'
    translations_reliable = False

    base_url = "https://apiv2.immersionkit.com"
    get_sentence_url = "https://apiv2.immersionkit.com/search?"
    default_params = "index=&exactMatch=false&limit=0&sort=sentence_length%3Aasc"

    def __init__(self):
        super().__init__()
        self.query_string = f"{self.get_sentence_url}?{self.default_params}"
        self.session = RobotsAwareSession(self.base_url, USER_AGENT)

    def yield_sentences(self, word):
        url = f"{self.query_string}&q={word}"
        print(url)
        response = self.session.get(url)
        response_json = response.json()
        data = response_json['examples']
        for example in data:
            jp_text = example['sentence']
            en_text = example['translation']
            credit = f"{titlecase(example['title'])} (ImmersionKit)"
            yield CandidateExampleSentence(jp_text, en_text, credit=credit)


class TatoebaASPM(ArbitrarySentenceProductionMethod):
    source_name = 'Tatoeba (via DB download)'
    license = "CC-BY 2.0 Fr"
    translations_reliable = True

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
        tatoeba_session = RobotsAwareSession("https://tatoeba.org", USER_AGENT)

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

            # unnecesary with robots-aware
            # time.sleep(3)  # Wait before retrying

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

    def _read_lan_file(self, language_tag: str):
        if language_tag not in ['jp','en']: raise Exception("Incorrect language tag in TatoebaASPM._read_lan_file")
        data = {}
        filepath = self.en_filepath if language_tag == 'en' else self.jp_filepath
        with open(filepath, encoding='utf-8') as file:
            reader = csv.reader(file, delimiter='\t')
            for idx, text, owner in reader:
                data[idx] = (text, owner if owner != "\\N" else "unknown")
        return data

    def _create_dataframe(self, start_at: int = 0):
        # this used to be written in pandas and yet somehow it was slower
        en_data = self._read_lan_file('en')
        jp_data = self._read_lan_file('jp')

        merged_data = []
        seen_jp_idx = set()  # To drop duplicates
        with open(self.pairs_filepath, encoding='utf-8') as f:
            for _ in range(start_at): next(f)
            reader = csv.reader(f, delimiter='\t')
            for en_idx, jp_idx in reader:
                if jp_idx in seen_jp_idx: continue
                seen_jp_idx.add(jp_idx)
                if jp_idx not in jp_data or en_idx not in en_data: continue
                jp_text, jp_owner = jp_data[jp_idx]
                en_text, en_owner = en_data[en_idx]
                merged_data.append((jp_text, jp_owner, en_text, en_owner))

        return merged_data

    def yield_sentences(self, start_at: int = 0) -> Iterator[CandidateExampleSentence]:
        df = self._create_dataframe(start_at=start_at)
        self.last_seen_index = start_at
        for jp_text, jp_owner, en_text, en_owner in df:
            yield CandidateExampleSentence(jp_text, en_text, credit=f"{jp_owner}, {en_owner} (Tatoeba)")
            self.last_seen_index += 1


class SentenceSearchNeocitiesASPM(ArbitrarySentenceProductionMethod):
    source_name = "sentencesearch.neocities.org"
    license = "Unknown"
    translations_reliable = False

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

    def yield_sentences(self, start_at: int = 0) -> Iterator[CandidateExampleSentence]:
        # sometimes a space precedes the newline (?)
        jap_pattern = re.compile(r'^ {4}"jap":\s"(.*?)", ?$')
        eng_pattern = re.compile(r'^ {4}"eng":\s"(.*?)"$')
        with open(self.filepath, 'r', encoding='utf-8') as file:

            line_number = 6*start_at
            for _ in range(start_at):
                if next(file)=="\n": line_number -=1 #don't count empty lines

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
                    self.last_seen_index = line_number//6


class ManyThingsTatoebaASPM(ArbitrarySentenceProductionMethod):
    source_name = "ManyThings.org Sentence Pairs"
    license = "CC-BY 2.0 Fr"
    translations_reliable = True

    def __init__(self):
        super().__init__()
        self.filepath = os.path.join(CACHE_DIR, 'manythings_tatoeba.txt')
        if not os.path.exists(self.filepath):
            self._download_data_to_cache()

    def _download_data_to_cache(self):
        zip_filepath = os.path.join(TEMP_FILES_DIR, 'jpn-eng.zip')
        if not os.path.exists(zip_filepath):
            url = 'https://www.manythings.org/anki/jpn-eng.zip'
            response = requests.get(url)
            with open(zip_filepath, 'wb') as file:
                file.write(response.content)
        with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
            with zip_ref.open('jpn.txt') as orig, open(self.filepath, 'wb') as dest:
                dest.write(orig.read())
        os.remove(zip_filepath)

    def yield_sentences(self, start_at: int = 0) -> Iterator[CandidateExampleSentence]:
        line_matcher = re.compile(r'([^\t]+)\t([^\t]+)\t([^\t]+)')
        license_matcher = re.compile(r'CC-BY 2\.0 \(France\) Attribution: tatoeba\.org #\d+ \((.+)\) & #\d+ \((.+)\)\n')
        with open(self.filepath, 'r', encoding='utf-8') as file:
            for _ in range(start_at): next(file)
            self.last_seen_index = start_at
            for line in file:
                line_match = line_matcher.match(line)
                eng_text, jap_text, license = line_match.groups()
                en_owner, jp_owner = license_matcher.match(license).groups()
                yield CandidateExampleSentence(jap_text, eng_text, credit=f"{jp_owner}, {en_owner} (Tatoeba)")
                self.last_seen_index += 1


class JParaCrawlASPM(ArbitrarySentenceProductionMethod):
    source_name = "JParaCrawl"
    license = "https://www.kecl.ntt.co.jp/icl/lirg/jparacrawl/"
    translations_reliable = False

    def __init__(self):
        super().__init__()
        # 10GB, so manual download required
        # find the compressed files at https://www.kecl.ntt.co.jp/icl/lirg/jparacrawl/
        self.filepath = os.path.join(EXTERNAL_DATASETS_DIR, 'en-ja.bicleaner05.txt')

    def yield_sentences(self, start_at: int = 0) -> Iterator[CandidateExampleSentence]:
        line_matcher = re.compile(r"([^\t]+)\t([^\t]+)\t([^\t]+)\t([^\t]+)\t([^\t]+)\n")
        self.last_seen_index = start_at
        with open(self.filepath, 'r', encoding='utf-8') as file:
            for _ in range(start_at): next(file)
            for line in file:
                source_1, source_2, score, en_text, jp_text = line_matcher.fullmatch(line).groups()
                common_source = self._common_source(source_1, source_2)
                credit = f"{common_source} (JParaCrawl)" if len(common_source) > 8 else "JParaCrawl"
                # TODO this can lead to really long credits (>60 chars) - we'll need to ensure the HTML can resize

                yield CandidateExampleSentence(jp_text, en_text, credit=credit)
                self.last_seen_index += 1

    @classmethod
    @lru_cache
    def _common_source(cls, str1: str, str2: str) -> str:
        l1, l2 = str1.split("."), str2.split(".")
        # just finds longest common substring
        # what's really in this class, moreso than the function, is the cache
        m = SequenceMatcher(None, l1, l2).find_longest_match()
        return ".".join(l1[m.a:m.a + m.size])


class JapaneseEnglishSubtitleCorpusASPM(ArbitrarySentenceProductionMethod):
    source_name = "Japanese-English Subtitle Corpus"
    license = "CC BY-SA 4.0"
    translations_reliable = False

    def __init__(self):
        super().__init__()
        # manual download required
        # find the compressed files at https://www.kecl.ntt.co.jp/icl/lirg/jparacrawl/
        self.filepath = os.path.join(EXTERNAL_DATASETS_DIR, 'parallel_subtitles')

    def yield_sentences(self, start_at: int = 0) -> Iterator[CandidateExampleSentence]:
        line_matcher = re.compile(r"([^\t]+)\t([^\t]+)\n")
        self.last_seen_index = start_at
        with open(self.filepath, 'r', encoding='utf-8') as file:
            for _ in range(start_at): next(file)
            for i,line in enumerate(file):
                en_text, jp_text = line_matcher.fullmatch(line).groups()
                yield CandidateExampleSentence(jp_text, en_text, credit=f"Japanese-English Subtitle Corpus")
                self.last_seen_index += 1


class SentenceProductionManager:

    # TODO in the future we might want to consider giving this an option to also return machine-translated tatoebas
    #  this should only be used when the client (in the app) explicitly asks for it
    #  e.g. a "generate sentences" button, and if clicking it doesn't generate enough sentences,
    #  then a "generate machine-translated sentences" button

    # regarding the absence of...
    # SentenceSearchNeocitiesASPM : dubious sourcing
    # TatoebaSPM :  fixing every new bug that crops up is a hassle, moreover easier to not have to include spms in model
    # ImmersionKitSPM : haven't asked permission + same as above + a lot of it does not make it past quality control

    aspms_for_ingesting = [
        ManyThingsTatoebaASPM(),

    ]

    aspms_for_searching = [
        TatoebaASPM(),
        JapaneseEnglishSubtitleCorpusASPM(),
        JParaCrawlASPM(),
    ]

    def __init__(self):
        self.quality_control = ExampleSentenceQualityEvaluator()

    def yield_starter_sentences(self, desired_amt: int,
                                filtering_fun: Callable[[CandidateExampleSentence], bool] = lambda s: True)\
            -> Iterator[ExampleSentence]:
        """
        intended to fill the database for the first time with a decent corpus covering most basic/intermediate vocab
        :param desired_amt: how many sentences to ingest from the 'basic sentences' corpora (ManyThingsTatoeba)
        :param filtering_fun: meant to be a callback fun that checks whether a sentence is in the db
        """
        if desired_amt <= 0: return

        for aspm in self.aspms_for_ingesting:
            evaluate_translations = False if aspm.translations_reliable else True
            for sentence in aspm.yield_sentences():
                evaluation = self.quality_control.evaluate_quality(sentence, evaluate_translation=evaluate_translations)
                if evaluation is QualityEvaluationResult.UNSUITABLE or not filtering_fun(sentence): continue
                yield ExampleSentence.from_candidate(sentence, aspm.source_tag, evaluation is QualityEvaluationResult.GOOD)
                desired_amt -= 1
                if desired_amt <= 0:
                    return

    def yield_new_sentences_with_word(self, word: str, desired_amt: int,
                                      filtering_fun: Callable[[CandidateExampleSentence], bool] = lambda s: True)\
            -> Iterator[ExampleSentence]:

        yield from map(lambda pair: pair[1],
                       self.yield_new_sentences_with_words([word], {word:desired_amt}, filtering_fun))

    def yield_new_sentences_with_words(self, word_desired_amts: Dict[str, int],
                                       filtering_fun: Callable[[CandidateExampleSentence], bool] = lambda s: True)\
            -> Iterator[Tuple[str, ExampleSentence]]:

        if max(word_desired_amts.values()) <= 0: return

        roots = {approximate_jp_root_form(word): word for word in word_desired_amts}
        for aspm in self.aspms_for_searching:
            evaluate_translations = False if aspm.translations_reliable else True
            for sentence in aspm.yield_sentences():

                # skip sentence if it doesn't contain root of any word we're searching
                found_root = next(filter(lambda root: root in sentence.sentence, roots), None)
                if found_root is None: continue

                # evaluate quality, check contains word lexically
                # +check filtering fun (most likely = check it's not in db)
                if not filtering_fun(sentence): continue
                found_word = roots[found_root]
                evaluation = self.quality_control.evaluate_quality(sentence)
                if evaluation is QualityEvaluationResult.UNSUITABLE: continue
                translation_evaluation = self.quality_control.evaluate_translation_quality(sentence)
                if translation_evaluation is QualityEvaluationResult.UNSUITABLE: continue

                yield found_word, ExampleSentence.from_candidate(sentence, aspm.source_tag, evaluation is QualityEvaluationResult.GOOD)

                # update search progress, break if finished
                word_desired_amts[found_word] -= 1
                if word_desired_amts[found_word] == 0:
                    word_desired_amts.pop(found_word)
                    roots.pop(found_root)
                if len(word_desired_amts) == 0:
                    return

    @sync_from_async
    async def async_yield_new_sentences_with_words(self, word_desired_amts: Dict[str, int],
                                             filtering_fun: Callable[[CandidateExampleSentence], bool] = lambda s: True,
                                             max_parallel_translations = 10)\
            -> Iterator[Tuple[str, ExampleSentence]]:

        if max(word_desired_amts.values()) <= 0: return

        roots = {approximate_jp_root_form(word): word for word in word_desired_amts}

        # TODO pass this on from up high
        translator = Translator()

        BATCH_SIZE = 3

        awaiting_batched_translation_queue = asyncio.Queue(maxsize=BATCH_SIZE)
        passed_all_checks_queue = asyncio.Queue(maxsize=1)
        batched_translation_tasks = set()
        single_translation_tasks = set()

        awaiting_batched_translation_type = Tuple[str, bool, int, CandidateExampleSentence]
        awaiting_single_translation_type = Tuple[int, str, bool, int, CandidateExampleSentence]
        passed_all_checks_type = Tuple[str, ExampleSentence]

        async def generate_and_primary_check():
            for aspm in self.aspms_for_searching:
                evaluate_translations = False if aspm.translations_reliable else True
                source_tag = aspm.source_tag
                for sentence in aspm.yield_sentences():

                    # skip sentence if it doesn't contain root of any word we're searching
                    found_root = next(filter(lambda root: root in sentence.sentence, roots), None)
                    if found_root is None: continue

                    # evaluate quality, check contains word lexically
                    # +check filtering fun (most likely = check it's not in db)
                    if not filtering_fun(sentence): continue
                    found_word = roots[found_root]
                    evaluation = self.quality_control.evaluate_quality(sentence, word = found_word)
                    if evaluation is QualityEvaluationResult.UNSUITABLE: continue
                    is_good = evaluation is QualityEvaluationResult.GOOD

                    if evaluate_translations:
                        res: awaiting_batched_translation_type = (found_root, is_good, source_tag, sentence)
                        await awaiting_batched_translation_queue.put(res)
                        if awaiting_batched_translation_queue.qsize() > BATCH_SIZE:
                            await translation_eval_job_batch_task()
                    else:
                        res: passed_all_checks_type = (found_root, ExampleSentence.from_candidate(sentence, source_tag, is_good))
                        await passed_all_checks_queue.put(res)
            if awaiting_batched_translation_queue.qsize() > 0:
                await translation_eval_job_batch_task()

        awaiting_single_translation_type = Tuple[int, str, bool, int, CandidateExampleSentence]

        async def translation_eval_job_batch_task():
            batch = [await awaiting_batched_translation_queue.get() for _ in range(BATCH_SIZE)]
            task = asyncio.create_task(batched_translation_eval_task(batch))
            batched_translation_tasks.add(task)
            task.add_done_callback(batched_translation_tasks.discard)

        async def single_translation_eval_task(item: awaiting_single_translation_type):
            counter, found_root, is_good, source_tag, sentence = item
            machine_translation = await translator.async_eng_to_jp(sentence.translation)
            evaluation = self.quality_control.evaluate_translation_quality(sentence, machine_translation)
            if evaluation is QualityEvaluationResult.UNSUITABLE:
                # TODO redo if necessary... you know
                return
            res: passed_all_checks_type = (found_root, ExampleSentence.from_candidate(sentence, source_tag, is_good))
            await passed_all_checks_queue.put(res)

        async def batched_translation_eval_task(batch: List[awaiting_batched_translation_type]):
            translation_batch = "\n".join([sentence.translation for _,_,_, sentence in batch])
            machine_translations = (await translator.async_eng_to_jp(translation_batch)).split("\n")
            if len(machine_translations) != len(translation_batch):
                for item in batch:
                    res: awaiting_single_translation_type = 0, *item
                    task = asyncio.create_task(single_translation_eval_task(res))
                    single_translation_tasks.add(task)
                    task.add_done_callback(single_translation_tasks.discard)
                return

            for (found_root, is_good, source_tag, sentence), machine_translation in zip(batch, machine_translations):
                evaluation = self.quality_control.evaluate_translation_quality(sentence, machine_translation)
                if evaluation is QualityEvaluationResult.UNSUITABLE:
                    # TODO redo if necessary... you know
                    continue
                res: passed_all_checks_type = (found_root, ExampleSentence.from_candidate(sentence, source_tag, is_good))
                await passed_all_checks_queue.put(res)

        producer_task = asyncio.create_task(generate_and_primary_check())

        while (not producer_task.done()
               or batched_translation_tasks
               or single_translation_tasks
               or awaiting_batched_translation_queue
               or awaiting_single_translation_type
               or passed_all_checks_queue):
            found_root, sentence = await passed_all_checks_queue.get()
            yield sentence

            found_word = roots[found_root]

            # update search progress, break if finished
            word_desired_amts[found_word] -= 1
            if word_desired_amts[found_word] == 0:
                word_desired_amts.pop(found_word)
                roots.pop(found_root)
            if len(word_desired_amts) == 0:
                break
