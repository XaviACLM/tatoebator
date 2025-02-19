import asyncio

from googletrans import Translator as GoogleTranslator


class Translator:

    # used to fail when we used the same translator object for different requests
    # seems not to happen anymore but we keep raise_exception=True to investigate - when we learn something about
    # exceptions we will be able to handle them... retrying a couple times, re-instantiating the TL object maybe

    def __init__(self):
        self.translator = GoogleTranslator(raise_exception=True)

    def jp_to_eng(self, text: str):
        print("REAL TR REQUEST!!!!!")
        translation = asyncio.run(self.translator.translate(text, src='ja', dest='en'))
        return translation.text

    def eng_to_jp(self, text: str):
        print("REAL TR REQUEST!!!!!")
        translation = asyncio.run(self.translator.translate(text, src='en', dest='ja'))
        return translation.text

    async def async_jp_to_eng(self, text: str):
        print("REAL TR REQUEST!!!!!")
        translation = await self.translator.translate(text, src='ja', dest='en')
        return translation.text

    async def async_eng_to_jp(self, text: str):
        print("REAL TR REQUEST!!!!!")
        translation = await self.translator.translate(text, src='en', dest='ja')
        return translation.text

    async def async_eng_to_jp(self, text: str):
        print("fake tr request")
        await asyncio.sleep(1)
        return "Oh man look at this fake translation. This isn't even japanese lol. Have a couple hanzi 私貴方"
