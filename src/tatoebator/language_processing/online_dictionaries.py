import re
from dataclasses import dataclass
from functools import cached_property
from typing import List

from bs4 import BeautifulSoup

from . import dictionary_form
from ..constants import USER_AGENT
from ..robots import RobotsAwareSession


@dataclass
class Definitions:
    en: List[str]
    jp: List[str]

    def __add__(self, other):
        return self.__class__(self.en + other.en, self.jp + other.jp)

    @property
    def complete(self):
        return bool(self.en and self.jp)

    @classmethod
    def empty(cls):
        return cls([], [])


class Dictionary:

    _base_url = None

    @cached_property
    def _session(self):
        return RobotsAwareSession(self._base_url, USER_AGENT)

    def get_maximum_rate(self) -> float:
        return self._session.get_maximum_rate()

    def get_definitions(self, word: str) -> Definitions:
        raise NotImplementedError()


class JapaneseDictionary(Dictionary):
    def get_definitions(self, word: str) -> Definitions:
        return Definitions([], self._get_jp_definition(word))

    def _get_jp_definition(self, word) -> List[str]:
        raise NotImplementedError()


class EnglishDictionary(Dictionary):
    def get_definitions(self, word: str) -> Definitions:
        return Definitions(self._get_en_definition(word), [])

    def _get_en_definition(self, word) -> List[str]:
        raise NotImplementedError()


class TanoshiiDictionary(Dictionary):

    _base_url = f"https://www.tanoshiijapanese.com"

    def get_definitions(self, word) -> Definitions:
        url = f"{self._base_url}/dictionary/index.cfm?j={word}&e=&search=Search+>"
        return self._get_definitions_from_url(word, url)

    def _get_definitions_from_url(self, word, url):
        response = self._session.get(url)

        if response.status_code != 200:
            # raise Exception(f"Something went wrong with the tanoshiijp request - status code {response.status_code}")
            print(f"Something went wrong with the tanoshiijp request - status code {response.status_code}")
            return Definitions.empty()

        soup = BeautifulSoup(response.content, 'html.parser')
        content_elem = soup.find('div', id='cncontentbody')
        decider_elem = content_elem.contents[1]
        if decider_elem.name == 'form':
            for elem in decider_elem.find_all('div', class_='message'):
                word_elem = elem.find('span', class_='copyable')
                found_word = "".join([elem.text for elem in word_elem.find_all('rb')])
                if not found_word: found_word = word_elem.text
                if word != found_word: continue
                break  # grab the first match (immediate nonetype exception otherwise)
            else:
                return Definitions.empty()

            found_url = elem.find('div', class_='entrylinks').contents[0]['href']

            new_url = f"{self._base_url}{found_url[2:]}"

            return self._get_definitions_from_url(word, new_url)

        elif decider_elem.name == 'div':
            # jp_elem = decider_elem.find('span', class_='copyable')
            # jp_text = "".join([elem.text for elem in jp_elem.find_all('rb')])

            id_english_meaning_elem = decider_elem.find('div', id='idEnglishMeaning')
            if id_english_meaning_elem is None:
                return Definitions.empty()
            text_en = sum([ol_elem.text[1:-1].split("\n") for ol_elem in id_english_meaning_elem.find_all('ol')], [])
            text_jp = []

            id_synonyms_elem = decider_elem.find('div', id='idSynonyms')
            if id_synonyms_elem is not None:
                jp_elems = id_synonyms_elem.find_all('tr', class_='jp')
                en_elems = id_synonyms_elem.find_all('tr', class_='en')
                for jp_elem, en_elem in zip(jp_elems, en_elems):
                    jp_word = jp_elem.contents[3].text
                    if jp_word != word and dictionary_form(jp_word) != word:
                        continue
                    jp_def = jp_elem.contents[5].text
                    en_word = en_elem.contents[3].text
                    en_def = en_elem.contents[5].text
                    en_def = f"{en_word}, {en_def}"
                    text_en.append(en_def)
                    text_jp.append(jp_def)

            # filter out empty strings
            text_en = list(filter(lambda x: x, text_en))
            text_jp = list(filter(lambda x: x, text_jp))

            return Definitions(text_en,text_jp)
        else:
            raise Exception("Tanoshiijp webpage had unexpected format")


class JishoDictionary(EnglishDictionary):

    _base_url = "https://jisho.org/"

    def _get_en_definition(self, word) -> List[str]:
        url = f"{self._base_url}/api/v1/search/words?keyword={word}"

        response = self._session.get(url)

        data = response.json()["data"]

        definitions = []
        for item in data:
            slug = item['slug']
            if slug != word and dictionary_form(slug) != word:
                continue
            senses = item['senses']
            for sense in senses:
                definitions.append(", ".join(sense['english_definitions']))

        # filter out empty strings
        definitions = list(filter(lambda x: x, definitions))

        return definitions


class WeblioDictionary(Dictionary):

    _base_url = f"https://ejje.weblio.jp"

    def get_definitions(self, word: str) -> Definitions:
        url = f"{self._base_url}/english-thesaurus/content/{word}"
        response = self._session.get(url)

        if response.status_code != 200:
            # raise Exception(f"Something went wrong with the weblio request - status code {response.status_code}")
            print(f"Something went wrong with the weblio request - status code {response.status_code}")
            return Definitions.empty()

        soup = BeautifulSoup(response.content, 'html.parser')
        table_elem = soup.find('tbody')
        # 29??
        text_jp = [elem.text[29:] for elem in table_elem.find_all('p', class_='wdntTCLJ')]
        text_en = [elem.text[29:] for elem in table_elem.find_all('p', class_='wdntTCLE')]

        # filter out empty strings
        text_en = list(filter(lambda x: x, text_en))
        text_jp = list(filter(lambda x: x, text_jp))
        return Definitions(text_en, text_jp)


class DefinitionFetcher:

    _dictionaries: List[Dictionary] = [WeblioDictionary(), TanoshiiDictionary(), JishoDictionary()]

    def __init__(self):
        self._dictionaries.sort(key=lambda x: -x.get_maximum_rate())

    def get_definitions(self, word: str) -> Definitions:
        for definitions in self._yield_aggregated_definitions(word):
            pass# if definitions.complete: return definitions
        definitions.en = self._remove_similar(definitions.en)
        definitions.jp = self._remove_similar(definitions.jp)
        return definitions

    def get_en_definition(self, word: str) -> List[str]:
        for definitions in self._yield_aggregated_definitions(word):
            if definitions.en: return self._remove_similar(definitions.en)

    def get_jp_definition(self, word: str) -> List[str]:
        for definitions in self._yield_aggregated_definitions(word):
            if definitions.jp: return self._remove_similar(definitions.jp)

    def _yield_aggregated_definitions(self, word: str):
        definitions = Definitions.empty()
        for dictionary in self._dictionaries:
            definitions = definitions + dictionary.get_definitions(word)
            yield definitions

    def _remove_similar(self, texts: List[str], threshold: float = 0.8):
        for i in range(len(texts)):
            for j in range(len(texts)-1,i,-1):
                if self._similarity(texts[i], texts[j]) > threshold:
                    texts.pop(j)
        return texts

    def _similarity(self, text1, text2):
        bw1, bw2 = self._bag_words(text1), self._bag_words(text2)
        if bw1 and bw2: return len(bw1 & bw2) / min(len(bw1), len(bw2))
        else: return 0

    def _bag_words(self, text):
        return set(re.findall(r"(\w+)", text.lower()))

