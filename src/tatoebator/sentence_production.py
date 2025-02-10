import os
import re
from typing import Iterator, Dict

import requests
from bs4 import BeautifulSoup, NavigableString

from .candidate_example_sentences import ExampleSentenceQualityEvaluator, QualityEvaluationResult
from .constants import CACHE_DIR
from .example_sentences import CandidateExampleSentence, ExampleSentence


class SentenceProductionMethod:
    def yield_sentences(self, word: str) -> Iterator[CandidateExampleSentence]:
        raise NotImplementedError()


class StandardSPM(SentenceProductionMethod):
    def yield_sentences(self, word):
        yield from iter(self._produce_sentence_list(word))

    def _produce_sentence_list(self, word):
        raise NotImplementedError()


class LexicalCheckStandardSPM(SentenceProductionMethod):
    def yield_sentences(self, word):
        yield from filter(lambda sentence: word in sentence.lexical_words, self._produce_unchecked_sentence_list(word))

    def _produce_unchecked_sentence_list(self, word):
        raise NotImplementedError()


class LexicalCheckSPM(SentenceProductionMethod):
    def yield_sentences(self, word):
        yield from filter(lambda sentence: word in sentence.lexical_words, self._yield_unchecked_sentences(word))

    def _yield_unchecked_sentences(self, word):
        raise NotImplementedError()


class ArbitrarySentenceProductionMethod():
    def yield_sentences(self) -> Iterator[CandidateExampleSentence]:
        raise NotImplementedError()


requests_session = requests.Session()
requests_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
})


# chatgpt wrote this
# led me to learn chatgpt is kinda ass at writing crawlers
# but i'm too lazy to rewrite it for now
def example_sentences_from_kanshudo(word: str) -> list[tuple[str]]:
    url = f'https://www.kanshudo.com/searcht?q={word}'
    response = requests_session.get(url)

    if response.status_code != 200:
        raise Exception(f"Something went wrong with the kanshudo request - status code {response.status_code}")

    soup = BeautifulSoup(response.content, 'html.parser')

    # Function to extract text from tatvoc_stop elements
    def extract_tatvoc_stop_text(element):
        return element.get_text(strip=True)

    # Function to extract text from tatvoc elements
    def extract_tatvoc_text(element):
        extracted_text = ''
        for child in element.children:
            if isinstance(child, NavigableString):
                extracted_text += child.strip()
            elif child.name == 'span' and all(cls in child.get('class', []) for cls in ['f_container', 'noflip']):
                f_kanji_elements = child.find_all('div', class_='f_kanji')
                for f_kanji in f_kanji_elements:
                    extracted_text += f_kanji.get_text(strip=True)
        return extracted_text.strip()

    # Function to extract text from tat_eng elements
    def extract_tat_eng_text(element):
        tat_eng_span = element.find('span', class_='tat_eng')
        if tat_eng_span:
            text_span = tat_eng_span.find('span', class_='text')
            if text_span:
                return text_span.get_text(strip=True)
        return ''

    sentence_translation_pairs = []

    for tatoeba_div in soup.find_all('div', class_='tatoeba'):
        extracted_text = []

        elements = tatoeba_div.find_all(['a', 'span'])
        for element in elements:
            if 'tatvoc-stop' in element.get('class', []):
                extracted_text.append(extract_tatvoc_stop_text(element))
            elif 'tatvoc' in element.get('class', []):
                extracted_text.append(extract_tatvoc_text(element))

        extracted_text = ''.join(extracted_text)
        tat_eng_text = extract_tat_eng_text(tatoeba_div)
        sentence_translation_pairs.append((extracted_text, tat_eng_text))

    return sentence_translation_pairs


class KanshudoSPM(LexicalCheckStandardSPM):
    def _produce_unchecked_sentence_list(self, word):
        return [CandidateExampleSentence(sentence, translation=translation)
                for sentence, translation
                in example_sentences_from_kanshudo(word)]


def example_sentences_from_tangorin(word: str) -> list[tuple[str]]:
    url = f'https://tangorin.com/sentences?search={word}'
    response = requests_session.get(url)

    if response.status_code != 200:
        raise Exception(f"Something went wrong with the tangorin request - status code {response.status_code}")

    soup = BeautifulSoup(response.content, 'html.parser')

    sentence_translation_pairs = []

    for entry_elem in soup.find_all('div', class_='entry entry-border sentences undefined'):
        jp_elem = entry_elem.find("dt")
        en_elem = entry_elem.find("dd")
        sentence_translation_pairs.append((jp_elem.text, en_elem.text))

    return sentence_translation_pairs


class TangorinSPM(LexicalCheckStandardSPM):
    def _produce_unchecked_sentence_list(self, word):
        return [CandidateExampleSentence(sentence, translation=translation)
                for sentence, translation
                in example_sentences_from_tangorin(word)]


def example_sentences_from_jisho(word: str) -> list[tuple[str]]:
    url = f'https://jisho.org/search/{word}%20%23sentences'
    response = requests_session.get(url)

    if response.status_code != 200:
        raise Exception(f"Something went wrong with the jisho request - status code {response.status_code}")

    soup = BeautifulSoup(response.content, 'html.parser')

    sentence_translation_pairs = []

    for entry_elem in soup.find_all('div', class_='sentence_content'):
        jp_elem = entry_elem.find("ul", class_='japanese_sentence japanese japanese_gothic clearfix')
        jp_str = []
        for child in jp_elem.children:
            if isinstance(child, NavigableString):
                jp_str.append(child.strip())
            elif child.name == 'li':
                f_kanji_elements = child.find_all('span', class_='unlinked')
                for f_kanji in f_kanji_elements:
                    jp_str.append(f_kanji.get_text(strip=True))
        jp_str = "".join(jp_str)
        en_elem = entry_elem.find("div", class_='english_sentence clearfix').find("span", class_='english')
        en_str = en_elem.text
        sentence_translation_pairs.append((jp_str, en_str))

    return sentence_translation_pairs


class JishoSPM(LexicalCheckStandardSPM):
    def _produce_unchecked_sentence_list(self, word):
        return [CandidateExampleSentence(sentence, translation=translation)
                for sentence, translation
                in example_sentences_from_jisho(word)]


tatoeba_jpn_matcher = re.compile(r'"text":"(.*)","lang":"jpn"')
tatoeba_eng_matcher = re.compile(r'"text":"(.*?)","lang":"eng"')


def example_sentences_from_tatoeba(word: str, page: int) -> tuple[int, list[tuple[str, str]]]:
    # takes the page to search. also returns the number of pages
    url = f'https://tatoeba.org/en/sentences/search?from=jpn&orphans=no&query={word}'\
          + f'&sort=random&to=eng&trans_filter=limit&trans_to=eng&unapproved=no'\
          + f'&word_count_min=6&rand_seed=JKwY&page={page}&sort=random'
    response = requests_session.get(url)

    if response.status_code != 200:
        raise Exception(f"Something went wrong with the jisho request - status code {response.status_code}")

    soup = BeautifulSoup(response.content, 'html.parser')

    paging_elem = soup.find('ul', class_='paging')
    if paging_elem is None:
        last_page = 1
    else:
        last_pg_elem = paging_elem.find_all('li')[-2]
        last_page = int(last_pg_elem.text)

    sentence_translation_pairs = []

    for elem in soup.find_all('div', attrs={'flex': True, 'sentence-and-translations': True}):
        text = elem.get('ng-init')
        jp_match = re.search(tatoeba_jpn_matcher, text)
        en_match = re.search(tatoeba_eng_matcher, text[jp_match.end():])
        jp_str = jp_match.group(1).encode().decode('unicode_escape')
        en_str = en_match.group(1)
        sentence_translation_pairs.append((jp_str, en_str))

    return last_page, sentence_translation_pairs


class TatoebaSPM(LexicalCheckSPM):
    def _yield_unchecked_sentences(self, word):
        max_page, sentences = example_sentences_from_tatoeba(word, 1)
        for sentence, translation in sentences:
            yield CandidateExampleSentence(sentence, translation=translation)
        for page in range(2, max_page + 1):
            _, sentences = example_sentences_from_tatoeba(word, page)
            for sentence, translation in sentences:
                yield CandidateExampleSentence(sentence, translation=translation)


class SentenceSearchNeocitiesASPM(ArbitrarySentenceProductionMethod):
    def __init__(self):
        self.filepath = os.path.join(CACHE_DIR, 'ssneocities_data.json')
        if not os.path.exists(self.filepath):
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


class SentenceProductionManager:

    spms_by_tag : Dict[int, SentenceProductionMethod] = {
        1: KanshudoSPM(),
        2: TangorinSPM(),
        3: JishoSPM(),
        4: TatoebaSPM(),
    }

    aspms_by_tag : Dict[int, ArbitrarySentenceProductionMethod] = {
        101: SentenceSearchNeocitiesASPM()
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

        c=0
        for tag, yielder in yielders_by_tag.items():
            for s in yielder:
                c+=1
                evaluation = self.quality_control.evaluate_quality(s)
                if evaluation is QualityEvaluationResult.UNSUITABLE:
                    continue
                yield ExampleSentence.from_candidate(s, tag, evaluation is QualityEvaluationResult.GOOD)
        print(c)
