"""
ai/engine.py — Handles AI inference.
Supports Anthropic (Claude) and OpenAI (GPT-4o) with conversation history.
"""

from __future__ import annotations
from collections import deque
from typing import Optional
import importlib


class AIEngine:
    def __init__(self, config):
        self.config  = config
        self._history: deque = deque(maxlen=config.HISTORY_DEPTH * 2)  # user+assistant pairs
        self._client = None
        self._init_client()

    # ------------------------------------------------------------------ #
    #  Public                                                              #
    # ------------------------------------------------------------------ #

    def get_answer(self, question: str) -> str:
        """Return AI answer for the given question."""
        try:
            self._history.append({"role": "user", "content": question})

            if self.config.AI_PROVIDER == "anthropic":
                answer = self._call_anthropic()
            else:
                answer = self._call_openai()

            self._history.append({"role": "assistant", "content": answer})
            return answer

        except Exception as e:
            error_msg = self._friendly_error(e)
            return f"⚠️ {error_msg}"

    def clear_history(self):
        self._history.clear()

    def reload(self, config):
        self.config = config
        self._history = deque(maxlen=config.HISTORY_DEPTH * 2)
        self._init_client()

    # ------------------------------------------------------------------ #
    #  Anthropic                                                           #
    # ------------------------------------------------------------------ #

    def _call_anthropic(self) -> str:
        if not self._client:
            raise RuntimeError("Anthropic client not initialised. Check API key.")

        response = self._client.messages.create(
            model=self.config.ANTHROPIC_MODEL,
            max_tokens=self.config.MAX_TOKENS,
            system=self.config.SYSTEM_PROMPT,
            messages=list(self._history),
        )
        return response.content[0].text

    # ------------------------------------------------------------------ #
    #  OpenAI                                                              #
    # ------------------------------------------------------------------ #

    def _call_openai(self) -> str:
        if not self._client:
            raise RuntimeError("OpenAI client not initialised. Check API key.")

        messages = [{"role": "system", "content": self.config.SYSTEM_PROMPT}]
        messages.extend(list(self._history))

        response = self._client.chat.completions.create(
            model=self.config.OPENAI_MODEL,
            max_tokens=self.config.MAX_TOKENS,
            messages=messages,
        )
        return response.choices[0].message.content

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _init_client(self):
        self._client = None
        try:
            if self.config.AI_PROVIDER == "anthropic":
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.config.ANTHROPIC_API_KEY)
            else:
                import openai
                self._client = openai.OpenAI(api_key=self.config.OPENAI_API_KEY)
        except ImportError as e:
            print(f"[AIEngine] Missing library: {e}. Install via requirements.txt")
        except Exception as e:
            print(f"[AIEngine] Init error: {e}")

    @staticmethod
    def _friendly_error(e: Exception) -> str:
        msg = str(e).lower()
        if "api_key" in msg or "authentication" in msg or "401" in msg:
            return "Invalid API key. Open Settings (⚙) and enter a valid key."
        if "rate" in msg or "429" in msg:
            return "Rate limit reached. Please wait a moment and try again."
        if "network" in msg or "connection" in msg:
            return "Network error. Check your internet connection."
        return f"AI error: {e}"
