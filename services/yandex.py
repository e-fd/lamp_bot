"""Yandex AI Studio (Foundation Models) — фолбэк для свободного диалога.

Важно: модель НИКОГДА не используется для фактов о светильниках,
ценах, наличии и условиях доставки — это зона каталога и FAQ.
Если ключа нет, класс просто возвращает None и бот работает офлайн.
"""
import asyncio

from config import (YANDEX_API_KEY, YANDEX_DESCRIPTIONS, YANDEX_FOLDER_ID,
                    YANDEX_MODEL, YANDEX_PROXY, YANDEX_URL, log)

try:
    import aiohttp
except ImportError:  # pragma: no cover
    aiohttp = None

SYSTEM_PROMPT = (
    "Ты — дружелюбный собеседник в чате магазина светильников «Ламп.ру». "
    "Отвечай коротко (1–2 предложения), живо и на русском языке. "
    "СТРОГИЙ ЗАПРЕТ: не придумывай названия товаров, цены, характеристики, "
    "наличие, сроки доставки и условия гарантии. Если спрашивают о товарах — "
    "ответь, что сейчас покажешь каталог, и ничего не выдумывай."
)


# Промпт для описаний товаров: модель работает ТОЛЬКО с переданными фактами.
DESCRIBE_PROMPT = (
    "Ты копирайтер магазина светильников. Тебе дают карточку товара. "
    "Напиши 2–3 предложения о том, как этот светильник ощущается в интерьере "
    "и для каких сценариев освещения подходит. "
    "СТРОГО ЗАПРЕЩЕНО: называть цену, наличие, сроки доставки, гарантию, "
    "любые числа, а также характеристики, которых нет в карточке. "
    "Не придумывай новые модели и не сравнивай с товарами других магазинов. "
    "Только текст описания, без заголовков."
)

# Если описание содержит что-то из этого — оно отбрасывается целиком
FORBIDDEN = ("руб", "₽", "цен", "стои", "скидк", "доставк", "гарант",
             "налич", "склад", "заказ", "оплат", "акци")


class YandexAI:
    def __init__(self):
        self.enabled = bool(YANDEX_API_KEY and YANDEX_FOLDER_ID and aiohttp)
        self._descriptions: dict[str, str] = {}   # кэш описаний по id товара
        if not self.enabled:
            log.info("Yandex AI не настроен — работаем на ML-модели, FAQ и диалогах")

    async def describe_item(self, item: dict) -> str | None:
        """Художественное описание товара строго по фактам из каталога.

        Важно: у Foundation Models нет доступа в интернет — модель не «ищет»
        характеристики, а только переформулирует то, что ей передали.
        Поэтому на вход идёт карточка из data/catalog.py, а результат
        проходит фильтр FORBIDDEN. Выключено по умолчанию.
        """
        if not (self.enabled and YANDEX_DESCRIPTIONS):
            return None
        if item["id"] in self._descriptions:
            return self._descriptions[item["id"]]

        card = (f"Название: {item['name']}\n"
                f"Тип: {item['type']}\n"
                f"Характеристики: {item['specs']}\n"
                f"Комнаты: {', '.join(item['rooms'])}")
        text = await self._complete(DESCRIBE_PROMPT, card, temperature=0.4)

        if text and self._is_safe(text):
            self._descriptions[item["id"]] = text
            return text
        if text:
            log.warning("Описание для %s отклонено фильтром: %r", item["id"], text[:120])
        return None

    @staticmethod
    def _is_safe(text: str) -> bool:
        """Отсекаем выдуманные цифры и коммерческие условия."""
        lowered = text.lower()
        if any(ch.isdigit() for ch in lowered):
            return False
        return not any(word in lowered for word in FORBIDDEN)

    async def ask(self, replica: str, history: list[tuple[str, str]] | None = None,
                  timeout: float = 8.0) -> str | None:
        if not self.enabled:
            return None

        messages = [{"role": "system", "text": SYSTEM_PROMPT}]
        for role, text in (history or [])[-6:]:
            messages.append({"role": "assistant" if role == "bot" else "user",
                             "text": text})
        messages.append({"role": "user", "text": replica})

        return await self._request(messages, temperature=0.6, timeout=timeout)

    async def _complete(self, system_prompt: str, user_text: str,
                        temperature: float = 0.6) -> str | None:
        """Одиночный запрос без истории — для служебных задач вроде описаний."""
        return await self._request(
            [{"role": "system", "text": system_prompt},
             {"role": "user", "text": user_text}],
            temperature=temperature,
        )

    async def _request(self, messages: list, temperature: float = 0.6,
                       timeout: float = 8.0) -> str | None:
        payload = {
            "modelUri": f"gpt://{YANDEX_FOLDER_ID}/{YANDEX_MODEL}",
            "completionOptions": {"stream": False, "temperature": temperature,
                                  "maxTokens": "200"},
            "messages": messages,
        }
        headers = {"Authorization": f"Api-Key {YANDEX_API_KEY}",
                   "x-folder-id": YANDEX_FOLDER_ID,
                   "Content-Type": "application/json"}

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as session:
                async with session.post(YANDEX_URL, json=payload, headers=headers,
                                        proxy=YANDEX_PROXY) as resp:
                    if resp.status != 200:
                        log.warning("Yandex AI вернул %s: %s", resp.status, await resp.text())
                        return None
                    data = await resp.json()
            text = data["result"]["alternatives"][0]["message"]["text"].strip()
            return text or None
        except asyncio.TimeoutError:
            log.warning("Yandex AI: таймаут")
        except Exception as exc:
            log.warning("Yandex AI: ошибка %s", exc)
        return None
