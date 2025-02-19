import asyncio

from googletrans import Translator as GoogleTranslator


class Translator:

    # used to fail when we used the same translator object for different requests
    # seems not to happen anymore but we keep raise_exception=True to investigate - when we learn something about
    # exceptions we will be able to handle them... retrying a couple times, re-instantiating the TL object maybe

    def __init__(self):
        self.translator = GoogleTranslator(raise_exception=True)

    def jp_to_eng(self, text: str):
        translation = asyncio.run(self.translator.translate(text, src='ja', dest='en'))
        return translation.text

    def eng_to_jp(self, text: str):
        translation = asyncio.run(self.translator.translate(text, src='en', dest='ja'))
        return translation.text

    async def async_jp_to_eng(self, text: str):
        translation = await self.translator.translate(text, src='ja', dest='en')
        return translation.text

    async def async_eng_to_jp(self, text: str):
        translation = await self.translator.translate(text, src='en', dest='ja')
        return translation.text

    c=0

    async def async_eng_to_jp(self, text: str):
        self.c += 1
        #print("fake tr request",self.c)
        #print("\t"+text.replace("\n","\n\t"))
        await asyncio.sleep(1)
        n = text.count("\n")
        from random import randint
        if randint(0,2)==0:
            return "Oh man look at this fake translation. This isn't even japanese lol. Have a couple hanzi 私貴方"
        else:
            return "\n".join(["私貴方"]*(n+1))
