# 🎧 NickReader

Läser upp PDF-filer med en lokal röst (Kokoro, engelska). Du kan pausa, hoppa en mening
bakåt eller framåt, ändra hastighet och se vilken mening som läses. Uppläsningen börjar
efter några sekunder, även för långa PDF-filer, eftersom ljudet görs i bitar medan du lyssnar.

Text inom `( )` och `[ ]` visas men läses inte upp.

## Kom igång

Kräver [uv](https://docs.astral.sh/uv/) och en Mac (ljudet görs lokalt, inget skickas ut).

```bash
# 1. Skapa venv och installera paketen
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt

# 2. Hämta röstmodellen (ca 115 MB) till mappen models/
gh release download model-files-v1.0 --repo thewh1teagle/kokoro-onnx \
  --pattern 'kokoro-v1.0.int8.onnx' --pattern 'voices-v1.0.bin' --dir models
```

## Använda appen

1. Lägg dina PDF-filer i mappen `pdf_in/`.
2. Starta appen, antingen med ikonen eller i terminalen:
   - **Ikonen:** dubbelklicka på `NickReader.app` (dra den gärna till Dock eller skrivbordet).
     Den startar appen i bakgrunden och öppnar den i webbläsaren. Första gången kan macOS
     varna för en okänd utvecklare, och då godkänner du den under Systeminställningar →
     Integritet och säkerhet. Loggen finns i `~/Library/Logs/NickReader.log`.
   - **Terminalen:**

     ```bash
     streamlit run src/app.py
     ```

3. Välj PDF och röst, och tryck på **Läs upp**.
4. När du är klar: tryck på **Stäng ned NickReader** längst ned på sidan, så att appen
   inte körs i bakgrunden i onödan.

Tangenter i spelaren (klicka i den först): mellanslag = spela/pausa, ← → = mening bakåt/framåt.

Skannade PDF-filer (bilder av text) fungerar inte, de saknar text att läsa upp.

## Mappar

| Mapp | Innehåll |
|---|---|
| `src/` | Koden: `app.py` (appen), `reader.html` (spelaren), `tts.py` (text till ljud), `chunks.py` (ljud i bitar), `pdf_text.py` (läser PDF) |
| `assets/` | Loggan och knapparna |
| `NickReader.app/` | Ikonen som startar appen (programmet utan ikon ligger i `Contents/MacOS/`) |
| `pdf_in/` | Dina PDF-filer (checkas inte in i git) |
| `models/` | Röstmodellerna (checkas inte in i git) |
| `src/static/` | Genererat ljud, fungerar som cache (checkas inte in i git) |

## Bra att veta

- Första gången en PDF öppnas görs ljudet, och sedan sparas det. Samma PDF med samma röst startar direkt nästa gång.
- Appen nås bara från den här datorn. Ändra `address` i `.streamlit/config.toml` om du vill nå den från mobilen.
- Röstmodellen är gjord för engelska. Svenska texter låter fel.
