from __future__ import annotations

import bz2
import csv
import os
import subprocess
import tarfile
import zipfile
from asyncio import Protocol
from enum import Enum
from typing import Dict, List, Optional, Type, Tuple
from urllib import parse as parse_url
import re

from requests import Session

from .config import SEVENZIP_EXE
from .constants import PATH_TO_EXTERNAL_DOWNLOADS, PATH_TO_TEMP_EXTERNAL_DOWNLOADS, USER_AGENT, PATH_TO_USER_FILES
from .robots import RobotsAwareSession


class ManualDownloadInstructionType(Enum):
    TEXT = 0
    URL_BUTTON = 1
    BUTTON = 2
    FILE_CHECK_WIDGET = 3


mdit = ManualDownloadInstructionType
ManualDownloadInstructions = List[Tuple[mdit, ...]]


class Downloadable:
    name: str  # tag name by which this is referenced
    item_filepaths: Dict[str, str]  # internal tags -> filepaths where the items *should* be found

    size = 'Unknown size'
    processed_size = None

    def get_manual_download_instructions(self) -> Optional[ManualDownloadInstructions]:
        return None

    @classmethod
    def are_files_downloaded(cls) -> bool:
        return all((os.path.exists(filepath) for filepath in cls.item_filepaths.values()))


class AutomaticallyDownloadable(Protocol):
    @classmethod
    def attempt_automatic_download(cls) -> None:
        raise NotImplemented


class ManyThingsTatoebaDownloadable(Downloadable, AutomaticallyDownloadable):
    name = 'ManyThingsTatoeba'
    item_filepaths = {'filepath': os.path.join(PATH_TO_EXTERNAL_DOWNLOADS, 'manythings_tatoeba.txt')}

    size = '4.4MB'
    processed_size = '17.1MB'

    _partial_download_filepaths = {'filepath': os.path.join(PATH_TO_TEMP_EXTERNAL_DOWNLOADS, 'jpn-eng.zip')}
    _direct_download_url = 'https://www.manythings.org/anki/jpn-eng.zip'

    @classmethod
    def attempt_automatic_download(cls) -> None:
        cls._download_zipped_files()
        cls._unzip_downloads()

    @classmethod
    def _download_zipped_files(cls) -> None:

        session = RobotsAwareSession('https://www.manythings.org', USER_AGENT)
        url = cls._direct_download_url
        response = session.get(url)
        if response.status_code != 200:
            raise Exception("Download GET request to manythings.org failed")
        with open(cls._partial_download_filepaths['filepath'], 'wb') as file:
            file.write(response.content)

    @classmethod
    def _unzip_downloads(cls) -> None:
        zip_filepath = cls._partial_download_filepaths['filepath']
        with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
            with zip_ref.open('jpn.txt') as orig, open(cls.item_filepaths['filepath'], 'wb') as dest:
                dest.write(orig.read())
        os.remove(zip_filepath)

    @classmethod
    def get_manual_download_instructions(cls) -> ManualDownloadInstructions:
        return [
            (mdit.TEXT, "You will need to download the file of tab-delimited bilingual sentence pairs in "
                        "Japanese/English from www.manythings.org. It can usually be downloaded directly "
                        "by visiting the following url:"),
            (mdit.URL_BUTTON, cls._direct_download_url),
            (mdit.TEXT, "If this fails, you should look for a download of the file jpn.eng.zip in the following url:"),
            (mdit.URL_BUTTON, 'https://www.manythings.org/anki/'),
            (mdit.TEXT, "If the above url does not exist either, you will need to try to find it manually: look for a "
                        "section with 'Tab-delimited Bilingual Sentence Pairs' somewhere in this website:"),
            (mdit.URL_BUTTON, 'https://www.manythings.org/'),
            (mdit.TEXT, "You should have been able to download a file called 'jpn-eng.zip' - if the file you found has "
                        "another name, you will need to rename it. Move the file to the path "
                        f"{cls._partial_download_filepaths['filepath']}"),
            (mdit.TEXT, "The following button will let you check if the file was moved to the correct location with "
                        "the correct name."),
            (mdit.FILE_CHECK_WIDGET, list(cls._partial_download_filepaths.values())),
            (mdit.TEXT, "Once the check above passes, hit this button to do some automatic processing on the "
                        "downloaded file"),
            (mdit.BUTTON, "Process file", cls._unzip_downloads),
            (mdit.TEXT, "If that worked, the following check should also pass. Once that works, you're done."),
            (mdit.FILE_CHECK_WIDGET, list(cls.item_filepaths.values())),
            (mdit.TEXT, "If the Process file button did not work, it should be fine to manually extract the file you "
                        "downloaded. You might need to redownload - locate the zip file, and extract from within "
                        "it the file called 'jpn.txt'. Rename it to " 
                        f"'{os.path.split(cls.item_filepaths['filepath'])[1]}' and move it to the path specified above.")
        ]


class TatoebaDownloadable(Downloadable, AutomaticallyDownloadable):
    name = 'Tatoeba'
    item_filepaths = {'pairs': os.path.join(PATH_TO_EXTERNAL_DOWNLOADS, 'tatoeba_pairs_data.tsv'),
                      'eng': os.path.join(PATH_TO_EXTERNAL_DOWNLOADS, 'tatoeba_eng_culled.tsv'),
                      'jpn': os.path.join(PATH_TO_EXTERNAL_DOWNLOADS, 'tatoeba_jpn_culled.tsv')}

    _partial_download_filepaths = {'pairs_unculled': os.path.join(PATH_TO_TEMP_EXTERNAL_DOWNLOADS, 'tatoeba_pairs_unculled.tsv'),
                                   'eng_zipped': os.path.join(PATH_TO_TEMP_EXTERNAL_DOWNLOADS, 'tatoeba_eng.tsv.bz2'),
                                   'jpn_zipped': os.path.join(PATH_TO_TEMP_EXTERNAL_DOWNLOADS, 'tatoeba_jpn.tsv.bz2'),
                                   'eng_unculled': os.path.join(PATH_TO_TEMP_EXTERNAL_DOWNLOADS, 'tatoeba_eng.tsv'),
                                   'jpn_unculled': os.path.join(PATH_TO_TEMP_EXTERNAL_DOWNLOADS, 'tatoeba_jpn.tsv')}

    size = '54.1MB'
    processed_size = '31.1MB'

    @classmethod
    def attempt_automatic_download(cls) -> None:
        session = RobotsAwareSession('https://tatoeba.org/', USER_AGENT)
        if not os.path.exists(cls.item_filepaths['pairs']):
            cls._download_pairs_data(session)

        for language in ['eng', 'jpn']:
            if not os.path.exists(cls.item_filepaths[language]):
                if not os.path.exists(cls._partial_download_filepaths[f'{language}_unculled']):
                    if not os.path.exists(cls._partial_download_filepaths[f'{language}_zipped']):
                        cls._download_lan_data(language, session)
                    cls._unzip_lan_data(language)
                cls._process_lan_data(language)

    @classmethod
    def _download_pairs_data(cls, session: Session):
        enter_url = "https://tatoeba.org/en/downloads"
        response = session.get(enter_url)
        if response.status_code != 200:
            raise Exception("Tatoeba session cookies GET failed")

        # this took some effort. Probably breaks TOS but I'm sure this isn't against the spirit of the project
        # just trying to save them a bajillion API calls by keeping the data here locally
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
            "x-csrf-token": session.cookies['csrfToken'],
            "x-requested-with": "XMLHttpRequest"
        }
        post_data = {
            # "fields[]": ["id", "text", "trans_id", "trans_text"],
            # would be good if there was some owner field to access but i couldn't find it
            # instead we do this silly goofy join
            "fields[]": ["id", "trans_id"],
            "format": "tsv",
            # so that the ordered field is eng - more convenient to clean up the massive eng sentence file
            # "from": "jpn", "to": "eng",
            "from": "eng", "to": "jpn",
            "type": "pairs"
        }
        session.headers.update({"referrer": "https://tatoeba.org/en/downloads"})

        response = session.post(post_url, data=post_data, headers=headers)

        export_info = response.json().get("export")
        export_id = export_info["id"]
        status_url = f"https://tatoeba.org/en/exports/get/{export_id}"

        while True:
            status_response = session.get(status_url)
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

        download_response = session.get(download_url)
        download_response.raise_for_status()
        with open(cls.item_filepaths['pairs'], "wb") as file:
            file.write(download_response.content[3:]) # some weird characters at the start (?)

    @classmethod
    def _cull_pairs_data(cls):
        in_file = cls._partial_download_filepaths['pairs_unculled']
        out_file = cls.item_filepaths['pairs']
        with open(in_file, 'r', encoding='utf-8') as f_in, open(out_file, 'w', encoding='utf-8') as f_out:
            for line in f_in:
                en_idx, _, jp_idx, _ = line.split('\t')
                f_out.write(f'{en_idx}\t{jp_idx}\n')
        os.remove(in_file)

    @classmethod
    def _download_lan_data(cls, language: str, session: Session):
        assert language in ['eng', 'jpn']
        zip_filepath = cls._partial_download_filepaths[f'{language}_zipped']
        url = f'https://downloads.tatoeba.org/exports/per_language/{language}/{language}_sentences_detailed.tsv.bz2'
        response = session.get(url)
        response.raise_for_status()
        with open(zip_filepath, 'wb') as file:
            file.write(response.content)

    @classmethod
    def _unzip_lan_data(cls, language: str):
        zip_filepath = cls._partial_download_filepaths[f'{language}_zipped']
        dest_filepath = cls._partial_download_filepaths[f'{language}_unculled']

        with bz2.open(zip_filepath, 'rb') as orig, open(dest_filepath, 'wb') as dest:
            dest.write(orig.read())
        os.remove(zip_filepath)

    @classmethod
    def _process_lan_data(cls, language: str):
        unculled_lan_filepath = cls._partial_download_filepaths[f'{language}_unculled']

        first_number_matcher = re.compile(r"(?:ï»¿)?(\d+)\t")
        second_number_matcher = re.compile(r"(?:ï»¿)?\d+\t(\d+)\n")
        with open(cls.item_filepaths['pairs'], 'r') as pair_file:
            if language == 'eng':
                pair_idxs = set(map(lambda line: int(first_number_matcher.match(line).group(1)), pair_file))
            if language == 'jpn':
                pair_idxs = set(map(lambda line: int(second_number_matcher.match(line).group(1)), pair_file))
        with open(unculled_lan_filepath, 'r', encoding='utf-8') as lan_file:
            lan_idxs = set(map(lambda line: int(first_number_matcher.match(line).group(1)), lan_file))
        common_idx = iter(sorted(pair_idxs.intersection(lan_idxs)))

        culled_lan_filepath = cls.item_filepaths[language]
        with open(unculled_lan_filepath, 'r', encoding='utf-8') as temp_file, open(culled_lan_filepath, 'w',
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
        os.remove(unculled_lan_filepath)

    @classmethod
    def get_manual_download_instructions(cls) -> ManualDownloadInstructions:
        return [
            (mdit.TEXT, "You will need to download three files from the Tatoeba project downloads section:"),
            (mdit.URL_BUTTON, 'https://tatoeba.org/en/downloads'),
            (mdit.TEXT, "The first is from the 'Custom exports' section. Click on 'Sentence pairs', select 'English' "
                        "for the 'Sentence language' field and 'Japanese' for 'Translation language' (the order is "
                        "important), and click on 'Download Sentence Pairs'. The file will be generated on demand, "
                        "which can take up to a minute. Rename this file to "
                        f"{os.path.split(cls._partial_download_filepaths['pairs_unculled'])[1]}."),
            (mdit.TEXT, "The other two files are from the 'Detailed Sentences' section. There's a good chance you can "
                        "download them directly from these URLs:"),
            (mdit.URL_BUTTON, 'https://downloads.tatoeba.org/exports/per_language/jpn/jpn_sentences_detailed.tsv.bz2'),
            (mdit.URL_BUTTON, 'https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences_detailed.tsv.bz2'),
            (mdit.TEXT, "Otherwise, look for the 'Detailed Sentences' section. Tick 'Only sentences in:' "
                        "and download the files for Japanese and English. Change the downloaded files' filenames to "
                        f"{os.path.split(cls._partial_download_filepaths['jpn_zipped'])[1]} "
                        "and " f"{os.path.split(cls._partial_download_filepaths['eng_zipped'])[1]}, respectively."),
            (mdit.TEXT, "Once you are done, move all these files to " f"{PATH_TO_TEMP_EXTERNAL_DOWNLOADS}. You can use "
                        "the widget below to check that all three files exist in the correct directory with the "
                        "correct name:"),
            (mdit.FILE_CHECK_WIDGET, [cls._partial_download_filepaths['pairs_unculled'],
                                      cls._partial_download_filepaths['jpn_zipped'],
                                      cls._partial_download_filepaths['eng_zipped']]),
            (mdit.TEXT, "Some processing now needs to be done on these files. Starting with the pairs file: some "
                        "unnecessary data has to be removed from it. Use the following button "
                        "to do this, and the widget to check that it was done correctly:"),
            (mdit.BUTTON, "Cull pairs file", cls._cull_pairs_data),
            (mdit.FILE_CHECK_WIDGET, [cls.item_filepaths['pairs']]),
            (mdit.TEXT, "Now the jpn and eng files: "
                        "first they need to be unzipped. The buttons below can try to do this automatically:"),
            (mdit.BUTTON, "Unzip jpn file", lambda: cls._unzip_lan_data("jpn")),
            (mdit.BUTTON, "Unzip eng file", lambda: cls._unzip_lan_data("eng")),
            (mdit.TEXT, "Otherwise you can unzip them yourself - to "
                        f"{os.path.split(cls._partial_download_filepaths['eng_unculled'])[0]}, with filenames "
                        f"{os.path.split(cls._partial_download_filepaths['jpn_unculled'])[1]} and "
                        f"{os.path.split(cls._partial_download_filepaths['eng_unculled'])[1]}, respectively. "
                        "Use the widget below to verify the process worked:"),
            (mdit.FILE_CHECK_WIDGET, [cls._partial_download_filepaths['jpn_unculled'],
                                      cls._partial_download_filepaths['eng_unculled']]),
            (mdit.TEXT, "Finally some unnecessary data has to be removed from the jpn and eng files aswell. The "
                        "following two buttons will serve to do this - they might need a few seconds:"),
            (mdit.BUTTON, 'Cull jpn file', lambda: cls._process_lan_data("jpn")),
            (mdit.BUTTON, 'Cull eng file', lambda: cls._process_lan_data("eng")),
            (mdit.TEXT, "Use this last widget to check that all the required files exist:"),
            (mdit.FILE_CHECK_WIDGET, cls.item_filepaths.values())
        ]


class JapaneseEnglishSubtitleCorpusDownloadable(Downloadable, AutomaticallyDownloadable):
    name = 'JapaneseEnglishSubtitleCorpus'
    item_filepaths = {'filepath': os.path.join(PATH_TO_EXTERNAL_DOWNLOADS, 'parallel_subtitles')}

    size = '218.7MB'

    _partial_download_filepaths = {'filepath': os.path.join(PATH_TO_TEMP_EXTERNAL_DOWNLOADS, 'raw.tar.gz')}
    _direct_download_url = 'https://nlp.stanford.edu/projects/jesc/data/raw.tar.gz'

    @classmethod
    def attempt_automatic_download(cls) -> None:
        cls._download_zipped_files()
        cls._unzip_downloads()

    @classmethod
    def _download_zipped_files(cls) -> None:

        session = RobotsAwareSession('https://nlp.stanford.edu/', USER_AGENT)
        url = cls._direct_download_url
        response = session.get(url)
        if response.status_code != 200:
            raise Exception("Download GET request to manythings.org failed")
        with open(cls._partial_download_filepaths['filepath'], 'wb') as file:
            file.write(response.content)

    @classmethod
    def _unzip_downloads(cls) -> None:
        zip_filepath = cls._partial_download_filepaths['filepath']
        with tarfile.open(zip_filepath, 'r') as tar_ref:
            with tar_ref.extractfile('raw/raw') as orig, open(cls.item_filepaths['filepath'], 'wb') as dest:
                dest.write(orig.read())
        os.remove(zip_filepath)

    @classmethod
    def get_manual_download_instructions(cls) -> ManualDownloadInstructions:
        return [
            (mdit.TEXT, "You should be able to download the Japanese-English Subtitle Corpus from the following link:"),
            (mdit.URL_BUTTON, cls._direct_download_url),
            (mdit.TEXT, "Otherwise, look for a download on the homepage of the corpus:"),
            (mdit.URL_BUTTON, "https://nlp.stanford.edu/projects/jesc/"),
            (mdit.TEXT, "You should obtain a file called something like 'raw.tar.gz'. Unzip it - inside, within a "
                        "folder called 'raw', you will find a file called 'raw'. Extract this file, rename it to "
                        f"'{os.path.split(cls.item_filepaths['filepath'])[1]}', and move it to "
                        f"{os.path.split(cls.item_filepaths['filepath'])[0]}. Your unzipping software might have some "
                        f"trouble with this file - this is because it is a .tar file, despite the name claiming that "
                        f"it is gzipped. It might help to rename the file to 'raw.tar'. If that doesn't help either, "
                        f"you can try to move the file to "
                        f"'{os.path.split(cls._partial_download_filepaths['filepath'])[0]}' and hit the following "
                        f"button:"),
            (mdit.BUTTON, "Attempt automatic untar", cls._unzip_downloads),
            (mdit.TEXT, f"Whatever method you used, you can use the widget below to check that the file was "
                        f"uncompressed correctly:"),
            (mdit.FILE_CHECK_WIDGET, cls.item_filepaths.values()),
            (mdit.TEXT, "If that check passes, you're done.")
        ]


class JParaCrawlDownloadable(Downloadable):
    name = 'JParaCrawl'
    item_filepaths = {'filepath': os.path.join(PATH_TO_EXTERNAL_DOWNLOADS, 'en-ja.bicleaner05.txt')}

    size = '2.8GB'
    processed_size = '9.1GB'

    @classmethod
    def get_manual_download_instructions(cls) -> ManualDownloadInstructions:
        return [
            (mdit.TEXT, "You will need a download of the JParaCrawl corpus. Usually one can be found directly here:"),
            (mdit.URL_BUTTON, 'https://www.kecl.ntt.co.jp/icl/lirg/jparacrawl/release/en/3.0/bitext/en-ja.tar.gz'),
            (mdit.TEXT, "If this fails, you should look for a download in the following page:"),
            (mdit.URL_BUTTON, 'https://www.kecl.ntt.co.jp/icl/lirg/jparacrawl/'),
            (mdit.TEXT, "You are looking for the English-Japanese corpus (or training set). Be careful not to "
                        "mistakenly download the Chinese-Japanese corpus, or any of the pretrained models."),
            (mdit.TEXT, "You should have obtained a file called something like 'en-ja.tar.gz'. Uncompress it - "
                        "somewhere within there should be a file called "
                        f"'{os.path.split(cls.item_filepaths['filepath'])[1]}'. "
                        "Move this file to "
                        f"'{os.path.split(cls.item_filepaths['filepath'])[0]}'. "
                        "Use the widget below to check that the file was moved to the correct directory and has the "
                        "correct name:"),
            (mdit.FILE_CHECK_WIDGET, list(cls.item_filepaths.values())),
            (mdit.TEXT, "If the check above passes, you are done.")
        ]



class ExternalDownloadGUIProtocol(Protocol):
    # this is a bit silly...
    @classmethod
    def factory(self,
                requested_download_name: str,
                sentence_corpus_downloadables: List[Downloadable],
                japanese_dictionary_downloadables: List[Downloadable],
                english_dictionary_downloadables: List[Downloadable],
                user_has_refused_to_download: Dict[str, bool]) \
            -> ExternalDownloadGUIProtocol:
        raise NotImplemented

    def execute(self):
        raise NotImplemented


class ExternalDownloadRequester:
    _sentence_corpus_downloadables: List[Downloadable] = [ManyThingsTatoebaDownloadable(),
                                                          TatoebaDownloadable(),
                                                          JapaneseEnglishSubtitleCorpusDownloadable(),
                                                          JParaCrawlDownloadable()]
    _japanese_dictionary_downloadables: List[Downloadable] = []
    _english_dictionary_downloadables: List[Downloadable] = []

    _refused_downloads_path = os.path.join(PATH_TO_USER_FILES, "user_refused_downloads.txt")

    def __init__(self, external_download_gui_protocol: Optional[Type[ExternalDownloadGUIProtocol]] = None):
        self._external_download_gui_protocol = external_download_gui_protocol
        sentence_corpus_downloadables = {downloadable.name: downloadable
                                         for downloadable in self._sentence_corpus_downloadables}
        japanese_dictionary_downloadables = {downloadable.name: downloadable
                                             for downloadable in self._japanese_dictionary_downloadables}
        english_dictionary_downloadables = {downloadable.name: downloadable
                                            for downloadable in self._english_dictionary_downloadables}

        self.all_downloadables: Dict[str, Downloadable] = dict()
        self.all_downloadables.update(sentence_corpus_downloadables)
        self.all_downloadables.update(japanese_dictionary_downloadables)
        self.all_downloadables.update(english_dictionary_downloadables)

        refused_downloads = self._load_refused_downloads()
        self.user_has_refused_to_download = {downloadable_name: downloadable_name in refused_downloads
                                             for downloadable_name in self.all_downloadables}

    def _load_refused_downloads(self):
        if os.path.exists(self._refused_downloads_path):
            with open(self._refused_downloads_path, "r") as f:
                return f.readlines()
        return []

    def _save_refused_downloads(self):
        with open(self._refused_downloads_path, "w") as f:
            f.write("\n".join([downloadable_name for downloadable_name in self.all_downloadables
                               if self.user_has_refused_to_download[downloadable_name]]))

    def get_external_downloadable(self, downloadable_name: str, prompt_user=True) -> Optional[Dict[str, str]]:
        downloadable = self.all_downloadables[downloadable_name]
        if downloadable.are_files_downloaded():
            return downloadable.item_filepaths
        elif prompt_user and not self.user_has_refused_to_download[downloadable_name]:
            self._prompt_user_for_download(downloadable_name)
            if downloadable.are_files_downloaded():
                return downloadable.item_filepaths
        return None

    def _prompt_user_for_download(self, downloadable_name: str) -> None:
        # here throw up brief explanatory window and then ExternalDownloadWidget
        # importantly this call has to be blocking - wait until user closes or exits window
        # no obligation to return info about whether user did download, this function's only job is to query user for dl
        # ...but it does have the obligation to update user_has_refused_to_download.
        # or does it? i guess the GUI can update that by itself. yes yes mutability bad but come on
        # oh i think the blocking is easy, just do .exec() instead of .show()
        if self._external_download_gui_protocol is None:
            raise Exception("ExternalDownloadRequester tried to prompt user for download without passed GUI")
        self.gui_instance = self._external_download_gui_protocol.factory(downloadable_name,
                                                                         self._sentence_corpus_downloadables,
                                                                         self._japanese_dictionary_downloadables,
                                                                         self._english_dictionary_downloadables,
                                                                         self.user_has_refused_to_download)
        self.gui_instance.execute()
        self._save_refused_downloads()
        del self.gui_instance
