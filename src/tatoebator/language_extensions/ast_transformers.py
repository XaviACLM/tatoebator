import io
import os
import sys
import token
import tokenize
from importlib.abc import Loader, MetaPathFinder
from importlib.util import spec_from_file_location

from ..constants import PACKAGE_DIR


class UnlessMetaFinder(MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if path is None or path == "": return None
        if len(path) == 0: return None
        if len(path) > 1: print(path, fullname); assert False
        if os.path.commonpath((PACKAGE_DIR, path[0])) != PACKAGE_DIR:
            return None
        *parents, name = fullname.split(".")
        for entry in path:
            if os.path.isdir(os.path.join(entry, name)):
                # this module has child modules
                filename = os.path.join(entry, name, "__init__.py")
                submodule_locations = [os.path.join(entry, name)]
            else:
                filename = os.path.join(entry, name + ".py")
                submodule_locations = None
            if not os.path.exists(filename):
                continue

            return spec_from_file_location(fullname, filename, loader=UnlessLoader(),
                                           submodule_search_locations=submodule_locations)


def transform_unless(source_code):
    """Rewrites `unless condition:` into `if not condition:` using tokenize"""
    result = []
    last_token = None  # Keep track of the last token type

    tokens = tokenize.generate_tokens(io.StringIO(source_code).readline)

    for toknum, tokval, start, end, line in tokens:
        if toknum == tokenize.NAME and tokval == "unless":
            # Ensure 'unless' is not part of a variable name, function, or string
            if last_token is None or last_token in {token.NEWLINE, token.NL, token.INDENT, token.DEDENT, token.OP,
                                                    token.COLON}:
                result.append((tokenize.NAME, "if"))
                result.append((tokenize.NAME, "not"))  # Insert `not` immediately
                last_token = tokenize.NAME
                continue  # Skip default append of `unless`

        result.append((toknum, tokval))
        last_token = toknum  # Track the last token type

    # Convert token list back to code
    return tokenize.untokenize(result)


class UnlessLoader(Loader):
    def __init__(self):
        pass

    def create_module(self, spec):
        return None  # use default module creation semantics

    def exec_module(self, module):
        with open(module.__file__, encoding='utf-8') as f:
            src = f.read()

        code = transform_unless(src)

        exec(code, module.__dict__)


def install_unless():
    sys.meta_path.insert(0, UnlessMetaFinder())
