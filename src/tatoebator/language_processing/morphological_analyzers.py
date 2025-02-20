import os
import subprocess
from dataclasses import dataclass
from typing import List, Set

from ..util import running_as_anki_addon


@dataclass
class Morpheme:
    surface: str
    part_of_speech: Set[str]
    dictionary_form: str
    is_oov: bool


class Tokenizer:
    def __call__(self, text: str) -> List[Morpheme]:
        raise NotImplementedError()


forced_utf8_env = os.environ.copy()
forced_utf8_env["PYTHONUTF8"] = "1"


if running_as_anki_addon():
    from ..timed_resource_manager import TimedResourceManager
    from ..config import SUDACHI_EXE


    def process_sudachi_cli_output_line(line: str) -> Morpheme:
        # remove lineskip (not really necessary b/c we never grab the final feature)
        line = line[:-1]
        # skipped (iirc): dictionari-er form (really using the plan form), readings, a list of dictionary ids
        # truncated to 7 elems b/c at times there's an (OOV) tag on the end (same info as dic_tag)
        surface, features, _, dictionary_form, _, dic_tag, _ = line.split("\t")[:7]
        part_of_speech = set(features.split(","))
        if "*" in part_of_speech: part_of_speech.remove("*")
        is_oov = dic_tag == '-1'
        return Morpheme(surface, part_of_speech, dictionary_form, is_oov)


    # works in normal env but randomly intersperses empty input lines / blocking calls on anki. god knows why
    class SudachiResource(TimedResourceManager):
        def _start_resource(self):
            self.process = subprocess.Popen([SUDACHI_EXE, '-s', 'core', '-m', 'C', '-a'],
                                            stdout=subprocess.PIPE,
                                            stdin=subprocess.PIPE,
                                            stderr=subprocess.PIPE,
                                            text=True, encoding='utf-8',
                                            shell=False,
                                            env=forced_utf8_env)

        def _stop_resource(self):
            self.process.stdin.close()
            self.process.terminate()
            self.process.wait()

        def _process_request(self, text):
            text = text.replace("\n", " ")
            self.process.stdin.write(text + "\n")
            self.process.stdin.flush()
            return iter(self.process.stdout.readline, "EOS\n")


    class SudachiTokenizer(Tokenizer):
        def __init__(self):
            self.sudachi_resource = SudachiResource()

        def __call__(self, text):
            output = self.sudachi_resource.process_request_managed(text)
            return list(map(process_sudachi_cli_output_line, output))


    """
    # a more uncomplicated interface to the .exe in case the other is too finnicky
    class SudachiTokenizer(Tokenizer):
        def __call__(self, text):
            text = text.replace("\n", " ")
            p = subprocess.Popen([SUDACHI_EXE_PATH,'-s', 'core','-m','C','-a'],
                                 stdout=subprocess.PIPE,
                                 stdin=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 text=True, encoding='utf-8',
                                 env=forced_utf8_env)
            stdout_data, _ = p.communicate(input=text)
            stdout_data_lines = stdout_data.splitlines()[:-1] # remove 'EOS\n'
            return list(map(process_sudachi_cli_output_line, stdout_data_lines))
    """
else:
    import sudachipy


    def from_sudachipy_morpheme(morpheme: sudachipy.Morpheme) -> Morpheme:
        part_of_speech = set(morpheme.part_of_speech())
        if "*" in part_of_speech: part_of_speech.remove("*")
        return Morpheme(surface=morpheme.raw_surface(),
                        part_of_speech=part_of_speech,
                        dictionary_form=morpheme.dictionary_form(),
                        is_oov=morpheme.is_oov())


    class SudachiTokenizer(Tokenizer):
        def __init__(self):
            self.tokenizer = sudachipy.Dictionary().create()
            self.mode = sudachipy.Tokenizer.SplitMode.C

        def __call__(self, text):
            return list(map(from_sudachipy_morpheme, self.tokenizer.tokenize(text, self.mode)))

if running_as_anki_addon():
    from ..timed_resource_manager import TimedResourceManager
    from ..config import MECAB_EXE


    def process_mecab_cli_output_line(line: str) -> Morpheme:
        # remove lineskip (not really necessary b/c we never grab the final feature)
        line = line[:-1]
        surface, features = line.split('\t')
        features = features.split(",")
        part_of_speech = set(features[:6])
        if "*" in part_of_speech: part_of_speech.remove("*")
        dictionary_form = features[6]
        is_oov = len(features) < 9
        return Morpheme(surface, part_of_speech, dictionary_form, is_oov)


    class MeCabResource(TimedResourceManager):
        def _start_resource(self):
            mecab_path, mecab_exe = os.path.split(MECAB_EXE)
            self.process = subprocess.Popen([mecab_exe],
                                            cwd=mecab_path,
                                            stdout=subprocess.PIPE,
                                            stdin=subprocess.PIPE,
                                            stderr=subprocess.PIPE,
                                            text=True, encoding='utf-8',
                                            shell=False,
                                            env=forced_utf8_env,
                                            creationflags=subprocess.CREATE_NO_WINDOW)

        def _stop_resource(self):
            self.process.stdin.close()
            self.process.terminate()
            self.process.wait()

        def _process_request(self, text):
            text = text.replace("\n", " ")
            self.process.stdin.write(text + "\n")
            self.process.stdin.flush()
            # grab items from readline until EOS
            return iter(self.process.stdout.readline, "EOS\n")


    class MeCabTokenizer(Tokenizer):
        def __init__(self):
            self.mecab_resource = MeCabResource()

        def __call__(self, text):
            output = self.mecab_resource.process_request_managed(text)
            return list(map(process_mecab_cli_output_line, output))


    """
    # a more uncomplicated interface to the .exe in case the other is too finnicky
    class MeCabTokenizer(Tokenizer):
        def __call__(self, text):
            text = text.replace("\n", " ")
            p = subprocess.Popen([MECAB_EXE_PATH],
                                 stdout=subprocess.PIPE,
                                 stdin=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 text=True, encoding='utf-8',
                                 env=forced_utf8_env)
            stdout_data, _ = p.communicate(input=text)
            stdout_data_lines = stdout_data.splitlines()[:-1] # remove 'EOS\n'
            return list(map(process_mecab_cli_output_line, stdout_data_lines))
    """
else:
    import MeCab


    class MeCabTokenizer:
        def __init__(self):
            self.tagger = MeCab.Tagger("-Ochasen")

        def __call__(self, text):
            morphemes = []
            node = self.tagger.parseToNode(text)
            while node is not None:
                surface = node.surface
                split_features = node.feature.split(",")
                part_of_speech = set(split_features[:6])
                if "*" in part_of_speech: part_of_speech.remove("*")
                dictionary_form = split_features[6]
                is_oov = len(split_features) < 9
                # unless surface == '': # BOS/EOS
                if not surface == '':  # BOS/EOS
                    morphemes.append(Morpheme(surface, part_of_speech, dictionary_form, is_oov))
                node = node.next
            return morphemes


DefaultTokenizer = MeCabTokenizer


class DictionaryFormComputer:

    tokenizer = DefaultTokenizer()

    def compute(self, word):
        morphemes = self.tokenizer(word)
        if len(morphemes) != 1:
            return None
        return morphemes[0].dictionary_form


dictionary_form = DictionaryFormComputer().compute
