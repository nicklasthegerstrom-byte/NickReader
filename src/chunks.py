"""Gör en PDF till ljud i bitar, i bakgrunden, så att uppläsningen kan börja direkt.

Varje bit sparas som en liten MP3-fil i src/static/audio/<nyckel>/ tillsammans med
en manifest.json som säger vilka bitar som är klara. Webbläsaren läser manifestet
och spelar bitarna efter varandra medan nästa bitar fortfarande görs.

Färdiga bitar ligger kvar på disk (cache). Öppnar du samma PDF med samma röst
igen går det direkt, och avbruten generering fortsätter där den slutade.
"""

import hashlib
import json
import os
import threading
from pathlib import Path

import soundfile as sf

from pdf_text import extract_text
from tts import DEFAULT_VOICE, split_sentences, synthesize_sentences

STATIC_DIR = Path(__file__).resolve().parent / "static"
AUDIO_ROOT = STATIC_DIR / "audio"
URL_ROOT = "/app/static/audio"  # så här serverar Streamlit mappen src/static

FIRST_CHUNK_CHARS = 300   # liten första bit, så att uppläsningen startar snabbt
CHUNK_CHARS = 900         # därefter större bitar (ca en till två minuters ljud)

_state_lock = threading.Lock()
_generation_lock = threading.Lock()   # röstmodellen används av en tråd i taget
_active_threads: dict[str, threading.Thread] = {}
_latest_key: str | None = None        # senast begärda PDF; äldre jobb pausar


def make_key(pdf_path: Path, voice: str) -> str:
    """Kort id för en PDF + röst. Ändras om filen ändras."""
    stat = pdf_path.stat()
    raw = f"v2|{pdf_path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}|{voice}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def plan_chunks(items: list[tuple[str, bool]]) -> list[tuple[int, int]]:
    """Delar meningarna i bitar. Returnerar (första_mening, antal) för varje bit."""
    plan: list[tuple[int, int]] = []
    start, size, limit = 0, 0, FIRST_CHUNK_CHARS
    for i, (sentence, _) in enumerate(items):
        size += len(sentence)
        if size >= limit:
            plan.append((start, i - start + 1))
            start, size, limit = i + 1, 0, CHUNK_CHARS
    if start < len(items):
        plan.append((start, len(items) - start))
    return plan


def _write_json(path: Path, data: object) -> None:
    """Skriver filen i ett svep, så att webbläsaren aldrig läser en halv fil."""
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _load_manifest(directory: Path, total_chunks: int) -> dict:
    path = directory / "manifest.json"
    if path.exists():
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["total_chunks"] = total_chunks
            return manifest
        except (json.JSONDecodeError, OSError):
            pass
    return {"status": "generating", "error": "", "total_chunks": total_chunks, "chunks": []}


def _generate(key: str, directory: Path, items: list, plan: list, voice: str) -> None:
    """Bakgrundsjobb: gör saknade bitar en i taget och uppdaterar manifestet."""
    manifest = _load_manifest(directory, len(plan))
    try:
        with _generation_lock:
            for index in range(len(manifest["chunks"]), len(plan)):
                if _latest_key != key:   # användaren har bytt PDF; fortsätt senare
                    return
                first, count = plan[index]
                audio = synthesize_sentences(
                    items[first:first + count], voice=voice, text_start=(index == 0)
                )
                filename = f"chunk_{index:04d}.mp3"
                part = directory / (filename + ".part")
                sf.write(part, audio.samples, audio.sample_rate, format="MP3")
                os.replace(part, directory / filename)

                manifest["chunks"].append({
                    "file": filename,
                    "first": first,
                    "count": count,
                    "duration": len(audio.samples) / audio.sample_rate,
                    "starts": [s / audio.sample_rate for s in audio.starts],
                })
                _write_json(directory / "manifest.json", manifest)
            manifest["status"] = "done"
            _write_json(directory / "manifest.json", manifest)
    except Exception as error:  # visas i appen i stället för att tråden dör tyst
        manifest["status"] = "error"
        manifest["error"] = f"{type(error).__name__}: {error}"
        _write_json(directory / "manifest.json", manifest)
    finally:
        with _state_lock:
            _active_threads.pop(key, None)


def start(pdf_path: Path, voice: str = DEFAULT_VOICE) -> dict | None:
    """Förbereder en PDF och startar ljudgenereringen i bakgrunden.

    Returnerar {"base_url", "sentences"} till webbläsarspelaren, eller None om
    PDF:en saknar text. Anropet väntar bara på textutvinningen, inte på ljudet.
    """
    global _latest_key
    key = make_key(pdf_path, voice)
    directory = AUDIO_ROOT / key
    directory.mkdir(parents=True, exist_ok=True)

    sentences_file = directory / "sentences.json"
    if sentences_file.exists():
        items = [tuple(item) for item in json.loads(sentences_file.read_text(encoding="utf-8"))]
    else:
        items = split_sentences(extract_text(pdf_path))
        if not items:
            return None
        _write_json(sentences_file, items)
    if not items:
        return None

    plan = plan_chunks(items)
    manifest = _load_manifest(directory, len(plan))
    _write_json(directory / "manifest.json", manifest)

    with _state_lock:
        _latest_key = key
        needs_work = manifest["status"] != "done"
        if needs_work and key not in _active_threads:
            if manifest["status"] == "error":
                manifest["status"], manifest["error"] = "generating", ""
                _write_json(directory / "manifest.json", manifest)
            thread = threading.Thread(
                target=_generate, args=(key, directory, items, plan, voice), daemon=True
            )
            _active_threads[key] = thread
            thread.start()

    return {"base_url": f"{URL_ROOT}/{key}/", "sentences": [text for text, _ in items]}
