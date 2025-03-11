import csv
import csv
import itertools
import os
import re
import time
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Optional, Iterator, List, Dict, Callable, Tuple

import requests
from titlecase import titlecase

from .candidate_example_sentences import ExampleSentenceQualityEvaluator, QualityEvaluationResult
from .example_sentences import CandidateExampleSentence, ExampleSentence
from ..constants import PATH_TO_SOURCES_FILE, USER_AGENT, \
    PATH_TO_EXTERNAL_DOWNLOADS
from ..external_download_requester import ExternalDownloadRequester
from ..language_processing import approximate_jp_root_form, Translator
from ..robots import RobotsAwareSession
from ..util import AutoRemovingThread


def _get_source_tag(source_name: str, license: str):
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
        self.source_tag = _get_source_tag(self.source_name, self.license)


class SentenceProductionMethod(TaggedSource):
    def yield_sentences(self, word: str) -> Iterator[CandidateExampleSentence]:
        raise NotImplementedError()


class ArbitrarySentenceProductionMethod(TaggedSource):
    last_seen_index = 0
    translations_reliable = False
    amt_sentences = None

    def yield_sentences(self, start_at: int = 0) -> Iterator[CandidateExampleSentence]:
        raise NotImplementedError()


class TatoebaSPM(SentenceProductionMethod):
    source_name = 'Tatoeba (via API)'
    license = "CC-BY 2.0 Fr"

    _base_url = "https://api.tatoeba.org"
    _get_sentence_url = "https://api.tatoeba.org/unstable/sentences"
    _default_params = "lang=jpn&trans%3Alang=eng&sort=created"
    _stringent_params = "&is_orphan=no&is_unapproved=no&trans%3Ais_direct=yes&trans%3Ais_unapproved=no&trans%3Ais_orphan=no"
    _block_size = 30

    def __init__(self, stringent=True):
        super().__init__()
        self.query_string = f"{self._get_sentence_url}?{self._default_params}{self._stringent_params if stringent else ''}&limit={self._block_size}"
        self.session = RobotsAwareSession(self._base_url, USER_AGENT)

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

    _base_url = "https://apiv2.immersionkit.com"
    _get_sentence_url = "https://apiv2.immersionkit.com/search?"
    _default_params = "index=&exactMatch=false&limit=0&sort=sentence_length%3Aasc"

    def __init__(self):
        super().__init__()
        self.query_string = f"{self._get_sentence_url}?{self._default_params}"
        self.session = RobotsAwareSession(self._base_url, USER_AGENT)

    def yield_sentences(self, word):
        url = f"{self.query_string}&q={word}"
        response = self.session.get(url)
        response_json = response.json()
        data = response_json['examples']
        for example in data:
            jp_text = example['sentence']
            en_text = example['translation']
            credit = f"{titlecase(example['title'])} (ImmersionKit)"
            yield CandidateExampleSentence(jp_text, en_text, credit=credit)


class SentenceSearchNeocitiesASPM(ArbitrarySentenceProductionMethod):
    source_name = "sentencesearch.neocities.org"
    license = "Unknown"
    translations_reliable = False
    amt_sentences = 45434

    _filepath = os.path.join(PATH_TO_EXTERNAL_DOWNLOADS, 'ssneocities_data.json')

    def __init__(self, external_download_requester: ExternalDownloadRequester):
        super().__init__()
        if not os.path.exists(self._filepath):
            self._download_data_to_cache()

    def _download_data_to_cache(self):
        url = 'https://sentencesearch.neocities.org/data/all_v11.json'
        response = requests.get(url)
        response.raise_for_status()
        with open(self._filepath, 'wb') as file:
            file.write(response.content)

    def yield_sentences(self, start_at: int = 0) -> Iterator[CandidateExampleSentence]:
        # sometimes a space precedes the newline (?)
        jap_pattern = re.compile(r'^ {4}"jap":\s"(.*?)", ?$')
        eng_pattern = re.compile(r'^ {4}"eng":\s"(.*?)"$')
        with open(self._filepath, 'r', encoding='utf-8') as file:

            line_number = 6 * start_at
            for _ in range(start_at):
                if next(file) == "\n": line_number -= 1  # don't count empty lines

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
                    self.last_seen_index = line_number // 6


class ManyThingsTatoebaASPM(ArbitrarySentenceProductionMethod):
    source_name = "ManyThings.org Sentence Pairs"
    license = "CC-BY 2.0 Fr"
    translations_reliable = True
    amt_sentences = 109964

    def __init__(self, external_download_requester: ExternalDownloadRequester):
        super().__init__()
        self._external_download_requester = external_download_requester

    @property
    def _filepath(self):
        filepaths = self._external_download_requester.get_external_downloadable('ManyThingsTatoeba')
        if filepaths is None: return None
        else: return filepaths['filepath']

    def yield_sentences(self, start_at: int = 0) -> Iterator[CandidateExampleSentence]:
        filepath = self._filepath
        if filepath is None:
            print("[Tatoebator] ManyThingsTatoebaASPM aborting because download was refused by user")
            return
        line_matcher = re.compile(r'([^\t]+)\t([^\t]+)\t([^\t]+)')
        license_matcher = re.compile(r'CC-BY 2\.0 \(France\) Attribution: tatoeba\.org #\d+ \((.+)\) & #\d+ \((.+)\)\n')
        with open(filepath, 'r', encoding='utf-8') as file:
            for _ in range(start_at): next(file)
            self.last_seen_index = start_at
            for line in file:
                line_match = line_matcher.match(line)
                eng_text, jap_text, license = line_match.groups()
                en_owner, jp_owner = license_matcher.match(license).groups()
                yield CandidateExampleSentence(jap_text, eng_text, credit=f"{jp_owner}, {en_owner} (Tatoeba)")
                self.last_seen_index += 1


class TatoebaASPM(ArbitrarySentenceProductionMethod):
    source_name = 'Tatoeba (via DB download)'
    license = "CC-BY 2.0 Fr"
    translations_reliable = True
    amt_sentences = 275845

    def __init__(self, external_download_requester: ExternalDownloadRequester):
        super().__init__()
        self._external_download_requester = external_download_requester

    @property
    def _filepaths(self):
        return self._external_download_requester.get_external_downloadable('Tatoeba')

    def _read_lan_file(self, language_tag: str):
        if language_tag not in ['jpn', 'eng']: raise Exception("Incorrect language tag in TatoebaASPM._read_lan_file")
        data = {}
        filepath = self._filepaths[language_tag]
        with open(filepath, encoding='utf-8') as file:
            reader = csv.reader(file, delimiter='\t')
            for idx, text, owner in reader:
                data[idx] = (text, owner if owner != "\\N" else "unknown")
        return data

    def _create_dataframe(self, start_at: int = 0):
        # this used to be written in pandas and yet somehow it was slower
        en_data = self._read_lan_file('eng')
        jp_data = self._read_lan_file('jpn')

        merged_data = []
        seen_jp_idx = set()  # To drop duplicates
        with open(self._filepaths['pairs'], encoding='utf-8') as f:
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
        if self._filepaths is None:
            print("[Tatoebator] TatoebaASPM aborting because download was refused by user")
            return
        df = self._create_dataframe(start_at=start_at)
        self.last_seen_index = start_at
        for jp_text, jp_owner, en_text, en_owner in df:
            yield CandidateExampleSentence(jp_text, en_text, credit=f"{jp_owner}, {en_owner} (Tatoeba)")
            self.last_seen_index += 1


class JapaneseEnglishSubtitleCorpusASPM(ArbitrarySentenceProductionMethod):
    source_name = "Japanese-English Subtitle Corpus"
    license = "CC BY-SA 4.0"
    translations_reliable = False
    amt_sentences = 2801388

    def __init__(self, external_download_requester: ExternalDownloadRequester):
        super().__init__()
        self._external_download_requester = external_download_requester

    @property
    def _filepath(self):
        filepaths = self._external_download_requester.get_external_downloadable('JapaneseEnglishSubtitleCorpus')
        if filepaths is None: return None
        else: return filepaths['filepath']

    def yield_sentences(self, start_at: int = 0) -> Iterator[CandidateExampleSentence]:
        filepath = self._filepath
        if filepath is None:
            print("[Tatoebator] JapaneseEnglishSubtitleCorpusASPM aborting because download was refused by user")
            return
        line_matcher = re.compile(r"([^\t]+)\t([^\t]+)\n")
        self.last_seen_index = start_at
        with open(filepath, 'r', encoding='utf-8') as file:
            for _ in range(start_at): next(file)
            for i, line in enumerate(file):
                en_text, jp_text = line_matcher.fullmatch(line).groups()
                yield CandidateExampleSentence(jp_text, en_text, credit=f"Japanese-English Subtitle Corpus")
                self.last_seen_index += 1


class JParaCrawlASPM(ArbitrarySentenceProductionMethod):
    source_name = "JParaCrawl"
    license = "https://www.kecl.ntt.co.jp/icl/lirg/jparacrawl/"
    translations_reliable = False
    amt_sentences = 25740835

    def __init__(self, external_download_requester: ExternalDownloadRequester):
        super().__init__()
        self._external_download_requester = external_download_requester

    @property
    def _filepath(self):
        filepaths = self._external_download_requester.get_external_downloadable('JParaCrawl')
        if filepaths is None: return None
        else: return filepaths['filepath']

    def yield_sentences(self, start_at: int = 0) -> Iterator[CandidateExampleSentence]:
        filepath = self._filepath
        if filepath is None:
            print("[Tatoebator] JParaCrawlASPM aborting because download was refused by user")
            return
        line_matcher = re.compile(r"([^\t]+)\t([^\t]+)\t([^\t]+)\t([^\t]+)\t([^\t]+)\n")
        self.last_seen_index = start_at
        with open(filepath, 'r', encoding='utf-8') as file:
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


class SentenceProductionManager:
    # TODO in the future we might want to consider giving this an option to also return machine-translated tatoebas
    #  this should only be used when the client (in the app) explicitly asks for it
    #  e.g. a "generate sentences" button, and if clicking it doesn't generate enough sentences,
    #  then a "generate machine-translated sentences" button

    # regarding the absence of...
    # SentenceSearchNeocitiesASPM : dubious sourcing
    # TatoebaSPM :  fixing every new bug that crops up is a hassle, moreover easier to not have to include spms in model
    # ImmersionKitSPM : haven't asked permission + same as above + a lot of it does not make it past quality control

    # TODO get response re permission for jparacrawl

    _aspms_for_ingesting = [
        ManyThingsTatoebaASPM,

    ]

    _aspms_for_searching = [
        TatoebaASPM,
        JapaneseEnglishSubtitleCorpusASPM,
        JParaCrawlASPM,
    ]

    def __init__(self, external_download_requester: ExternalDownloadRequester):
        self._quality_control = ExampleSentenceQualityEvaluator()
        self.amt_searchable_sentences = sum([aspm.amt_sentences for aspm in self._aspms_for_searching])
        self.amt_starter_sentences = sum([aspm.amt_sentences for aspm in self._aspms_for_ingesting])
        self._translator = Translator()  # TODO pass this on from up high

        self._aspms_for_searching = [ASPM(external_download_requester) for ASPM in self._aspms_for_searching]
        self._aspms_for_ingesting = [ASPM(external_download_requester) for ASPM in self._aspms_for_ingesting]

    def yield_starter_sentences(self, desired_amt: Optional[int] = None,
                                filtering_fun: Callable[[CandidateExampleSentence], bool] = lambda s: True) \
            -> Iterator[ExampleSentence]:
        """
        intended to fill the database for the first time with a decent corpus covering most basic/intermediate vocab
        :param desired_amt: how many sentences to ingest from the 'basic sentences' corpora (ManyThingsTatoeba)
        :param filtering_fun: meant to be a callback fun that checks whether a sentence is in the db
        """
        if desired_amt is None: desired_amt = self.amt_starter_sentences
        if desired_amt <= 0: return

        for aspm in self._aspms_for_ingesting:
            evaluate_translations = False if aspm.translations_reliable else True
            for sentence in aspm.yield_sentences():
                evaluation = self._quality_control.evaluate_quality(sentence)
                if evaluation is QualityEvaluationResult.UNSUITABLE or not filtering_fun(sentence): continue
                yield ExampleSentence.from_candidate(sentence, aspm.source_tag,
                                                     evaluation is QualityEvaluationResult.GOOD)
                desired_amt -= 1
                if desired_amt <= 0:
                    return

    def find_new_sentences_with_word(self, word: str, desired_amt: int,
                                     filtering_fun: Callable[[CandidateExampleSentence], bool] = lambda s: True,
                                     progress_callback: Optional[Callable[..., None]] = None) \
            -> List[ExampleSentence]:

        return self.find_new_sentences_with_words({word: desired_amt},
                                                  filtering_fun,
                                                  progress_callback=progress_callback)[word]

    def _snyc_yield_new_sentences_with_words(self, word_desired_amts: Dict[str, int],
                                             filtering_fun: Callable[[CandidateExampleSentence], bool] = lambda s: True) \
            -> Iterator[Tuple[str, ExampleSentence]]:

        # synchronous version of the function below
        # unused, fallback in case problems crop up

        if max(word_desired_amts.values()) <= 0: return

        roots = {approximate_jp_root_form(word): word for word in word_desired_amts}
        for aspm in self._aspms_for_searching:
            evaluate_translations = False if aspm.translations_reliable else True
            for sentence in aspm.yield_sentences():

                # skip sentence if it doesn't contain root of any word we're searching
                found_root = next(filter(lambda root: root in sentence.sentence, roots), None)
                if found_root is None: continue

                # evaluate quality, check contains word lexically
                # +check filtering fun (most likely = check it's not in db)
                if not filtering_fun(sentence): continue
                found_word = roots[found_root]
                evaluation = self._quality_control.evaluate_quality(sentence)
                if evaluation is QualityEvaluationResult.UNSUITABLE: continue
                translation_evaluation = self._quality_control.evaluate_translation_quality(sentence,
                                                                                            translator=self._translator)
                if translation_evaluation is QualityEvaluationResult.UNSUITABLE: continue

                yield found_word, ExampleSentence.from_candidate(sentence, aspm.source_tag,
                                                                 evaluation is QualityEvaluationResult.GOOD)

                # update search progress, break if finished
                word_desired_amts[found_word] -= 1
                if word_desired_amts[found_word] == 0:
                    word_desired_amts.pop(found_word)
                    roots.pop(found_root)
                if len(word_desired_amts) == 0:
                    return

    def find_new_sentences_with_words(self, word_desired_amts: Dict[str, int],
                                      filtering_fun: Callable[[CandidateExampleSentence], bool] = lambda s: True,
                                      max_parallel_translations: int = 50,
                                      translation_batch_size: int = 5,
                                      max_retranslation_attempts: int = 3,
                                      progress_callback: Optional[Callable[..., None]] = None) \
            -> Dict[str, List[ExampleSentence]]:
        """
        searches the searchable aspms for example sentences containing any of the words in word_desired_amts
         puts them through quality control, incl. tl quality. tries to return as many sentences
         as requested in word_desired_amts, but may run short.

        only returns sentences that satisfy filtering_fun (usually a callback meant to determine if
         a sentence is already in the db)

        uses threading to run translation requests in parallel - max_parallel_translations specifies how many
        batches translations to try to keep the amount of api requests down - translation_batch_size
        :param word_desired_amts: dict word -> int, how many sentences to return per each word
        :param filtering_fun: bool callable on ExampleSentence - if false sentence is discarded
        :param max_parallel_translations: -
        :param translation_batch_size: -
        :param max_retranslation_attempts: -
        :return: dict (word -> ExampleSentence) where word is in ExampleSentence (lexically, as verified by qc)
        """

        if max(word_desired_amts.values()) <= 0: return

        words_by_root = {approximate_jp_root_form(word): word for word in word_desired_amts}

        # same as word_desired_amts but with roots (roots are passed around more easily)
        root_desired_amts = {root: word_desired_amts[word] for root, word in words_by_root.items()}
        # same as root_desired_amts but updated along the way to reflect how many we've already found
        root_desired_remaining = root_desired_amts.copy()
        # counts sentences that are currently going through TL eval
        root_being_processed_amts = {root: 0 for root in words_by_root}

        further_processing_queue = []
        awaiting_batched_translation = []
        awaiting_single_translation = []
        passed_all_checks = []
        batch_translation_tasks = set()
        single_translation_tasks = set()

        # to avoid duplicates within search
        seen_sentences = []

        # attempts_left, root, is_good, source_tag, c.e.sentence
        awaiting_translation_type = Tuple[int, str, bool, int, CandidateExampleSentence]
        # root, e.sentence
        passed_all_checks_type = Tuple[str, ExampleSentence]

        found_sentences = {word: [] for word in word_desired_amts}

        def batch_translation_job(batch: List[awaiting_translation_type]):
            translation_batch = "\n".join([sentence.translation for _, _, _, _, sentence in batch])
            machine_translations = self._translator.eng_to_jp(translation_batch).split("\n")
            if len(machine_translations) != len(batch):
                # if the batch translation went wrong (batch elements got mixed up), send everything to single tl
                # don't increase n_attempts counter, this wasn't a real tl attempt bc it didn't go to evaluation
                awaiting_single_translation.extend(batch)
                return

            # if batch translation worked, evaluate everything normally
            # this mirrors the code in single tl eval, except failures are sent back to the batch translation queue
            # (instead of single tl queue)
            for (amt_tries, found_root, is_good, source_tag, sentence), machine_translation in zip(batch,
                                                                                                   machine_translations):
                evaluation = self._quality_control.evaluate_translation_quality(sentence, machine_translation)
                if evaluation is not QualityEvaluationResult.UNSUITABLE:
                    res: passed_all_checks_type = (
                    found_root, ExampleSentence.from_candidate(sentence, source_tag, is_good))
                    passed_all_checks.append(res)
                elif amt_tries + 1 < max_retranslation_attempts:
                    awaiting_batched_translation.append((amt_tries + 1, found_root, is_good, source_tag, sentence))
                else:
                    root_being_processed_amts[found_root] -= 1

        def single_translation_job(item: awaiting_translation_type):
            amt_tries, found_root, is_good, source_tag, sentence = item
            machine_translation = self._translator.eng_to_jp(sentence.translation)
            evaluation = self._quality_control.evaluate_translation_quality(sentence, machine_translation)
            if evaluation is QualityEvaluationResult.UNSUITABLE:
                # if no more tries, give up on this sentence
                amt_tries += 1
                if amt_tries >= max_retranslation_attempts:
                    root_being_processed_amts[found_root] -= 1
                    return
                # otherwise try again - create a new single tl task
                item = (amt_tries, found_root, is_good, source_tag, sentence)
                awaiting_single_translation.append(item)
                return
            # if tl check passes, this sentence is no longer being processed. send it to final queue
            res: passed_all_checks_type = (found_root, ExampleSentence.from_candidate(sentence, source_tag, is_good))
            passed_all_checks.append(res)

        def push_processing_queue_to_tl_queue():
            t = 0  # we could just do the reverse index trick but then the queue would be lifo
            for idx in range(len(further_processing_queue)):
                idx -= t
                root = further_processing_queue[idx][1]
                if root_desired_remaining[root] <= root_being_processed_amts[root]: continue
                res = further_processing_queue.pop(idx)
                awaiting_batched_translation.append(res)
                root_being_processed_amts[root] += 1
                t -= 1

        def create_tl_tasks(ignore_batch_size=False):
            while len(batch_translation_tasks) + len(single_translation_tasks) + 1 <= max_parallel_translations:
                if len(awaiting_batched_translation) >= translation_batch_size \
                        or (ignore_batch_size and len(awaiting_batched_translation) > 0):
                    batch = awaiting_batched_translation[:translation_batch_size]
                    del awaiting_batched_translation[:translation_batch_size]

                    task = AutoRemovingThread(target=batch_translation_job, args=(batch,),
                                              thread_set=batch_translation_tasks)
                    task.daemon = True
                    task.start()

                elif len(awaiting_single_translation) > 0:
                    item = awaiting_single_translation.pop(0)

                    task = AutoRemovingThread(target=single_translation_job, args=(item,),
                                              thread_set=single_translation_tasks)
                    task.daemon = True
                    task.start()

                else:
                    break

        def gather_approved_sentences():
            while passed_all_checks:
                found_root, example_sentence = passed_all_checks.pop(0)
                root_desired_remaining[found_root] -= 1
                root_being_processed_amts[found_root] -= 1
                seen_sentences.append(example_sentence.sentence)

                found_word = words_by_root[found_root]
                found_sentences[found_word].append(example_sentence)

                if root_desired_remaining[found_root] == 0:
                    root_desired_remaining.pop(found_root)
                    assert root_being_processed_amts[found_root] == 0
                    root_being_processed_amts.pop(found_root)

                    # clear further_processing queue of this root
                    for idx in range(len(further_processing_queue) - 1, -1):
                        fpq_root = further_processing_queue[idx][1]
                        if fpq_root == found_root:
                            further_processing_queue.pop(idx)

                    for idx in range(len(seen_sentences) - 1, -1):
                        if found_root in seen_sentences[idx]:
                            seen_sentences.pop(idx)

        search_idx = 0
        for aspm in self._aspms_for_searching:
            evaluate_translations = False if aspm.translations_reliable else True
            source_tag = aspm.source_tag
            for sentence in aspm.yield_sentences():
                search_idx += 1
                search_ratio = search_idx / self.amt_searchable_sentences

                if search_idx % 10000 == 0 and progress_callback is not None:
                    progress_callback(aspm.source_name, search_ratio)

                if search_idx % 10000 == 0 or further_processing_queue or passed_all_checks:
                    push_processing_queue_to_tl_queue()
                    create_tl_tasks()
                    gather_approved_sentences()

                    if len(root_desired_remaining) == 0:
                        assert len(single_translation_tasks) == 0
                        assert len(batch_translation_tasks) == 0
                        return found_sentences

                # skip sentence if it doesn't contain root of any word we're searching for
                found_root = next((root for root in root_desired_remaining if root in sentence.sentence), None)
                if found_root is None: continue

                # evaluate quality, check contains word lexically
                # +check filtering fun (most likely = check it's not in db)
                if sentence.sentence in seen_sentences or not filtering_fun(sentence): continue
                found_word = words_by_root[found_root]
                evaluation = self._quality_control.evaluate_quality(sentence, word=found_word)
                if evaluation is QualityEvaluationResult.UNSUITABLE: continue
                is_good = evaluation is QualityEvaluationResult.GOOD

                # if the proportion of sentences found for this word is lesser than the proportion of the
                # searching db we've looked through, mark it as urgent:
                # meaning it will attempt to be retranslated a few times if the quality check fails
                found_ratio = root_desired_remaining[found_root] / root_desired_amts[found_root]
                urgent = search_ratio + found_ratio > 1
                starting_index = 0 if urgent else max_retranslation_attempts - 1

                if evaluate_translations:
                    res: awaiting_translation_type = (starting_index, found_root, is_good, source_tag, sentence)
                    further_processing_queue.append(res)
                else:
                    res: passed_all_checks_type = (
                        found_root, ExampleSentence.from_candidate(sentence, source_tag, is_good))
                    root_being_processed_amts[found_root] += 1
                    passed_all_checks.append(res)

        # if we still have some leftover stuff in the batch tl queue, make sure to push that through
        while awaiting_single_translation or awaiting_batched_translation or single_translation_tasks or batch_translation_tasks:
            time.sleep(0.1)
            create_tl_tasks(ignore_batch_size=True)
            gather_approved_sentences()
            if len(root_desired_remaining) == 0:
                assert len(single_translation_tasks) == 0
                assert len(batch_translation_tasks) == 0
                return found_sentences

        return found_sentences
