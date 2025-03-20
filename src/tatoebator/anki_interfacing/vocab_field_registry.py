import os
from dataclasses import dataclass
from typing import List

from ..constants import PATH_TO_USER_FILES
from ..language_extensions import TransientSingleton
from ..persistence import PossiblyEmptyPersistable


@dataclass(frozen=True)
class FieldPointer:
    deck_id: int
    notetype_id: int
    field_ord: int


class VocabFieldRegistry(PossiblyEmptyPersistable, TransientSingleton):
    default_filepath = os.path.join(PATH_TO_USER_FILES, "vocab_field_registry.ejson")

    def __init__(self, field_pointers: List[FieldPointer]):
        self.field_pointers = field_pointers

    @classmethod
    def empty(cls):
        return cls([])

    def __getitem__(self, key):
        return self.field_pointers[key]

    def clear(self):
        return self.field_pointers.clear()

    def extend(self, *args, **kwargs):
        return self.field_pointers.extend(*args, **kwargs)

    def __iter__(self):
        return iter(self.field_pointers)
