import asyncio

from googletrans import Translator as GoogleTranslator


class Translator:

    # used to fail when we used the same translator object for different requests
    # seems not to happen anymore but we keep raise_exception=True to investigate - when we learn something about
    # exceptions we will be able to handle them... retrying a couple times, re-instantiating the TL object maybe

    # also have to experiment with how much leeway we have before hitting the rate limit
    # try w sync v async and long v short sentences. eng -> so entropy per character remains stable
    # i'm assuming the rate limit will be linear in these 4 vars, so if we know them we can endow this class w
    # the capacity to estimate how many requests it has left - so it can warn the gui if relevant

    def __init__(self):
        self._google_translator = GoogleTranslator(raise_exception=True)

    # sync methods just instantiate a new translator to avoid having to worry abt the event loop
    def jp_to_eng(self, text: str):
        translation = asyncio.run(GoogleTranslator(raise_exception=True).translate(text, src='ja', dest='en'))
        return translation.text

    def eng_to_jp(self, text: str):
        translation = asyncio.run(GoogleTranslator(raise_exception=True).translate(text, src='en', dest='ja'))
        return translation.text

    async def async_jp_to_eng(self, text: str):
        translation = await self._google_translator.translate(text, src='ja', dest='en')
        return translation.text

    async def async_eng_to_jp(self, text: str):
        translation = await self._google_translator.translate(text, src='en', dest='ja')
        return translation.text
