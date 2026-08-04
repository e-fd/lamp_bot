"""Голосовой ввод: OGG/Opus -> WAV 16 кГц (ffmpeg) -> текст (Vosk, офлайн).

Модель vosk-model-small-ru-0.22 весит ~50 МБ и не требует интернета.
"""
import asyncio
import json
import wave
from pathlib import Path

from config import VOSK_MODEL_PATH, log

try:
    from vosk import KaldiRecognizer, Model, SetLogLevel

    SetLogLevel(-1)
    _VOSK_AVAILABLE = True
except Exception:  # pragma: no cover
    _VOSK_AVAILABLE = False


async def ogg_to_wav(src: Path, dst: Path) -> bool:
    """Конвертация голосового Telegram в WAV 16 кГц моно."""
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
        "-ar", "16000", "-ac", "1", "-f", "wav", str(dst),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        log.error("ffmpeg: %s", stderr.decode(errors="ignore")[:300])
        return False
    return True


class SpeechToText:
    def __init__(self, model_path=VOSK_MODEL_PATH):
        self.model = None
        if not _VOSK_AVAILABLE:
            log.warning("Пакет vosk не установлен — распознавание речи отключено")
            return
        if not Path(model_path).exists():
            log.warning("Модель Vosk не найдена: %s — распознавание отключено", model_path)
            return
        self.model = Model(str(model_path))
        log.info("Vosk загружен: %s", model_path)

    @property
    def enabled(self) -> bool:
        return self.model is not None

    def _recognize_sync(self, wav_path: Path) -> str:
        with wave.open(str(wav_path), "rb") as wf:
            recognizer = KaldiRecognizer(self.model, wf.getframerate())
            recognizer.SetWords(False)
            chunks = []
            while True:
                data = wf.readframes(4000)
                if not data:
                    break
                if recognizer.AcceptWaveform(data):
                    chunks.append(json.loads(recognizer.Result()).get("text", ""))
            chunks.append(json.loads(recognizer.FinalResult()).get("text", ""))
        return " ".join(part for part in chunks if part).strip()

    async def transcribe(self, ogg_path: Path) -> str:
        """Асинхронная обёртка: тяжёлая работа уходит в отдельный поток."""
        if not self.enabled:
            return ""
        wav_path = ogg_path.with_suffix(".wav")
        if not await ogg_to_wav(ogg_path, wav_path):
            return ""
        try:
            return await asyncio.to_thread(self._recognize_sync, wav_path)
        finally:
            wav_path.unlink(missing_ok=True)
