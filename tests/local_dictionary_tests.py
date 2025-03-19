from tatoebator.yomitan_utils.dev_main import test_timings, test_dictdir

#test_timings()
test_dictdir()

"""
a class that keeps a list of dictionaries (how?)

you can ask it to look for definitions of one (or many) words

will look through dicts
 maybe in some specific order, some logic as to how many definitions to look for, etc
 important also that logic about the redirects you can find in jitendex (stored to look through first?)

produces definition objects. these also keep a reference to the dict that they're from

so that a DefinitionHTMLGenerator class (or something like that) can take just the definition object

handle creating the html itself, with the help of StructuredContentGenerator
and pass to the latter, perhaps use itself, a TatoebatorContentManager
this is to gather certain files from the dictionary files to anki's media folder, handling renaming also

"""

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