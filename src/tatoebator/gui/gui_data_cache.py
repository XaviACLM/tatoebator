import os
from typing import Optional

from ..constants import PATH_TO_USER_FILES
from ..persistence import PossiblyEmptyPersistable


class GuiDataCache(PossiblyEmptyPersistable):
    default_filepath = os.path.join(PATH_TO_USER_FILES, "gui_data_cache.ejson")

    def __init__(self,
                 last_selected_deck_id: Optional[int] = None,
                 word_table_help_menu_clicked: bool = False):
        self._save_on_changes = False

        self.last_selected_deck_id = last_selected_deck_id
        self.word_table_help_menu_clicked = word_table_help_menu_clicked

        self._save_on_changes = True

    @classmethod
    def empty(cls):
        return cls()

    def __setattr__(self, key, value):
        super().__setattr__(key, value)
        if key.startswith("_"): return
        if not self._save_on_changes: return
        self.save()
