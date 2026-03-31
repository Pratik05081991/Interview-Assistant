# ⚡ Real-Time AI Interview Assistant

A lightweight, **screen-share invisible** Python desktop app that listens to
your interview questions and provides instant AI-powered answers — just like
Parakeet AI.

---

## ✨ Features

| Feature | Detail |
|---|---|
| 🎙 **Live mic listening** | Auto-transcribes interviewer questions in real time |
| ⌨ **Manual input** | Type any question for an instant answer |
| 🤖 **Claude / GPT-4o** | Pluggable AI backend — switch in Settings |
| 🙈 **Screen-share invisible** | Window hidden from Zoom, Teams, Meet captures |
| 📋 **One-click copy** | Copy any answer to clipboard instantly |
| 🌗 **Dark / Light theme** | Configurable opacity and font size |
| ⌨ **Global hotkeys** | F9 mic · F10 clear · F11 hide |
| 💾 **Persistent config** | Settings saved to `~/.interview_assistant_config.json` |

---

## 🗂 Project Structure

```
interview_assistant/
├── main.py            ← Entry point
├── app.py             ← Orchestrator (wires UI + audio + AI)
├── config.py          ← All settings
├── requirements.txt
├── ai/
│   └── engine.py      ← Anthropic / OpenAI inference + history
├── audio/
│   └── listener.py    ← Mic capture + Google STT / Whisper
└── ui/
    └── overlay.py     ← Tkinter overlay + screen-share exclusion
```

---

## 🚀 Quick Start

### 1. Clone / download the project

```bash
git clone <repo-url>
cd interview_assistant
```

### 2. Create a virtual environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **PyAudio on Windows** — if pip fails:
> ```bash
> pip install pipwin && pipwin install pyaudio
> ```
>
> **PyAudio on macOS**:
> ```bash
> brew install portaudio && pip install pyaudio
> ```
>
> **Tkinter on Ubuntu**:
> ```bash
> sudo apt install python3-tk portaudio19-dev python3-pyaudio
> ```

### 4. Set your API key

**Option A — environment variable (recommended):**
```bash
# Windows
set ANTHROPIC_API_KEY=sk-ant-...
# macOS / Linux
export ANTHROPIC_API_KEY=sk-ant-...
```

**Option B — in-app Settings panel:**
Click ⚙ in the top-right corner of the app.

### 5. Run

```bash
python main.py
```

---

## 🙈 Screen-Share Invisibility

### Windows (best support)
Uses `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` via ctypes.
- Requires **Windows 10 v2004** (May 2020 Update) or later.
- Works with Zoom, Teams, Google Meet, Discord, etc.
- Run as a **standard user** (not Administrator) — some capture APIs bypass
  the flag when elevated.

### macOS
Uses `NSWindowSharingNone` via PyObjC.
```bash
pip install pyobjc-framework-Cocoa
```
Then uncomment the line in `requirements.txt` and restart.

### Linux
No reliable system API exists. Recommended workaround:
1. Start a virtual display:  `Xephyr :1 -screen 1920x1080 &`
2. Run your interview browser on `:1`.
3. Run this assistant on your main display `:0`.
4. Share only the Xephyr window.

---

## ⚙ Configuration

All settings live in `config.py` and are also editable via the in-app ⚙ panel.

| Key | Default | Description |
|---|---|---|
| `AI_PROVIDER` | `anthropic` | `anthropic` or `openai` |
| `ANTHROPIC_API_KEY` | env var | Your Claude API key |
| `OPENAI_API_KEY` | env var | Your OpenAI API key |
| `STT_BACKEND` | `google` | `google` (free) or `whisper` (local) |
| `WHISPER_MODEL` | `base` | `tiny` / `base` / `small` / `medium` / `large` |
| `PAUSE_THRESHOLD` | `1.2` | Silence (sec) before phrase is sent |
| `OPACITY` | `0.95` | Window opacity |
| `THEME` | `dark` | `dark` or `light` |
| `FONT_SIZE` | `13` | Answer text size |
| `HISTORY_DEPTH` | `10` | Number of Q&A pairs kept in AI context |
| `SYSTEM_PROMPT` | see config | AI persona / instructions |

---

## ⌨ Hotkeys

| Key | Action |
|---|---|
| `F9` | Toggle microphone on / off |
| `F10` | Clear Q&A history |
| `F11` | Hide / show window |
| `Enter` | Submit typed question |

---

## 🔧 Using Whisper (Offline STT)

For better accuracy without sending audio to Google:

```bash
pip install openai-whisper numpy soundfile
```

Then in Settings → STT Backend → select `whisper`.
Model sizes: `tiny` (fastest) → `large` (most accurate, needs GPU).

---

## 📝 Tips for Interviews

1. **Before the call** — launch the app and test with a sample question.
2. **Mic sensitivity** — adjust `PAUSE_THRESHOLD` if questions get cut off.
3. **Manual fallback** — if a question isn't picked up, just type it.
4. **Copy answers** — use 📋 to paste polished answers into your IDE / notes.
5. **Minimise** — press ▂ or drag the window to a corner for minimal footprint.

---

## 🤝 Contributing

PRs welcome! Ideas:
- Whisper streaming (real-time word-by-word display)
- Question category detection (DSA / system design / HR)
- Answer history export to PDF
- Tray icon for quick show/hide

---

## ⚠ Disclaimer

This tool is for **practice and learning**. Use responsibly and in accordance
with the terms of the interview platform you are using.
