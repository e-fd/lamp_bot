"""Генеративный слой на датасете диалогов dialogues.txt.

Датасет «сырой»: диалоги разделены пустой строкой, реплики начинаются
с маркера '- '. Берём только первые две строки (вопрос — ответ),
чистим повторы и строим индекс по словам.
"""
from config import DIALOGUES_PATH, log
from nlp.preprocess import clear_phrase, levenshtein

MAX_PAIRS_PER_WORD = 1000
LENGTH_TOLERANCE = 0.2
DISTANCE_TOLERANCE = 0.2


class DialoguesEngine:
    def __init__(self, path=DIALOGUES_PATH):
        self.path = path
        self.index: dict[str, list] = {}
        self.loaded = False

    def load(self) -> None:
        if not self.path.exists():
            log.warning("Датасет диалогов не найден: %s — слой отключён", self.path)
            return

        with open(self.path, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        dialogues_str = content.split("\n\n")
        dialogues = [d.split("\n")[:2] for d in dialogues_str]

        filtered, questions = [], set()
        for dialogue in dialogues:
            if len(dialogue) != 2:
                continue
            question, answer = dialogue
            question = clear_phrase(question[2:])
            answer = answer[2:].strip()
            if question and answer and question not in questions:
                questions.add(question)
                filtered.append([question, answer])

        structured: dict[str, list] = {}
        for question, answer in filtered:
            for word in set(question.split(" ")):
                structured.setdefault(word, []).append([question, answer])

        for word, pairs in structured.items():
            pairs.sort(key=lambda pair: len(pair[0]))
            self.index[word] = pairs[:MAX_PAIRS_PER_WORD]

        self.loaded = True
        log.info("Датасет диалогов загружен: %d пар, %d ключей",
                 len(filtered), len(self.index))

    def generate(self, replica: str) -> str | None:
        if not self.loaded:
            return None
        replica = clear_phrase(replica)
        if not replica:
            return None

        mini_dataset, seen = [], set()
        for word in set(replica.split(" ")):
            for pair in self.index.get(word, []):
                key = pair[0]
                if key not in seen:          # убираем повторы
                    seen.add(key)
                    mini_dataset.append(pair)

        answers = []  # [[distance_weighted, question, answer]]
        for question, answer in mini_dataset:
            if not question:
                continue
            if abs(len(replica) - len(question)) / len(question) < LENGTH_TOLERANCE:
                distance = levenshtein(replica, question)
                distance_weighted = distance / len(question)
                if distance_weighted < DISTANCE_TOLERANCE:
                    answers.append([distance_weighted, question, answer])

        if answers:
            return min(answers, key=lambda three: three[0])[2]
        return None
