"""NickReader: Streamlit-app som läser upp PDF-filer.

Starta från projektmappen:
    streamlit run src/app.py
"""

import base64
import json
import os
import signal
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import chunks
from pdf_text import PDF_DIR
from tts import DEFAULT_VOICE, american_voices

SRC_DIR = Path(__file__).resolve().parent
UI_DIR = SRC_DIR.parent / "assets" / "ui"
READER_HTML = SRC_DIR / "reader.html"
ICON_NAMES = ["play", "pause", "stop", "prev", "next"]

st.set_page_config(page_title="NickReader", page_icon=str(UI_DIR / "play.png"), layout="centered")

# Tjocka svarta konturer och "knappskuggor", i samma stil som loggan och knapparna
st.markdown(
    """
    <style>
      [data-testid="stSelectbox"] [role="group"] {
        border: 3px solid #111 !important; border-radius: 14px !important;
        background: #fff !important; font-weight: 600;
      }
      [data-testid="stSelectbox"] input { font-weight: 600; }
      .stButton > button {
        border: 3px solid #111; border-radius: 14px; font-weight: 800;
        box-shadow: 0 5px 0 #111; transition: transform .08s, box-shadow .08s;
      }
      .stButton > button:hover { border-color: #111; filter: brightness(1.05); }
      .stButton > button:active { transform: translateY(4px); box-shadow: 0 1px 0 #111; }
      [data-testid="stCaptionContainer"] { font-weight: 600; }
      [data-testid="stImage"] { width: 100% !important; display: flex; justify-content: center; }
      [data-testid="stImageContainer"] { margin: 0 auto; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_icons() -> dict[str, str]:
    """Läser knappbilderna och gör om dem till data-URL:er som spelaren kan visa."""
    icons = {}
    for name in ICON_NAMES:
        encoded = base64.b64encode((UI_DIR / f"{name}.png").read_bytes()).decode("ascii")
        icons[name] = "data:image/png;base64," + encoded
    return icons


@st.cache_data(show_spinner=False)
def load_logo() -> str:
    """Loggan som data-URL, så att den kan centreras i sidan."""
    encoded = base64.b64encode((UI_DIR / "logo.png").read_bytes()).decode("ascii")
    return "data:image/png;base64," + encoded


def shutdown_footer() -> None:
    """Knapp längst ned som stänger ned appen, så att den inte körs i bakgrunden i onödan."""
    st.divider()
    if st.button("⏻ Stäng ned NickReader"):
        st.info(
            "NickReader stängs ned. Du kan stänga den här fliken. "
            "Felmeddelandet om anslutning som visas strax är normalt."
        )
        time.sleep(1)  # ger webbläsaren tid att visa meddelandet
        os.kill(os.getpid(), signal.SIGTERM)


def render_reader(info: dict) -> None:
    """Visar spelaren (HTML och JavaScript) som hämtar ljudbitarna medan de görs."""
    payload = {"baseUrl": info["base_url"], "sentences": info["sentences"], "icons": load_icons()}
    # "</" escapas så att texten aldrig kan avsluta script-taggen i förtid
    data = json.dumps(payload).replace("</", "<\\/")
    html = READER_HTML.read_text(encoding="utf-8").replace("__DATA__", data)
    components.html(html, height=700)


st.markdown(
    f'<div style="text-align:center"><img src="{load_logo()}" alt="NickReader" '
    'style="width:360px;max-width:100%"></div>',
    unsafe_allow_html=True,
)

PDF_DIR.mkdir(exist_ok=True)
pdf_files = sorted(PDF_DIR.glob("*.pdf"))

if not pdf_files:
    st.info(f"Lägg en PDF-fil i mappen `{PDF_DIR}` och ladda om sidan.")
    shutdown_footer()
    st.stop()

left, right = st.columns([3, 1])
chosen = left.selectbox("PDF", pdf_files, format_func=lambda p: p.name)
voices = american_voices()
voice = right.selectbox("Röst", voices, index=voices.index(DEFAULT_VOICE))

if st.button("Läs upp", type="primary"):
    with st.spinner("Läser ut texten..."):
        info = chunks.start(chosen, voice)
    st.session_state["info"] = info
    st.session_state["info_name"] = f"{chosen.name} · röst {voice}"
    st.session_state["no_text"] = info is None

if st.session_state.get("no_text"):
    st.warning("Ingen text hittades. PDF:en är troligen en skannad bild (kräver OCR).")
elif st.session_state.get("info"):
    info = st.session_state["info"]
    st.caption(f"{st.session_state['info_name']} · {len(info['sentences'])} meningar")
    render_reader(info)

shutdown_footer()
