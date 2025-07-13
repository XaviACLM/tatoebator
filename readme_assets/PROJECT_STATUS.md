This tool is complete in terms of its original goals: it retrieves high-quality bilingual example sentences for arbitrary Japanese words, using a large corpus and carefully tuned filters. However, in practice, I've found that this approach - while useful for common words - begins to break down for less frequent vocabulary.

For many mid- to high-level words (like やるせない), the number of usable sentence pairs is in the single digits, even across tens of millions of sentences. And those few that do appear are often difficult to learn from: they tend to be long, context-dependent, and filled with other low-frequency vocabulary. This reflects a deeper issue with using natural-language corpora for language learning, where the examples are real enough but not particularly accessible.

Addressing this meaningfully will require a shift in strategy. I have ideas for how to move forward on this, but for now development is on hold while I consider what shape that next iteration might take.

### What's Done, What's Missing

Tansō is stable, fully usable, and has no known bugs. Nonetheless, it is stuck at an awkward stage of development: only a few days into completion of its major features, where many medium-scope todos have not yet been taken care of. Some examples of the scale of the issues this refers to, straight from the todo file:

> TODO better db init: if no exist create w/o covering index, then insert, then create covering index
> 
> TODO segregate user_files content by active user - the config files, anyway, but not sentence.db or the big downloads
> 
> TODO anki interface type annotations, docs
> 
> TODO add new sentences menu (partially semi automatic translations)

These are not particularly relevant to any end user but they do mean that few parts of the codebase can be assumed to be stable.

### Lessons from a Working Prototype

Tansō does what it was designed to do: given a Japanese word, it searches large bilingual corpora for example sentences, filters them for quality, and presents them for study. However, as the project matured, it became clear that the real limitations weren't technical but rather structural, baked into the approach itself.

A good example of this is やるせない (*yarusenai*), the word that shaped much of the second half of this project’s development. It’s not obscure - just a little literary, a little poetic: I came across it in a song, a fluent speaker would likely recognize it. The first time I ran it through an early version of Tansō, which only used the Tatoeba corpus, it returned nothing. A month later, after building a finely tuned pipeline to search tens of millions of sentences across massive corpora, the tool could only surface six usable examples of やるせない - and even those weren't especially learner-friendly, but rather long, contextless, and full of other low-frequency vocabulary.

Similar results appeared for many words at this level of complexity. This wasn't a fluke - the codebase was running up to the natural limitations of the method. Namely:

**(1) Natural-language corpora aren't for learners.**

As mentioned above, learner-oriented corpora (read: the Tatoeba Corpus) cannot be relied on for words at a mid-to-advanced level, and thus we turned to large natural language corpora intended for machine learning. These have some issues with retaining stable quality and correctness, which we were able to resolve with strict quality control - but this reveals another issue: People speaking in natural language are never dialing down their language for a hypothetical learner, they're talking to people who are already fluent - and thus very often use structure and vocabulary that are beyond the reach of even later stage learners. Consider the first sentence in this paragraph: how useful could it really be to someone trying to learn the meaning of "mentioned", "above", or "learner"?

**(2) Vocabulary is never really isolated.**

A broader insight about language learning - past a core vocabulary of about a couple thousand words, it becomes increasingly difficult to learn "one-word-at-a-time" - in other words, it learning "how to speak Japanese" starts to have less ROI than learning things like "how to speak *about food* in Japanese". Words live in certain contexts - if one learns about triangles there's a good chance they're also learning about squares, circles, angles, etc, and all these bits of knowledge will be reinforcing each other in one's head. For our approach, despite the example sentence's objective of providing context to the word, it is ironically missing context itself, and is thus very liable to throw words at you from contexts that you're not familiar with and can't be reasonably expected to be learning at this time.

**(3) Logographic languages are particularly ill-suited to this approach.**

Both of the prior problems are magnified by the structure of Japanese, specifically the use of kanji. Because of their role as a semantic unit at a level lower than vocabulary, one fluent in Japanese can often guess the pronunciation and meaning of a word on first contact, and thus have a much easier time picking it up - which enables much larger vocabularies.  This is bad for us both in the obvious way (more words -> each word is less frequent -> more difficult to find examples for) and indirectly (each word in the sentence you do find will also be more infrequent on average).

### Next Steps (Eventually)

This project is paused. I have several ideas for how it could evolve, but they require a pivot from the current approach. The possibilities more or less organize themselves according to the skill level group that they would benefit:

- **For beginner learners,** Tansō is in principle useful, as the more common thousand or so words are common enough that we can be choosy and select particularly simple sentences straight from the Tatoeba corpus. Doing this properly presents a couple speedbumps;
    - Tansō is capable of taking into account sentence comprehensibility to the user, but this isn't particularly meaningful to a beginner learner where nothing is yet comprehensible - it would be useful then to strengthen Tansō's understanding of sentence *complexity* (i.e. how complicated is this vocabulary/syntax). Something like this is already present, but at a very rudimentary level.
    - Generally speaking it's not very reasonable to expect a beginner learner to be deciding which words to learn - rather they learn words from some premade source that gives them a core vocabulary to work with. Tansō would benefit from a way to integrate with this, e.g., being able to point it at a "core 1k" deck so that it goes through it and adds example sentences to every card therein. The way that this works would also make it very easy to export this deck in such a way that it can be used by anyone, including people who do not have Tansō installed.

    Both of these ideas seem like they will not present any major implementation challenges.

- **For advanced learners,** Tansō is probably already useful, the only pressing issue being how sentence length tends to explode for uncommon words. It should be possible, albeit this is a bit of a hard-to-grasp problem, to use some elementary NLP techniques to be able to chop down sentences into only the parts that are relevant to the word that we're trying to learn - for instance, chopping down this entire sentence to "It should be possible [...] to use some elementary NLP techniques."
- **For intermediate learners,** the three issues laid out in the last section are at their worst, which means that this is the area where the most significant pivot would be required - in particular, there should be a move towards enabling the learning of words in clusters - topic, discourse type, emotional context, etc. Addressing this would require endowing Tansō with some notion of semantic domains. There are a few avenues towards this: leveraging corpus metadata, building statistical associations based on co-ocurrence, ML-based embedding space clustering, etc. Implementing any of this would be non-trivial, requiring both infrastructure to (unsupervisedly) categorize vocabulary and sentences by topic and also a rethinking of the interface to allow the user to guide the tool towards specific areas of interest.

In working on Tansō, I ended up building something that’s effective for learners both ahead of and behind me in the process - but my own use case, the intermediate stage, surfaced the approach’s limitations. These limitations are in *my* way specifically and require significant rethinking to address, which is why this project is currently paused - nonetheless, I now have a much sharper view of what a better system could look like, such that there's a clear path ahead for if/when I return to it.