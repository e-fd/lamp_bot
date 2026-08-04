"""Конфигурация проекта. Все секреты читаются из .env."""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

YANDEX_API_KEY = os.getenv("YANDEX_API_KEY", "")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID", "")
YANDEX_MODEL = os.getenv("YANDEX_MODEL", "yandexgpt-lite/latest")
# Разрешить модели писать художественное описание к товарам каталога
YANDEX_DESCRIPTIONS = os.getenv("YANDEX_DESCRIPTIONS", "false").lower() == "true"
YANDEX_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

# Прокси (опционально): нужен, если Telegram или Yandex Cloud недоступны напрямую
TELEGRAM_PROXY = os.getenv("TELEGRAM_PROXY", "") or None
YANDEX_PROXY = os.getenv("YANDEX_PROXY", "") or None

VOSK_MODEL_PATH = BASE_DIR / os.getenv("VOSK_MODEL_PATH", "models/vosk-model-small-ru-0.22")
DIALOGUES_PATH = BASE_DIR / os.getenv("DIALOGUES_PATH", "data/dialogues.txt")
DB_PATH = BASE_DIR / os.getenv("DB_PATH", "dialog_history.db")
EMO_DICT_PATH = BASE_DIR / "data" / "emo_dict.csv"  # kartaslov, необязателен

LOG_DIR = BASE_DIR / "logs"
TMP_DIR = BASE_DIR / "tmp"
LOG_DIR.mkdir(exist_ok=True)
TMP_DIR.mkdir(exist_ok=True)

# Периодическая реклама: каждые N реплик пользователя
AD_EVERY_N = int(os.getenv("AD_EVERY_N", "7"))

GREETING = (
    "Здравствуйте, я чат-бот компании Ламп.ру. Со мной можно просто поговорить, "
    "а если станет актуально, я помогу подобрать светильник для ваших нужд."
)


def setup_logging() -> logging.Logger:
    """Логи диалогов и заявок пишутся в logs/bot.log."""
    logger = logging.getLogger("lampbot")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")

    file_handler = RotatingFileHandler(
        LOG_DIR / "bot.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    logger.addHandler(stream)
    return logger


log = setup_logging()
