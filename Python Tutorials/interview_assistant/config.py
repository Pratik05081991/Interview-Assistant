"""
config.py — All user-tunable settings in one place.
Edit this file OR change values via the in-app Settings panel.
"""

import os
import json
from pathlib import Path

CONFIG_FILE = Path.home() / ".interview_assistant_config.json"


class Config:
    # ── AI ──────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "sk-ant-api03-xxxxxxxxxxxxxxxx")
    OPENAI_API_KEY: str    = os.getenv("OPENAI_API_KEY", "")

    # Which provider: "anthropic" | "openai"
    AI_PROVIDER: str = "anthropic"

    # Anthropic model
    ANTHROPIC_MODEL: str = "claude-opus-4-5"

    # OpenAI model (fallback)
    OPENAI_MODEL: str = "gpt-4o"

    # Max tokens in AI response
    MAX_TOKENS: int = 1024

    # Conversation memory — keep last N exchanges for context
    HISTORY_DEPTH: int = 10

    # System prompt (defines AI persona)
    SYSTEM_PROMPT: str = (
        "You are an expert interview coach and senior software engineer. "
        "The user is in a live technical or HR interview. "
        "Answer questions concisely, clearly, and confidently — as if the user is speaking. "
        "For coding questions provide clean code with a brief explanation. "
        "For behavioural questions use the STAR method. "
        "Keep answers under 200 words unless the question is complex. "
        "Do NOT reveal you are an AI."
    )

    # ── Audio / Speech-to-text ───────────────────────────────────────────
    # STT backend: "google" (free, needs internet) | "whisper" (local)
    STT_BACKEND: str = "google"

    # Whisper model size if STT_BACKEND == "whisper"
    # Sizes: tiny, base, small, medium, large
    WHISPER_MODEL: str = "base"

    # Silence threshold (seconds) before a phrase is considered complete
    PAUSE_THRESHOLD: float = 1.2

    # Minimum phrase duration to process (seconds)
    MIN_PHRASE_DURATION: float = 1.0

    # Microphone device index (None = system default)
    MIC_INDEX: int = None

    # ── UI ───────────────────────────────────────────────────────────────
    # Window always on top
    ALWAYS_ON_TOP: bool = True

    # Default window opacity (0.0 – 1.0)
    OPACITY: float = 0.95

    # Font size
    FONT_SIZE: int = 13

    # Theme: "dark" | "light"
    THEME: str = "dark"

    # Hotkeys
    HOTKEY_TOGGLE_LISTEN: str = "<F9>"
    HOTKEY_CLEAR:         str = "<F10>"
    HOTKEY_HIDE:          str = "<F11>"

    # ── Persistence ─────────────────────────────────────────────────────
    def __init__(self):
        self._load_from_file()

    def _load_from_file(self):
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text())
                for k, v in data.items():
                    if hasattr(self, k):
                        setattr(self, k, v)
            except Exception:
                pass

    def save(self):
        data = {k: getattr(self, k) for k in dir(self)
                if k.isupper() and not k.startswith("_")}
        CONFIG_FILE.write_text(json.dumps(data, indent=2))

    def update(self, new_values: dict):
        for k, v in new_values.items():
            if hasattr(self, k):
                setattr(self, k, v)
        self.save()
