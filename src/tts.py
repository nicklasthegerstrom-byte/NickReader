"""Gör om text till ljud, mening för mening, med rösten Kokoro.

Varje mening görs till ljud av Kokoro (lokal röstmodell, engelska) och sätts
ihop till en enda ljudsekvens. Vi sparar var varje mening börjar, så att
spelaren senare kan hoppa exakt till en viss mening.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from kokoro_onnx import Kokoro

PROJECT_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_DIR / "models" / "kokoro-v1.0.int8.onnx"
VOICES_PATH = PROJECT_DIR / "models" / "voices-v1.0.bin"

SAMPLE_RATE = 24000          # Kokoro ger alltid 24 000 Hz
DEFAULT_VOICE = "af_heart"   # amerikansk engelska, kvinnlig
LANGUAGE = "en-us"
SENTENCE_GAP_SECONDS = 0.25  # kort paus mellan meningar
PARAGRAPH_GAP_SECONDS = 0.7  # längre paus mellan stycken


@dataclass
class Audio:
    """Färdigt ljud plus information om meningarna."""

    samples: np.ndarray        # ljudet, mono, float32
    sample_rate: int
    sentences: list[str]       # meningarnas text
    starts: list[int]          # sampelposition där varje mening börjar


def split_sentences(text: str) -> list[tuple[str, bool]]:
    """Delar text i meningar. Returnerar (mening, börjar_nytt_stycke).

    Radbrytningar mitt i en mening (vanligt i PDF) slås ihop till ett mellanslag.
    En tom rad räknas som styckegräns.
    """
    result: list[tuple[str, bool]] = []
    for paragraph in re.split(r"\n\s*\n", text):
        flat = re.sub(r"\s+", " ", paragraph).strip()
        if not flat:
            continue
        parts = re.split(r"(?<=[.!?])\s+", flat)
        for i, part in enumerate(parts):
            if part.strip():
                result.append((part.strip(), i == 0))
    return result


@lru_cache(maxsize=1)
def _load_model() -> Kokoro:
    """Laddar röstmodellen en gång och återanvänder den."""
    if not MODEL_PATH.exists() or not VOICES_PATH.exists():
        raise FileNotFoundError(
            f"Hittar inte röstmodellen i {MODEL_PATH.parent}. "
            "Ladda ner kokoro-v1.0.int8.onnx och voices-v1.0.bin dit."
        )
    return Kokoro(str(MODEL_PATH), str(VOICES_PATH))


def _speak(sentence: str, voice: str, speed: float) -> np.ndarray:
    """Låter Kokoro läsa en mening och returnerar ljudet som en array."""
    samples, rate = _load_model().create(sentence, voice=voice, speed=speed, lang=LANGUAGE)
    if rate != SAMPLE_RATE:
        raise RuntimeError(f"Oväntad samplingsfrekvens: {rate}")
    return samples.astype("float32")


def synthesize(text: str, voice: str = DEFAULT_VOICE, speed: float = 1.0) -> Audio:
    """Gör hela texten till ljud och håller reda på var meningarna börjar."""
    pieces: list[np.ndarray] = []
    sentences: list[str] = []
    starts: list[int] = []
    position = 0

    for sentence, new_paragraph in split_sentences(text):
        gap = PARAGRAPH_GAP_SECONDS if new_paragraph and sentences else SENTENCE_GAP_SECONDS
        silence = np.zeros(int(gap * SAMPLE_RATE), dtype="float32")
        audio = _speak(sentence, voice, speed)

        pieces.extend([silence, audio])
        position += len(silence)
        sentences.append(sentence)
        starts.append(position)
        position += len(audio)

    samples = np.concatenate(pieces) if pieces else np.zeros(0, dtype="float32")
    return Audio(samples, SAMPLE_RATE, sentences, starts)
