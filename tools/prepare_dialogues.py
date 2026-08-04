"""Подготовка «сырого» dialogues.txt: длинные диалоги режем до пары
вопрос-ответ, повторяющиеся вопросы убираем.

Запуск:  python -m tools.prepare_dialogues data/dialogues_raw.txt data/dialogues.txt
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nlp.preprocess import clear_phrase  # noqa: E402


def prepare(src: Path, dst: Path) -> None:
    content = src.read_text(encoding="utf-8", errors="ignore")
    blocks = content.split("\n\n")

    seen, pairs = set(), []
    for block in blocks:
        lines = block.split("\n")[:2]
        if len(lines) != 2:
            continue
        question, answer = lines[0][2:], lines[1][2:]
        key = clear_phrase(question)
        if not key or not answer.strip() or key in seen:
            continue
        seen.add(key)
        pairs.append((question.strip(), answer.strip()))

    with open(dst, "w", encoding="utf-8") as f:
        for question, answer in pairs:
            f.write(f"- {question}\n- {answer}\n\n")

    print(f"Готово: {len(blocks)} блоков -> {len(pairs)} уникальных пар -> {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    prepare(Path(sys.argv[1]), Path(sys.argv[2]))
