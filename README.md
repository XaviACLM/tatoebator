**Tatoebator** is an anki addon for sentence mining and flashcard generation, designed to make japanese learning more natural, more contextual, and less of a chore. It integrates with Anki to automatically enrich your flashcards with example sentences, clean audio, and dictionary definitions, all drawn from a carefully curated and properly licensed database of over 20 million multilingual sentence pairs.

The goal is to move away from memorizing isolated words and toward a workflow that mirrors real language use—seeing words in context, hearing them spoken, and reinforcing them with meaningful examples. Tatoebator understands conjugations, tracks vocabulary coverage, and helps you prioritize new words based on actual reading material. If you feed it a Japanese text, it can break it down, identify unfamiliar vocabulary, and generate full Anki cards—definitions, sentences, and audio included.

<!-- Everything is exposed through a full-featured UI, with automatic downloading of required resources and configuration-light setup. While the backend is fairly complex, the goal is simplicity on the user’s end: efficient card generation with minimal friction, and no license headaches. -->

**Project status.** This tool works as intended and is feature-complete for now, but development is on hold while I rethink some aspects of the approach. See [here](readme_assets/PROJECT_STATUS.md) for more.

## Install

This is an anki addon, and can be easily installed by just copying this to your `Anki2/addons21` folder. Note that it is not currently published in Ankiweb.

The program will at some point query you to download the files from which it ingests sentence data (it can do this automatically or give instructions for manual download). It is not necessary to download all of these sources, Tatoebator will work fine with any combination of them.

The program requires that MeCab (or Sudachi) and Voicevox (or VoicePeak, or w-okada-tts) be installed. It will assume that these can be found in Program Files, but if this is not the case the paths to the executables can be easily changed in `config.py`, at the module's top level.

## Project overview

The primary feature of Tatoebator is the sentence database:
- Over 20 million bilingual sentence pairs to pull from,
- Enough understanding of grammar to recognize words in any form,
- Integration with anki allowing the db to recognize words that are already known,
  - In turn allowing sentences to be graded and sorted by comprehensibility (also possible during search, on the fly), 
- Integration with several TTS options (most of them free) to generate and store readings for every sentence used,
- Optimized batch search, capable of looking for any amount of words through all 20+M sentences in less than a minute.

The intended usage of this database is to, upon card creation, preferably in batches, query the database to find 5-20 example sentences for each word, with audio, translations, and furigana, and insert these sentences into the corresponding anki card for each word. Tatoebator handles everything mentioned above, including the production of furigana and the creation of the decks, cards, notes, notetypes, etc.

This is all easily usable by client code, but the intent is to use one of the two methods of card creation that come packaged into Tatoebator. Namely:

- **Yomitan intercept.** Tatoebator can be configured to hook onto the anki card creation process and intercept cards created in the yomitan format by ankiconnect, modifying them to add the example sentences as desired.

- **Word mining.** Tatoebator features a menu where the user can insert any japanese text, from which Tatoebator will extract all words in their dictionary form, discard those that are already known (also give the option to discard proper nouns, etc), and then create cards for all selected new words.

Tatoebator also makes sure to only use correctly attributed data within license, and has options both to automatically download the required data or instruct the user on how to do it.

## Structure

See [here.](readme_assets/STRUCTURE.md)

## Notes

**Sourcing.** Sentences are extracted from the Tatoeba Corpus, also using the pared-down version in ManyThings.org, and from the Japanese-English Subtitle Corpus (JESC) and JParaCrawl. Each sentence in the db is tagged with the corresponding attribution (including the specific source in the case of Tatoeba or JParaCrawl), and this is always displayed whenever the sentences appear in the UI.

**Licensing.** Each sentence in the db is accompanied by an integer tag describing its source and database - what these mean can be checked in `user_files/annotated_data_sources.txt.` All licenses are CC-BY and permit usage in this tool, with the exception of JParaCrawl, which is in a grey area, hence why it is not used by default.

**On the name.** "Tatoeba" (例えば) means "for example", hence the usage in the naming of a tool which is primarily about providing example sentences. This is a slightly dubious, since "example" (as a noun rather than a word in the locution "for example") is better translated as rei (例), in particular reibun (例文), "example sentence". In some sense thus this project would've been better off being called "Reibunator", but "for example" has a more dynamic feel than just "example". This mirrors the naming of the Tatoeba Corpus, though this is in fact unintentional - this project began as entirely unrelated to the Tatoeba Corpus.
