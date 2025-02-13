import atexit
from typing import List, Set, Dict

from sqlalchemy import create_engine, Column, Integer, SmallInteger, String, Text, ForeignKey, Index, func, Boolean, \
    case, update
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, joinedload

from ..sentences import ExampleSentence
from ..constants import DATABASE_URL

Base = declarative_base()


class Sentence(Base):
    __tablename__ = 'sentences'
    id = Column(Integer, primary_key=True)
    english = Column(Text, nullable=False)
    japanese = Column(Text, nullable=False, unique=True)  # Ensure uniqueness for Japanese sentence
    audio_file_id = Column(String(32), nullable=True)
    source_tag = Column(SmallInteger, nullable=False)
    trusted = Column(Boolean, nullable=False)
    credit = Column(Text, nullable=True)

    # redundant but useful for querying
    n_keywords = Column(SmallInteger, nullable=True)  # Total words in the sentence
    n_known_words = Column(SmallInteger, nullable=True)  # Known words count
    n_unknown_words = Column(SmallInteger, nullable=True)  # Unknown words count (redundant, but useful)

    keywords = relationship("SentenceKeyword", back_populates="sentence")


class SentenceKeyword(Base):
    """Association table between sentences and keywords."""
    __tablename__ = 'sentence_keywords'
    id = Column(Integer, primary_key=True)
    sentence_id = Column(Integer, ForeignKey('sentences.id'), nullable=False, index=True)
    keyword_id = Column(Integer, ForeignKey('keywords.id'), nullable=False, index=True)

    sentence = relationship("Sentence", back_populates="keywords")
    keyword = relationship("Keyword")

    __table_args__ = (
        Index('idx_sentence_keyword_sentence_id', 'sentence_id'),
        Index('idx_sentence_keyword_keyword_id', 'keyword_id'),
        Index('idx_sentence_keyword_sentence_keyword', 'sentence_id', 'keyword_id'),  # For faster joins
    )


class Keyword(Base):
    """Stores unique keywords and whether they are known."""
    __tablename__ = 'keywords'
    id = Column(Integer, primary_key=True)
    keyword = Column(Text, unique=True, nullable=False)
    known = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index('idx_keywords_keyword', 'keyword'),
    )


class SentenceDbInterface:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(self.engine)
        atexit.register(self.engine.dispose)

        self.Session = sessionmaker(bind=self.engine)
        self.session = None  # do we really need to worry about this? keeping a single session should be fine...

    def _open_session(self):
        self.session = self.Session()

    def close_session(self):
        # careful, doesn't commit!!
        self.session.close()

    def check_sentence(self, sentence: str, commit=True):
        if self.session is None: self._open_session()
        existing = self.session.query(Sentence).filter_by(japanese=sentence).first()
        if commit: self.session.commit()
        return existing or None  # None if existing is falsey

    def _insert_keywords(self, keywords: Set[str]) -> Dict[str, int]:
        keywords_in_database = {k.keyword: k for k in
                                self.session.query(Keyword).filter(Keyword.keyword.in_(keywords)).all()}
        keywords_to_insert = {k: Keyword(keyword=k, known=False) for k in keywords if k not in keywords_in_database}
        self.session.add_all(keywords_to_insert.values())
        self.session.flush()
        keywords_in_database.update(keywords_to_insert)
        return {k: keyword.id for k, keyword in keywords_in_database.items()}

    def insert_sentence(self, sentence, verify_not_repeated=True):
        if self.session is None: self._open_session()

        if verify_not_repeated:
            existing = self.check_sentence(sentence.sentence, commit=False)
            if existing is not None:
                raise Exception(f"Sentence already exists with ID {existing.id}.")

        # insert sentence
        new_sentence = self._row_from_example_sentence(sentence)
        self.session.add(new_sentence)
        self.session.flush()  # Flush to get the new sentence ID

        # insert keywords that aren't already present, get keyword -> db id map
        keyword_to_id = self._insert_keywords(set(sentence.lexical_words))

        # use sentence id and keyword id map to insert SentenceKeyword Pairs
        self.session.add_all([SentenceKeyword(sentence_id=new_sentence.id, keyword_id=keyword_to_id[lw])
                              for lw in sentence.lexical_words])
        self.session.flush()

        self.session.commit()

    def insert_sentences_batched(self, sentences, verify_not_repeated=True):
        if self.session is None: self._open_session()

        keyword_by_sentence = []
        keywords_to_insert = set()
        for sentence in sentences:

            if verify_not_repeated:
                existing = self.check_sentence(sentence.sentence, commit=False)
                if existing is not None:
                    raise Exception(f"Sentence already exists with ID {existing.id}.")

            new_sentence = self._row_from_example_sentence(sentence)
            self.session.add(new_sentence)
            self.session.flush()  # Flush to get ID for keywords

            keywords_to_insert.update(sentence.lexical_words)
            keyword_by_sentence.append((new_sentence.id, sentence.lexical_words))

        keyword_to_id = self._insert_keywords(keywords_to_insert)
        relations_to_insert = []
        for sentence_id, keywords in keyword_by_sentence:
            relations_to_insert.extend([SentenceKeyword(sentence_id=sentence_id,
                                                        keyword_id=keyword_to_id[keyword])
                                        for keyword in keywords])
        self.session.add_all(relations_to_insert)
        self.session.flush()
        self.session.commit()

    @classmethod
    def _row_from_example_sentence(cls, sentence: ExampleSentence):
        # careful, you can't just insert this as-is! use the insert function to also register lexical word relations
        return Sentence(
            english=sentence.translation,
            japanese=sentence.sentence,
            audio_file_id=sentence.audio_fileid,
            source_tag=sentence.source_tag,
            trusted=sentence.trusted,
            credit=sentence.credit,
            n_keywords=sentence.n_lexical_words,
            n_known_words=sentence.n_known_words,
            n_unknown_words=sentence.n_unknown_words,
        )

    @staticmethod
    def _row_to_example_sentence(row):
        # this should come pre-joined with the required rows in Keyword
        # otherwise the bit to fill in lexical_words will require a db query
        # (one for every single sentence! this function isn't batched!!)
        return ExampleSentence(row.japanese,
                               translation=row.english,
                               lexical_words=[sk.keyword.keyword for sk in row.keywords],
                               audio_fileid=row.audio_file_id,
                               source_tag=row.source_tag,
                               trusted=row.trusted,
                               credit=row.credit,
                               # this might falsely lead one to believe a row has 0 known words when
                               # it is just not updated
                               # but then again, obviously the value not being updated can lead to the value being wrong
                               # so None -> 0 is okay
                               n_known_words=row.n_known_words or 0)

    def get_sentences_by_word(self, word, max_desired_amt: int = None):
        """
        Retrieve sentences containing a certain word
        :param word: word to search for
        :param ensure_audio: if true, sentences with no audio_fileid will generate one
        :return: list of found sentences, as ExampleSentences
        """
        if self.session is None: self._open_session()

        results = (
            self.session.query(Sentence)
                .join(SentenceKeyword, Sentence.id == SentenceKeyword.sentence_id)
                .join(Keyword, SentenceKeyword.keyword_id == Keyword.id)
                .filter(Keyword.keyword == word)
                .limit(max_desired_amt)
                .options(joinedload(Sentence.keywords).joinedload(SentenceKeyword.keyword))  # retain keywords
                .all()
        )

        return list(map(SentenceDbInterface._row_to_example_sentence, results))

    '''
    # unused
    def get_sentences_by_word_batched(self, words, ensure_audio=False):
        """
        Retrieve sentences grouped by keywords.
        :param ensure_audio:  if true, sentences with no audio_fileid will generate one
        :param words: List of keywords to search for.
        :return: Dictionary where each keyword maps to a list of sentences.
        """
        if self.session is None: self._open_session()
        results = (
            self.session.query(Keyword.keyword, Sentence)
            .join(Sentence, Keyword.sentence_id == Sentence.id)
            .filter(Keyword.keyword.in_(words))
            .all()
        )

        word_to_sentences = {word: [] for word in words}
        for word, sentence in results:
            word_to_sentences[word].append(sentence)

        for word in words:
            word_to_sentences[word] = list(map(SentenceDbInterface._row_to_example_sentence, word_to_sentences[word]))

        if ensure_audio:
            updated_sentences = []
            for sentence in itertools.chain(word_to_sentences.values()):
                if sentence.audio_fileid is None:
                    updated_sentences.append(sentence)
                    sentence.generate_audio()
            if updated_sentences:
                self._update_audio_file_ids(updated_sentences)

        return word_to_sentences
    '''

    def update_audio_file_ids(self, sentences: List[ExampleSentence]):
        """
        Updates the database with new audio_file_id values for sentences.
        :param sentences: List of ExampleSentence objects with updated audio_fileid.
        """
        if self.session is None:
            self._open_session()

        updates = {sentence.sentence: sentence.audio_fileid for sentence in sentences}
        self.session.query(Sentence).filter(Sentence.japanese.in_(updates.keys())).update(
            {"audio_file_id": case(updates, value=Sentence.japanese)},
            synchronize_session=False
        )

        self.session.commit()

    def count_keywords(self, keywords):
        if self.session is None: self._open_session()
        result = (
            self.session.query(Keyword.keyword, func.count(Keyword.keyword))
                .filter(Keyword.keyword.in_(keywords))
                .join(SentenceKeyword, Keyword.id == SentenceKeyword.keyword_id)
                .group_by(Keyword.keyword)
                .all()
        )
        counts = {row[0]: row[1] for row in result}
        return {keyword: counts.get(keyword, 0) for keyword in keywords}

    def count_keywords_by_sentence_comprehensibility(self, keywords, min_comprehensibility):
        if self.session is None: self._open_session()
        result = (
            self.session.query(Keyword.keyword, func.count(Keyword.keyword))
                .filter(Keyword.keyword.in_(keywords))
                .join(SentenceKeyword, Keyword.id == SentenceKeyword.keyword_id)
                .join(Sentence, SentenceKeyword.sentence_id == Sentence.id)
                .filter((Sentence.n_known_words/Sentence.n_keywords)>=min_comprehensibility)
                .group_by(Keyword.keyword)
                .all()
        )
        counts = {row[0]: row[1] for row in result}
        return {keyword: counts.get(keyword, 0) for keyword in keywords}

    def get_all_audio_ids(self) -> Set[str]:
        if self.session is None:
            self._open_session()

        referenced_audio_ids = set(
            row[0] for row in
            self.session.query(Sentence.audio_file_id).filter(Sentence.audio_file_id.isnot(None)).all()
        )

        return referenced_audio_ids

    def update_known_unknown_counts(self):
        self._update_known_counts()
        self._update_unknown_counts()

    def _update_known_counts(self, reset_to_zero=False):
        if self.session is None:
            self._open_session()

        knowns_by_id = (
            self.session.query(
                SentenceKeyword.sentence_id,
                func.count(SentenceKeyword.id).label("count")
            )
                .join(Keyword, SentenceKeyword.keyword_id == Keyword.id)
                .filter(Keyword.known == True)
                .group_by(SentenceKeyword.sentence_id)
                .subquery()
        )

        self.session.query(Sentence).update(
            {
                Sentence.n_known_words: (
                    self.session.query(knowns_by_id.c.count)
                        .filter(Sentence.id == knowns_by_id.c.sentence_id)
                        .as_scalar()
                )
            },
            synchronize_session=False
        )

        self.session.commit()

    def _update_unknown_counts(self):
        if self.session is None:
            self._open_session()

        self.session.query(Sentence).update(
            {Sentence.n_unknown_words: Sentence.n_keywords - Sentence.n_known_words},
            synchronize_session=False
        )

        self.session.commit()

    def update_known_field(self, known_words):
        if self.session is None:
            self._open_session()
        self.session.query(Keyword).filter(Keyword.keyword.in_(known_words)).update({"known": True},
                                                                                    synchronize_session=False)
        self.session.commit()
