"""Spelare för uppläst text: starta, pausa, hoppa mellan meningar.

Spelaren vet inget om terminalen eller fönster. Den tar emot färdigt ljud
(från tts.py) och har enkla metoder som både ett terminalprogram och ett
framtida gränssnitt kan anropa.
"""

import threading

import numpy as np
import sounddevice as sd

from tts import Audio

# Om vi är längre in än så här i en mening går "bakåt" till meningens början
# i stället för till föregående mening.
RESTART_THRESHOLD_SECONDS = 1.5


class Player:
    def __init__(self, audio: Audio) -> None:
        self.audio = audio
        self._position = 0          # nuvarande plats i ljudet (sampel)
        self._paused = True         # startar pausad tills play() anropas
        self._lock = threading.Lock()
        self._stream: sd.OutputStream | None = None

    # ---------- Tillstånd ----------

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def finished(self) -> bool:
        return self._position >= len(self.audio.samples)

    @property
    def sentence_index(self) -> int:
        """Index på den mening som spelas just nu."""
        starts = self.audio.starts
        index = 0
        for i, start in enumerate(starts):
            if start <= self._position:
                index = i
            else:
                break
        return index

    @property
    def current_sentence(self) -> str:
        return self.audio.sentences[self.sentence_index] if self.audio.sentences else ""

    # ---------- Styrning ----------

    def start(self) -> None:
        """Öppnar ljudutgången och börjar spela från nuvarande plats."""
        if self._stream is None:
            self._stream = sd.OutputStream(
                samplerate=self.audio.sample_rate,
                channels=1,
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()
        self._paused = False

    def toggle_pause(self) -> None:
        with self._lock:
            if self.finished:  # är vi i slutet börjar vi om vid nästa tryck
                self._position = 0
            self._paused = not self._paused

    def next_sentence(self) -> None:
        with self._lock:
            self._position = self._start_of(min(self.sentence_index + 1, len(self.audio.starts) - 1))

    def previous_sentence(self) -> None:
        with self._lock:
            index = self.sentence_index
            seconds_in = (self._position - self.audio.starts[index]) / self.audio.sample_rate
            if seconds_in > RESTART_THRESHOLD_SECONDS or index == 0:
                self._position = self._start_of(index)
            else:
                self._position = self._start_of(index - 1)

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._paused = True

    # ---------- Internt ----------

    def _start_of(self, index: int) -> int:
        return self.audio.starts[index] if self.audio.starts else 0

    def _callback(self, outdata: np.ndarray, frames: int, time, status) -> None:
        """Anropas av ljudsystemet hela tiden; fyller bufferten med ljud."""
        with self._lock:
            if self._paused or self.finished:
                outdata.fill(0)
                return
            chunk = self.audio.samples[self._position:self._position + frames]
            outdata[:len(chunk), 0] = chunk
            outdata[len(chunk):] = 0
            self._position += len(chunk)
