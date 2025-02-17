import asyncio

from googletrans import Translator as GoogleTranslator


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
