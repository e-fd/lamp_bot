"""Диалоговое ядро: связывает NLU, FAQ, датасет диалогов, Yandex AI и рекламу."""
import random
from dataclasses import dataclass, field

from bot.ads import AdEngine
from config import log
from data.catalog import (CATALOG, CATALOG_BY_ID, format_catalog, format_item,
                          item_card, item_photos)
from data.intents import BOT_CONFIG
from nlp.classifier import IntentClassifier
from nlp.dialogues import DialoguesEngine
from nlp.entities import extract_name, extract_phone
from nlp.preprocess import detect_room, preprocess
from nlp.sentiment import SentimentAnalyzer
from services.db import Storage
from services.yandex import YandexAI

FAREWELL_WORDS = {"пока", "до свидания", "прощай", "досвидания", "бай", "до встречи"}
CANCEL_WORDS = {"отмена", "отменить", "отмени", "не надо", "передумал", "стоп"}


@dataclass
class Reply:
    """Ответ бота: текст, фотографии товара и признак конца диалога."""
    text: str
    images: list = field(default_factory=list)
    finished: bool = False


@dataclass
class UserState:
    theme: str = "*"                 # текущая тема диалога
    funnel: str = "idle"             # idle | wait_name | wait_phone
    order_name: str | None = None
    order_product: str | None = None
    last_item: str | None = None     # id товара, о котором шла речь
    last_room: str | None = None
    interested: list = field(default_factory=list)


class ChatBot:
    def __init__(self):
        self.classifier = IntentClassifier()
        self.classifier.fit()
        self.dialogues = DialoguesEngine()
        self.dialogues.load()
        self.sentiment = SentimentAnalyzer()
        self.yandex = YandexAI()
        self.ads = AdEngine()
        self.storage = Storage()
        self.states: dict[int, UserState] = {}
        self.stats = {"intent": 0, "generate": 0, "yandex": 0, "failure": 0, "ad": 0}
        self._pending_images: list = []

    def state(self, user_id: int) -> UserState:
        return self.states.setdefault(user_id, UserState())

    # ------------------------------------------------------------------
    async def respond(self, user_id: int, replica: str) -> Reply:
        """Главная точка входа: возвращает Reply(text, images, finished)."""
        state = self.state(user_id)
        processed = preprocess(replica)
        tone_label, tone_value = self.sentiment.label(replica)
        self._pending_images = []          # заполняется в _answer_by_intent

        # 1. Воронка заявки имеет приоритет над всем остальным
        if state.funnel != "idle":
            answer = self._handle_funnel(user_id, replica, state)
            self._log_turn(user_id, replica, answer, "order_funnel", tone_value)
            return Reply(answer)

        # 2. NLU
        intent, confidence = self.classifier.predict(replica)

        # 3. Прощание — завершаем диалог
        if intent == "bye" or processed["cleaned"] in FAREWELL_WORDS:
            answer = random.choice(BOT_CONFIG["intents"]["bye"]["responses"])
            self.ads.reset(user_id)
            self.states.pop(user_id, None)
            self._log_turn(user_id, replica, answer, "bye", tone_value)
            return Reply(answer, finished=True)

        # 4. Заготовленный ответ по интенту
        answer = None
        if intent:
            answer = await self._answer_by_intent(user_id, intent, replica, state)
            if answer:
                self.stats["intent"] += 1

        # 4a. Карточка товара уже содержит фото — реклама сверху не нужна
        if self._pending_images:
            self._log_turn(user_id, replica, answer, intent or "item_info", tone_value)
            return Reply(answer, images=self._pending_images)

        # 5. Контекстная реклама: пользователь упомянул комнату
        room = detect_room(replica)
        if room and room != state.last_room:
            state.last_room = room
            offer = self.ads.room_offer(user_id, room)
            answer = f"{answer}\n\n{offer}" if answer else offer
            self._log_turn(user_id, replica, answer, intent or "room_ad", tone_value)
            return Reply(answer)

        # 6. Датасет диалогов
        if not answer:
            answer = self.dialogues.generate(replica)
            if answer:
                self.stats["generate"] += 1

        # 7. Yandex AI — только свободный диалог, без фактов о товарах
        if not answer:
            history = self.storage.history(user_id, limit=6)
            answer = await self.yandex.ask(replica, history)
            if answer:
                self.stats["yandex"] += 1

        # 8. Заглушка + мягкая подстройка под тональность
        if not answer:
            self.stats["failure"] += 1
            answer = random.choice(BOT_CONFIG["failure_phrases"])
            if tone_label == "отрицательная":
                answer = "Похоже, настроение не очень. " + answer

        # 9. Периодическая реклама — каждые N реплик
        ad = self.ads.tick(user_id)
        if ad:
            self.stats["ad"] += 1
            answer = f"{answer}\n\n{ad}"

        self._log_turn(user_id, replica, answer, intent or "unknown", tone_value)
        return Reply(answer)

    # ------------------------------------------------------------------
    async def _answer_by_intent(self, user_id: int, intent: str,
                                replica: str, state: UserState) -> str | None:
        data = BOT_CONFIG["intents"].get(intent)
        if not data:
            return None

        # проверка применимости интента к текущей теме
        applicable = data.get("theme_app", ["*"])
        if "*" not in applicable and state.theme not in applicable:
            return None

        response = random.choice(data["responses"])
        state.theme = data.get("theme_gen", state.theme)

        if response == "__CATALOG__":
            self.ads.reset(user_id)
            return format_catalog()

        if response == "__ROOM__":
            room = detect_room(replica)
            if room:
                state.last_room = room
                return self.ads.room_offer(user_id, room)
            return ("Для какой комнаты подбираем? Кухня, гостиная, спальня, "
                    "детская, кабинет или прихожая?")

        if response == "__ITEM__":
            item = self._find_item(replica) or self._last_item(state)
            if not item:
                return ("О каком светильнике рассказать? Могу показать любой "
                        "из каталога — /catalog.")
            state.last_item = item["id"]
            state.order_product = item["name"]
            self._pending_images = item_photos(item)
            description = await self.yandex.describe_item(item)
            return item_card(item, description)

        if response == "__STOCK__":
            lines = [f"• {i['name']}: {i['stock']} шт." for i in CATALOG]
            return "Остатки на складе:\n" + "\n".join(lines)

        if response == "__ORDER__":
            state.funnel = "wait_name"
            state.order_product = state.order_product or self._guess_product(replica)
            product = state.order_product or "подбор по каталогу"
            return (f"Отлично, оформляем: {product}.\n"
                    "Как к вам обращаться?")
        return response

    def _find_item(self, replica: str) -> dict | None:
        """Ищет товар по названию, бренду, модели или типу светильника."""
        tokens = set(preprocess(replica)["tokens"]) | set(preprocess(replica)["corrected"].split())
        best, best_score = None, 0
        for item in CATALOG:
            haystack = f"{item['name']} {item['type']}"
            keys = set(preprocess(haystack)["tokens"])
            keys |= {w.lower() for w in haystack.split() if len(w) > 2}
            score = len(tokens & keys)
            if score > best_score:
                best, best_score = item, score
        return best if best_score else None

    def _last_item(self, state: UserState) -> dict | None:
        return CATALOG_BY_ID.get(state.last_item) if state.last_item else None

    def _guess_product(self, replica: str) -> str | None:
        tokens = set(preprocess(replica)["tokens"])
        for item in CATALOG:
            keys = preprocess(item["name"] + " " + item["type"])["tokens"]
            if tokens & set(keys):
                return item["name"]
        return None

    def _handle_funnel(self, user_id: int, replica: str, state: UserState) -> str:
        if preprocess(replica)["cleaned"] in CANCEL_WORDS:
            state.funnel = "idle"
            state.order_product = None
            state.theme = "*"
            return "Хорошо, заявку отменил. Если передумаете — скажите «хочу заказать»."

        if state.funnel == "wait_name":
            name = extract_name(replica) or replica.strip()[:40]
            state.order_name = name
            state.funnel = "wait_phone"
            return (f"Приятно познакомиться, {name}! "
                    "Оставьте телефон — менеджер перезвонит и подтвердит наличие.")

        if state.funnel == "wait_phone":
            phone = extract_phone(replica)
            if not phone:
                return ("Не разобрал номер. Напишите в формате +7 999 123-45-67, "
                        "пожалуйста, или скажите «отмена».")
            product = state.order_product or "подбор по каталогу"
            order_id = self.storage.save_order(user_id, state.order_name or "—",
                                               phone, product)
            state.funnel = "idle"
            state.theme = "*"
            return (f"Заявка №{order_id} принята: {product}.\n"
                    f"Перезвоним на {self._pretty_phone(phone)} в рабочее время. Спасибо!")
        state.funnel = "idle"
        return "Продолжим?"

    @staticmethod
    def _pretty_phone(digits: str) -> str:
        tail = digits[-10:]
        return f"+7 {tail[:3]} {tail[3:6]}-{tail[6:8]}-{tail[8:]}"

    # ------------------------------------------------------------------
    def _log_turn(self, user_id: int, replica: str, answer: str,
                  intent: str, tone: float) -> None:
        self.storage.save_message(user_id, "user", replica, intent, tone)
        self.storage.save_message(user_id, "bot", answer)
        log.info("user=%s | intent=%s | tone=%.2f | in=%r | out=%r | stats=%s",
                 user_id, intent, tone, replica[:80], answer[:80], self.stats)

    def catalog_text(self) -> str:
        return format_catalog()

    def item_card(self, index: int) -> str:
        return format_item(CATALOG[index % len(CATALOG)])
