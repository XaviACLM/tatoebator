import json
import os
import re
import zipfile
from typing import Dict, Optional, Callable, Any

from bs4 import BeautifulSoup

from tatoebator.yomitan_utils.anki_template_renderer_content_manager import AnkiTemplateRendererContentManager
from tatoebator.yomitan_utils.structured_content_generator import StructuredContentGenerator

"""
def destructure(item: Any, attrs: List[str]):
    # todo might have to hasattr the attrs themselves
    if not hasattr(item, 'get'):
        return [None] * len(attrs)
    return [item.get(attr) for attr in attrs]


class HtmlTemplateCollection:
    def __init__(self):
        self._templates = dict()

    def load_from_files(self, urls: List[str]):
        for url in urls:
            with open(url, "r") as f:
                templates_document = BeautifulSoup(f, 'html.parser')
            self.load(templates_document)

    def load(self, source: BeautifulSoup):
        pattern = re.compile("([\w\W]+)-template")
        for template in source.select('template'):
            match = pattern.match(template['id'])
            if match is None: continue
            self._templates[match.group(1)] = template

    def instantiate(self, name):
        template = self.get_template_content(name)
        if template is None or not template.contents:
            raise ValueError(f"Failed to find template content element: {name}")
        # what? looking at the file i'm not sure why it only gets the first child. again, we'll see later
        # todo revise
        first_element = template.contents[0]
        return first_element

    def instantiate_fragment(self, name):
        template = self.get_template_content(name)
        if template is None:
            raise ValueError(f"Template not found: {name}")
        return template.contents

    def get_template_content(self, name):
        return self._templates.get(name)


# h = HtmlTemplateCollection()
# h.load_from_files(['templates-display.html'])
# t=h._templates['term-entry']



def get_disambiguations(headwords, headword_indices, all_terms_set, all_readings_set):
    all_terms_set = set(all_terms_set)
    all_readings_set = set(all_readings_set)

    terms = set()
    readings = set()

    for headword_index in (
            headword_indices or []):  # todo COMPLETELY making shit up but this throws an error w/o the elvis and i suspect this is js default behaviour
        term = headwords[headword_index].get('term')
        reading = headwords[headword_index].get('reading')
        terms.add(term)
        readings.add(reading)

    disambiguations = []
    add_terms = terms != all_terms_set
    add_readings = readings != all_readings_set
    if add_terms:
        disambiguations.extend(terms & all_terms_set)
    if add_readings:
        if add_terms:
            for term in terms:
                readings.remove(term)
        disambiguations.extend(readings & all_readings_set)

    return disambiguations


class DisplayGenerator:
    def __init__(self):
        self._templates = HtmlTemplateCollection()

        self._structured_content_generator = StructuredContentGenerator()

    def prepare(self):
        self._templates.load_from_files(['templates-display.html'])

    def create_term_entry(self, dictionary_entry, dictionary_info):  # todo types
        node = self._instantiate('term-entry')

        ...

        return node

    def _create_term_definition(self, definition, dictionary_tag, headwords, unique_terms, unique_readings):
        dictionary, tags, headword_indices, entries = destructure(definition,
                                                                  ['dictionary', 'tags', 'headwordIndices', 'entries'])
        tags = tags or []  # todo guessing standard behaviour
        # todo is headwordIndices right?

        # oh this is from language. i forgot we needed a bunch of crap from language. dude - shit
        # maybe we can just skip it?
        # seems easy to rewrite, actually, but let's wait until we figure out if we'll be needing more stuff
        # todo review
        disambiguations = get_disambiguations(headwords, headword_indices, unique_terms, unique_readings)

        node = self._instantiate('definition-item')

        # todo better be sure that bs4's select returns a reference to sth mutable
        tag_list_container = self._query_selector(node, '.definition-tag-list')
        only_list_container = self._query_selector(node, '.definition-disambiguation-list')
        entries_container = self._query_selector(node, '.gloss-list')

        # todo is this right?
        node['data-dictionary'] = dictionary

        print([*tags, dictionary_tag], disambiguations, entries)
        self._append_multiple(tag_list_container, self._create_tag, [*tags, dictionary_tag])
        self._append_multiple(only_list_container, self._create_term_disambiguation, disambiguations)
        self._append_multiple(entries_container, self._create_term_definition_entry, entries, dictionary)

        return node

    def _create_term_definition_entry(self, entry: Union[str, dict], dictionary):
        if isinstance(entry, str):
            return self._create_term_definition_entry_text(entry)
        elif isinstance(entry, dict):
            t = entry['type']
            if t == 'image':
                return self._create_term_definition_entry_image(entry, dictionary)
            elif t == 'structured-content':
                return self._create_term_definition_entry_structured_content(entry, dictionary)
            elif t == 'text':
                # what?
                # todo figure out if this is a mistake. check out if this actually exists in the dicts and run it
                #  through the code to see if mb these get rendered elsewhere. otherwise the fix is obvious
                pass
        return None

    def _create_term_definition_entry_text(self, text: str):
        node = self._instantiate('gloss-item')
        container = node.select('.gloss-content')
        self._set_multiline_text_content(container, text)
        return node

    def _instantiate(self, name):
        return self._templates.instantiate(name)

    def _query_selector(self, element, selector) -> bs4.BeautifulSoup:
        return element.select_one(selector)  # todo is this supposed to always return one?

    def _create_term_definition_entry_image(self, data, dictionary):
        description = data.get('description')

        node = self._instantiate('gloss-item')

        content_container = self._query_selector(node, '.gloss-content')
        image = self._structured_content_generator.create_definition_image(data, dictionary)
        content_container.append(image)

        if isinstance(description, str):
            fragment = self._templates.instantiate_fragment('gloss-item-image-description')
            container = self._query_selector(fragment, '.gloss-image-description')
            self._set_multiline_text_content(container, description)
            content_container.append(fragment)

        return node

    def _create_term_definition_entry_structured_content(self, content, dictionary):
        node = self._instantiate('gloss-item')
        content_container = self._query_selector(node, '.gloss-content')
        self._structured_content_generator.append_structured_content(content_container, content, dictionary)
        return node

    def _create_tag(self, tag):
        content = tag.get('content')
        name = tag.get('name')
        category = tag.get('category')
        redundant = tag.get('redundant')

        node = self._instantiate('tag')

        inner = self._query_selector(node, '.tag-label-content')

        content_string = '\n'.join(content)

        node['title'] = content_string
        self._set_text_content(inner, name)
        # todo the data sth, check this is ok
        node['data-details'] = content_string or name
        node['data-category'] = category
        if redundant:
            node['data-redundant'] = 'true'

        return node

    def _append_multiple(self, container, create_item, details_array, arg=None):
        # arg being defaulted to None makes sense but i'm uneasy - gotta check to see that the places where it ends up
        # being passed handle that well
        # todo revise
        count = 0
        if hasattr(details_array, '__iter__'):
            for details in details_array:
                if arg is None:
                    item = create_item(details)
                else:
                    item = create_item(details, arg)
                if item is None: continue
                container.append(item)
                if isinstance(item, BeautifulSoup):
                    # originally
                    # (item).dataset.index = `${count}`;
                    # some odd stuff with the naming here... this is a js thing i believe
                    # todo revise
                    item['data-index'] = str(count)
                count += 1

        container['data-index'] = count

        return count

    def _set_text_content(self, node, value, language: str = 'jp'):
        # same as w _set_multiline_text_content
        node['language'] = language
        node['textContent'] = value

    def _set_multiline_text_content(self, node: BeautifulSoup, value: str, language: str = 'jp'):

        # skipping some calls here - don't know what's going on. Class appears to at some point have wanted to
        # incorporate multilanguage support, but it's hardcoded to jp and most of it wouldn't work anyway
        node['language'] = language

        start = 0
        while True:
            end = value.find('\n', start)
            if end == -1: break

            text_node = BeautifulSoup(value[start:end], 'html.parser')
            br_tag = BeautifulSoup('<br>', 'html.parser')
            node.append(text_node)
            node.append(br_tag)
            start = end + 1

        if start < len(value):
            text_node = BeautifulSoup(value[start:], 'html.parser')
            node.append(text_node)

    def _create_term_disambiguation(self, disambiguation):
        node = self._instantiate('definition-disambiguation')
        node['data-term'] = disambiguation  # todo data-
        self._set_text_content(node, disambiguation)
        return node

    def _create_dictionary_tag(self, dictionary):
        return self._create_tag_data(dictionary, 'dictionary')

    def _create_tag_data(self, name, category):
        return {
            'name': name,
            'category': category,
            'order': 0,
            'score': 0,
            'content': [],
            'dictionaries': [],
            'redundant': False,
        }


d = DisplayGenerator()
d.prepare()
"""



# todo correctly handle the taigigo dict. honestly best we filter dicts manually at this point
atrcm = AnkiTemplateRendererContentManager(None, None)
scg = StructuredContentGenerator(atrcm)

'''
sample_jitendex_entry = """['ドライビングコンテスト', 'ドライビングコンテスト', '', '', 0, [{'type': 'structured-content', 'content': [{'tag': 'div', 'content': [{'tag': 'span', 'title': 'noun (common) (futsuumeishi)', 'style': {'fontSize': '0.8em', 'fontWeight': 'bold', 'padding': '0.2em 0.3em', 'wordBreak': 'keep-all', 'borderRadius': '0.3em', 'verticalAlign': 'text-bottom', 'backgroundColor': '#565656', 'color': 'white', 'cursor': 'help', 'marginRight': '0.25em'}, 'data': {'code': 'n'}, 'content': 'noun'}, {'tag': 'span', 'style': {'fontSize': '0.8em', 'fontWeight': 'bold', 'padding': '0.2em 0.3em', 'wordBreak': 'keep-all', 'borderRadius': '0.3em', 'verticalAlign': 'text-bottom', 'backgroundColor': 'purple', 'color': 'white', 'marginRight': '0.25em'}, 'data': {'code': 'golf'}, 'content': 'golf'}, {'tag': 'div', 'content': [{'tag': 'ul', 'style': {'listStyleType': 'none', 'paddingLeft': '0'}, 'data': {'content': 'glossary'}, 'content': {'tag': 'li', 'content': 'driving contest'}}, {'tag': 'div', 'style': {'marginLeft': '0.5em'}, 'data': {'content': 'extra-info'}, 'content': {'tag': 'div', 'content': {'tag': 'div', 'style': {'borderStyle': 'none none none solid', 'padding': '0.5rem', 'borderRadius': '0.4rem', 'borderWidth': 'calc(3em / var(--font-size-no-units, 14))', 'marginTop': '0.5rem', 'marginBottom': '0.5rem', 'borderColor': '#1A73E8', 'backgroundColor': 'color-mix(in srgb, #1A73E8 5%, transparent)'}, 'data': {'content': 'xref'}, 'content': [{'tag': 'div', 'style': {'fontSize': '1.3em'}, 'content': [{'tag': 'span', 'lang': 'en', 'style': {'fontSize': '0.8em', 'marginRight': '0.5rem', 'color': '#1A73E8'}, 'content': 'See also'}, {'tag': 'a', 'lang': 'ja', 'href': '?query=%E3%83%89%E3%83%A9%E3%82%B3%E3%83%B3&wildcards=off', 'content': 'ドラコン'}]}, {'tag': 'div', 'style': {'fontSize': '0.8rem'}, 'data': {'content': 'xref-glossary'}, 'content': 'driving contest; longest drive contest'}]}}}]}]}, {'tag': 'div', 'style': {'marginTop': '0.5rem'}, 'data': {'content': 'forms'}, 'content': [{'tag': 'span', 'title': 'spelling and reading variants', 'style': {'fontSize': '0.8em', 'fontWeight': 'bold', 'padding': '0.2em 0.3em', 'wordBreak': 'keep-all', 'borderRadius': '0.3em', 'verticalAlign': 'text-bottom', 'backgroundColor': '#565656', 'color': 'white', 'cursor': 'help', 'marginRight': '0.25em'}, 'content': 'forms'}, {'tag': 'ul', 'style': {'fontSize': '1.3em'}, 'content': [{'tag': 'li', 'content': 'ドライビングコンテスト'}, {'tag': 'li', 'content': 'ドライビング・コンテスト'}]}]}, {'tag': 'div', 'style': {'fontSize': '0.7em', 'textAlign': 'right'}, 'data': {'content': 'attribution'}, 'content': {'tag': 'a', 'href': 'https://www.edrdg.org/jmwsgi/entr.py?svc=jmdict&q=2506050', 'content': 'JMdict'}}]}], 2506050, '']"""
sample_jitendex_def = """[{'type': 'structured-content', 'content': [{'tag': 'div', 'content': [{'tag': 'span', 'title': 'noun (common) (futsuumeishi)', 'style': {'fontSize': '0.8em', 'fontWeight': 'bold', 'padding': '0.2em 0.3em', 'wordBreak': 'keep-all', 'borderRadius': '0.3em', 'verticalAlign': 'text-bottom', 'backgroundColor': '#565656', 'color': 'white', 'cursor': 'help', 'marginRight': '0.25em'}, 'data': {'code': 'n'}, 'content': 'noun'}, {'tag': 'span', 'title': "nouns which may take the genitive case particle 'no'", 'style': {'fontSize': '0.8em', 'fontWeight': 'bold', 'padding': '0.2em 0.3em', 'wordBreak': 'keep-all', 'borderRadius': '0.3em', 'verticalAlign': 'text-bottom', 'backgroundColor': '#565656', 'color': 'white', 'cursor': 'help', 'marginRight': '0.25em'}, 'data': {'code': 'adj-no'}, 'content': 'no-adj'}, {'tag': 'div', 'content': {'tag': 'ul', 'data': {'content': 'glossary'}, 'content': [{'tag': 'li', 'content': "a woman's natural inclination to care for others"}, {'tag': 'li', 'content': 'big-sisterly disposition'}]}}]}, {'tag': 'div', 'style': {'marginTop': '0.5rem'}, 'data': {'content': 'forms'}, 'content': [{'tag': 'span', 'title': 'spelling and reading variants', 'style': {'fontSize': '0.8em', 'fontWeight': 'bold', 'padding': '0.2em 0.3em', 'wordBreak': 'keep-all', 'borderRadius': '0.3em', 'verticalAlign': 'text-bottom', 'backgroundColor': '#565656', 'color': 'white', 'cursor': 'help', 'marginRight': '0.25em'}, 'content': 'forms'}, {'tag': 'ul', 'style': {'fontSize': '1.3em'}, 'content': [{'tag': 'li', 'content': '姉御肌'}, {'tag': 'li', 'content': '姐御肌'}, {'tag': 'li', 'content': 'アネゴ肌'}]}]}, {'tag': 'div', 'style': {'fontSize': '0.7em', 'textAlign': 'right'}, 'data': {'content': 'attribution'}, 'content': {'tag': 'a', 'href': 'https://www.edrdg.org/jmwsgi/entr.py?svc=jmdict&q=2773680', 'content': 'JMdict'}}]}]"""
exec(f'sample_jitendex_def = {sample_jitendex_def}')
sample_jitendex_def = sample_jitendex_def[0]['content']
sc = scg.create_structured_content(sample_jitendex_def, None)
print(sc)
'''

downloads_dir = r"C:\Users\xavia\Downloads"
dicts_zip_filepath = os.path.join(downloads_dir, "Japanese-20250312T213821Z-001.zip")

cci = 0
with zipfile.ZipFile(dicts_zip_filepath, "r") as dicts_zip:
    for dict_zipinfo in dicts_zip.filelist:
        dict_zipfilename = dict_zipinfo.filename

        with dicts_zip.open(dict_zipfilename, 'r') as dict_zipfile:
            with zipfile.ZipFile(dict_zipfile, 'r') as dict_zip:
                files = set(map(lambda x: x.split("/")[0], [x.filename for x in dict_zip.filelist]))
                if 'index.json' in files:
                    with dict_zip.open('index.json', 'r') as f:
                        pass  # print("\t",f.read().decode('utf-8'))
                cc = 0
                ci = 0
                cs = 0
                for filename in files:
                    if re.fullmatch("term_bank_\d+\.json", filename) is None: continue
                    with dict_zip.open(filename, 'r') as f:
                        data = json.loads(f.read())
                        for item in data:
                            term, reading, def_tags, deinflections, popularity_number, definitions, seq_number, term_tags = item
                            cci += 1
                            assert isinstance(definitions, list)
                            for definition in definitions:
                                # todo handle these somewhere else. str is just definition, list is uh...
                                #  a chain of deinflection rules that explain a redirecton... something something
                                #  "Deinflection of the term to an uninflected term.",
                                #  only jitendex uses these, and only for words that simply redirect elsewhere
                                #  so we can use them as a cue that we should be looking for another word (the deinflection)
                                #  but that leaves the issue of seeing which definitions should be thrown out bc they are just redirections
                                #  or, in general, b/c they're empty without the internal href
                                if isinstance(definition, str): continue
                                if isinstance(definition, list):
                                    print(definition)
                                    print(definitions)
                                    print("")
                                    continue
                                try:
                                    pass  # scg.create_structured_content(definition['content'], None)
                                except:
                                    import traceback

                                    print(traceback.format_exc())
                                    print(item)
                                    print(definitions)
                                    print(jjsj)
                            # if not (isinstance(definitions, list) and len(definitions) == 1 and isinstance(definitions[0], str)) and cci%10000==0:
                            #    print(definitions[0]['content'])
                            #    print(scg.create_structured_content(definitions[0]['content'], None))
                            #    input()
                            if isinstance(definitions, list) and len(definitions) == 1 and isinstance(definitions[0],
                                                                                                      str):
                                cc += 1
                            if isinstance(definitions, list) and all([
                                isinstance(definition, str) or (
                                        isinstance(definition, dict) and "type" in definition and definition[
                                    "type"] == "structured-content") for definition in definitions
                            ]):
                                cs += 1
                    ci += len(data)
                    # print("\t\t",c,"/",len(data))
        if ci > 0:
            print(cc, "/", cs, "/", ci, dict_zipfilename)

"""
with structured_content counts - as expected, it's all of the entries:

2306 / 2306 / 2306 Japanese/[JA-JA] 福日木健二字熟語.zip
4017 / 4017 / 4017 Japanese/[JA-JA Yoji] YOJI-JUKUGO.zip
46210 / 46210 / 46210 Japanese/[JA-JA Kanji] 漢字林.zip
0 / 1312 / 1312 Japanese/[JA-JA Counters] 数え方辞典オンライン (2024-02-13).zip
0 / 13965 / 13965 Japanese/[JA-JA Antonyms] 対義語辞典オンライン [2024-04-30].zip
60839 / 60839 / 60839 Japanese/[JA-JA] 全訳漢辞海.zip
0 / 1479 / 1479 Japanese/[JA Grammar] nihongo_no_sensei_1_04.zip
56840 / 56840 / 56840 Japanese/[JA-JA] 例解学習国語辞典 第十一版 [2024-04-30].zip
0 / 266 / 266 Japanese/[JA-EN Onomatopoeia] Onomatoproject.zip
0 / 1422 / 1422 Japanese/[JA-JA Onomatopoeia] surasura.zip
0 / 3738 / 3738 Japanese/[JA-JA Dialect] 全国方言辞典.zip
0 / 8513 / 8513 Japanese/[JA-JA Expressions] 故事・ことわざ・慣用句オンライン.zip
2795 / 2795 / 2795 Japanese/[JA-JA Origins] 語源由来辞典.zip
0 / 18294 / 18294 Japanese/[JA-JA] 新語時事用語辞典.zip
200 / 222 / 222 Japanese/[JA-JA Origins] 複合語起源.zip
0 / 628 / 628 Japanese/[JA Grammar] 日本語NET(nihongo_kyoushi)_v1_03.zip
0 / 7782 / 7782 Japanese/[JA-JA Yoji] 四字熟語辞典オンライン.zip
535 / 535 / 535 Japanese/[JA Grammar] dojg-consolidated-v1_01.zip
212882 / 212882 / 212882 Japanese/[JA-EN] Babylon_Japanese_English.v1.0.0.zip
0 / 12151 / 12151 Japanese/[JA-JA Thesaurus] 類語辞典オンライン (2024-02-09).zip
47958 / 47958 / 47958 Japanese/[JA-JA Kogo] weblio_kogo_expanded_with_conjugation.zip
0 / 1397 / 1397 Japanese/[JA Grammar] [画像付き] 絵でわかる日本語 v3.zip
4354 / 4354 / 4354 Japanese/[JA-JA] 日本語俗語辞書.zip
0 / 1082 / 1082 Japanese/[JA Grammar] どんなときどう使う 日本語表現文型辞典_1_05.zip
5484 / 5484 / 5484 Japanese/[JA-JA Yoji] 学研 四字熟語辞典.zip
152202 / 152202 / 152202 Japanese/[JA-EN] 新和英.zip
48085 / 48085 / 48085 Japanese/[JA-JA] 漢字源.zip
0 / 17350 / 17350 Japanese/[JA-JA Thesaurus] 使い方の分かる 類語例解辞典 [2024-05-02].zip
4194 / 4194 / 4194 Japanese/[JA-JA Yoji] 新明解四字熟語辞典.zip
0 / 86213 / 86213 Japanese/[JA-JA] 現代国語例解辞典　第五版.zip
0 / 8027 / 8027 Japanese/[JA-JA] 漢字でGO!.zip
15577 / 15577 / 15577 Japanese/[JA-JA Expressions] 故事ことわざの辞典.zip
0 / 1248 / 1248 Japanese/other/[JA Grammar] edewakaru_v_1_03.zip
0 / 55379 / 55379 Japanese/[JA-JA] 実用日本語表現辞典.zip
0 / 5120 / 5120 Japanese/[JA-JA] 語彙力・二字熟語の百科事典.zip
0 / 1252 / 1252 Japanese/other/ポケモン図鑑.zip
0 / 1924 / 1924 Japanese/other/TMW Club v2 [2024-05-12].zip
0 / 5451 / 5451 Japanese/[JA-JA Yoji] 四字熟語の百科事典 [2024-06-30].zip
0 / 15371 / 15371 Japanese/[JA-JA Encyclopedia] きっずジャポニカ 新版.zip
89173 / 92217 / 92217 Japanese/[JA-JA] 旺文社国語辞典 第十一版.zip
286365 / 286365 / 286365 Japanese/[JA-JA] 精選版 日本国語大辞典.zip
0 / 2307 / 2307 Japanese/other/全市区町村辞典 [2024-04-30].zip
0 / 7135 / 7135 Japanese/[JA-JA] ことわざ・慣用句の百科事典.zip
0 / 257602 / 257602 Japanese/[JA-JA] 広辞苑 第七版.zip
24154 / 73068 / 73068 Japanese/[JA-JA] 明鏡国語辞典　第二版_2023_07_22.zip
0 / 51590 / 51590 Japanese/[JA-JA] 漢検漢字辞典　第二版.zip
0 / 100593 / 100593 Japanese/[JA-JA] 新明解国語辞典　第八版.zip
595831 / 666782 / 666782 Japanese/[JA-JA Names] JMnedict (2024-11-23).zip
0 / 44970 / 44970 Japanese/[JA-JA] 国語辞典オンライン.zip
16546 / 47504 / 47504 Japanese/[JA-EN] NEW 斎藤和英大辞典.zip
0 / 76625 / 76625 Japanese/[JA-JA] 岩波国語辞典　第八版.zip
very long
0 / 93091 / 93091 Japanese/[JA-JA] 三省堂国語辞典　第八版.zip
very long
0 / 288767 / 301765 Japanese/[JA-EN] jitendex-yomitan (2025-03-04).zip
0 / 294146 / 294146 Japanese/other/素材辞典 v4.2 [2024-05-21].zip
seems worthless, just google images links and similar

0 / 118331 / 118331 Japanese/[JA-JA] 新選国語辞典　第十版.zip
"""

# jesus christ the yomichan format is MASSIVE
# we need an action plan here.
# a lot of extraneous html data. really we'd be fine throwing most of it away
# but we need it to be user readable. its probably better to parse it. word table will change quite a bit to accomodate
# we look for one word (or several at a time)
#  we could gather metadata (frequency ratings). you know what, that's probably a good idea and not too hard.
#   let me check the dicts
#    innocentranked looks like [["要る", "freq", 1], ["から", "freq", 2], ["板", "freq", 3]
#    but aozora bunko looks a bit weird: [["見","freq",{"value":1,"displayValue":"1 (12407)"}],["思","freq",{"value":2,"displayValue":"2 (12319)"}]
#    conjecture that "freq"/"value" is just a ranking of which kanjo are more common ON EACH DICT, not necessarily related
#    display_value is well, meant for display, guessing aozora bunko displays the actual count of ocurrences
#   let's not overcomplicate: just show sth like
#   freq rankings:
#    #67 on Aozora Bunko
#    #316 on innocentranked
#   users are smart, they can figure it out
#   we get this data from term_meta_bank_i.json files in [JA Freq] dicts
#  but most importantly we look for definitions.
#   (...looked at the files for a while)
#   jesus christ. look at jitendex:
#    ["管理対象", "かんりたいしょう", "", "", 0, [{"type": "structured-content", "content": [{"tag": "div", "content":
#    [{"tag": "span", "title": "noun (common) (futsuumeishi)", "style": {"fontSize": "0.8em", "fontWeight": "bold",
#    "padding": "0.2em 0.3em", "wordBreak": "keep-all", "borderRadius": "0.3em", "verticalAlign": "text-bottom",
#    "backgroundColor": "#565656", "color": "white", "cursor": "help", "marginRight": "0.25em"}, "data": {"code": "n"},
#    "content": "noun"}, {"tag": "span", "style": {"fontSize": "0.8em", "fontWeight": "bold", "padding": "0.2em 0.3em",
#    "wordBreak": "keep-all", "borderRadius": "0.3em", "verticalAlign": "text-bottom", "backgroundColor": "purple",
#    "color": "white", "marginRight": "0.25em"}, "data": {"code": "comp"}, "content": "computing"}, {"tag": "div",
#    "content": {"tag": "ul", "style": {"listStyleType": "none", "paddingLeft": "0"}, "data": {"content": "glossary"},
#    "content": {"tag": "li", "content": "managed object"}}}]}, {"tag": "div", "style": {"fontSize": "0.7em",
#    "textAlign": "right"}, "data": {"content": "attribution"}, "content": {"tag": "a", "href":
#    "https://www.edrdg.org/jmwsgi/entr.py?svc=jmdict&q=2347770", "content": "JMdict"}}]}], 2347770, ""]
#   the actual definition there is 'managed object', w the extra bit of 'computing', which i assume is language domain
#   this is rather troubling. as far as i can't tell there isn't any canonical distinction in the json between the
#   actual definition and the tag.
#   which makes enough sense. yt's job is just to show you the dictionary, you do the thinking
#   this in fact makes sense for us too (hence the fact that yt already has anki integration), but it means that we
#   need to be able to parse this whole mess into html
#   which despite my repeated googling doesn't seem like something that's readily available on github? what the hell is
#   up with that???
#   i guess we just have to
#   figuring out how to display html in the boxes - you know, the boxes - shouldn't be too hard
#   it'll need a redesign to make any sense.
#   and the html parser can't be too complicated. it does concern me whether the yt structured-content format can
#   actually be cleanly mapped onto html, but by god i'm just going to ignore anything that's too complicated to fit
#   images will need a bit of extra processing.
#   . . .
#   or we could do some preliminary inspection - look through the dicts and count how many words each of them has
#   if it turns out that 98% of the words are in like three dictionaries we might aswell just look at the specific formats
#   like if we scrape jisho but jisho is in fact just jmedict/jitendex then surely jitendex's format is, despite all
#   the fucking around, regular in itself, so we should be able to write a nice JitendexInterface (best pick a better name)
#   that looks through the mess and kicks out a standarized Definition object (for either lang) - with the text of the
#   definition itself, possibly support for furigana, definitely support for images, maybe some tags or whatever -
#   depending on which dict we look at.
#   but really, if we have pictures we'll end up having to redesign the word table either way. god
#   ...
#   some of the other dicts are thankfully pretty simple - more of that fifth element just being a ['<definition>']
#   ...
#   sometimes if you keep looking down through the 'content' elements it turns out you arrive at a single string.
#   we can take those and ignore the html probably
#   dude, no. wait a minute. look at the antonym dict.
#   ["楽","らく","","",0,
#     [{"type": "structured-content","content": [{
#             "tag": "div","data": {"name": "解説部"},"content": [{
#                 "tag": "div","data": {"name": "大語義"},"content": {
#                   "tag": "div","data": {"name": "語義"},"content": [{
#                       "tag": "span","data": {"name": "対義語"},
#                       "content": "苦   (く)"}]}}]}]}],0,""]
#   the "definition" is just 苦, which is an ANTONYM. the fact that it is an antonym is contained in the 'name' of the
#   span that contains the definition. the 'name' isn't even something that shows up - i'm supposed to know how to
#   interpret this myself? even if i am, does that mean I also have to care about the 解説部, 大語義, 語義 tags?
#   or if i want to parse this naively am i supposed to tell the user each time that he's about to read a meaning,
#   subsection of general meaning in the explanation section? what the hell, man?
#   checked that 対義語 does not appear on the relevant schema. Seriously what the hell?
#   and the dictionary does not appear to carry any css information or anything about how to handle it??????????????
#   god! man! what do i do with this shit?
#   all the [JA-JA something] might just be too spicy for me. best stick to [JA-JA]
#   . . .
#   okay, really, action plan: the first step is to programmatically investigate the dicts. for each count
#   how many words within
#   how many of these have a definition (or several) which is thankfully just a single string
#   we might get favorable results from this
#   . . .
#   moreover be absolutely sure to include the images where possible
#   . . .
#   the donna toki doo tsukau nihongo something something makes good on its name: the definition is mostly just a bunch of examples
#   oh yeah on that subject i forgot to say we should look through the [JA Grammar]-s too. I love the ones with the pictures
#   a lot of the grammars blur the line between languages, though.
#   . . .
#   having slept on it (haven't done anything yet) i can't help but think it's really weird that yomitan doesn't expose an api for this
#   there are some issues on gh about it. one with updates two weeks ago, in fact
#   but i guess it's a bit too much to ask? what i'm asking for specifically, i mean, i don't know what those apis plan to expose
#   but the fact of the matter is that all the info is there and turning it into html shouldn't be that hard, and more to the point,
#   it's not particularly meaningful to want to do this in yomichan as opposed to python b/c it's not like the communication between them
#   can be all that clean, either
#   ...maybe. that's a bit of a flimsy argument. but it is true that it's a slightly odd request to want access to the _rendering_ portion of yomichan
#   well, yomitan, whatever. speaking of, one thing we _should_ integrate is to look for dicts in yomitan's files
#   speaking of, where are my yomitan's files?

#   ...
#   yeah a lot has been learned since i wrote that. i don't feel like elaborating now but an important point for later
#   is we can probably just take structured-content-generator.js and translate that to python
