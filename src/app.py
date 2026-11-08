"""NickReader: Streamlit-app som läser upp PDF-filer.

Starta från projektmappen:
    streamlit run src/app.py
"""

import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import chunks
from pdf_text import PDF_DIR
from tts import DEFAULT_VOICE, american_voices

READER_HTML = Path(__file__).with_name("reader.html")

st.set_page_config(page_title="NickReader", page_icon="🎧", layout="centered")


def render_reader(info: dict) -> None:
    """Visar spelaren (HTML och JavaScript) som hämtar ljudbitarna medan de görs."""
    payload = {"baseUrl": info["base_url"], "sentences": info["sentences"]}
    # "</" escapas så att texten aldrig kan avsluta script-taggen i förtid
    data = json.dumps(payload).replace("</", "<\\/")
    html = READER_HTML.read_text(encoding="utf-8").replace("__DATA__", data)
    components.html(html, height=680)


st.title("🎧 NickReader")

PDF_DIR.mkdir(exist_ok=True)
pdf_files = sorted(PDF_DIR.glob("*.pdf"))

if not pdf_files:
    st.info(f"Lägg en PDF-fil i mappen `{PDF_DIR}` och ladda om sidan.")
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
