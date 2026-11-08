"""Litet testprogram för spelaren, med inbyggd text.

Kör från projektmappen:
    python src/player_demo.py

Tangenter:  mellanslag = pausa/fortsätt   ← = bakåt   → = framåt   q = avsluta
"""

import select
import sys
import termios
import tty

from player import Player
from tts import synthesize

DEMO_TEXT = """This is a test of the reader.

This is the first sentence of the first paragraph. The second sentence follows right after it.
Here comes a third sentence, which is a little longer than the others, so that you have time to try pausing.

A new paragraph starts here. Now try rewinding and skipping forward. This is the last sentence."""


def read_key() -> str | None:
    """Läser en tangent om en är nedtryckt, annars None. Piltangenter blir 'left'/'right'."""
    if not select.select([sys.stdin], [], [], 0.1)[0]:
        return None
    key = sys.stdin.read(1)
    if key == "\x1b":
        rest = sys.stdin.read(2)
        return {"[C": "right", "[D": "left"}.get(rest)
    return key


def main() -> None:
    print("Gör text till ljud, ett ögonblick...")
    audio = synthesize(DEMO_TEXT)
    player = Player(audio)
    player.start()

    print("mellanslag = pausa/fortsätt   ← bakåt   → framåt   q = avsluta\n")

    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        while True:
            key = read_key()
            if key == "q":
                break
            if key == " ":
                player.toggle_pause()
            elif key == "left":
                player.previous_sentence()
            elif key == "right":
                player.next_sentence()

            status = "⏸ " if player.paused else "▶ "
            line = f"{status}[{player.sentence_index + 1}/{len(audio.sentences)}] {player.current_sentence}"
            print("\r\033[K" + line[:100], end="", flush=True)

            if player.finished and not player.paused:
                player.toggle_pause()  # pausa i slutet
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        player.stop()
        print()


if __name__ == "__main__":
    main()
