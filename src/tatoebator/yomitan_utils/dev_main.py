from __future__ import annotations

import json
import os
import re
import zipfile
from dataclasses import dataclass
from functools import cached_property
from typing import Protocol, List, IO, Optional, Union, Dict, Any
from zipfile import ZipFile

from .anki_template_renderer_content_manager import AnkiTemplateRendererContentManager
from .structured_content_generator import StructuredContentGenerator


class OpenedDictionaryRef(Protocol):
    def get_file_names(self) -> List[str]:
        ...

    def open(self, file_name: str) -> IO[bytes]:
        ...

    @cached_property
    def name(self) -> Optional[str]:
        file_names = self.get_file_names()
        if 'index.json' not in file_names:
            return None
        with self.open('index.json') as f:
            data = json.load(f)
            return data.get('title')


class DictionaryRef:
    def __enter__(self) -> OpenedDictionaryRef:
        raise NotImplementedError

    def __exit__(self, exc_type, exc_val, exc_tb):
        raise NotImplementedError

    @cached_property
    def fallback_name(self) -> str:
        raise NotImplementedError


class UnzippedDictionaryRef(OpenedDictionaryRef, DictionaryRef):
    def __init__(self, folder_path: str):
        self._folder_path = folder_path

    def get_file_names(self) -> List[str]:
        return os.listdir(self._folder_path)

    def open(self, file_name: str) -> IO[bytes]:
        file_path = os.path.join(self._folder_path, file_name)
        return open(file_path, "rb")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @cached_property
    def fallback_name(self) -> str:
        return os.path.split(self._folder_path)[1]


class ZippedDictionaryRef(DictionaryRef):
    def __init__(self, zipped_folder_path: str):
        self._zipped_folder_path = zipped_folder_path

    def __enter__(self):
        self._zipfile = zipfile.ZipFile(self._zipped_folder_path, "r")
        self._opened_zipfile = self._zipfile.__enter__()  # probably the same object but can't be too sure
        self._opened_zipped_dictionary_ref = OpenedZippedDictionaryRef(self._opened_zipfile)
        return self._opened_zipped_dictionary_ref

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._zipfile.__exit__(exc_type, exc_val, exc_tb)
        self._zipfile = None
        self._opened_zipfile = None

    @cached_property
    def fallback_name(self) -> str:
        return os.path.split(self._zipped_folder_path)[1]


class OpenedZippedDictionaryRef(OpenedDictionaryRef):
    def __init__(self, opened_zipped_dictionary_ref: ZipFile):
        self._opened_zipfile = opened_zipped_dictionary_ref

    def get_file_names(self) -> List[str]:
        return [zipinfo.filename for zipinfo in self._opened_zipfile.filelist]

    def open(self, file_name: str) -> IO[bytes]:
        return self._opened_zipfile.open(file_name, 'r')


@dataclass
class DictionaryEntry:
    term: str
    reading: str
    def_tags: List[str]
    deinflections: List[str]
    popularity_number: int
    definitions: List[Union[str, Dict, List]]
    seq_number: int
    term_tags: List[str]
    dictionary_name: str

    @classmethod
    def from_json_entry(cls, item: List, dictionary_name: str) -> DictionaryEntry:
        term, reading, def_tags, deinflections, popularity_number, definitions, seq_number, term_tags = item
        def_tags = [] if not def_tags else def_tags.split(" ")
        deinflections = [] if not deinflections else deinflections.split(" ")
        term_tags = [] if not term_tags else term_tags.split(" ")
        return cls(term, reading, def_tags, deinflections, popularity_number, definitions, seq_number, term_tags,
                   dictionary_name)


class DictionaryDirectory:
    # no redundant state, just reread the folder every time
    def __init__(self, path_to_dicts_folder):
        self._path_to_dicts_folder = path_to_dicts_folder

    def _yield_dictionaries(self):
        for item_name in os.listdir(self._path_to_dicts_folder):
            item_path = os.path.join(self._path_to_dicts_folder, item_name)
            if zipfile.is_zipfile(item_path):
                yield ZippedDictionaryRef(item_path)
            else:
                yield UnzippedDictionaryRef(item_path)

    def search_word(self, word: str) -> Optional[DictionaryEntry]:
        for dictionary_ref in self._yield_dictionaries():
            with dictionary_ref as opened_dictionary_ref:
                print(opened_dictionary_ref.name)
                val = self._search_word_in_opened_dict(opened_dictionary_ref, word)
                if val is not None:
                    return DictionaryEntry.from_json_entry(val, opened_dictionary_ref.name
                                                           or dictionary_ref.fallback_name)
        return None

    @classmethod
    def _search_word_in_opened_dict(cls, dict_ref: OpenedDictionaryRef, word: str) -> Optional[List[Any]]:
        file_names = dict_ref.get_file_names()
        for file_name in file_names:
            if re.fullmatch("term_bank_\d+\.json", file_name) is None: continue
            with dict_ref.open(file_name) as term_bank:
                val = cls._search_word_in_opened_term_bank(term_bank, word)
                if val is not None: return val
        return None

    @classmethod
    def _search_word_in_opened_term_bank(cls, term_bank: IO[bytes], word: str) -> Optional[List[Any]]:
        data = json.loads(term_bank.read())
        for item in data:
            if item[0] == word:  # todo deinflection?
                return item
        return None


def test_dictdir():
    downloads_dir = r"C:\Users\xavia\Downloads"
    dicts_zip_filepath = os.path.join(downloads_dir, "Japanese-20250312T213821Z-001.zip")
    dicts_unzipped_filepath = os.path.join(downloads_dir, "Japanese-20250312T213821Z-001")
    dicts_extra_unzipped_filepath = os.path.join(downloads_dir, "Japanese-20250312T213821Z-001-extraunzipped")

    dict_dir = DictionaryDirectory(dicts_unzipped_filepath)
    print(dict_dir.search_word("毎日"))


def test_timings():
    """
    results
    unzipping the outer folder provides mild speedup for just going through the files
    about 30% of maybe 15 seconds or so to go through EVERY dict?
    unzipping the inner folders too might provide some benefit aswell, but so minor i couldn't tell

    as for actually generating the html i should've figured this but obv the unzipping has no effect since we don't
    pass any handle to the scg

    conclusion: best approach will be to just keep the dict folders OR zips, either is fine, we can use both (up to the
    user, somehow) in a folder
    """
    atrcm = AnkiTemplateRendererContentManager(None, None)
    scg = StructuredContentGenerator(atrcm)

    downloads_dir = r"C:\Users\xavia\Downloads"
    dicts_zip_filepath = os.path.join(downloads_dir, "Japanese-20250312T213821Z-001.zip")
    dicts_unzipped_filepath = os.path.join(downloads_dir, "Japanese-20250312T213821Z-001")
    dicts_extra_unzipped_filepath = os.path.join(downloads_dir, "Japanese-20250312T213821Z-001-extraunzipped")

    num_dicts_to_test = 15

    from time import time
    then = time()

    with zipfile.ZipFile(dicts_zip_filepath, "r") as dicts_zip:
        for dict_zipinfo in dicts_zip.filelist[:num_dicts_to_test]:
            inner_then = time()
            dict_zipfilename = dict_zipinfo.filename
            cd = 0
            with dicts_zip.open(dict_zipfilename, 'r') as dict_zipfile:
                with zipfile.ZipFile(dict_zipfile, 'r') as dict_zip:
                    files = set(map(lambda x: x.split("/")[0], [x.filename for x in dict_zip.filelist]))
                    if 'index.json' in files:
                        with dict_zip.open('index.json', 'r') as f:
                            pass  # print("\t",f.read().decode('utf-8'))
                    for filename in files:
                        if re.fullmatch("term_bank_\d+\.json", filename) is None: continue
                        with dict_zip.open(filename, 'r') as f:
                            data = json.loads(f.read())
                            for item in data:
                                term, reading, def_tags, deinflections, popularity_number, definitions, seq_number, term_tags = item
                                assert isinstance(definitions, list)
                                for definition in definitions:
                                    cd += 1
                                    if isinstance(definition, str): continue
                                    if isinstance(definition, list): continue
                                    try:
                                        scg.create_structured_content(definition['content'], None)
                                    except:
                                        import traceback
                                        print(traceback.format_exc())
                                        print(item)
                                        print(definitions)
                                        print(jjsj)
            inner_now = time()
            print(inner_now - inner_then, cd, dict_zipfilename)
    now = time()
    print("double zipped", now - then)

    then = time()
    for dict_zipfilename in os.listdir(dicts_unzipped_filepath):
        inner_then = time()
        cd = 0
        dict_zipfilepath = os.path.join(dicts_unzipped_filepath, dict_zipfilename)
        with zipfile.ZipFile(dict_zipfilepath, 'r') as dict_zip:
            files = set(map(lambda x: x.split("/")[0], [x.filename for x in dict_zip.filelist]))
            if 'index.json' in files:
                with dict_zip.open('index.json', 'r') as f:
                    pass  # print("\t",f.read().decode('utf-8'))
            for filename in files:
                if re.fullmatch("term_bank_\d+\.json", filename) is None: continue
                with dict_zip.open(filename, 'r') as f:
                    data = json.loads(f.read())
                    for item in data:
                        term, reading, def_tags, deinflections, popularity_number, definitions, seq_number, term_tags = item
                        assert isinstance(definitions, list)
                        for definition in definitions:
                            cd += 1
                            if isinstance(definition, str): continue
                            if isinstance(definition, list): continue
                            try:
                                scg.create_structured_content(definition['content'], None)
                            except:
                                import traceback
                                print(traceback.format_exc())
                                print(item)
                                print(definitions)
                                print(jjsj)
        inner_now = time()
        print(inner_now - inner_then, cd, dict_zipfilename)
    now = time()
    print("single zipped", now - then)

    then = time()
    for dict_foldername in os.listdir(dicts_extra_unzipped_filepath):
        inner_then = time()
        cd = 0
        dict_folderpath = os.path.join(dicts_extra_unzipped_filepath, dict_foldername)
        files = set(os.listdir(dict_folderpath))
        if 'index.json' in files:
            with open(os.path.join(dict_folderpath, 'index.json'), 'r') as f:
                pass  # print("\t",f.read().decode('utf-8'))
        for filename in files:
            filepath = os.path.join(dict_folderpath, filename)
            if re.fullmatch("term_bank_\d+\.json", filename) is None: continue
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.loads(f.read())
                for item in data:
                    term, reading, def_tags, deinflections, popularity_number, definitions, seq_number, term_tags = item
                    assert isinstance(definitions, list)
                    for definition in definitions:
                        cd += 1
                        if isinstance(definition, str): continue
                        if isinstance(definition, list): continue
                        try:
                            scg.create_structured_content(definition['content'], None)
                        except:
                            import traceback
                            print(traceback.format_exc())
                            print(item)
                            print(definitions)
                            print(jjsj)
        inner_now = time()
        print(inner_now - inner_then, cd, dict_zipfilename)
    now = time()
    print("unzipped", now - then)
