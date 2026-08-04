"""Извлечение именованных сущностей библиотекой Natasha.

Используется в воронке заявки: имя клиента, телефон, бюджет.
Если natasha не установлена — работают регулярные выражения.
"""
import re

from config import log

PHONE_RE = re.compile(r"(?:\+7|8)?[\s\-(]*\d{3}[\s\-)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}")
MONEY_RE = re.compile(r"\b(\d{3,6})\s*(?:р|руб|₽|рублей|рубля)?\b", re.IGNORECASE)

# служебные слова, которые не могут быть именем
STOP_WORDS = {"меня", "зовут", "имя", "это", "привет", "здравствуйте", "можно",
              "просто", "мое", "моё", "звать", "обращаться", "буду", "давайте",
              "добрый", "день", "спасибо", "хорошо"}

_natasha_ready = False
try:
    from natasha import (Doc, MorphVocab, NamesExtractor, NewsEmbedding,
                         NewsMorphTagger, NewsNERTagger, Segmenter)

    _segmenter = Segmenter()
    _morph_vocab = MorphVocab()
    _emb = NewsEmbedding()
    _morph_tagger = NewsMorphTagger(_emb)
    _ner_tagger = NewsNERTagger(_emb)
    _names_extractor = NamesExtractor(_morph_vocab)
    _natasha_ready = True
except Exception as exc:  # pragma: no cover
    log.warning("Natasha недоступна (%s) — сущности извлекаются регулярками", exc)


def extract_phone(text: str) -> str | None:
    match = PHONE_RE.search(text)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group())
    return digits if len(digits) >= 10 else None


def extract_budget(text: str) -> int | None:
    values = [int(m) for m in MONEY_RE.findall(text)]
    values = [v for v in values if 100 <= v <= 500_000]
    return max(values) if values else None


def extract_name(text: str) -> str | None:
    """Имя человека: сначала Natasha NER, потом простая эвристика."""
    if _natasha_ready:
        doc = Doc(text)
        doc.segment(_segmenter)
        doc.tag_morph(_morph_tagger)
        doc.tag_ner(_ner_tagger)
        for span in doc.spans:
            if span.type == "PER":
                span.normalize(_morph_vocab)
                span.extract_fact(_names_extractor)
                if span.fact and span.fact.as_dict.get("first"):
                    return span.fact.as_dict["first"].capitalize()
                return span.normal.split()[0].capitalize()

    candidates = [w for w in re.findall(r"[А-ЯЁ][а-яё]{2,}", text)
                  if w.lower() not in STOP_WORDS]
    if candidates:
        return candidates[0]
    words = [w for w in re.findall(r"[а-яё]{3,}", text.lower())
             if w not in STOP_WORDS]
    return words[0].capitalize() if len(words) == 1 else None


def extract_all(text: str) -> dict:
    return {"name": extract_name(text),
            "phone": extract_phone(text),
            "budget": extract_budget(text)}
