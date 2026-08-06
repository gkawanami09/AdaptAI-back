from functools import lru_cache

import spacy
from spacy.language import Language


@lru_cache(maxsize=1)
def carregar_pipeline() -> Language:
    return spacy.load("pt_core_news_md")
