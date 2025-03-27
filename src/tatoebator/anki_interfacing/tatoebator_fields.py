class TatoebatorFields:
    WORD = "word"
    WORD_AUDIO = "word_audio"
    WORD_FURIGANA = "word_furigana"
    DEFINITION_EN = "definition_en"
    DEFINITION_JP = "definition_jp"
    SENTENCE_DATA = "sentence_data"
    ALL_DEFINITIONS = "_all_definitions"
    OTHER_DATA = "_other_data"

    all = [WORD, WORD_AUDIO, WORD_FURIGANA, DEFINITION_EN, DEFINITION_JP, SENTENCE_DATA, ALL_DEFINITIONS, OTHER_DATA]

    @classmethod
    def index(cls, field_name: str) -> int:
        return cls.all.index(field_name)
