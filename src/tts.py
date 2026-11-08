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
SILENT_SENTENCE_SECONDS = 0.2  # längd för en mening utan något att läsa upp


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
        for i, part in enumerate(_split_flat(flat)):
            result.append((part, i == 0))
    return result


MAX_BRACKET_SPAN = 500  # en glömd ( eller [ får inte stoppa meningsdelningen för alltid


def _split_flat(flat: str) -> list[str]:
    """Delar ett stycke vid . ! ? följt av mellanslag, men inte inuti ( ) eller [ ].

    Annars skulle till exempel "(Smith et al. 2020)" delas mitt i parentesen.
    """
    parts: list[str] = []
    depth = 0
    start = 0
    for i, char in enumerate(flat):
        if char in "([":
            depth += 1
        elif char in ")]":
            depth = max(0, depth - 1)
        elif char in ".!?" and i + 1 < len(flat) and flat[i + 1] == " ":
            if depth == 0 or i - start > MAX_BRACKET_SPAN:
                parts.append(flat[start:i + 1].strip())
                start = i + 1
                depth = 0
    tail = flat[start:].strip()
    if tail:
        parts.append(tail)
    return [part for part in parts if part]


def speakable(sentence: str) -> str:
    """Texten som ska läsas upp: utan text i ( ) och [ ]. Texten på skärmen ändras inte."""
    text = sentence
    previous = None
    while previous != text:  # tar bort innersta paren först, så nästlade fungerar
        previous = text
        text = re.sub(r"\([^()]*\)|\[[^\[\]]*\]", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)      # "word ." -> "word."
    text = re.sub(r"([,;:])(\s*[,;:])+", r"\1", text)  # ", ," -> ","
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=1)
def _load_model() -> Kokoro:
    """Laddar röstmodellen en gång och återanvänder den."""
    if not MODEL_PATH.exists() or not VOICES_PATH.exists():
        raise FileNotFoundError(
            f"Hittar inte röstmodellen i {MODEL_PATH.parent}. "
            "Ladda ner kokoro-v1.0.int8.onnx och voices-v1.0.bin dit."
        )
    return Kokoro(str(MODEL_PATH), str(VOICES_PATH))


def american_voices() -> list[str]:
    """Lista över amerikanska röster (af_ = kvinnlig, am_ = manlig)."""
    return sorted(v for v in _load_model().get_voices() if v.startswith(("af_", "am_")))


def _speak(sentence: str, voice: str, speed: float) -> np.ndarray:
    """Låter Kokoro läsa en mening och returnerar ljudet som en array."""
    samples, rate = _load_model().create(sentence, voice=voice, speed=speed, lang=LANGUAGE)
    if rate != SAMPLE_RATE:
        raise RuntimeError(f"Oväntad samplingsfrekvens: {rate}")
    return samples.astype("float32")


def synthesize(text: str, voice: str = DEFAULT_VOICE, speed: float = 1.0) -> Audio:
    """Gör hela texten till ljud och håller reda på var meningarna börjar."""
    return synthesize_sentences(split_sentences(text), voice, speed)


def synthesize_sentences(
    items: list[tuple[str, bool]],
    voice: str = DEFAULT_VOICE,
    speed: float = 1.0,
    text_start: bool = True,
) -> Audio:
    """Gör en lista meningar (från split_sentences) till ljud.

    `text_start` ska vara True för den allra första biten av en text, så att
    den inte får en lång styckepaus i början. Följande bitar anger False.
    """
    pieces: list[np.ndarray] = []
    sentences: list[str] = []
    starts: list[int] = []
    position = 0

    for i, (sentence, new_paragraph) in enumerate(items):
        very_first = text_start and i == 0
        gap = PARAGRAPH_GAP_SECONDS if new_paragraph and not very_first else SENTENCE_GAP_SECONDS
        silence = np.zeros(int(gap * SAMPLE_RATE), dtype="float32")
        spoken = speakable(sentence)
        if any(char.isalnum() for char in spoken):
            audio = _speak(spoken, voice, speed)
        else:
            # Bara parentes (t.ex. "(See Figure 3.)"): visas, men låter inget.
            # Kort tystnad ger meningen en egen startpunkt, så att hoppen funkar.
            audio = np.zeros(int(SILENT_SENTENCE_SECONDS * SAMPLE_RATE), dtype="float32")

        pieces.extend([silence, audio])
        position += len(silence)
        sentences.append(sentence)
        starts.append(position)
        position += len(audio)

    samples = np.concatenate(pieces) if pieces else np.zeros(0, dtype="float32")
    return Audio(samples, SAMPLE_RATE, sentences, starts)
