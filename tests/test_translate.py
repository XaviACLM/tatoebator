import asyncio
import time

from tatoebator.external_download_requester import ExternalDownloadRequester
from tatoebator.language_processing.translator import Translator
from tatoebator.sentences.sentence_production import JParaCrawlASPM

# investigating the speed boost of using async w googletrans
text = []
c = 0
for sentence in JParaCrawlASPM(ExternalDownloadRequester()).yield_sentences(start_at=3010):
    text.append(sentence.sentence)
    c+=1
    if c==10:
        break

translator = Translator()

async def translation_yielder(sentences):
    pending_tasks = set()
    queue = asyncio.Queue()

    async def do_thing(sentence):
        tl = await translator.async_jp_to_eng(sentence)
        await queue.put(tl)

    for sentence in sentences:
        task = asyncio.create_task(do_thing(sentence))
        pending_tasks.add(task)
        task.add_done_callback(pending_tasks.discard)

        while not queue.empty():
            yield await queue.get()
    await asyncio.gather(*pending_tasks)
    while not queue.empty():
        yield await queue.get()

def translation_yielder_normal(sentences):
    for sentence in sentences:
        yield translator.jp_to_eng(sentence)

async def main():
    async for sentence in translation_yielder(text):
        print(sentence)

def main_normal():
    for sentence in translation_yielder_normal(text):
        print(sentence)

then = time.time()
# main_normal()
asyncio.run(main())
now = time.time()
print(now-then)

#1.9 vs 18 at 10 TLs async vs sync
#2.9 vs maybe 300 at 100 TLs
#good stuff, good stuff. both of those were w instantiating the translator object at each call

#let's try not doing that, see if we can get it to work

# no point in using bulk ('advanced') translation: it just does a different call for each string passed
# might be use in trying to do our own shitty bulk translation:
# instead of tl(a), tl(b), rather tl(a+"\n"+b).split("\n")
# will be finnicky so need to redo the TLs if the amount of newlines turns out incorrect
# context will affect translations but that's an acceptable tradeoff if we can style on the rate limit
# the issue is this significantly complicates the TL interface

# TODO moreover the TL object should have an estimation of the number of requests left before it hits the rate limit
# this should come up in the gui (when you press a button that might run up against it)
# so the TL object will have to exis all the way at Tatoebator and be passed down all the way to QL. jeesh
# probably make more sense to do dependency insertion here:
# one tatoebator -> one conductor -> one wordtable -> one repository -> one spmanager -> one quality controller