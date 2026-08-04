"""Очистка ввода, исправление опечаток и лемматизация."""
import re
from functools import lru_cache

from data.catalog import ROOM_KEYWORDS
from data.intents import intent_vocabulary

ALPHABET = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюя0123456789- ")

# Морфологический анализатор (pymorphy3). Если пакет не установлен —
# деградируем до простого стемминга, бот продолжает работать.
try:
    import pymorphy3

    _morph = pymorphy3.MorphAnalyzer()
except Exception:  # pragma: no cover
    _morph = None

_SUFFIXES = ("ами", "ями", "ого", "его", "ыми", "ими", "ов", "ев", "ам", "ям",
             "ах", "ях", "ой", "ий", "ый", "ая", "ое", "ые", "ие", "а", "я",
             "ы", "и", "у", "ю", "е", "о")


def clear_phrase(phrase: str) -> str:
    """Нижний регистр, удаление посторонних символов и лишних пробелов."""
    phrase = phrase.lower().replace("ё", "е")
    result = "".join(symbol for symbol in phrase if symbol in ALPHABET or symbol == "ё")
    return re.sub(r"\s+", " ", result).strip()


def levenshtein(a: str, b: str) -> int:
    """Расстояние Левенштейна (вставка/удаление/замена)."""
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1,        # удаление
                               current[j - 1] + 1,     # вставка
                               previous[j - 1] + (ca != cb)))  # замена
        previous = current
    return previous[-1]


def _build_vocabulary() -> set:
    vocab = set(intent_vocabulary())
    for synonyms in ROOM_KEYWORDS.values():
        vocab.update(w for w in synonyms if len(w) > 3)
    vocab.update({"светильник", "лампа", "торшер", "люстра", "подвесной", "потолочный",
                  "настенный", "настольная", "доставка", "гарантия", "скидка", "заказ",
                  "каталог", "цена", "наличие", "цоколь", "яркость", "монтаж"})
    return vocab


VOCABULARY = _build_vocabulary()


@lru_cache(maxsize=4096)
def correct_word(word: str) -> str:
    """Spell correction: ищем ближайшее слово словаря по Левенштейну."""
    # короткие слова не правим: «Иван» иначе превратится в «диван»
    if len(word) <= 4 or word in VOCABULARY:
        return word
    max_distance = 1 if len(word) <= 6 else 2
    best, best_distance = word, max_distance + 1
    for candidate in VOCABULARY:
        if abs(len(candidate) - len(word)) > max_distance:
            continue
        distance = levenshtein(word, candidate)
        if distance < best_distance:
            best, best_distance = candidate, distance
            if distance == 1:
                break
    return best if best_distance <= max_distance else word


def correct_phrase(phrase: str, protected: set[str] | None = None) -> str:
    protected = protected or set()
    return " ".join(w if w in protected else correct_word(w) for w in phrase.split())


def _capitalized_tokens(raw: str) -> set[str]:
    """Слова с заглавной буквы (кроме первого) считаем именами собственными."""
    words = re.findall(r"\w+", raw, flags=re.UNICODE)
    return {w.lower().replace("ё", "е") for w in words[1:] if w[:1].isupper()}


@lru_cache(maxsize=8192)
def lemmatize_word(word: str) -> str:
    """Приведение к начальной форме. Fallback — стемминг по окончаниям."""
    if _morph is not None:
        return _morph.parse(word)[0].normal_form
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def lemmatize(phrase: str) -> str:
    return " ".join(lemmatize_word(w) for w in phrase.split())


def preprocess(text: str) -> dict:
    """Полный конвейер: чистка -> опечатки -> лемматизация."""
    cleaned = clear_phrase(text)
    corrected = correct_phrase(cleaned, protected=_capitalized_tokens(text))
    lemmas = lemmatize(corrected)
    return {"raw": text, "cleaned": cleaned, "corrected": corrected,
            "lemmas": lemmas, "tokens": lemmas.split()}


def detect_room(text: str) -> str | None:
    """Определяет комнату для контекстной рекламы.

    Работает по очищенному тексту без spell correction, чтобы случайное
    исправление опечатки не выдумало комнату.
    """
    cleaned = clear_phrase(text)
    lemmas = set(lemmatize(cleaned).split())
    for room, keywords in ROOM_KEYWORDS.items():
        for keyword in keywords:
            if keyword in cleaned or lemmatize_word(keyword) in lemmas:
                return room
    return None
