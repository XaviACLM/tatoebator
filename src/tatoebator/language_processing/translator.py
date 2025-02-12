import asyncio

from googletrans import Translator

# not really using this
# let's keep it commented unless we need to use it later
# b/c many people on the forum mention package issues when working with google packages within anki
# so we avoid unnecessary risk

# TODO - occasional "event loop is closed" error. Something to do with session length mb?

translator = Translator()


def translate(sentence):
    translation = asyncio.run(translator.translate(sentence, src='ja', dest='en'))
    return translation.text
