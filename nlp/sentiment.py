"""Анализ тональности по словарю с коэффициентами (шкала -1..+1).

Если рядом лежит data/emo_dict.csv из проекта kartaslov
(https://github.com/dkulagin/kartaslov -> dataset/emo_dict, ~28 тыс. слов),
используется он. Иначе — встроенный минимальный словарь.
"""
import csv

from config import EMO_DICT_PATH, log
from nlp.preprocess import lemmatize_word, preprocess

FALLBACK_DICT = {
    "люблю": 1.0, "нравится": 0.8, "отлично": 0.9, "супер": 0.9, "класс": 0.8,
    "хорошо": 0.6, "спасибо": 0.7, "рад": 0.7, "красивый": 0.6, "удобно": 0.5,
    "прекрасный": 0.9, "счастливый": 1.0, "интересно": 0.4,
    "плохо": -0.7, "ужасно": -0.9, "ненавижу": -1.0, "дорого": -0.4,
    "грустно": -0.6, "устал": -0.5, "бесит": -0.9, "сломался": -0.7,
    "разочарован": -0.8, "жаль": -0.4, "проблема": -0.5, "долго": -0.3,
}

NEGATIONS = {"не", "ни", "нет"}
INTENSIFIERS = {"очень": 1.4, "крайне": 1.5, "слишком": 1.3, "немного": 0.6}


class SentimentAnalyzer:
    def __init__(self):
        self.lexicon = dict(FALLBACK_DICT)
        self._load_kartaslov()

    def _load_kartaslov(self) -> None:
        if not EMO_DICT_PATH.exists():
            log.info("emo_dict.csv не найден — используется встроенный словарь тональности")
            return
        try:
            with open(EMO_DICT_PATH, encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=";")
                next(reader, None)  # заголовок
                for row in reader:
                    if len(row) < 3:
                        continue
                    word, tag, value = row[0].strip().lower(), row[1], row[2]
                    try:
                        score = float(value.replace(",", "."))
                    except ValueError:
                        continue
                    self.lexicon[word] = max(-1.0, min(1.0, score))
            log.info("Тональный словарь загружен: %d слов", len(self.lexicon))
        except Exception as exc:  # pragma: no cover
            log.warning("Не удалось прочитать emo_dict.csv: %s", exc)

    def score(self, text: str) -> float:
        tokens = preprocess(text)["corrected"].split()
        total, count, multiplier, negate = 0.0, 0, 1.0, False
        for token in tokens:
            if token in NEGATIONS:
                negate = True
                continue
            if token in INTENSIFIERS:
                multiplier = INTENSIFIERS[token]
                continue
            value = self.lexicon.get(token) or self.lexicon.get(lemmatize_word(token))
            if value is None:
                continue
            value *= multiplier
            if negate:
                value = -value
            total += value
            count += 1
            multiplier, negate = 1.0, False
        if not count:
            return 0.0
        return max(-1.0, min(1.0, total / count))

    def label(self, text: str) -> tuple[str, float]:
        value = self.score(text)
        if value > 0.25:
            return "положительная", value
        if value < -0.25:
            return "отрицательная", value
        return "нейтральная", value
