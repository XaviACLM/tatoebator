import atexit
from typing import List, Set, Dict, Optional

from sqlalchemy import create_engine, Column, Integer, SmallInteger, String, Text, ForeignKey, Index, func, Boolean, \
    case
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, joinedload

from ..constants import PATH_TO_DATABASE
from ..sentences import ExampleSentence

Base = declarative_base()


class Sentence(Base):
    __tablename__ = 'sentences'
    id = Column(Integer, primary_key=True)
    english = Column(Text, nullable=False)
    japanese = Column(Text, nullable=False, unique=True)  # Ensure uniqueness for Japanese sentence
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
        self._database_url = f'sqlite:///{PATH_TO_DATABASE}'
        self._engine = create_engine(self._database_url)
        Base.metadata.create_all(self._engine)
        atexit.register(self._engine.dispose)

        self._session_constructor = sessionmaker(bind=self._engine)
        self._session = None  # no real need to worry about this but cleaner this way

    def _open_session(self):
        self._session = self._session_constructor()

    def close_session(self):
        # careful, doesn't commit!!
        self._session.close()

    def check_sentence(self, sentence: str, commit=True):
        if self._session is None: self._open_session()
        existing = self._session.query(Sentence).filter_by(japanese=sentence).first()
        if commit: self._session.commit()
        return existing or None  # None if existing is falsey

    def count_n_sentences(self):
        if self._session is None: self._open_session()

        return self._session.query(func.count(Sentence.id)).scalar()

    def _insert_keywords(self, keywords: Set[str]) -> Dict[str, int]:
        keywords_in_database = {k.keyword: k for k in
                                self._session.query(Keyword).filter(Keyword.keyword.in_(keywords)).all()}
        keywords_to_insert = {k: Keyword(keyword=k, known=False) for k in keywords if k not in keywords_in_database}
        self._session.add_all(keywords_to_insert.values())
        self._session.flush()
        keywords_in_database.update(keywords_to_insert)
        return {k: keyword.id for k, keyword in keywords_in_database.items()}

    def insert_sentence(self, sentence, verify_not_repeated=True):
        if self._session is None: self._open_session()

        if verify_not_repeated:
            existing = self.check_sentence(sentence.sentence, commit=False)
            if existing is not None:
                raise Exception(f"Sentence already exists with ID {existing.id}.")

        # insert sentence
        new_sentence = self._row_from_example_sentence(sentence)
        self._session.add(new_sentence)
        self._session.flush()  # Flush to get the new sentence ID

        # insert keywords that aren't already present, get keyword -> db id map
        keyword_to_id = self._insert_keywords(set(sentence.lexical_words))

        # use sentence id and keyword id map to insert SentenceKeyword Pairs
        self._session.add_all([SentenceKeyword(sentence_id=new_sentence.id, keyword_id=keyword_to_id[lw])
                               for lw in sentence.lexical_words])
        self._session.flush()

        self._session.commit()

    def insert_sentences_batched(self, sentences, verify_not_repeated=True):
        if self._session is None: self._open_session()

        keyword_by_sentence = []
        keywords_to_insert = set()
        for sentence in sentences:

            if verify_not_repeated:
                existing = self.check_sentence(sentence.sentence, commit=False)
                if existing is not None:
                    raise Exception(f"Sentence already exists with ID {existing.id}.")

            new_sentence = self._row_from_example_sentence(sentence)
            self._session.add(new_sentence)
            self._session.flush()  # Flush to get ID for keywords

            keywords_to_insert.update(sentence.lexical_words)
            keyword_by_sentence.append((new_sentence.id, sentence.lexical_words))

        keyword_to_id = self._insert_keywords(keywords_to_insert)
        relations_to_insert = []
        for sentence_id, keywords in keyword_by_sentence:
            relations_to_insert.extend([SentenceKeyword(sentence_id=sentence_id,
                                                        keyword_id=keyword_to_id[keyword])
                                        for keyword in keywords])
        self._session.add_all(relations_to_insert)
        self._session.flush()
        self._session.commit()

    @classmethod
    def _row_from_example_sentence(cls, sentence: ExampleSentence):
        # careful, you can't just insert this as-is! use the insert function to also register lexical word relations
        return Sentence(
            english=sentence.translation,
            japanese=sentence.sentence,
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
                               audio_file_ref=None,
                               source_tag=row.source_tag,
                               trusted=row.trusted,
                               credit=row.credit,
                               # this might falsely lead one to believe a row has 0 known words when
                               # it is just not updated
                               # but then again, obviously the value not being updated can lead to the value being wrong
                               # so None -> 0 is okay
                               n_known_words=row.n_known_words or 0)

    def get_sentences_by_word(self, word: str, desired_amt: Optional[int] = None):
        """
        Retrieve sentences containing a certain word
        :param word: word to search for
        :param ensure_audio: if true, sentences with no audio_fileid will generate one
        :return: list of found sentences, as ExampleSentences
        """
        # todo update so it uses the proper order
        if self._session is None: self._open_session()

        results = (
            self._session.query(Sentence)
                .join(SentenceKeyword, Sentence.id == SentenceKeyword.sentence_id)
                .join(Keyword, SentenceKeyword.keyword_id == Keyword.id)
                .filter(Keyword.keyword == word)
                .limit(desired_amt)
                .options(joinedload(Sentence.keywords).joinedload(SentenceKeyword.keyword))  # retain keywords
                .all()
        )

        return list(map(SentenceDbInterface._row_to_example_sentence, results))

    def get_sentences_by_word_batched(self, word_desired_amts: Dict[str, int]):

        if self._session is None: self._open_session()

        words = list(word_desired_amts.keys())
        max_limit = max(word_desired_amts.values())

        ids_by_word_query = (
            self._session.query(Keyword.keyword,
                                SentenceKeyword.sentence_id,
                                func.row_number()
                                # order by comprehensibility, with a bonus for trusted (=passed extra checks) sentences
                                # which is more significant for shorter sentences
                                .over(partition_by=Keyword.keyword,
                                      order_by=(Sentence.n_unknown_words-2*Sentence.trusted)/Sentence.n_keywords)
                                .label("rn")
                                )
            .join(SentenceKeyword, SentenceKeyword.keyword_id == Keyword.id)
            .join(Sentence, SentenceKeyword.sentence_id == Sentence.id)
            .filter(Keyword.keyword.in_(words))
            .subquery()
        )

        results = (
            self._session.query(ids_by_word_query.c.keyword,
                                Sentence)
            .filter(ids_by_word_query.c.rn <= max_limit)
            .join(Sentence, Sentence.id == ids_by_word_query.c.sentence_id)
            .all()
        )

        # not 100% sqlalchemy optimizes away the joins
        # leaving this here for debug in case we have performance issues down the line
        # from sqlalchemy import text
        # explain_query = text("EXPLAIN " + str(results.statement.compile(compile_kwargs={"literal_binds": True})))
        # print("\n".join(map(str,self._session.execute(explain_query))))

        word_to_sentences = {word: [] for word in words}
        for word, sentence in results:
            word_to_sentences[word].append(sentence)

        for word in words:
            word_to_sentences[word] = word_to_sentences[word][:word_desired_amts[word]]
            word_to_sentences[word] = list(map(SentenceDbInterface._row_to_example_sentence, word_to_sentences[word]))

        return word_to_sentences

    def count_keywords(self, keywords):
        if self._session is None: self._open_session()
        result = (
            self._session.query(Keyword.keyword, func.count(Keyword.keyword))
                .filter(Keyword.keyword.in_(keywords))
                .join(SentenceKeyword, Keyword.id == SentenceKeyword.keyword_id)
                .group_by(Keyword.keyword)
                .all()
        )
        counts = {row[0]: row[1] for row in result}
        return {keyword: counts.get(keyword, 0) for keyword in keywords}

    def count_keywords_by_sentence_comprehensibility(self, keywords, min_comprehensibility):
        if self._session is None: self._open_session()
        result = (
            self._session.query(Keyword.keyword, func.count(Keyword.keyword))
                .filter(Keyword.keyword.in_(keywords))
                .join(SentenceKeyword, Keyword.id == SentenceKeyword.keyword_id)
                .join(Sentence, SentenceKeyword.sentence_id == Sentence.id)
                .filter((Sentence.n_known_words/Sentence.n_keywords)>=min_comprehensibility)
                .group_by(Keyword.keyword)
                .all()
        )
        counts = {row[0]: row[1] for row in result}
        return {keyword: counts.get(keyword, 0) for keyword in keywords}

    def update_known_unknown_counts(self):
        self._update_known_counts()
        self._update_unknown_counts()

    def _update_known_counts(self, reset_to_zero=False):
        if self._session is None:
            self._open_session()

        knowns_by_id = (
            self._session.query(
                SentenceKeyword.sentence_id,
                func.count(SentenceKeyword.id).label("count")
            )
                .join(Keyword, SentenceKeyword.keyword_id == Keyword.id)
                .filter(Keyword.known == True)
                .group_by(SentenceKeyword.sentence_id)
                .subquery()
        )

        self._session.query(Sentence).update(
            {
                Sentence.n_known_words: (
                    self._session.query(knowns_by_id.c.count)
                        .filter(Sentence.id == knowns_by_id.c.sentence_id)
                        .as_scalar()
                )
            },
            synchronize_session=False
        )

        self._session.commit()

    def _update_unknown_counts(self):
        if self._session is None:
            self._open_session()

        self._session.query(Sentence).update(
            {Sentence.n_unknown_words: Sentence.n_keywords - Sentence.n_known_words},
            synchronize_session=False
        )

        self._session.commit()

    def update_known_field(self, known_words):
        if self._session is None:
            self._open_session()
        existing_keywords = {kw[0] for kw in
                             self._session.query(Keyword.keyword).filter(Keyword.keyword.in_(known_words)).all()}
        new_keywords = [Keyword(keyword=word, known=True) for word in known_words if word not in existing_keywords]
        self._session.query(Keyword).filter(Keyword.keyword.in_(existing_keywords)).update({"known": True},
                                                                                           synchronize_session=False)

        # keywords that aren't in any sentence in the db are inserted anyway - this is important so we can calculate
        # comprehensibility for sentence search
        if new_keywords:
            self._session.add_all(new_keywords)

        self._session.commit()
        return
        if self._session is None:
            self._open_session()
        self._session.query(Keyword).filter(Keyword.keyword.in_(known_words)).update({"known": True},
                                                                                     synchronize_session=False)
        self._session.commit()

    def get_known_keywords_subset(self, keywords: List[str]):
        if self._session is None: self._open_session()
        result = (
            self._session.query(Keyword.keyword)
                .distinct(Keyword.keyword)
                .filter(Keyword.keyword.in_(keywords))
                .filter(Keyword.known)
                .all()
        )
        return result