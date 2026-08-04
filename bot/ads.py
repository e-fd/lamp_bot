"""Сценарии рекламы товара.

1) Контекстная: пользователь упомянул комнату/ремонт — предлагаем каталог
   с позициями под эту комнату.
2) Периодическая: каждые AD_EVERY_N реплик добавляем предложение товара,
   перебирая каталог по кругу.
"""
import random

from config import AD_EVERY_N
from data.catalog import CATALOG, format_item, items_for_room

PERIODIC_TEMPLATES = [
    "Кстати, пока не забыл: {name} — {price} ₽, {stock} шт. на складе. {pitch}.",
    "Между прочим, у нас есть {name} за {price} ₽. {pitch}.",
    "Раз уж зашла речь: {name}, {price} ₽. {pitch}. Осталось {stock} шт.",
]

ROOM_INTROS = [
    "Раз речь о комнате «{room}» — вот что из каталога туда просится:",
    "Для комнаты «{room}» обычно берут вот это:",
    "Под «{room}» у нас есть подходящие варианты:",
]


class AdEngine:
    """Один экземпляр на всех: состояние хранится по user_id."""

    def __init__(self, every_n: int = AD_EVERY_N):
        self.every_n = every_n
        self._counters: dict[int, int] = {}
        self._cursor: dict[int, int] = {}
        self._shown_rooms: dict[int, set] = {}

    # ---------- периодическая реклама ----------
    def tick(self, user_id: int) -> str | None:
        """Считает реплики пользователя; каждые N — возвращает рекламу."""
        count = self._counters.get(user_id, 0) + 1
        self._counters[user_id] = count
        if count % self.every_n != 0:
            return None
        return self.next_product_pitch(user_id)

    def next_product_pitch(self, user_id: int) -> str:
        """Товары перебираются по кругу — каждый получит своё эфирное время."""
        index = self._cursor.get(user_id, 0)
        item = CATALOG[index % len(CATALOG)]
        self._cursor[user_id] = (index + 1) % len(CATALOG)
        template = random.choice(PERIODIC_TEMPLATES)
        pitch = item["pitch"][0].upper() + item["pitch"][1:]
        return template.format(name=item["name"], price=item["price"],
                               stock=item["stock"], pitch=pitch)

    # ---------- контекстная реклама ----------
    def room_offer(self, user_id: int, room: str) -> str:
        items = items_for_room(room) or CATALOG[:2]
        self._shown_rooms.setdefault(user_id, set()).add(room)
        # сброс периодического счётчика: реклама уже показана
        self._counters[user_id] = 0
        intro = random.choice(ROOM_INTROS).format(room=room)
        body = "\n".join(format_item(item) for item in items[:3])
        return f"{intro}\n{body}\n\nЕсли что-то приглянулось — скажите «хочу заказать»."

    def reset(self, user_id: int) -> None:
        self._counters.pop(user_id, None)
        self._cursor.pop(user_id, None)
        self._shown_rooms.pop(user_id, None)
