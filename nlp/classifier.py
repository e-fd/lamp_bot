"""Классификация намерений: TF-IDF (символьные 3-граммы) + LinearSVC."""
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import cross_val_score
from sklearn.svm import LinearSVC

from config import log
from data.intents import BOT_CONFIG, build_dataset
from nlp.preprocess import clear_phrase, levenshtein, preprocess

# Порог уверенности: ниже него интент считаем unknown и уходим в фолбэк
DECISION_THRESHOLD = 0.18


class IntentClassifier:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
        self.clf = LinearSVC(C=1.0)
        self._fitted = False

    def fit(self) -> None:
        x_text, y = build_dataset()
        x_text = [clear_phrase(t) for t in x_text]
        x = self.vectorizer.fit_transform(x_text)
        self.clf.fit(x, y)
        self._fitted = True
        try:
            scores = cross_val_score(LinearSVC(C=1.0), x, y, cv=3)
            log.info("Классификатор обучен: %d примеров, %d классов, CV=%.2f",
                     len(y), len(set(y)), scores.mean())
        except Exception:
            log.info("Классификатор обучен: %d примеров, %d классов", len(y), len(set(y)))

    def predict(self, replica: str) -> tuple[str | None, float]:
        """Возвращает (intent, confidence). Пустой интент -> unknown."""
        if not self._fitted:
            self.fit()
        cleaned = preprocess(replica)["corrected"]
        if not cleaned:
            return None, 0.0

        vector = self.vectorizer.transform([cleaned])
        margins = self.clf.decision_function(vector)[0]
        best_index = int(np.argmax(margins))
        intent = self.clf.classes_[best_index]
        # нормируем отрыв лидера от второго места
        ordered = np.sort(margins)[::-1]
        confidence = float(ordered[0] - ordered[1]) if len(ordered) > 1 else 1.0

        if confidence < DECISION_THRESHOLD and not self._close_to_example(cleaned, intent):
            return None, confidence
        return intent, confidence

    @staticmethod
    def _close_to_example(replica: str, intent: str) -> bool:
        """Страховка расстоянием Левенштейна, как в методичке."""
        for example in BOT_CONFIG["intents"][intent]["examples"]:
            example = clear_phrase(example)
            if example and levenshtein(replica, example) / len(example) <= 0.4:
                return True
        return False
