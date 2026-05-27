from __future__ import annotations

import queue
import os
import threading
import tkinter as tk
from tkinter import scrolledtext
from tkinter import ttk

from app import config
from app.transcriber import ALLOWED_MODELS
from app.pipeline import run_realtime_translation_loop


class TranslatorWindow(tk.Tk):
    """Simple always-on-top UI for the validated console pipeline."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Local Live Translator")
        self.geometry("760x300")
        self.minsize(560, 240)
        self.attributes("-topmost", True)

        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.messages: queue.Queue[tuple[str, str, str | None]] = queue.Queue()

        self.status_var = tk.StringVar(value="Stopped")
        self.model_var = tk.StringVar(value=config.WHISPER_MODEL)
        self.backend_var = tk.StringVar(value=config.TRANSLATION_BACKEND)
        self.transcript_var = tk.StringVar(value="Transcript: not started")
        self.history: list[tuple[str, str]] = []

        self._build_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.process_messages)

    def _build_widgets(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(root)
        toolbar.pack(fill=tk.X)

        self.start_button = ttk.Button(toolbar, text="Start", command=self.start_capture)
        self.start_button.pack(side=tk.LEFT)

        self.stop_button = ttk.Button(toolbar, text="Stop", command=self.stop_capture, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=(8, 0))

        self.clear_button = ttk.Button(toolbar, text="Clear", command=self.clear_history)
        self.clear_button.pack(side=tk.LEFT, padx=(8, 0))

        self.open_transcripts_button = ttk.Button(
            toolbar,
            text="Open Transcripts",
            command=self.open_transcripts_folder,
        )
        self.open_transcripts_button.pack(side=tk.LEFT, padx=(8, 0))

        status = ttk.Label(toolbar, textvariable=self.status_var)
        status.pack(side=tk.LEFT, padx=(16, 0))

        self.model_combo = ttk.Combobox(
            toolbar,
            textvariable=self.model_var,
            values=[model for model in ("small.en", "medium.en", "large-v3-turbo") if model in ALLOWED_MODELS],
            width=14,
            state="readonly",
        )
        self.model_combo.pack(side=tk.LEFT, padx=(16, 0))

        self.backend_combo = ttk.Combobox(
            toolbar,
            textvariable=self.backend_var,
            values=["marian", "argos"],
            width=8,
            state="readonly",
        )
        self.backend_combo.pack(side=tk.LEFT, padx=(8, 0))

        settings = (
            f"chunk={config.CHUNK_SECONDS}s | device={config.WHISPER_DEVICE} | compute={config.WHISPER_COMPUTE_TYPE} | "
            f"beam={config.WHISPER_BEAM_SIZE}"
        )
        settings_label = ttk.Label(toolbar, text=settings)
        settings_label.pack(side=tk.RIGHT)

        transcript_label = ttk.Label(root, textvariable=self.transcript_var)
        transcript_label.pack(fill=tk.X, pady=(8, 0))

        content = ttk.Frame(root)
        content.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        self.history_text = scrolledtext.ScrolledText(
            content,
            wrap=tk.WORD,
            font=("Segoe UI", 11),
            height=8,
            state=tk.DISABLED,
        )
        self.history_text.grid(row=0, column=0, sticky="nsew")
        self.history_text.tag_configure("en", font=("Segoe UI", 10), foreground="#404040")
        self.history_text.tag_configure("es", font=("Segoe UI", 13, "bold"), foreground="#000000")
        self.history_text.tag_configure("gap", spacing3=10)

        self.bind("<Configure>", self._update_wraplength)

    def _update_wraplength(self, _event: tk.Event) -> None:
        wrap = max(self.winfo_width() - 48, 320)
        for child in self.winfo_children():
            self._set_wraplength_recursive(child, wrap)

    def _set_wraplength_recursive(self, widget: tk.Widget, wrap: int) -> None:
        if isinstance(widget, ttk.Label):
            try:
                widget.configure(wraplength=wrap)
            except tk.TclError:
                pass
        for child in widget.winfo_children():
            self._set_wraplength_recursive(child, wrap)

    def start_capture(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        self.stop_event.clear()
        self.start_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)
        self.model_combo.configure(state=tk.DISABLED)
        self.backend_combo.configure(state=tk.DISABLED)
        self.status_var.set("Loading models...")

        self.worker = threading.Thread(target=self._worker_main, daemon=True)
        self.worker.start()

    def stop_capture(self) -> None:
        self.stop_event.set()
        self.status_var.set("Stopping after current chunk...")
        self.stop_button.configure(state=tk.DISABLED)

    def _worker_main(self) -> None:
        def on_translation(english: str, spanish: str) -> None:
            self.messages.put(("translation", english, spanish))

        def on_error(exc: Exception) -> None:
            self.messages.put(("error", f"{type(exc).__name__}: {exc}", None))

        def on_status(status: str) -> None:
            self.messages.put(("status", status, None))

        def on_transcript(path) -> None:
            self.messages.put(("transcript", str(path), None))

        self.messages.put(("status", "Running", None))
        try:
            run_realtime_translation_loop(
                chunk_seconds=config.CHUNK_SECONDS,
                model_name=self.model_var.get(),
                whisper_device=config.WHISPER_DEVICE,
                compute_type=config.WHISPER_COMPUTE_TYPE,
                beam_size=config.WHISPER_BEAM_SIZE,
                audio_device_index=config.AUDIO_DEVICE_INDEX,
                max_queue_chunks=config.MAX_AUDIO_QUEUE_CHUNKS,
                translation_backend=self.backend_var.get(),
                on_translation=on_translation,
                on_error=on_error,
                on_status=on_status,
                on_transcript=on_transcript,
                stop_event=self.stop_event,
            )
        finally:
            self.messages.put(("stopped", "Stopped", None))

    def process_messages(self) -> None:
        while True:
            try:
                kind, first, second = self.messages.get_nowait()
            except queue.Empty:
                break

            if kind == "translation":
                self.status_var.set("Running")
                self.add_history(first, second or "")
            elif kind == "error":
                self.status_var.set(f"ERROR: {first}")
            elif kind == "status":
                self.status_var.set(first)
            elif kind == "transcript":
                self.transcript_var.set(f"Transcript: {first}")
            elif kind == "stopped":
                self.status_var.set(first)
                self.start_button.configure(state=tk.NORMAL)
                self.stop_button.configure(state=tk.DISABLED)
                self.model_combo.configure(state="readonly")
                self.backend_combo.configure(state="readonly")

        self.after(100, self.process_messages)

    def add_history(self, english: str, spanish: str) -> None:
        self.history.append((english, spanish))
        self.history = self.history[-config.UI_HISTORY_LINES :]

        self.history_text.configure(state=tk.NORMAL)
        self.history_text.delete("1.0", tk.END)
        for english_text, spanish_text in self.history:
            self.history_text.insert(tk.END, f"EN: {english_text}\n", "en")
            self.history_text.insert(tk.END, f"ES: {spanish_text}\n\n", ("es", "gap"))
        self.history_text.see(tk.END)
        self.history_text.configure(state=tk.DISABLED)

    def clear_history(self) -> None:
        self.history.clear()
        self.history_text.configure(state=tk.NORMAL)
        self.history_text.delete("1.0", tk.END)
        self.history_text.configure(state=tk.DISABLED)

    def open_transcripts_folder(self) -> None:
        config.TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(config.TRANSCRIPTS_DIR)

    def on_close(self) -> None:
        self.stop_event.set()
        self.destroy()


def main() -> None:
    app = TranslatorWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
