"""Озвучивание ответа: pyttsx3 (локально) -> WAV -> OGG/Opus для Telegram."""
import asyncio
import uuid
from pathlib import Path

from config import TMP_DIR, log

try:
    import pyttsx3

    _TTS_AVAILABLE = True
except Exception:  # pragma: no cover
    _TTS_AVAILABLE = False


class TextToSpeech:
    def __init__(self, rate: int = 170):
        self.rate = rate
        self.enabled = _TTS_AVAILABLE
        if not self.enabled:
            log.warning("pyttsx3 недоступен — ответы будут только текстом")

    def _synthesize_sync(self, text: str, wav_path: Path) -> bool:
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            for voice in engine.getProperty("voices"):
                if "ru" in str(getattr(voice, "id", "")).lower() or \
                   "russian" in str(getattr(voice, "name", "")).lower():
                    engine.setProperty("voice", voice.id)
                    break
            engine.save_to_file(text, str(wav_path))
            engine.runAndWait()
            engine.stop()
            return wav_path.exists() and wav_path.stat().st_size > 0
        except Exception as exc:
            log.error("pyttsx3: %s", exc)
            return False

    async def speak(self, text: str) -> Path | None:
        """Возвращает путь к OGG-файлу с озвученным ответом."""
        if not self.enabled or not text.strip():
            return None
        stem = TMP_DIR / f"tts_{uuid.uuid4().hex}"
        wav_path, ogg_path = stem.with_suffix(".wav"), stem.with_suffix(".ogg")

        ok = await asyncio.to_thread(self._synthesize_sync, text[:600], wav_path)
        if not ok:
            return None

        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path),
            "-c:a", "libopus", "-b:a", "32k", "-ar", "48000", "-ac", "1", str(ogg_path),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        wav_path.unlink(missing_ok=True)

        if process.returncode != 0:
            log.error("ffmpeg (opus): %s", stderr.decode(errors="ignore")[:300])
            ogg_path.unlink(missing_ok=True)
            return None
        return ogg_path
