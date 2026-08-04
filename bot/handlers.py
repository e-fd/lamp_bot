"""Хендлеры Telegram (aiogram 3). Всё асинхронно: голосовое одного
пользователя не блокирует остальных."""
import uuid
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import FSInputFile, InputMediaPhoto, Message

from bot.core import ChatBot
from config import GREETING, TMP_DIR, log
from services.stt import SpeechToText
from services.tts import TextToSpeech

router = Router()

chatbot = ChatBot()
stt = SpeechToText()
tts = TextToSpeech()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    chatbot.ads.reset(message.from_user.id)
    chatbot.states.pop(message.from_user.id, None)
    await message.answer(
        f"{GREETING}\n\n"
        "Команды: /catalog — каталог, /help — что я умею.\n"
        "Можно писать текстом или присылать голосовые."
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Я умею:\n"
        "• поддержать обычный разговор;\n"
        "• рассказать про светильники, цены, доставку, гарантию;\n"
        "• подобрать свет под комнату;\n"
        "• принять заявку — скажите «хочу заказать»;\n"
        "• понять голосовое сообщение и ответить голосом.\n\n"
        "Чтобы закончить, просто напишите «пока»."
    )


@router.message(Command("catalog"))
async def cmd_catalog(message: Message) -> None:
    await message.answer(chatbot.catalog_text())


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    await message.answer(f"Статистика источников ответов: {chatbot.stats}")


async def send_reply(message: Message, reply) -> None:
    """Текст плюс, если есть, альбом фотографий товара.

    Фото отправляются только по запросу о конкретной модели;
    /catalog остаётся текстовым, чтобы не заваливать чат картинками.
    """
    if not reply.images:
        await message.answer(reply.text)
        return

    if len(reply.images) == 1:
        await message.answer_photo(FSInputFile(reply.images[0]), caption=reply.text[:1024])
        return

    media = [InputMediaPhoto(media=FSInputFile(path)) for path in reply.images]
    media[0].caption = reply.text[:1024]
    await message.answer_media_group(media)


@router.message(F.voice)
async def handle_voice(message: Message, bot: Bot) -> None:
    """OGG/Opus -> WAV 16 кГц (ffmpeg) -> Vosk -> текстовый конвейер -> pyttsx3 -> OGG."""
    if not stt.enabled:
        await message.answer("Голосовые пока не распознаю — напишите, пожалуйста, текстом.")
        return

    ogg_path = Path(TMP_DIR) / f"voice_{uuid.uuid4().hex}.ogg"
    try:
        file = await bot.get_file(message.voice.file_id)
        await bot.download_file(file.file_path, destination=ogg_path)

        text = await stt.transcribe(ogg_path)
        if not text:
            await message.answer("Не расслышал. Попробуйте записать ещё раз.")
            return

        await message.answer(f"🎧 Распознал: «{text}»")
        reply = await chatbot.respond(message.from_user.id, text)
        await send_reply(message, reply)

        voice_path = await tts.speak(reply.text)
        if voice_path:
            try:
                await message.answer_voice(FSInputFile(voice_path))
            finally:
                voice_path.unlink(missing_ok=True)

        if reply.finished:
            log.info("Диалог с user=%s завершён", message.from_user.id)
    except Exception as exc:
        log.exception("Ошибка обработки голосового: %s", exc)
        await message.answer("Что-то пошло не так с голосовым. Напишите текстом, пожалуйста.")
    finally:
        ogg_path.unlink(missing_ok=True)


@router.message(F.text)
async def handle_text(message: Message) -> None:
    reply = await chatbot.respond(message.from_user.id, message.text)
    await send_reply(message, reply)
    if reply.finished:
        log.info("Диалог с user=%s завершён", message.from_user.id)


@router.message()
async def handle_other(message: Message) -> None:
    await message.answer("Я понимаю текст и голосовые сообщения.")
