"""
ui/overlay.py — The floating overlay window.

KEY FEATURE — Screen-share invisibility:
  • Windows : SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE=0x11)
  • macOS   : setSharingType_(NSWindowSharingNone=0)
  • Linux   : Not natively supported; window is hidden via opacity trick tip.

The window is always-on-top, semi-transparent, and keyboard-shortcut driven.
"""

from __future__ import annotations
import sys
import platform
import queue
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import time


# ── Colour palettes ─────────────────────────────────────────────────────────

DARK = {
    "bg":         "#0d0d0d",
    "panel":      "#141414",
    "border":     "#2a2a2a",
    "accent":     "#00e5ff",
    "accent2":    "#7c4dff",
    "text":       "#e8e8e8",
    "muted":      "#888888",
    "q_bg":       "#1a1a2e",
    "a_bg":       "#0a1628",
    "success":    "#00e676",
    "warning":    "#ff6d00",
    "error":      "#ff1744",
    "thinking":   "#ffd740",
}

LIGHT = {
    "bg":         "#f4f4f8",
    "panel":      "#ffffff",
    "border":     "#d0d0d8",
    "accent":     "#0060df",
    "accent2":    "#7c4dff",
    "text":       "#1a1a2e",
    "muted":      "#666688",
    "q_bg":       "#eaf0ff",
    "a_bg":       "#f0f8ff",
    "success":    "#00897b",
    "warning":    "#e65100",
    "error":      "#b71c1c",
    "thinking":   "#f57f17",
}


class OverlayWindow:
    def __init__(self, config, answer_queue: queue.Queue):
        self.config       = config
        self.answer_queue = answer_queue
        self.C            = DARK if config.THEME == "dark" else LIGHT

        # Callbacks wired by app.py
        self.on_manual_question: callable = lambda q: None
        self.on_toggle_listen:   callable = lambda b: None
        self.on_clear:           callable = lambda: None
        self.on_settings_save:   callable = lambda d: None

        self._listening  = False
        self._minimised  = False
        self._qa_items   = []          # list of (question, answer) for history

        self._build_ui()
        self._apply_screen_share_exclusion()
        self._bind_hotkeys()
        self._start_answer_poller()

    # ================================================================== #
    #  UI Construction                                                     #
    # ================================================================== #

    def _build_ui(self):
        self.root = tk.Tk()
        self.root.title("Interview Assistant")
        self.root.geometry("680x780+60+60")
        self.root.configure(bg=self.C["bg"])
        self.root.attributes("-topmost", self.config.ALWAYS_ON_TOP)
        self.root.attributes("-alpha", self.config.OPACITY)
        self.root.resizable(True, True)

        # Remove window chrome (optional — comment out if you want title bar)
        # self.root.overrideredirect(True)

        self._build_titlebar()
        self._build_status_bar()
        self._build_qa_area()
        self._build_input_area()
        self._build_settings_panel()   # hidden by default

        # Handle close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Title bar ────────────────────────────────────────────────────────

    def _build_titlebar(self):
        bar = tk.Frame(self.root, bg=self.C["panel"], height=48)
        bar.pack(fill=tk.X, side=tk.TOP)

        # Logo / title
        tk.Label(
            bar, text="⚡ Interview Assistant",
            font=("Courier New", 13, "bold"),
            bg=self.C["panel"], fg=self.C["accent"],
        ).pack(side=tk.LEFT, padx=14, pady=10)

        # Right-side controls
        ctrl = tk.Frame(bar, bg=self.C["panel"])
        ctrl.pack(side=tk.RIGHT, padx=8)

        self._btn_settings = self._icon_btn(ctrl, "⚙", self._toggle_settings)
        self._btn_settings.pack(side=tk.RIGHT, padx=3)

        self._btn_clear = self._icon_btn(ctrl, "🗑", self._do_clear)
        self._btn_clear.pack(side=tk.RIGHT, padx=3)

        self._btn_min = self._icon_btn(ctrl, "▂", self._toggle_minimise)
        self._btn_min.pack(side=tk.RIGHT, padx=3)

        # Separator
        tk.Frame(self.root, bg=self.C["border"], height=1).pack(fill=tk.X)

    # ── Status bar ───────────────────────────────────────────────────────

    def _build_status_bar(self):
        bar = tk.Frame(self.root, bg=self.C["panel"], height=40)
        bar.pack(fill=tk.X)

        # Mic toggle button
        self._mic_btn = tk.Button(
            bar, text="🎙 Start Listening",
            font=("Courier New", 10, "bold"),
            bg=self.C["border"], fg=self.C["text"],
            activebackground=self.C["accent"], activeforeground="#000",
            relief=tk.FLAT, padx=12, pady=6,
            cursor="hand2", command=self._toggle_mic,
        )
        self._mic_btn.pack(side=tk.LEFT, padx=10, pady=5)

        # Status label
        self._status_var = tk.StringVar(value="Ready  •  F9 to listen  •  F10 clear  •  F11 hide")
        tk.Label(
            bar, textvariable=self._status_var,
            font=("Courier New", 9), bg=self.C["panel"], fg=self.C["muted"],
        ).pack(side=tk.LEFT, padx=6)

        # Live indicator dot
        self._dot_var = tk.StringVar(value="●")
        self._dot_lbl = tk.Label(
            bar, textvariable=self._dot_var,
            font=("Arial", 14), bg=self.C["panel"], fg=self.C["muted"],
        )
        self._dot_lbl.pack(side=tk.RIGHT, padx=10)

        tk.Frame(self.root, bg=self.C["border"], height=1).pack(fill=tk.X)

    # ── Q&A scroll area ──────────────────────────────────────────────────

    def _build_qa_area(self):
        container = tk.Frame(self.root, bg=self.C["bg"])
        container.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        # Canvas + scrollbar for custom Q&A cards
        self._canvas = tk.Canvas(container, bg=self.C["bg"], highlightthickness=0)
        self._scrollbar = ttk.Scrollbar(container, orient="vertical",
                                        command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._cards_frame = tk.Frame(self._canvas, bg=self.C["bg"])
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._cards_frame, anchor="nw"
        )

        self._cards_frame.bind("<Configure>", self._on_cards_resize)
        self._canvas.bind("<Configure>",      self._on_canvas_resize)
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Welcome message
        self._add_welcome_card()

    def _add_welcome_card(self):
        f = tk.Frame(self._cards_frame, bg=self.C["panel"],
                     relief=tk.FLAT, bd=0)
        f.pack(fill=tk.X, padx=4, pady=6)

        header = tk.Frame(f, bg=self.C["accent2"], height=3)
        header.pack(fill=tk.X)

        body = tk.Frame(f, bg=self.C["panel"])
        body.pack(fill=tk.X, padx=12, pady=10)

        tk.Label(
            body, text="👋  Welcome to Interview Assistant",
            font=("Courier New", 12, "bold"),
            bg=self.C["panel"], fg=self.C["accent"],
            anchor="w",
        ).pack(fill=tk.X)

        tips = (
            "• Press F9 to start/stop mic listening\n"
            "• Type a question below and press Enter or ↵\n"
            "• F10 clears history  •  F11 hides the window\n"
            "• This window is INVISIBLE to screen-share software"
        )
        tk.Label(
            body, text=tips,
            font=("Courier New", 10),
            bg=self.C["panel"], fg=self.C["muted"],
            justify=tk.LEFT, anchor="w",
        ).pack(fill=tk.X, pady=(6, 0))

    # ── Input area ───────────────────────────────────────────────────────

    def _build_input_area(self):
        tk.Frame(self.root, bg=self.C["border"], height=1).pack(fill=tk.X)

        frame = tk.Frame(self.root, bg=self.C["panel"], pady=8)
        frame.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Label(frame, text="Ask:", font=("Courier New", 10, "bold"),
                 bg=self.C["panel"], fg=self.C["muted"]).pack(side=tk.LEFT, padx=(10, 4))

        self._input_var = tk.StringVar()
        self._input = tk.Entry(
            frame, textvariable=self._input_var,
            font=("Courier New", 11),
            bg=self.C["bg"], fg=self.C["text"],
            insertbackground=self.C["accent"],
            relief=tk.FLAT, bd=0,
        )
        self._input.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=4)
        self._input.bind("<Return>", self._on_submit)

        send_btn = tk.Button(
            frame, text="Send ↵",
            font=("Courier New", 10, "bold"),
            bg=self.C["accent2"], fg="#fff",
            activebackground=self.C["accent"], activeforeground="#000",
            relief=tk.FLAT, padx=10, pady=6,
            cursor="hand2", command=self._on_submit,
        )
        send_btn.pack(side=tk.RIGHT, padx=(4, 10))

    # ── Settings panel ───────────────────────────────────────────────────

    def _build_settings_panel(self):
        self._settings_visible = False
        self._settings_frame = tk.Frame(
            self.root, bg=self.C["panel"], relief=tk.FLAT, bd=1,
        )
        # Don't pack yet — toggled by button

        tk.Label(
            self._settings_frame, text="⚙  Settings",
            font=("Courier New", 12, "bold"),
            bg=self.C["panel"], fg=self.C["accent"],
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 6))

        fields = [
            ("AI Provider", "AI_PROVIDER", ["anthropic", "openai"]),
            ("Anthropic API Key", "ANTHROPIC_API_KEY", None),
            ("OpenAI API Key",    "OPENAI_API_KEY",    None),
            ("STT Backend",      "STT_BACKEND", ["google", "whisper"]),
            ("Opacity (0–1)",    "OPACITY",           None),
            ("Font Size",        "FONT_SIZE",         None),
            ("Theme",            "THEME",   ["dark", "light"]),
        ]

        self._setting_vars: dict[str, tk.Variable] = {}

        for i, (label, key, options) in enumerate(fields, start=1):
            tk.Label(
                self._settings_frame, text=label,
                font=("Courier New", 10),
                bg=self.C["panel"], fg=self.C["muted"],
            ).grid(row=i, column=0, sticky="w", padx=12, pady=3)

            current = getattr(self.config, key, "")

            if options:
                var = tk.StringVar(value=str(current))
                widget = ttk.Combobox(self._settings_frame, textvariable=var,
                                      values=options, state="readonly", width=22)
            else:
                show_char = "*" if "KEY" in key else ""
                var = tk.StringVar(value=str(current))
                widget = tk.Entry(self._settings_frame, textvariable=var,
                                  show=show_char, width=26,
                                  bg=self.C["bg"], fg=self.C["text"],
                                  insertbackground=self.C["accent"], relief=tk.FLAT)

            widget.grid(row=i, column=1, padx=12, pady=3, sticky="w")
            self._setting_vars[key] = var

        # System prompt
        tk.Label(
            self._settings_frame, text="System Prompt",
            font=("Courier New", 10),
            bg=self.C["panel"], fg=self.C["muted"],
        ).grid(row=len(fields) + 1, column=0, sticky="nw", padx=12, pady=3)

        self._prompt_text = tk.Text(
            self._settings_frame,
            font=("Courier New", 9),
            bg=self.C["bg"], fg=self.C["text"],
            insertbackground=self.C["accent"],
            relief=tk.FLAT, height=4, width=42, wrap=tk.WORD,
        )
        self._prompt_text.insert("1.0", self.config.SYSTEM_PROMPT)
        self._prompt_text.grid(row=len(fields) + 1, column=1, padx=12, pady=3, sticky="w")

        save_btn = tk.Button(
            self._settings_frame, text="💾  Save & Apply",
            font=("Courier New", 10, "bold"),
            bg=self.C["success"], fg="#000",
            relief=tk.FLAT, padx=10, pady=6,
            cursor="hand2", command=self._save_settings,
        )
        save_btn.grid(row=len(fields) + 2, column=0, columnspan=2,
                      padx=12, pady=10, sticky="w")

    # ================================================================== #
    #  Q&A Cards                                                           #
    # ================================================================== #

    def _add_qa_card(self, question: str, answer: str, source: str = "manual"):
        """Render a question + answer card in the scroll area."""
        source_icon = "🎙" if source == "mic" else "⌨"

        card = tk.Frame(self._cards_frame, bg=self.C["panel"],
                        relief=tk.FLAT, bd=0)
        card.pack(fill=tk.X, padx=4, pady=4)

        # Accent top strip
        accent_color = self.C["accent"] if source == "mic" else self.C["accent2"]
        tk.Frame(card, bg=accent_color, height=2).pack(fill=tk.X)

        body = tk.Frame(card, bg=self.C["panel"])
        body.pack(fill=tk.X, padx=12, pady=8)

        # Question row
        q_frame = tk.Frame(body, bg=self.C["q_bg"])
        q_frame.pack(fill=tk.X, pady=(0, 6))

        tk.Label(q_frame, text=f"{source_icon}  Q:",
                 font=("Courier New", 9, "bold"),
                 bg=self.C["q_bg"], fg=self.C["accent"],
                 ).pack(side=tk.LEFT, padx=8, pady=6)

        q_lbl = tk.Label(q_frame, text=question,
                         font=("Courier New", 10),
                         bg=self.C["q_bg"], fg=self.C["text"],
                         justify=tk.LEFT, anchor="w", wraplength=520)
        q_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), pady=6)

        # Answer
        a_frame = tk.Frame(body, bg=self.C["a_bg"])
        a_frame.pack(fill=tk.X)

        tk.Label(a_frame, text="💡 A:",
                 font=("Courier New", 9, "bold"),
                 bg=self.C["a_bg"], fg=self.C["success"],
                 ).pack(side=tk.LEFT, padx=8, pady=6, anchor="n")

        a_lbl = tk.Label(a_frame, text=answer,
                         font=("Courier New", self.config.FONT_SIZE),
                         bg=self.C["a_bg"], fg=self.C["text"],
                         justify=tk.LEFT, anchor="w",
                         wraplength=490)
        a_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), pady=8)

        # Copy button
        tk.Button(
            body, text="📋 Copy",
            font=("Courier New", 8),
            bg=self.C["border"], fg=self.C["muted"],
            relief=tk.FLAT, padx=6, pady=2,
            cursor="hand2",
            command=lambda a=answer: self._copy_to_clipboard(a),
        ).pack(anchor="e", pady=(4, 0))

        self._scroll_to_bottom()
        self._qa_items.append((question, answer))

    def _add_thinking_card(self, question: str, source: str):
        """Show 'thinking…' card; returns card frame for later removal."""
        card = tk.Frame(self._cards_frame, bg=self.C["panel"])
        card.pack(fill=tk.X, padx=4, pady=4)
        tk.Frame(card, bg=self.C["thinking"], height=2).pack(fill=tk.X)

        inner = tk.Frame(card, bg=self.C["panel"])
        inner.pack(fill=tk.X, padx=12, pady=8)

        source_icon = "🎙" if source == "mic" else "⌨"
        tk.Label(inner, text=f"{source_icon}  {question}",
                 font=("Courier New", 10),
                 bg=self.C["panel"], fg=self.C["muted"],
                 wraplength=560, justify=tk.LEFT).pack(anchor="w")

        self._thinking_lbl_var = tk.StringVar(value="⏳  Thinking…")
        tk.Label(inner, textvariable=self._thinking_lbl_var,
                 font=("Courier New", 10, "italic"),
                 bg=self.C["panel"], fg=self.C["thinking"]).pack(anchor="w", pady=4)

        self._scroll_to_bottom()
        return card

    # ================================================================== #
    #  Public methods called by app.py                                     #
    # ================================================================== #

    def show_thinking(self, question: str, source: str):
        """Show thinking indicator (called from background thread)."""
        self.root.after(0, lambda: self._show_thinking_main(question, source))

    def _show_thinking_main(self, question: str, source: str):
        self._pending_card = self._add_thinking_card(question, source)

    def run(self):
        """Start Tkinter main loop."""
        self.root.mainloop()

    # ================================================================== #
    #  Event handlers                                                      #
    # ================================================================== #

    def _on_submit(self, event=None):
        text = self._input_var.get().strip()
        if text:
            self._input_var.set("")
            self.on_manual_question(text)

    def _toggle_mic(self):
        self._listening = not self._listening
        if self._listening:
            self._mic_btn.configure(
                text="🔴 Stop Listening",
                bg=self.C["error"], fg="#fff",
            )
            self._status_var.set("🎙 Listening — speak your question…")
            self._dot_var.set("●")
            self._dot_lbl.configure(fg=self.C["success"])
            self._animate_dot()
        else:
            self._mic_btn.configure(
                text="🎙 Start Listening",
                bg=self.C["border"], fg=self.C["text"],
            )
            self._status_var.set("Ready  •  F9 to listen  •  F10 clear  •  F11 hide")
            self._dot_var.set("●")
            self._dot_lbl.configure(fg=self.C["muted"])

        self.on_toggle_listen(self._listening)

    def _animate_dot(self):
        if not self._listening:
            return
        current = self._dot_var.get()
        self._dot_var.set("○" if current == "●" else "●")
        self.root.after(600, self._animate_dot)

    def _do_clear(self):
        for widget in self._cards_frame.winfo_children():
            widget.destroy()
        self._qa_items.clear()
        self._add_welcome_card()
        self.on_clear()

    def _toggle_minimise(self):
        self._minimised = not self._minimised
        if self._minimised:
            self.root.geometry("680x48")
        else:
            self.root.geometry("680x780")

    def _toggle_settings(self):
        self._settings_visible = not self._settings_visible
        if self._settings_visible:
            self._settings_frame.pack(fill=tk.X, side=tk.BOTTOM,
                                      before=self._input_bar_ref())
        else:
            self._settings_frame.pack_forget()

    def _input_bar_ref(self):
        # Return the input frame widget (last packed before settings)
        return self.root.winfo_children()[-1]

    def _save_settings(self):
        new_vals = {k: var.get() for k, var in self._setting_vars.items()}
        try:
            new_vals["OPACITY"]   = float(new_vals.get("OPACITY", 0.95))
            new_vals["FONT_SIZE"] = int(new_vals.get("FONT_SIZE", 13))
        except ValueError:
            pass
        new_vals["SYSTEM_PROMPT"] = self._prompt_text.get("1.0", tk.END).strip()
        self.on_settings_save(new_vals)
        self.root.attributes("-alpha", new_vals.get("OPACITY", self.config.OPACITY))
        messagebox.showinfo("Settings", "Settings saved! Restart mic if you changed STT backend.")
        self._toggle_settings()

    def _copy_to_clipboard(self, text: str):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._status_var.set("Copied to clipboard ✓")
        self.root.after(2000, lambda: self._status_var.set(
            "Ready  •  F9 to listen  •  F10 clear  •  F11 hide"
        ))

    def _on_close(self):
        self.root.quit()
        self.root.destroy()

    # ================================================================== #
    #  Answer poller — reads from answer_queue, updates UI                #
    # ================================================================== #

    def _start_answer_poller(self):
        self._poll_answers()

    def _poll_answers(self):
        try:
            while True:
                item = self.answer_queue.get_nowait()
                # Remove thinking card if present
                if hasattr(self, "_pending_card") and self._pending_card:
                    self._pending_card.destroy()
                    self._pending_card = None
                self._add_qa_card(item["question"], item["answer"], item.get("source", "manual"))
        except queue.Empty:
            pass
        self.root.after(100, self._poll_answers)

    # ================================================================== #
    #  Hotkeys                                                             #
    # ================================================================== #

    def _bind_hotkeys(self):
        self.root.bind(self.config.HOTKEY_TOGGLE_LISTEN, lambda e: self._toggle_mic())
        self.root.bind(self.config.HOTKEY_CLEAR,         lambda e: self._do_clear())
        self.root.bind(self.config.HOTKEY_HIDE,          lambda e: self._toggle_hide())

    def _toggle_hide(self):
        if self.root.state() == "withdrawn":
            self.root.deiconify()
        else:
            self.root.withdraw()

    # ================================================================== #
    #  Scroll helpers                                                      #
    # ================================================================== #

    def _on_cards_resize(self, event):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _scroll_to_bottom(self):
        self.root.after(50, lambda: self._canvas.yview_moveto(1.0))

    # ================================================================== #
    #  SCREEN-SHARE INVISIBILITY                                           #
    # ================================================================== #

    def _apply_screen_share_exclusion(self):
        """
        Makes this window invisible to screen-share / capture software.
        Must be called AFTER the window is created and mapped.
        """
        self.root.update_idletasks()   # ensure HWND is allocated
        system = platform.system()

        if system == "Windows":
            self._exclude_windows()
        elif system == "Darwin":
            self._exclude_macos()
        else:
            self._exclude_linux_tip()

    def _exclude_windows(self):
        """
        SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        WDA_EXCLUDEFROMCAPTURE = 0x00000011  (requires Windows 10 2004+)
        """
        try:
            import ctypes
            import ctypes.wintypes

            hwnd = ctypes.windll.user32.GetForegroundWindow()
            # Prefer the actual Tk HWND
            try:
                hwnd = self.root.winfo_id()
            except Exception:
                pass

            WDA_EXCLUDEFROMCAPTURE = 0x00000011
            result = ctypes.windll.user32.SetWindowDisplayAffinity(
                hwnd, WDA_EXCLUDEFROMCAPTURE
            )
            if result:
                print("[Overlay] ✅ Windows: Screen-share exclusion applied.")
            else:
                err = ctypes.GetLastError()
                print(f"[Overlay] ⚠️  SetWindowDisplayAffinity failed (err={err}). "
                      "Requires Windows 10 v2004+ and a non-elevated process.")
        except Exception as e:
            print(f"[Overlay] Windows exclusion error: {e}")

    def _exclude_macos(self):
        """
        Use PyObjC to set NSWindowSharingNone on the native window.
        Requires:  pip install pyobjc-framework-Cocoa
        """
        try:
            from AppKit import NSApplication, NSWindowSharingNone
            app = NSApplication.sharedApplication()
            # Find the native window that wraps the Tk window
            for win in app.windows():
                try:
                    win.setSharingType_(NSWindowSharingNone)
                except Exception:
                    pass
            print("[Overlay] ✅ macOS: Screen-share exclusion applied.")
        except ImportError:
            print("[Overlay] ⚠️  macOS exclusion: Install pyobjc-framework-Cocoa  →  "
                  "pip install pyobjc-framework-Cocoa")
        except Exception as e:
            print(f"[Overlay] macOS exclusion error: {e}")

    def _exclude_linux_tip(self):
        """
        Linux has no reliable API for this; workarounds exist per-compositor.
        We print a tip.
        """
        print(
            "[Overlay] ℹ️  Linux: True screen-share exclusion requires compositor support.\n"
            "   Tip: Use a virtual display (Xephyr / Xvfb) and share only the interview\n"
            "   browser window, keeping this tool on the hidden display."
        )

    # ================================================================== #
    #  Utility                                                             #
    # ================================================================== #

    def _icon_btn(self, parent, icon: str, command) -> tk.Button:
        return tk.Button(
            parent, text=icon,
            font=("Arial", 13),
            bg=self.C["panel"], fg=self.C["muted"],
            activebackground=self.C["border"], activeforeground=self.C["text"],
            relief=tk.FLAT, padx=6, pady=2,
            cursor="hand2", command=command,
        )
