The central part of this repo is what the README refers to as the sentence database. To describe it more accurately, we have to clarify that:
- the main object is actually the `SentenceRepository`,
- The database (`SentenceDbInterface`) is subordinate to this repository,
- neither of the two contain 20 million sentences - these belong to the repository's `SentenceProducer` (SP).

To be clearer about their specific purpose, it is helpful to look at some example code:

```python
mm = MediaManager()
edr = ExternalDownloadRequester()
sentence_repository = SentenceRepository(mm, edr)

example_sentences = sentence_repository.produce_sentences_for_words(
    {"やるせない": 5,
     "やる": 20,
     "感知": 20},
    produce_new=True,
    ensure_audio=False,
    with_furigana=False,
    progress_callback=print
)
```

Note that the repository will internally instantiate `SentenceDbInterface` and `SentenceProducer`.

The client code's call of `.produce_sentences_for_words(...)` queries the repository to find 5 sentences containing やるせない, 20 containing やる, etc. The repository will first attempt to find these sentences in the database - if this fails, it will turn to the SP, which will scan through up to 20 million sentences to find what the repository has requested. When it returns what it's found to the repository, these new sentences will undergo some onboarding (semantic analysis, generation of audio/furigana, etc) and be inserted into the database for future use. When all this is completed, the repository finally returns the requested sentences to the client code.

The sentence repository in itself doesn't do anything very complicated - it manages some settings on the database and SP, but apart from that it just runs the two-step process described above while interpreting instructions from the queries it receives (`produce_new`, `ensure_audio`, etc.) to decide which internal subsystems to fire up.

Before we go into detail about these subsystems, it is useful to briefly explain one of the more fundamental capabilities of Tansō:

## Japanese Language Processing

The `tatoebator.language_processing` submodule interfaces with a japanese language tokenizer (preferably MeCab, alternatively Sudachi), either as a python package or though the cli via subprocess. Using these and regex, it exposes a series of objects that the rest of the code uses to process japanese language. By far, the two most important capabilities of this submodule are:

- To extract from any text a list every word within, in dictionary form, classified by parts of speech,
  - E.g. in english: "Tom's boss ran a marathon yesterday" -> {verbs: to run; nouns: boss, marathon; adverbs: yesterday; grammatical words: 's, a; proper nouns: Tom},
- To generate and add furigana to text.

It bears mentioning that, as this submodule allows the rest of the code to distinguish words that are grammatical (e.g. to, of, a) from words that are semantic (e.g. house, thousand, to dance), Tansō generally only cares about semantic words, e.g. it will never try to find example sentences for "of" nor will it count the word "of" when looking through a sentence that contains it. This is on purpose - grammatical words are better off being learned from a book or an anki deck tailor-made for them.

Also worth mentioning are a couple functionalities that help the SP make some judgement calls to optimize its search process:

- A translator (via `googletrans`),
- A crude semantic distance estimator.

## The Sentence Database

Corresponding to `tatoebator.db.core.SentenceDbInterface`. This is a contains data about all the sentences that Tansō has made use of (i.e. sentences that actually are in cards). It is an SQLAlchemy database with three tables:

- *Sentences.* Contains sentence id, text in english and japanese, credit (i.e. where it's from), source_tag (indicates license under which the source is distributed), and some extra data used for priority during querying.
- *Keywords.* This contains the dictionary forms of words that have been recognized by the language processing module. It also keeps a boolean indicating whether the user has learned this particular word yet.
- A relation between the last two tables, telling us which words are present in which sentences.

Realistically speaking it would be very unlikely for the amount of sentences on this database to ever go above 100.000. Because of this and some covering indices on the keywords, database search is relatively fast - wait times on repository queries are never due to the database.

`SentenceDbInterface` is relatively straightforward and has all the (/batch) querying/updating functions one would expect. Of note is that it uses its knowledge of which words are known by the user to maintain comprehensibility scores for every sentence (% words understood by user), which it uses to prefer returning more comprehensible sentences, and allow the repository to impose hard limits on comprehensibility.

## Sentence Production

Sentence production is handled by an instance of `tatoebator.sentences.SentenceProducer` kept by the repository. Internally, this SP keeps a number of `SentenceProductionMethod`s (SPMs) - these are objects from which the SP can get an iterator of bilingual sentence pairs. The SP also keeps an instance of a `ExampleSentenceQualityEvaluator`, used to reject sentences that fail certain quality checks before they can be ingested into the database.

Upon receiving a request for some sentences containing some words, the SP will proceed to search through every sentence from every SPM in order, pushing these sentences through a highly customized pipeline that makes sure to keep sentences at a certain level of quality and comprehensibility (via callback to the repository), while also minimizing the amount of unnecessary computation, using multithreading to maximize speed, and providing regular UI callbacks to update the user on progress. The settings of this pipeline also depend on the specifics of the request passed by the repository and how much the SP trusts the SPM that it is currently using.

We go through some of the more complicated aspects of this overview.

### SPMs

The SP has the capability to draw sentences from several different sources, each of which corresponds to one SPM, i.e. one subclass of `SentenceProductionMethod`, e.g. `JapaneseEnglishSubtitleCorpusASPM`. This SPM "contains" almost 3 million sentences, but by default none of these are present in the program files. The way that this actually works is via an object called the `ExternalDownloadRequester` (EDR) - this warrants an aside in of itself:
> The first time that the SP requests sentences from an SPM, the SPM will call upon a reference that it has to the EDR - observe that this dependency was inserted all the way back at the creation of the repository, as it normally goes all the way to the frontend code. This will throw up a window that will ask the user to either download the data required by the SPM (the program can either do this automatically or instruct the user on how to do it), or reject the download. This decision will be remembered and the window will not be thrown up again.
> 
> This UX is not as bad as it sounds: By default the EDR will present the user will all the external download options at once, such that the window only has to be looked through once, clicking "Download" or "Reject" on each of the options. Moreover the user can at any point through the app settings open the EDR window again and change any of the decisions, deleting or redownloading the data as necessary.

Having access to this, the SPM simply requests the download from the EDR, and then either:
- if the download was rejected, informs the SP that it has no sentences to provide,
- if the download was carried out normally, gets pointers to the relevant files from the EDR, and uses its own private functions to process these files into a continuous stream of example sentences that it relays to the SP.

From the SP's perspective, each SPM's only job is to provide a stream of bilingual sentence pairs, each with proper attribution, and possibly audio - but the SPM makes no promises that the translations it provides are correct, that the format isn't broken, or even that the sentences are in japanese or english at all. Hence why the SP has to handle the following section:

### Quality control

The SP has a `ExampleSentenceQualityEvaluator` object which it calls `_quality_control` (QC), which it uses to cull every sentence of insufficient quality before relaying anything back to the repository. It's important to mention that:

- The QC will have to do quite a lot of computations
- Not all of these computations are necessary
- The knowledge of which computations are necessary lies with the SP, not the QC

so the QC and the SP are somewhat coupled, though to the QC this only means that its interface splits its checks into two stages for no obvious reason. Namely, it exposes two functions to the SP:

- `evaluate_quality`, which simply checks that the sentence pair has no obvious mistakes - characters are in the correct alphabet, no weird html tags lying around, sentences of a reasonable length, etc.
- `evaluate_translation_quality`, which ensures within reason that the pair of sentences are actually a translation of each other. For this a translation has to be generated - this can be a large bottleneck, so the SP handles it and passes the translation to the QC.

It is also worth mentioning that we told a small lie earlier: the SPMs are in fact capable of making promises about quality, by having a class variable `translations_reliable = True`. When this is the case, the SP can judiciously skip the second step of the checks above.

### Search process

The SP sequentially takes sentences from its SPMs and pushes them into a multiprocessing pipeline. This pipeline several steps, at any of which a sentence may drop out. The steps are:

- Check that the sentence contains at least one of the desired words,
- Check that the sentence isn't already in the database, via callback,
- Check that the sentence passes the first round of quality control,
- Check that the sentence has the required comprehensibility, via callback,
- If translations are not trusted, generate a machine translation for the sentence - this is done batched and in parallel,
- Check, with the machine translations as reference, that the sentence passes the second round of quality control,
- These last two steps may repeat (because translation isn't deterministic: if we're having trouble finding one specific word, we might give sentences with it a few extra attempts).

There are some details missing here (single vs batched translation, progress callbacks, searching for declensed words, complications with parallel searching of different words...), but this is the general idea of how the SP supplies the repository with new sentences of reliable quality whenever needed.

### Misc.

Two closing notes about the SP:

- The SP also has a fixed amount of sentences (~15000) (those from a specific, highly reliable SPM) that it can give to the repository upon request - the repository uses this to kickstart the database, thus comfortably obtaining a decent amount of sentences for every reasonably common word.

- The SP used to distinguish between SPMs and ASPMs (the A meaning "Arbitrary") - this difference is still present in the nomenclature, as all the SPMs we've mentioned are actually ASPMs in the code. SPMs used to work slightly differently in that the SP was able to query them to search for a specific word - these SPMs were usually bots that would then proceed to use the search function to obtain sentences from websites like Tatoeba.org (this whole project started as a tiny Kanshudo crawler). There are many reasons why this isn't used anymore: it's far slower, leads to far more licensing issues, requires internet usage, and is far more prone to return copies of the same sentence - and beyond that, the SP would become much too complicated if it had to account for the possibility of using (non-A)SPMs on top of the regular ASPMs.

## Audio

Audio is handled by an instance of `tatoebator.audio.media_manager` (MM) kept by the repository. This refers primarily to audio generation, but also intake of external audio files, ensuring that everything is kept as 64 kbps mp3s (via ffmpeg), and managing of a permanent non-blocking audio generation queue that runs in the background.

The MM takes responsibility of all the audio bookkeeping, and thus the database (and anything that the repository gets from the database) knows nothing about whether any of its sentences have audio or where this audio lives. In this way, whenever the repository gets a request that requires audio, upon first getting these sentences from the database or SP, these sentences will not contain a reference to any audio file - thus the repository has to rely on the MM to endow the sentences with audio.

There is a caveat to the prior paragraph, though, which is that the MM is decoupled enough from the rest of the model that it doesn't actually know what an `ExampleSentence` object is - thus it falls on the repository to handle the high-level logic relating to this process. Specifically:

- When getting any sentence (from db or SP), the repository will ask the MM whether this sentence already has audio
- If this is not the case, and the sentence comes with external audio, the repository will tell the MM to enqueue intake of this audio
- Otherwise, the repository will tell the MM to enqueue generation of the necessary audio
- The repository will ask the MM were the required audio is (or is going to be), and endows the example sentence with a reference to this filepath.

The above outlines the four functionalities that the repository requires from the MM (plus some extra for bookkeeping). A couple of aspects from the MM's internals are worth highlighting:

**Task queueing.** That the audio be generated/processed in the background is vital: although one sentence doesn't take more than a couple seconds, the average repository query will probably be asking for upwards of a hundred sentences. For this reason the management of a background queue is a vital feature of the MM - and, importantly, because this queue might be several minutes long, the MM is also capable of persisting it through executions, in case the program terminates before the queue completes.

**No bookkeeping.** Internally, the MM doesn't actually do any bookkeeping. Rather, it hashes incoming sentences into 32-character strings which it uses as filenames for the audio of these sentences. In this way, it does not need to use or persist a table of sentences -> files.

**Audio generation.** This is handled by an instance of a subclass of `tatoebator.audio.tts.TTSManager` kept by the MM, which exposes a relatively straightforward interface to generate japanese audio for passed strings (allowing also control of speed, speaker selection, etc.) Subclasses of `TTSManager` provide interfaces to specific TTS services - namely [w-okada](https://github.com/w-okada/ttsclient), [VoiceVox](https://voicevox.hiroshiba.jp/) and [VoicePeak](https://www.ah-soft.com/voice/). Note that VoicePeak requires a license - the best free option is likely VoiceVox (w-okada has better average quality, but sometimes drops words and the like).

## Misc

**Furigana.** Furigana is fairly cheap to generate, so the backend doesn't actually persist it anywhere - it gets generated on-demand by the repository when it recieves a query that requires it. This is done via (a local copy of) [this other repository of mine](https://github.com/XaviACLM/furigana), living in the language processing module, which relies on the tokenizer (mecab / sudachi) to obtain the readings for each word.

**Frontend.** The frontend is built on PyQt5 (no QtDesigner). The overall application controller is the `Tatoebator` object, which creates and manages some conductor objects (e.g. `MiningProcessConductor`) to take the application through certain user flows. The gui takes care to avoid making the user repeat itself: the controller keeps a persisted cache of gui data (e.g. last selected field), and each conductor keeps a local cache of flow-specific data so that e.g. fields do not need to be refilled when the user goes back. The frontend is of generally straightforward design, possibly with the exception of `WordTableWidget` and its subclasses.

**Persistables.** Some classes defined in `persistence.py` are used across the codebase as a drop-in way to persist data across executions - this works as a sort of json-type serialization and is best suited to dataclasses (where the fields are basic python types or compositions thereof, incl. dataclasses). It is essentially meant to be a version of Pickle that doesn't require the codebase to be entirely static, but only the elements of it that are referenced by the persisted data (i.e. the class and attribute names).

**Card data.** The decks generated by Tansō are intended to work fine even in the abscence of Tansō (e.g. when exported), so none of this codebase can be relied on to help when it comes to rendering the cards. For this reason, the cards have to keep within themselves the data about the sentences that they contain (and a reference to the audio file).
