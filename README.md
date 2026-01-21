# pdf-filer (macOS)

Automates filing scanned PDFs from an input folder ("Ablage") into subfolders under a target folder ("Dokumente").

It runs fully locally and combines:
- PDF text extraction (text layer) + fallback OCR via **macOS Vision**
- Multi-stage sender classification via **Ollama** (small model first, bigger model on low confidence)
- SQLite logging of model outputs and routing decisions (for later analysis)
- Daily automation via **launchd** (no cron)


---

## Features
- Processes **all PDFs currently in the input folder** (no state tracking required because files get moved out)
- Renames PDFs with a date prefix `YYYY-MM-DD` using **file/PDF metadata only** (never from PDF text)
- Collision handling: appends `_1`, `_2`, ... if a filename already exists in the destination folder
- Safe fallback folder for uncertain classification (`Dokumente/_Unklar`) 
- Stores raw model JSON responses (stage1 + stage2 + final) in SQLite for later analysis

---

## Requirements
- macOS (Vision framework via pyobjc)
- Python 3.10+
- Ollama installed and running

---

## Privacy & Data Protection

All document processing happens locally on the user's machine.

- OCR uses macOS Vision locally.
- Classification is sent to Ollama (assumed local, default `http://localhost:11434`).

⚠️ Logs and the SQLite DB may contain filenames, routing decisions, and raw model outputs.  
Treat `~/.pdf_filer/` as sensitive and do not share or upload it.  
Users are responsible for complying with local data protection laws (e.g. GDPR).

### Safety checklist
- [ ] Keep config/mapping in `~/.pdf_filer/`, not in the repo
- [ ] Do not commit logs/DB (`gitignore.example` helps)
- [ ] Keep Ollama local unless you understand the implications

---

## Setup

### 1) Create venv & install
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

> Note: `pyobjc-*` dependencies are macOS-only. Install on macOS.

### 2) Install & start Ollama
Install Ollama and pull models, e.g.:
```bash
ollama pull qwen2.5:1.5b-instruct
ollama pull qwen2.5:3b-instruct
```

Ensure the Ollama server is running (default `http://localhost:11434`).

#### Ollama note
This project assumes Ollama runs locally (default `http://localhost:11434`).  
If you point it to a remote endpoint, document text/sender cues may leave your machine.

### 3) Configure
Copy and edit:
- `config.example.yaml` → `~/.pdf_filer/config.yaml`
- `sender_mapping.example.json` → `~/.pdf_filer/sender_mapping.json`

### 4) Run manually
```bash
pdf-filer run --config ~/.pdf_filer/config.yaml
```

Dry run:
```bash
pdf-filer run --config ~/.pdf_filer/config.yaml --dry-run
```

### 5) launchd automation
Edit `launchd/com.user.pdf_filer.plist`:
- Replace `<USER>` with your username
- Update paths to your venv python if needed

Then:
```bash
mkdir -p ~/Library/LaunchAgents
cp launchd/com.user.pdf_filer.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.user.pdf_filer.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.user.pdf_filer.plist
launchctl list | grep pdf_filer
```

To view logs:
- See `logs_dir` in config (defaults to `~/.pdf_filer/logs/`)

---

## Notes on accuracy
- Best results come from high-quality scans.
- Vision OCR is good, but for very noisy documents you may want to increase `ocr.max_pages` or `ocr.dpi`.
- The SQLite DB (`db_path`) lets you review low-confidence/unknown cases to update your mapping JSON.

---

## Troubleshooting
- If OCR fails: ensure the PDF is not password-protected and try higher `ocr.dpi`.
- If Ollama errors: check `ollama serve` and the URL in config.
- If launchd doesn't run: check logs in `~/.pdf_filer/logs/` and `launchctl list`.

---

## Development / tests
```bash
pytest -q
```
