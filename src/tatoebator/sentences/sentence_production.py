import asyncio
import csv
import itertools
import os
import re
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
        return self._external_download_requester.get_external_downloadable('ManyThingsTatoeba')['filepath']

    def yield_sentences(self, start_at: int = 0) -> Iterator[CandidateExampleSentence]:
        line_matcher = re.compile(r'([^\t]+)\t([^\t]+)\t([^\t]+)')
        license_matcher = re.compile(r'CC-BY 2\.0 \(France\) Attribution: tatoeba\.org #\d+ \((.+)\) & #\d+ \((.+)\)\n')
        with open(self._filepath, 'r', encoding='utf-8') as file:
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
        df = self._create_dataframe(start_at=start_at)
        self.last_seen_index = start_at
        for jp_text, jp_owner, en_text, en_owner in df:
            yield CandidateExampleSentence(jp_text, en_text, credit=f"{jp_owner}, {en_owner} (Tatoeba)")
            self.last_seen_index += 1


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


class JapaneseEnglishSubtitleCorpusASPM(ArbitrarySentenceProductionMethod):
    source_name = "Japanese-English Subtitle Corpus"
    license = "CC BY-SA 4.0"
    translations_reliable = False
    amt_sentences = 2801388

    def __init__(self, external_download_requester: ExternalDownloadRequester):
        super().__init__()
        # manual download required
        # find the compressed files at https://www.kecl.ntt.co.jp/icl/lirg/jparacrawl/
        self.filepath = os.path.join(PATH_TO_EXTERNAL_DOWNLOADS, 'parallel_subtitles')

    def yield_sentences(self, start_at: int = 0) -> Iterator[CandidateExampleSentence]:
        line_matcher = re.compile(r"([^\t]+)\t([^\t]+)\n")
        self.last_seen_index = start_at
        with open(self.filepath, 'r', encoding='utf-8') as file:
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
        # 10GB, so manual download required
        # find the compressed files at https://www.kecl.ntt.co.jp/icl/lirg/jparacrawl/
        self._filepath = os.path.join(PATH_TO_EXTERNAL_DOWNLOADS, 'en-ja.bicleaner05.txt')

    def yield_sentences(self, start_at: int = 0) -> Iterator[CandidateExampleSentence]:
        line_matcher = re.compile(r"([^\t]+)\t([^\t]+)\t([^\t]+)\t([^\t]+)\t([^\t]+)\n")
        self.last_seen_index = start_at
        with open(self._filepath, 'r', encoding='utf-8') as file:
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

    def snyc_yield_new_sentences_with_words(self, word_desired_amts: Dict[str, int],
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

        uses asyncio to run translation requests in parallel - max_parallel_translations specifies how many
        batches translations to try to keep the amount of api requests down - translation_batch_size
        :param word_desired_amts: dict word -> int, how many sentences to return per each word
        :param filtering_fun: bool callable on ExampleSentence - if false sentence is discarded
        :param max_parallel_translations: -
        :param translation_batch_size: -
        :param max_retranslation_attempts: -
        :return: yields (word, ExampleSentence) pairs where word is in ExampleSentence (lexically, as verified by qc)
        """

        # abandon all hope ye who enter here
        # this is very bad code. much too complicated a task for a first experience with asyncio

        if max(word_desired_amts.values()) <= 0: return

        roots = {approximate_jp_root_form(word): word for word in word_desired_amts}

        # same as word_desired_amts but with roots (roots are passed around more easily)
        root_desired_amts = {root: word_desired_amts[word] for root, word in roots.items()}
        # same as root_desired_amts but updated along the way to reflect how many we've already found
        root_desired_remaining = root_desired_amts.copy()
        # counts sentences that are currently going through TL eval
        root_being_processed_amts = {root: 0 for root in roots}

        awaiting_batched_translation_queue = asyncio.Queue(maxsize=translation_batch_size)
        passed_all_checks_queue = asyncio.Queue(maxsize=1)
        batched_translation_tasks = set()
        single_translation_tasks = set()

        # attempts_left, root, is_good, source_tag, c.e.sentence
        awaiting_translation_type = Tuple[int, str, bool, int, CandidateExampleSentence]
        # root, e.sentence
        passed_all_checks_type = Tuple[str, ExampleSentence]

        # to avoid duplicates within search
        seen_sentences = set()

        async def generate_and_primary_check():
            idx = 0
            for aspm in self._aspms_for_searching:
                evaluate_translations = False if aspm.translations_reliable else True
                source_tag = aspm.source_tag
                for sentence in aspm.yield_sentences():
                    idx += 1
                    search_ratio = idx / self.amt_searchable_sentences
                    if idx % 10000 == 0 and progress_callback is not None:
                        progress_callback(aspm.source_name, search_ratio)
                    if idx % 100000 == 0 and progress_callback is not None:
                        await asyncio.sleep(0.1) # 1s per 10m sentences

                    if idx%1000000==0:
                        print(idx, root_desired_remaining, root_being_processed_amts, len(asyncio.all_tasks()))

                    # skip sentence if it doesn't contain root of any word we're searching for
                    found_root = next(
                        filter(lambda root: root_desired_remaining[root] > root_being_processed_amts[root]
                                            and root in sentence.sentence, roots), None)
                    if found_root is None: continue

                    print(found_root, root_desired_remaining[found_root], root_being_processed_amts[found_root])

                    root_being_processed_amts[found_root] += 1

                    # evaluate quality, check contains word lexically
                    # +check filtering fun (most likely = check it's not in db)
                    if sentence.sentence in seen_sentences or not filtering_fun(sentence):
                        root_being_processed_amts[found_root] -= 1
                        continue
                    found_word = roots[found_root]
                    evaluation = self._quality_control.evaluate_quality(sentence, word=found_word)
                    if evaluation is QualityEvaluationResult.UNSUITABLE:
                        root_being_processed_amts[found_root] -= 1
                        continue
                    is_good = evaluation is QualityEvaluationResult.GOOD

                    # if the proportion of sentences found for this word is lesser than the proportion of the
                    # searching db we've looked through, mark it as urgent:
                    # meaning it will attempt to be retranslated a few times if the quality check fails
                    found_ratio = root_desired_remaining[found_root] / root_desired_amts[found_root]
                    urgent = search_ratio + found_ratio > 1
                    starting_index = 0 if urgent else max_retranslation_attempts - 1

                    if evaluate_translations:
                        res: awaiting_translation_type = (starting_index, found_root, is_good, source_tag, sentence)
                        await awaiting_batched_translation_queue.put(res)
                        if awaiting_batched_translation_queue.qsize() >= translation_batch_size:
                            await translation_eval_job_batch_task(translation_batch_size)
                            await asyncio.sleep(0.1)  # yield execution (to translator)
                    else:
                        res: passed_all_checks_type = (
                        found_root, ExampleSentence.from_candidate(sentence, source_tag, is_good))

                        await passed_all_checks_queue.put(res)
                        await asyncio.sleep(0.1)

            if awaiting_batched_translation_queue.qsize() > 0:
                await translation_eval_job_batch_task(awaiting_batched_translation_queue.qsize())

        async def translation_eval_job_batch_task(this_batch_size: int):
            batch = [await awaiting_batched_translation_queue.get() for _ in range(this_batch_size)]
            while (len(batched_translation_tasks) + 1) * translation_batch_size + len(
                    single_translation_tasks) > max_parallel_translations:
                await asyncio.sleep(0.1)
            task = asyncio.create_task(batched_translation_eval_task(batch))
            batched_translation_tasks.add(task)
            task.add_done_callback(batched_translation_tasks.discard)

        async def single_translation_eval_task(item: awaiting_translation_type):
            print("\t"*20,"single tl")
            amt_tries, found_root, is_good, source_tag, sentence = item
            machine_translation = await self._translator.async_eng_to_jp(sentence.translation)
            print("\t"*20,"single tl finished")
            evaluation = self._quality_control.evaluate_translation_quality(sentence, machine_translation)
            if evaluation is QualityEvaluationResult.UNSUITABLE:

                # if no more tries, give up on this sentence
                amt_tries += 1
                if amt_tries >= max_retranslation_attempts:
                    root_being_processed_amts[found_root] -= 1
                    return

                # otherwise try again - create a new single tl task
                item = (amt_tries, found_root, is_good, source_tag, sentence)
                while (len(batched_translation_tasks) - 1) * translation_batch_size + len(
                        single_translation_tasks) + 1 > max_parallel_translations:
                    await asyncio.sleep(0.1)
                task = asyncio.create_task(single_translation_eval_task(item))
                task.set_name("single-tl")
                single_translation_tasks.add(task)
                task.add_done_callback(single_translation_tasks.discard)
                return

            # if tl check passes, this sentence is no longer being processed. send it to final queue
            res: passed_all_checks_type = (found_root, ExampleSentence.from_candidate(sentence, source_tag, is_good))
            await passed_all_checks_queue.put(res)

        async def batched_translation_eval_task(batch: List[awaiting_translation_type]):
            print("\t"*20,"batch tl")
            translation_batch = "\n".join([sentence.translation for _, _, _, _, sentence in batch])
            machine_translations = (await self._translator.async_eng_to_jp(translation_batch)).split("\n")
            print("\t"*20,"batch tl finished")
            if len(machine_translations) != len(batch):
                print("\t"*20, "batch tl mismatched lengths")
                # if the batch translation went wrong (batch elements got mixed up), send everything to single tl
                # don't increase n_attempts counter, this wasn't a real tl attempt bc it didn't go to evaluation
                for item in batch:
                    while (len(batched_translation_tasks) - 1) * translation_batch_size + len(
                            single_translation_tasks) + 1 > max_parallel_translations:
                        await asyncio.sleep(0.1)
                    task = asyncio.create_task(single_translation_eval_task(item))
                    task.set_name("single-tl")
                    single_translation_tasks.add(task)
                    task.add_done_callback(single_translation_tasks.discard)
                return

            # if batch translation worked, evaluate everything normally
            # this mirrors the code in single tl eval, except failures are sent back to the batch translation queue
            # (instead of single tl queue)
            print("\t"*20, "batch tl matched lengths: looking into it...")
            for (amt_tries, found_root, is_good, source_tag, sentence), machine_translation in zip(batch,
                                                                                                   machine_translations):
                print("\t"*21, sentence.sentence, "//", machine_translation)
                evaluation = self._quality_control.evaluate_translation_quality(sentence, machine_translation)
                if evaluation is QualityEvaluationResult.UNSUITABLE:
                    amt_tries += 1
                    if amt_tries >= max_retranslation_attempts:
                        print("\t" * 21, "batch tl bad tl, too many tries, discarding")
                        root_being_processed_amts[found_root] -= 1
                        continue
                    print("\t" * 21, "batch tl bad tl, going back into batch tl queue")
                    await awaiting_batched_translation_queue.put((amt_tries, found_root, is_good, source_tag, sentence))

                    continue
                res: passed_all_checks_type = (
                found_root, ExampleSentence.from_candidate(sentence, source_tag, is_good))
                print("\t" * 21, "batch tl good tl: going into final queue")
                await passed_all_checks_queue.put(res)

        async def main_task():
            producer_task = asyncio.create_task(generate_and_primary_check())
            producer_task.set_name("producer")

            found_sentences = {word: [] for word in word_desired_amts}

            while (not producer_task.done()
                   or batched_translation_tasks
                   or single_translation_tasks
                   or not awaiting_batched_translation_queue.empty()
                   or not passed_all_checks_queue.empty()):

                try:
                    found_root, sentence = await asyncio.wait_for(passed_all_checks_queue.get(),1)
                except asyncio.exceptions.TimeoutError:
                    continue
                found_word = roots[found_root]

                # double check in case a duplicate pair was awaiting TL simultaneously
                if sentence.sentence in seen_sentences: continue
                seen_sentences.add(sentence.sentence)

                print(found_word, sentence.sentence)

                found_sentences[found_word].append(sentence)

                # update search progress, break if finished
                root_desired_remaining[found_root] -= 1
                root_being_processed_amts[found_root] -= 1
                if root_desired_remaining[found_root] == 0:
                    root_desired_remaining.pop(found_root)
                    roots.pop(found_root)
                if len(root_desired_remaining) == 0:
                    break

            producer_task.cancel()

            return found_sentences

        return asyncio.run(main_task())

    def find_new_sentences_with_words_2(self, word_desired_amts: Dict[str, int],
                                      filtering_fun: Callable[[CandidateExampleSentence], bool] = lambda s: True,
                                      max_parallel_translations: int = 50,
                                      translation_batch_size: int = 5,
                                      max_retranslation_attempts: int = 3,
                                      progress_callback: Optional[Callable[..., None]] = None) \
            -> Dict[str, List[ExampleSentence]]:
        pass
        #we got two main threads
        #one of em produces the sentences and stuff them in the tl queues
        #and... or maybe it should be one single main thread? it ends up being the same computation cost of you look inna it
        # so main thread: loops, produces sentences, checks they contain root, puts them through first quality check
        # let's not think about limiting amounts yet
        # once they go through all prelim checks they get put on a queue - really could be a list. fuck it, will be a list
        # awaiting batch tl queue
        # main loop handles this: if the queue hits the certain size it creates a task for batch tl
        # goes in a list of queued batch tls. perhaps this list has a max size? oh with the math, we know how  to do this
        # from batch tl goes back into batch tl (can also create a new task) or into single tl or into final queue - we know all this
        # main loop picks it back up - at some point it peeps into the final queue and emits if appropiate
        # (¿yields? - i'm not sure. we'll have to look into the possibility of suspending threads. actually
        #    that is a problem, we want to know when the search ENDS so we can kill all threads. i mean there's ways...
        #    but i don't know, it doesn't feel correct)
        # batch size config is easy.
        # max parallel translations - its easy at any point to know how many translations are going on. we can keep
        # stuff in a TL queue (NOT a task queue). two tl queues, really
        # main loop handles creating ALL translation tasks from the tl queues when there is enough space for them.
        # if all tl slots are closed then no tl tasks are readied this loop, that's fine, we'll get to them
        # but what about the limiting?
        # well, best we don't throw away anything prematurely. everything gets put in the queues.
        # approach 1: count how many sentences with a certain word you still need. while >0, generate new tl tasks
        # problem: simultaneous tl tasks means we might generate more than needed
        # approach 2: count how many sentences are in processing. Ensure that amount is lesser than the amount of
        #  sentences you still need before generating new tl tasks.
        # problem: most tl tasks fail. When we only want one last sentence, we're slowing ourselves down by only doing
        #  one tl at a time
        #  is this really a problem, though? B/c of parallelism this wastes as much time for one word as for 100
        #  and assuming 4/5 TLs fail and we can do 10 concurrent TLs and they take 1s then this means
        #  last is 5-1s slower, then 5/2-1, then 5/3-1, then 5/4-1... 4+3/2+2/3+1/4 ~ 6.5s
        #  i mean i don't know. we can fix it with approach 3 but i'm not sure it's even worth it
        #  esp considering this is assuming we get all our queued-for-tl sentences instantly, which is v far from the truth
        #  if they are separated by a single second then the difference vanishes
        #  makes it seem like we would be just fine with one tl worker per keyword. but that disables batching so eh eh
        #  oh yeah i forgot about batching. yeah this problem isn't really that significant
        #  approach 3 was pretty much just to allow some slack on the constraint of approach 2
        #  one task of slack gets the worst case slowdown to 2.5s, two tasks to <1s. maybe it'd be good?
        #  or maybe we avoid it to save ourselves from having to code the logic of discarding overproduction after tl checks
