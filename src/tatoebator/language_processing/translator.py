import asyncio

from googletrans import Translator as GoogleTranslator

# not really using this
# let's keep it commented unless we need to use it later
# b/c many people on the forum mention package issues when working with google packages within anki
# so we avoid unnecessary risk

# TODO - occasional "event loop is closed" error. Something to do with session length mb?




def translate(sentence):
    translator = GoogleTranslator()
    translation = asyncio.run(translator.translate(sentence, src='ja', dest='en'))
    return translation.text



class Translator:

    @staticmethod
    def jp_to_eng(text: str):
        translator = GoogleTranslator()
        translation = asyncio.run(translator.translate(text, src='ja', dest='en'))
        return translation.text

    @staticmethod
    def eng_to_jp(text: str):
        translator = GoogleTranslator()
        translation = asyncio.run(translator.translate(text, src='en', dest='ja'))
        return translation.text
