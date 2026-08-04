"""Каталог товаров и рекламные сценарии.

Факты о светильниках берутся ТОЛЬКО отсюда — генеративная модель
(Yandex AI) к описанию товаров не допускается.
"""
from pathlib import Path

# Фотографии товаров: data/images/<файл>. Каталог может отсутствовать —
# тогда бот просто отвечает текстом.
IMAGES_DIR = Path(__file__).resolve().parent / "images"

CATALOG = [
    {
        "id": "odeon_7109",
        "images": ["odeon_7109_1.jpg", "odeon_7109_2.jpg", "odeon_7109_3.jpg"],
        "name": "Потолочный светильник Odeon Light Magia 7109/1C",
        "type": "потолочный",
        "price": 4120,
        "stock": 113,
        "specs": "бронзовый/белый, стекло/металл, IP20, цоколь E14, 5 Вт, 220 В",
        "rooms": ["кухня", "прихожая", "коридор", "ванная", "спальня"],
        "pitch": "компактный потолочный светильник, не съедает высоту потолка "
                 "и хорошо смотрится в небольших комнатах",
    },
    {
        "id": "citilux_cl450101",
        "images": ["citilux_cl450101_1.jpg", "citilux_cl450101_2.jpg", "citilux_cl450101_3.jpg"],
        "name": "Подвесной светильник Citilux Jedison CL450101",
        "type": "подвесной",
        "price": 4890,
        "stock": 85,
        "specs": "подвес, регулируемая длина шнура, цоколь E27",
        "rooms": ["кухня", "гостиная", "столовая"],
        "pitch": "классический подвес над обеденным столом или барной стойкой — "
                 "высоту можно отрегулировать под свой потолок",
    },
    {
        "id": "lussole_lsp0674",
        "images": ["lussole_lsp0674_1.jpg", "lussole_lsp0674_2.jpg", "lussole_lsp0674_3.jpg", "lussole_lsp0674_4.jpg"],
        "name": "Торшер Lussole Union LSP-0674",
        "type": "торшер",
        "price": 4696,
        "stock": 13,
        "specs": "напольный торшер, металл, цоколь E27",
        "rooms": ["гостиная", "спальня", "кабинет"],
        "pitch": "напольный свет для кресла или дивана: мягкий вечерний сценарий "
                 "без верхнего света",
    },
    {
        "id": "vitaluce_v2710",
        "images": ["vitaluce_v2710_1.jpg", "vitaluce_v2710_2.jpg"],
        "name": "Настольная лампа Vitaluce V2710-1/1L",
        "type": "настольная лампа",
        "price": 2024,
        "stock": 3,
        "specs": "настольная, металл/ткань, цоколь E27",
        "rooms": ["кабинет", "детская", "спальня"],
        "pitch": "рабочий свет на стол — для чтения и уроков; "
                 "остались последние экземпляры",
    },
    {
        "id": "ambrella_fl66383",
        "images": ["ambrella_fl66383_1.jpg", "ambrella_fl66383_2.jpg", "ambrella_fl66383_3.jpg", "ambrella_fl66383_4.jpg"],
        "name": "Настенный светильник светодиодный Ambrella Comfort FL66383",
        "type": "настенный (бра)",
        "price": 1350,
        "stock": 22,
        "specs": "светодиодный, форма шара, настенное крепление",
        "rooms": ["спальня", "прихожая", "коридор", "детская", "ванная"],
        "pitch": "бра-шар у изголовья кровати или в прихожей: "
                 "самый бюджетный вариант в каталоге",
    },
]

CATALOG_BY_ID = {item["id"]: item for item in CATALOG}

# Комнаты, которые бот распознаёт в реплике для контекстной рекламы
ROOM_KEYWORDS = {
    "кухня": ["кухня", "кухонный", "кухне", "столовая", "обеденный"],
    "гостиная": ["гостиная", "зал", "гостиной", "диван", "телевизор"],
    "спальня": ["спальня", "спальне", "кровать", "изголовье"],
    "детская": ["детская", "ребенок", "ребёнок", "детской", "уроки"],
    "кабинет": ["кабинет", "рабочий стол", "офис", "компьютер"],
    "прихожая": ["прихожая", "коридор", "холл"],
    "ванная": ["ванная", "санузел", "ванной"],
}


def format_item(item: dict, with_pitch: bool = True) -> str:
    stock = f"в наличии {item['stock']} шт." if item["stock"] else "под заказ"
    text = f"• {item['name']} — {item['price']} ₽, {stock}\n  {item['specs']}"
    if with_pitch:
        text += f"\n  {item['pitch'].capitalize()}."
    return text


def format_catalog() -> str:
    lines = ["Каталог Ламп.ру:", ""]
    lines += [format_item(item, with_pitch=False) for item in CATALOG]
    lines.append("")
    lines.append("Скажите, для какой комнаты подбираете, — предложу подходящее.")
    return "\n".join(lines)


def items_for_room(room: str) -> list:
    return [item for item in CATALOG if room in item["rooms"]]


def item_photos(item: dict, limit: int = 4) -> list:
    """Существующие на диске фотографии товара, не более `limit` штук."""
    paths = [IMAGES_DIR / name for name in item.get("images", [])]
    return [p for p in paths if p.exists()][:limit]


def item_card(item: dict, description: str | None = None) -> str:
    """Развёрнутая карточка товара для ответа на вопрос о конкретной модели."""
    stock = f"в наличии {item['stock']} шт." if item["stock"] else "под заказ"
    lines = [item["name"], f"Цена: {item['price']} ₽ — {stock}",
             f"Характеристики: {item['specs']}"]
    if description:
        lines.append("")
        lines.append(description)
    else:
        lines.append("")
        lines.append(item["pitch"][0].upper() + item["pitch"][1:] + ".")
    lines.append("")
    lines.append("Скажите «хочу заказать» — оформлю заявку.")
    return "\n".join(lines)
