import os
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Tuple

import anki.collection
from aqt import mw

from .audio import MediaManager
from .constants import PATH_TO_USER_FILES, INTER_FIELD_SEPARATOR
from .language_extensions import TransientSingleton
from .language_processing import Definitions, add_furigana_html
from .persistence import PossiblyEmptyPersistable
from .sentences import ExampleSentence


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


class TatoebatorAnkiObjectRegistrar(PossiblyEmptyPersistable):
    default_filepath = os.path.join(PATH_TO_USER_FILES, "anki_id_registrar.ejson")

    default_tatoebator_deck_name = "Tatoebator Mined Vocab"
    default_tatoebator_notetype_name = "Tatoebator Notetype"

    recognition_cardtype_name = "Recognition"
    recognition_vocab_field_ord = 1  # TODO or is it 0?

    def __init__(self,
                 deck_id: Optional[int],
                 notetype_id: Optional[int]):
        self.deck_id = deck_id
        self.notetype_id = notetype_id

    @classmethod
    def empty(cls):
        return cls(None, None)

    @property
    def field_pointer(self):
        return FieldPointer(self.deck_id, self.notetype_id, self.recognition_vocab_field_ord)

    def ensure_objects_exist(self, col: anki.collection.Collection):
        self._ensure_deck(col)
        self._ensure_notetype(col)
        self.save()

    def _ensure_deck(self, col: anki.collection.Collection):
        id_ = self.deck_id
        if id_ is None or id_ != col.decks.get(id_)['id']:
            self._create_tatoebator_deck(col)

    def _create_tatoebator_deck(self, col: anki.collection.Collection):
        deck = col.decks.new_deck()
        deck.name = self.default_tatoebator_deck_name
        id_ = col.decks.add_deck(deck).id
        self.deck_id = id_

    def _ensure_notetype(self, col: anki.collection.Collection):
        id_ = self.notetype_id
        if id_ is None or col.models.get(id_) is None:
            self._create_tatoebator_notetype(col)

    def _create_tatoebator_notetype(self, col: anki.collection.Collection):
        mm = col.models
        m = mm.new(self.default_tatoebator_notetype_name)

        mm.addField(m, mm.new_field("word"))
        mm.addField(m, mm.new_field("word_audio"))
        mm.addField(m, mm.new_field("word_furigana"))
        mm.addField(m, mm.new_field("definition_eng"))
        mm.addField(m, mm.new_field("definition_jpn"))
        mm.addField(m, mm.new_field("sentence_data"))
        mm.addField(m, mm.new_field("other_data"))

        t = mm.new_template(self.recognition_cardtype_name)

        # css

        # m["css"] += """\
        m["css"] = """\
.card {
  font-family: arial;
  font-size: 20px;
  text-align: center;
  color: black;
  background-color: #f9f9ff;
}
.sentence {
  position: relative;
  padding: 1em 0;
  margin: 1% 3% 1% 3%;
  border-radius: 0.6em;
  background-color: #fff;
}
.sentence .sentence-jpn {
  font-size: 100%;
  font-weight: normal;
  color: #111;
  padding: 0.2em;
}
.sentence .sentence-eng {
  font-size: 80%;
  color: #333;
  padding: 0.2em;
  visibility: hidden;
}
.sentence .sentence-source {
  position: absolute;
  bottom:10px;
  right:10px;
  font-size: 60%;
  color: #ccc;
  padding: 0.2em;
}
.sentence:hover .sentence-eng {
  visibility: visible;
}

.night-mode .card {
  background-color: #191930;
  background-color: #222;
}
.night-mode .sentence {
  background-color: #2c2c2c;
}
.night-mode .sentence .sentence-jpn {
  color: #eee;
}
.night-mode .sentence .sentence-eng {
  color: #eee;
}
.night-mode .sentence .sentence-source {
  color: #666;
}
"""


        t["qfmt"] = """\
{{word_audio}} {{word_furigana}}
<hr>
<div id='definition-eng-elem'>{{definition_eng}}
<hr>
</div>
<div id='definition-jpn-elem'>{{definition_jpn}}
<hr>
</div>

<!-- just here to deliver the data in proper format. gets deleted by js immediately -->
<div id="sentence-data-container">{{sentence_data}}</div>

<div id="sentences-container">
    <div class="sentence">
        <div class="sentence-audio" style="display: inline-block;"></div>
        <div class="sentence-jpn" style="display: inline-block;"></div>
        <div class="sentence-eng"></div>
        <div class="sentence-source"></div>
    </div>
</div>

<!-- here to pass info from the front script block to the back script. always with display set to none -->
<div id="message-passing-div" style="display: none"></div>

<!-- used during debug and to notify user if there is trouble in the javascript -->
<div id="debug-div">debug elem visible (this means something went wrong in the card js)</div>

<script>
function main(){
    //abort if script has already run
    const sentence_data_elem = document.getElementById("sentence-data-container");
    if (sentence_data_elem==null) {
        return;
    }

    //string->int hashing (complements of bryc on a StackOverflow post)
    const cyrb53 = (str, seed = 0) => {
      let h1 = 0xdeadbeef ^ seed, h2 = 0x41c6ce57 ^ seed;
      for(let i = 0, ch; i < str.length; i++) {
        ch = str.charCodeAt(i);
        h1 = Math.imul(h1 ^ ch, 2654435761);
        h2 = Math.imul(h2 ^ ch, 1597334677);
      }
      h1  = Math.imul(h1 ^ (h1 >>> 16), 2246822507);
      h1 ^= Math.imul(h2 ^ (h2 >>> 13), 3266489909);
      h2  = Math.imul(h2 ^ (h2 >>> 16), 2246822507);
      h2 ^= Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  
      return 4294967296 * (2097151 & h2) + (h1 >>> 0);
    };

    //randomness setup
    var oneDayInMs = 1000 * 60 * 60 * 24;
    var currentTimeInMs = new Date().getTime();
    var timeInDays = Math.floor(currentTimeInMs / oneDayInMs);
    var numberForToday = timeInDays % 9999;
    var seed = numberForToday+cyrb53("{{word}}");
    function random() {
      seed = ((1103515245*seed+12345)%2147483648);
      return seed/2147483648;
    }

    //gather and organize sentence data
    const sentence_data_str = sentence_data_elem.innerHTML;
    sentence_data_elem.remove();
    const sentence_data = sentence_data_str.split("##SEP##");
    const n_sentences = Math.floor(sentence_data.length/5);

    //generate indices for back/front sentences
    //TODO these numbers have to be set by config (much like parts of the html)
    const amt_sentences_back = Math.min(n_sentences, 5);
    const amt_sentences_front = Math.min(n_sentences, 2);
    let selected_indices = [];
    while (selected_indices.length<amt_sentences_back) {
        idx = Math.floor(random()*n_sentences);
        if (!selected_indices.includes(idx)) {
            selected_indices.push(idx);
        }
    }

    //locate/generate html for example sentences
    const sentence_container_elem = document.getElementById("sentences-container");
    const base_sentence_elem = document.querySelector(".sentence");
    let sentence_elems = [base_sentence_elem];
    for (i=1; i<amt_sentences_back; i++) {
        sentence_elems.push(base_sentence_elem.cloneNode(true));
        sentence_container_elem.appendChild(sentence_elems[i]);
    }

    //populate sentence elems
		let j;
    for(i=0;i<amt_sentences_back;i++){
        j = selected_indices[i];
        sentence_elems[i].querySelector(".sentence-audio").innerHTML = sentence_data[5*j+3];
        sentence_elems[i].querySelector(".sentence-jpn").innerHTML = sentence_data[5*j+1];
        sentence_elems[i].querySelector(".sentence-eng").innerHTML = sentence_data[5*j+2];
        sentence_elems[i].querySelector(".sentence-source").innerHTML = sentence_data[5*j+4];
    }


		// hiding stuff that shouldn't be on the front of the card. will be unhid by the back
    for (i=amt_sentences_front; i<amt_sentences_back; i++) sentence_elems[i].style.display = 'none';
    for (i=0; i<amt_sentences_back; i++) sentence_elems[i].querySelector(".sentence-eng").style.display = 'none';
    document.getElementById("definition-eng-elem").style.display = 'none';
    document.getElementById("definition-jpn-elem").style.display = 'none';

    // autoplay visible sentences
    let full_autoplay_command = 'play:q:0';
    for (i=0; i<amt_sentences_back; i++) {
        full_autoplay_command += ','+(selected_indices[i]+1);
    }
    front_autoplay_command = full_autoplay_command.slice(0,8+2*amt_sentences_front);
    //TODO uncomment this once we succesfully pushed changes
    // pycmd(front_autoplay_command);
    // in the meantime...
    pycmd('play:q:0');

    // leave the full autoplay command where the backside script block can find it
    message_passing_elem = document.getElementById("message-passing-div");
    message_passing_elem.textContent = full_autoplay_command;

    //debug stuff
    const debug_elem = document.getElementById("debug-div");
    debug_elem.textContent = "";
}
main();
</script>        
"""

        t["afmt"] = """\
{{FrontSide}}
<script>
function main(){
    //locate html for example sentences
    const sentence_container_elem = document.getElementById("sentences-container");
    const sentence_elems = document.querySelectorAll(".sentence");
    const amt_sentences_back = sentence_elems.length;

		// unhiding stuff for the back of the card
    for (i=0; i<amt_sentences_back; i++) sentence_elems[i].style.display = 'block';
    for (i=0; i<amt_sentences_back; i++) sentence_elems[i].querySelector(".sentence-eng").style.display = 'block';
    document.getElementById("definition-eng-elem").style.display = 'block';
    document.getElementById("definition-jpn-elem").style.display = 'block';

    // get the full autoplay command from front
    message_passing_elem = document.getElementById("message-passing-div");
    full_autoplay_command = message_passing_elem.textContent;
    //TODO uncomment this once we succesfully pushed changes
    // pycmd(full_autoplay_command);
    // in the meantime...
    pycmd('play:q:0');


    const debug_elem = document.getElementById("debug-div");
    debug_elem.textContent = "";
}
main();
</script>
"""
        mm.addTemplate(m, t)
        id_ = mm.add(m).id

        self.notetype_id = id_


class WordInLibraryType(Enum):
    NOT_IN_LIBRARY = 1
    IN_LIBRARY_KNOWN = 2
    IN_LIBRARY_NEW = 3


class TatoebatorRecognitionNoteWrapper:
    def __init__(self, note_id: int):
        self.note_id = note_id


class TatoebatorCardCreator:
    def __init__(self, col: anki.collection.Collection, tatoebator_objects: TatoebatorAnkiObjectRegistrar,
                 media_manager: MediaManager):
        self.col = col
        self.tatoebator_objects = tatoebator_objects
        self.media_manager = media_manager

    def create_note(self, word: str, definitions: Definitions, sentences: List[ExampleSentence]):
        note = self.col.new_note(self.tatoebator_objects.notetype_id)

        word_audio_file_ref = self.media_manager.create_audio_file(word, 0.8, None)

        note['word'] = word
        note['word_audio'] = f'[sound:{word_audio_file_ref}]'
        note['word_furigana'] = add_furigana_html(word, ignore_unknown_words=True)
        note['definition_eng'] = "\n- ".join(definitions.en)
        note['definition_jpn'] = "\n- ".join(definitions.jp)
        note['sentence_data'] = INTER_FIELD_SEPARATOR.join((INTER_FIELD_SEPARATOR.join([sentence.sentence,
                                                                                        sentence.furigana,
                                                                                        sentence.translation,
                                                                                        f"[sound:{sentence.audio_file_ref}]",
                                                                                        sentence.credit])
                                                            for sentence in sentences))
        note['other_data'] = ''

        self.col.add_note(note, self.tatoebator_objects.deck_id)


class AnkiDbInterface:

    def __init__(self, media_manager: MediaManager):
        self.col = mw.col
        self.other_vocab_fields = VocabFieldRegistry.load_or_create()
        self.tatoebator_objects = TatoebatorAnkiObjectRegistrar.load_or_create()
        self.card_creator = TatoebatorCardCreator(self.col, self.tatoebator_objects, media_manager)


        self.tatoebator_objects.ensure_objects_exist(self.col)

        # cards = self.col.add_notes()

        # self.col.genCards

    def _get_deck_ids_by_name(self) -> Dict[str, int]:
        col = self.col
        return {name: id_ for id_, name in self.col.db.all("SELECT id,name FROM decks")}

    def _get_notetypes_and_fields_in_deck(self, deck_id: int) -> Tuple[Dict[str, int], Dict[str, Dict[str, int]]]:
        # notetype ids - notetype names - field names - field ords in a certain deck
        data = self.col.db.all(f"SELECT f.ntid, nt.name, f.ord, f.name AS notetype_name\
                    FROM fields f\
                    JOIN notetypes nt ON f.ntid = nt.id\
                    WHERE nt.id IN (\
                        SELECT mid\
                        FROM notes\
                        WHERE id IN (\
                            SELECT nid\
                            FROM cards\
                            WHERE did = {deck_id}\
                        )\
                    );")

        notetype_ids_by_name = {name: id_ for id_, name, _, _ in data}  # some repeats - should be fine
        field_ords_by_name = {name: dict() for name in notetype_ids_by_name}
        for _, notetype_name, field_ord, field_name in data:
            field_ords_by_name[notetype_name][field_name] = field_ord

        return notetype_ids_by_name, field_ords_by_name

    def get_all_field_data(self) -> Tuple[
        Dict[str, int], Dict[str, Dict[str, int]], Dict[str, Dict[str, Dict[str, int]]]]:
        deck_ids_by_name = self._get_deck_ids_by_name()
        notetype_ids_by_names = {deck_name: dict() for deck_name in deck_ids_by_name}
        field_ords_by_names = {deck_name: dict() for deck_name in deck_ids_by_name}
        for deck_name, deck_id in deck_ids_by_name.items():
            notetype_ids_by_name, field_ords_by_name = self._get_notetypes_and_fields_in_deck(deck_id)
            notetype_ids_by_names[deck_name] = notetype_ids_by_name
            field_ords_by_names[deck_name] = field_ords_by_name
        return deck_ids_by_name, notetype_ids_by_names, field_ords_by_names

    def _search_cards_in_deck(self, field_pointer: FieldPointer, search_strings):
        col = self.col

        query = f"""
            SELECT 
                field_at_index(n.flds, {field_pointer.field_ord}) AS string, 
                c.ivl AS ivl
            FROM notes n
            JOIN cards c ON n.id = c.nid
            WHERE n.mid = {field_pointer.notetype_id} AND c.did = {field_pointer.deck_id} 
                  AND field_at_index(n.flds, {field_pointer.field_ord}) IN ({",".join((f'"{s}"' for s in search_strings))})
        """

        data = col.db.all(query)

        # Separate known and pending words
        known_words = {row[0] for row in data if row[1] > 0}
        pending_words = {row[0] for row in data if row[1] <= 0} - known_words  # in case there's more than one cardtype
        unknown_words = set(search_strings) - known_words - pending_words

        return {WordInLibraryType.NOT_IN_LIBRARY: unknown_words,
                WordInLibraryType.IN_LIBRARY_KNOWN: known_words,
                WordInLibraryType.IN_LIBRARY_NEW: pending_words, }

    def _get_known_words_in_deck(self, field_pointer: FieldPointer):
        col = self.col

        col.db.all(f"CREATE TEMPORARY TABLE results AS\
                    SELECT field_at_index(n.flds, {field_pointer.field_ord}) AS string, c.ivl AS ivl\
                    FROM notes n\
                    JOIN cards c ON n.id = c.nid\
                    WHERE n.mid = {field_pointer.notetype_id} AND c.did = {field_pointer.deck_id}")

        data_known = col.db.all("SELECT string FROM results WHERE ivl > 0")
        col.db.all("DROP TABLE results")

        known_words = set([row[0] for row in data_known])
        return known_words

    def group_text_by_library(self, words):
        classified = {kind: set() for kind in WordInLibraryType}
        for field_pointer in self.other_vocab_fields:
            classified_deck = self._search_cards_in_deck(field_pointer, words)
            for kind in WordInLibraryType:
                classified[kind] = classified[kind].union(classified_deck[kind])
        classified[WordInLibraryType.NOT_IN_LIBRARY] -= classified[WordInLibraryType.IN_LIBRARY_NEW]
        classified[WordInLibraryType.NOT_IN_LIBRARY] -= classified[WordInLibraryType.IN_LIBRARY_KNOWN]
        classified[WordInLibraryType.IN_LIBRARY_NEW] -= classified[WordInLibraryType.IN_LIBRARY_KNOWN]
        return classified

    def get_known_words(self):
        known_words = set()
        for field_pointer in self.other_vocab_fields:
            known_words.update(self._get_known_words_in_deck(field_pointer))
        return known_words
