"""
Atlas window app: a simple chat window for the voice assistant.
It uses the same brain, memory, tools and voice as voice_assistant.py.

How to run:
  python atlas_app.py      (or double-click the "Atlas" shortcut on the Desktop)

  - Type a message and press Enter (or click Send).
  - Click "Talk", speak, then click "Stop & send".
  - Click "Stop voice" to make Atlas stop talking.
"""

import os
import queue
import re
import sys
import threading
import tkinter as tk
from tkinter import scrolledtext

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# When started by double-click there is no terminal, so messages and errors
# go to atlas_log.txt instead (useful if something goes wrong).
if sys.stdout is None or sys.stderr is None:
    log_file = open(os.path.join(PROJECT_DIR, "atlas_log.txt"), "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log_file

import atlas_tools
import voice_assistant as va

# Colors
BG = "#1e1e2e"
PANEL = "#2a2a3c"
TEXT = "#e0e0e8"
YOU = "#7aa2f7"
ATLAS = "#9ece6a"
INFO = "#8a8aa0"
FONT = ("Segoe UI", 11)


class AtlasApp:
    def __init__(self, root):
        self.root = root
        self.ui_queue = queue.Queue()  # background threads put UI updates here
        self.busy = True               # True while loading, thinking or speaking
        self.recording = False
        self.speak_answers = True
        self.recorder = va.Recorder()
        self.whisper = None
        self.kokoro = None
        self.history = va.new_history()

        self.build_window()
        atlas_tools.on_reminder = self.on_reminder
        self.root.after(100, self.process_queue)
        threading.Thread(target=self.load_models, daemon=True).start()

    # ---------- Window ----------

    def build_window(self):
        self.root.title(va.ASSISTANT_NAME)
        self.root.geometry("560x680")
        self.root.minsize(400, 420)
        self.root.configure(bg=BG)

        self.chat = scrolledtext.ScrolledText(
            self.root, wrap="word", state="disabled", font=FONT, bg=BG, fg=TEXT,
            relief="flat", padx=12, pady=12, borderwidth=0)
        self.chat.pack(fill="both", expand=True)
        self.chat.tag_config("you", foreground=YOU, font=(FONT[0], FONT[1], "bold"))
        self.chat.tag_config("atlas", foreground=ATLAS, font=(FONT[0], FONT[1], "bold"))
        self.chat.tag_config("info", foreground=INFO, font=(FONT[0], 10, "italic"))

        bottom = tk.Frame(self.root, bg=PANEL, padx=10, pady=10)
        bottom.pack(fill="x")

        self.entry = tk.Entry(bottom, font=FONT, bg=BG, fg=TEXT, insertbackground=TEXT,
                              relief="flat")
        self.entry.pack(fill="x", ipady=6)
        self.entry.bind("<Return>", self.send_typed)
        self.entry.focus_set()

        buttons = tk.Frame(bottom, bg=PANEL)
        buttons.pack(fill="x", pady=(8, 0))
        style = dict(font=FONT, relief="flat", bg="#3b3b55", fg=TEXT,
                     activebackground="#4a4a6a", activeforeground=TEXT, padx=12, pady=4)
        self.send_button = tk.Button(buttons, text="Send", command=self.send_typed, **style)
        self.send_button.pack(side="left")
        self.talk_button = tk.Button(buttons, text="Talk", command=self.toggle_talk, **style)
        self.talk_button.pack(side="left", padx=6)
        tk.Button(buttons, text="Stop voice", command=va.stop_speaking, **style).pack(side="left")

        self.voice_check = tk.BooleanVar(value=True)
        tk.Checkbutton(buttons, text="Speak answers", variable=self.voice_check,
                       command=self.on_voice_toggle, font=FONT, bg=PANEL, fg=TEXT,
                       selectcolor=BG, activebackground=PANEL, activeforeground=TEXT
                       ).pack(side="right")

        self.status = tk.Label(self.root, text="Starting...", anchor="w", font=(FONT[0], 9),
                               bg=PANEL, fg=INFO, padx=10, pady=4)
        self.status.pack(fill="x")
        self.set_busy(True)

    def add_message(self, who, text, tag):
        """Add a line to the chat, e.g. add_message("You", "hi", "you")."""
        text = re.sub(r"[\U00010000-\U0010FFFF]", "", text)  # emojis can break the window
        self.chat.configure(state="normal")
        if who:
            self.chat.insert("end", f"{who}: ", tag)
            self.chat.insert("end", text + "\n\n")
        else:
            self.chat.insert("end", text + "\n\n", tag)
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def add_info(self, text):
        self.add_message(None, text, "info")

    def set_status(self, text):
        self.status.configure(text=text)

    def set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.send_button.configure(state=state)
        if not self.recording:
            self.talk_button.configure(state=state)

    def post(self, function):
        """Run `function` on the window's thread (tkinter is not thread-safe)."""
        self.ui_queue.put(function)

    def process_queue(self):
        while not self.ui_queue.empty():
            self.ui_queue.get_nowait()()
        self.root.after(100, self.process_queue)

    def on_voice_toggle(self):
        self.speak_answers = self.voice_check.get()

    # ---------- Loading ----------

    def load_models(self):
        """Runs in the background so the window appears right away."""
        self.post(lambda: self.set_status("Loading speech recognition..."))
        try:
            self.whisper = va.load_whisper()
        except Exception as e:
            error = f"Could not load speech recognition ({e}). Typing still works."
            self.post(lambda: self.add_info(error))

        self.post(lambda: self.set_status("Loading voice..."))
        self.kokoro = va.load_kokoro()

        remembered = len(self.history) - 1

        def ready():
            if remembered:
                self.add_info(f"Remembered {remembered} messages from earlier conversations.")
            self.add_info(f"Hi! I'm {va.ASSISTANT_NAME}. Type a message, or click Talk.")
            self.set_busy(False)
            self.set_status("Ready")
        self.post(ready)

    # ---------- Typing and talking ----------

    def send_typed(self, event=None):
        text = self.entry.get().strip()
        if not text or self.busy:
            return
        self.entry.delete(0, "end")
        self.add_message("You", text, "you")
        self.set_busy(True)
        threading.Thread(target=self.run_answer, args=(text,), daemon=True).start()

    def toggle_talk(self):
        if not self.recording:
            if self.busy:
                return
            if self.whisper is None:
                self.add_info("Speech recognition isn't loaded, please type instead.")
                return
            try:
                self.recorder.start()
            except Exception as e:
                self.add_info(f"Microphone error: {e}")
                return
            self.recording = True
            self.set_busy(True)
            self.talk_button.configure(text="Stop & send", state="normal")
            self.set_status("Listening... click 'Stop & send' when you're done.")
        else:
            audio = self.recorder.stop()
            self.recording = False
            self.talk_button.configure(text="Talk")
            if audio is None or len(audio) < va.SAMPLE_RATE * 0.5:
                self.add_info("That was too short, please try again.")
                self.set_busy(False)
                self.set_status("Ready")
                return
            self.set_status("Transcribing...")
            threading.Thread(target=self.transcribe_and_answer, args=(audio,), daemon=True).start()

    def transcribe_and_answer(self, audio):
        text = va.transcribe(self.whisper, audio)
        if not text:
            def nothing():
                self.add_info("I didn't catch anything. Try speaking louder or closer to the mic.")
                self.set_busy(False)
                self.set_status("Ready")
            self.post(nothing)
            return
        self.post(lambda: self.add_message("You", text, "you"))
        self.run_answer(text)

    def run_answer(self, text):
        """Runs in a background thread: ask the AI, show and speak the reply."""
        self.post(lambda: self.set_status("Thinking..."))
        reply = va.answer(self.history, text, status=lambda m: self.post(lambda: self.add_info(m)))
        if reply is not None:
            self.post(lambda: self.add_message(va.ASSISTANT_NAME, reply, "atlas"))
            if self.speak_answers:
                self.post(lambda: self.set_status("Speaking... (click 'Stop voice' to stop)"))
                try:
                    va.speak(reply, self.kokoro)
                except Exception as e:
                    error = f"(Could not play speech: {e})"
                    self.post(lambda: self.add_info(error))

        def done():
            self.set_busy(False)
            self.set_status("Ready")
        self.post(done)

    # ---------- Reminders and closing ----------

    def on_reminder(self, message):
        """Called by a reminder timer (from a background thread)."""
        def show():
            self.add_message(va.ASSISTANT_NAME, f"Reminder: {message}", "atlas")
            self.root.deiconify()  # bring the window to the front
            self.root.lift()
            self.root.bell()
        self.post(show)
        if self.speak_answers:
            va.speak(f"Reminder: {message}", self.kokoro)

    def on_close(self):
        if self.recording:
            self.recorder.stop()
        va.stop_speaking()
        self.root.destroy()


def main():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # sharp text on high-resolution screens
    except Exception:
        pass
    root = tk.Tk()
    app = AtlasApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
