#!/usr/bin/env python3
"""
J.A.R.V.I.S. — HUD window.

  pythonw gui.py             open the Jarvis window
  pythonw gui.py --startup   window + "Welcome, master" greeting (used at PC login)

Mic button / Ctrl+Space = speak one command. "Wake word" toggle = always listening for "Jarvis".
"""
import argparse
import datetime
import math
import queue
import random
import threading
import time
import tkinter as tk

import jarvis as J

try:
    import psutil
except ImportError:
    psutil = None

# ── palette ──
BG = "#03060b"
PANEL = "#07101d"
PANEL2 = "#0b1829"
LINE = "#14324d"
CYAN = "#2bd8ff"
TEXT = "#d4f3ff"
MUTED = "#5b86a3"
GREEN = "#38ffa5"
AMBER = "#ffb53d"
RED = "#ff4d6d"
WHITE = "#ffffff"

STATES = {
    "idle":      (CYAN,  "STANDING BY"),
    "listening": (GREEN, "LISTENING"),
    "thinking":  (AMBER, "PROCESSING"),
    "speaking":  (CYAN,  "SPEAKING"),
    "offline":   (RED,   "OFFLINE"),
    "booting":   (AMBER, "BOOTING"),
}

QUICK = [("Status", "system status"), ("Weather", "weather"), ("Time", "what time is it"),
         ("Screenshot", "take a screenshot"), ("Notes", "read my notes"), ("Joke", "tell me a joke")]


def mix(c1, c2, t):
    """Blend two hex colors (Tk has no alpha, so glows are faked with blends)."""
    t = max(0.0, min(1.0, t))
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * t) for x, y in zip(a, b))


# ─────────────────────────── bridges to the jarvis engine ─────────────────────
class GuiVoice(J.Voice):
    def __init__(self, ui):
        self.ui = ui
        super().__init__(muted=False)

    def say(self, text, wait=True):
        self.ui.post("jarvis", text)
        self.ui.set_state("speaking")
        super().say(text, wait)


class GuiJarvis(J.Jarvis):
    def __init__(self, voice, ui):
        self.ui = ui
        super().__init__(voice, None)

    def ask_user(self, prompt, timeout=6):
        self.say(prompt)
        if self.ui.mic_ok:
            return self.ui.capture(timeout=timeout) or ""
        self.ui.post("system", "Type your answer below.")
        return self.ui.wait_for_typed(30)

    def cmd_exit(self, m, t):
        self.say(f"Going offline. Goodbye, {J.TITLE}.")
        self.ui.ui_q.put(("quit",))

    def on_meeting_change(self):
        self.ui.ui_q.put(("toggles",))
        self.ui.ui_q.put(("banner", False))

    def report_minutes(self, result):
        lines = ["📋 MEETING MINUTES READY", ""]
        if result["tldr"]:
            lines += [result["tldr"], ""]
        if result["highlights"]:
            lines += ["Highlights:"] + [f"  • {h}" for h in result["highlights"][:8]] + [""]
        if result["actions"]:
            lines += ["Action items:"] + [f"  ☐ {a}" for a in result["actions"][:8]] + [""]
        lines.append("📄 Word document created and opened: Documents › Jarvis Meetings › "
                     + __import__("os").path.basename(result["path"]))
        self.ui.post("minutes", "\n".join(lines))
        self.voice.say(f"Your meeting minutes are ready, {J.TITLE}. {result['tldr']}".strip())
        if J.IS_WIN:
            import os
            os.startfile(result["path"])


# ─────────────────────────── the window ───────────────────────────────────────
class App:
    def __init__(self, root, startup=False):
        self.root = root
        self.state = "booting"
        self.level = 0.0
        self.smooth = 0.0
        self.t0 = time.time()
        self.hover_mic = False

        self.ui_q = queue.Queue()
        self.cmd_q = queue.Queue()
        self.answer_q = None
        self.mic_lock = threading.Lock()
        self.busy = False
        self.manual_listening = False
        self.alive = True

        self.listener = None
        self.mic_ok = False
        self.wake_enabled = bool(J.CFG.get("wake_word_on_start", True))
        self.voice_enabled = True

        self._build()
        self.voice = GuiVoice(self)
        self.jarvis = GuiJarvis(self.voice, self)

        threading.Thread(target=self._boot, args=(startup,), daemon=True).start()
        threading.Thread(target=self._command_worker, daemon=True).start()
        threading.Thread(target=self._wake_loop, daemon=True).start()
        threading.Thread(target=self._discord_watch, daemon=True).start()

        self._pump()
        self._animate()
        self._tick_clock()
        self._tick_stats()

    # ── layout ──
    def _build(self):
        r = self.root
        r.title("J.A.R.V.I.S.")
        r.configure(bg=BG)
        r.geometry("1080x660")
        r.minsize(900, 600)

        # top bar
        top = tk.Frame(r, bg=BG, height=64)
        top.pack(fill="x", padx=24, pady=(12, 0))
        left = tk.Frame(top, bg=BG)
        left.pack(side="left")
        tk.Label(left, text="J . A . R . V . I . S", bg=BG, fg=CYAN,
                 font=("Segoe UI Semibold", 18)).pack(anchor="w")
        tk.Label(left, text="JUST A RATHER VERY INTELLIGENT SYSTEM", bg=BG, fg=MUTED,
                 font=("Consolas", 8)).pack(anchor="w")
        right = tk.Frame(top, bg=BG)
        right.pack(side="right")
        self.clock_lbl = tk.Label(right, text="", bg=BG, fg=TEXT, font=("Consolas", 20))
        self.clock_lbl.pack(anchor="e")
        self.stats_lbl = tk.Label(right, text="", bg=BG, fg=MUTED, font=("Consolas", 9))
        self.stats_lbl.pack(anchor="e")
        tk.Frame(r, bg=LINE, height=1).pack(fill="x", padx=24, pady=(10, 0))

        body = tk.Frame(r, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=14)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # ── left: HUD + mic ──
        hud = tk.Frame(body, bg=BG)
        hud.grid(row=0, column=0, sticky="ns", padx=(0, 24))
        self.hud = tk.Canvas(hud, width=340, height=340, bg=BG, highlightthickness=0)
        self.hud.pack()
        self.state_lbl = tk.Label(hud, text="", bg=BG, fg=CYAN, font=("Consolas", 11, "bold"))
        self.state_lbl.pack(pady=(0, 6))

        self.mic = tk.Canvas(hud, width=90, height=90, bg=BG, highlightthickness=0, cursor="hand2")
        self.mic.pack(pady=(0, 0))
        self.mic.bind("<Button-1>", self.on_mic)
        self.mic.bind("<Enter>", lambda e: setattr(self, "hover_mic", True))
        self.mic.bind("<Leave>", lambda e: setattr(self, "hover_mic", False))

        toggles = tk.Frame(hud, bg=BG)
        toggles.pack(pady=(8, 0))
        self.wake_btn = self._toggle(toggles, self.toggle_wake)
        self.voice_btn = self._toggle(toggles, self.toggle_voice)
        self.meet_btn = tk.Label(hud, bg=PANEL2, font=("Consolas", 10, "bold"), padx=16, pady=7, cursor="hand2")
        self.meet_btn.pack(pady=(8, 0))
        self.meet_btn.bind("<Button-1>", lambda e: self.toggle_meeting())
        self._refresh_toggles()

        # ── right: conversation ──
        chat = tk.Frame(body, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        chat.grid(row=0, column=1, sticky="nsew")
        head = tk.Frame(chat, bg=PANEL)
        head.pack(fill="x", padx=18, pady=(14, 4))
        tk.Label(head, text="COMMAND LOG", bg=PANEL, fg=MUTED, font=("Consolas", 9, "bold")).pack(side="left")
        clear = tk.Label(head, text="clear", bg=PANEL, fg=MUTED, font=("Consolas", 9), cursor="hand2")
        clear.pack(side="right")
        clear.bind("<Button-1>", lambda e: self._clear_log())

        bar = tk.Frame(chat, bg=PANEL2, highlightbackground=LINE, highlightthickness=1)
        bar.pack(side="bottom", fill="x", padx=18, pady=(8, 18))
        self.entry = tk.Entry(bar, bg=PANEL2, fg=TEXT, insertbackground=CYAN, bd=0,
                              font=("Segoe UI", 12), highlightthickness=0)
        self.entry.pack(side="left", fill="x", expand=True, padx=14, pady=10)
        send = tk.Label(bar, text="SEND  ➤", bg=PANEL2, fg=CYAN, font=("Consolas", 10, "bold"),
                        padx=14, cursor="hand2")
        send.pack(side="right", fill="y")
        send.bind("<Button-1>", lambda e: self.on_enter())
        self.entry.bind("<Return>", lambda e: self.on_enter())
        chips = tk.Frame(chat, bg=PANEL)
        chips.pack(side="bottom", fill="x", padx=18, pady=(8, 0))
        for label, cmd in QUICK:
            c = tk.Label(chips, text=label, bg=PANEL2, fg=TEXT, font=("Segoe UI", 9),
                         padx=12, pady=5, cursor="hand2")
            c.pack(side="left", padx=(0, 6))
            c.bind("<Button-1>", lambda e, cmd=cmd: self.submit(cmd))
            c.bind("<Enter>", lambda e, w=c: w.configure(bg=LINE))
            c.bind("<Leave>", lambda e, w=c: w.configure(bg=PANEL2))

        self.banner = tk.Frame(chat, bg=mix(AMBER, PANEL, 0.82), highlightbackground=AMBER, highlightthickness=1)
        tk.Label(self.banner, text="🎧  Discord call detected. Take meeting minutes?",
                 bg=mix(AMBER, PANEL, 0.82), fg=TEXT, font=("Segoe UI", 10)).pack(side="left", padx=12, pady=8)
        later = tk.Label(self.banner, text="Not now", bg=mix(AMBER, PANEL, 0.82), fg=MUTED,
                         font=("Segoe UI", 9), padx=10, cursor="hand2")
        later.pack(side="right", padx=(0, 8))
        later.bind("<Button-1>", lambda e: self._show_banner(False))
        go = tk.Label(self.banner, text="START", bg=AMBER, fg=BG, font=("Consolas", 9, "bold"),
                      padx=12, pady=3, cursor="hand2")
        go.pack(side="right", padx=4)
        go.bind("<Button-1>", lambda e: (self._show_banner(False), self.submit("start meeting notes")))
        self._chips_frame = chips

        log_wrap = tk.Frame(chat, bg=PANEL)
        log_wrap.pack(fill="both", expand=True, padx=(18, 6))
        self.log = tk.Text(log_wrap, bg=PANEL, fg=TEXT, font=("Segoe UI", 11), wrap="word", bd=0,
                           highlightthickness=0, padx=2, pady=6, spacing1=2, spacing3=2,
                           cursor="arrow", insertbackground=PANEL, state="disabled")
        sb = tk.Scrollbar(log_wrap, command=self.log.yview, bg=PANEL, troughcolor=PANEL,
                          activebackground=LINE, bd=0, width=8)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        self.log.tag_configure("h_jarvis", foreground=CYAN, font=("Consolas", 9, "bold"), spacing1=12)
        self.log.tag_configure("h_you", foreground=GREEN, font=("Consolas", 9, "bold"), spacing1=12)
        self.log.tag_configure("h_system", foreground=MUTED, font=("Consolas", 9, "bold"), spacing1=12)
        self.log.tag_configure("b_jarvis", foreground=TEXT)
        self.log.tag_configure("b_you", foreground=WHITE)
        self.log.tag_configure("b_system", foreground=MUTED, font=("Segoe UI", 10, "italic"))
        self.log.tag_configure("h_minutes", foreground=AMBER, font=("Consolas", 9, "bold"), spacing1=12)
        self.log.tag_configure("b_minutes", foreground=TEXT, background=PANEL2, lmargin1=10, lmargin2=10,
                               rmargin=10, spacing1=1, spacing3=1, font=("Segoe UI", 10))

        self._placeholder_on()
        self.entry.bind("<FocusIn>", lambda e: self._placeholder_off())
        self.entry.bind("<FocusOut>", lambda e: self._placeholder_on())

        r.bind("<Control-space>", self.on_mic)
        r.bind("<Escape>", lambda e: self.root.focus_set())
        r.protocol("WM_DELETE_WINDOW", self.close)

    def _toggle(self, parent, cmd):
        b = tk.Label(parent, bg=PANEL2, font=("Consolas", 9, "bold"), padx=12, pady=6, cursor="hand2")
        b.pack(side="left", padx=4)
        b.bind("<Button-1>", lambda e: cmd())
        return b

    def _refresh_toggles(self):
        for btn, name, on in ((self.wake_btn, "WAKE WORD", self.wake_enabled),
                              (self.voice_btn, "VOICE", self.voice_enabled)):
            btn.configure(text=f"{name}  ● {'ON' if on else 'OFF'}", fg=GREEN if on else MUTED)
        mtg = getattr(getattr(self, "jarvis", None), "meeting", None)
        if mtg and mtg.active:
            e = int(mtg.elapsed())
            self.meet_btn.configure(text=f"■  STOP MEETING   {e // 60:02d}:{e % 60:02d}", fg=WHITE, bg=RED)
        else:
            self.meet_btn.configure(text="●  RECORD MEETING MINUTES", fg=RED, bg=PANEL2)

    def _placeholder_on(self):
        if not self.entry.get():
            self.entry.insert(0, "Type a command…   or press Ctrl+Space to talk")
            self.entry.configure(fg=MUTED)
            self._ph = True

    def _placeholder_off(self):
        if getattr(self, "_ph", False):
            self.entry.delete(0, "end")
            self.entry.configure(fg=TEXT)
            self._ph = False

    # ── thread-safe UI messages ──
    def post(self, who, text):
        self.ui_q.put(("msg", who, text))

    def set_state(self, s):
        self.ui_q.put(("state", s))

    def _pump(self):
        try:
            while True:
                item = self.ui_q.get_nowait()
                if item[0] == "msg":
                    self._append(item[1], item[2])
                elif item[0] == "state":
                    self.state = item[1]
                elif item[0] == "toggles":
                    self._refresh_toggles()
                elif item[0] == "banner":
                    self._show_banner(item[1])
                elif item[0] == "quit":
                    self.set_state("offline")
                    self.root.after(1500, self.close)
        except queue.Empty:
            pass
        if self.alive:
            self.root.after(40, self._pump)

    def _append(self, who, text):
        name = {"jarvis": "JARVIS", "you": "YOU", "system": "SYSTEM", "minutes": "JARVIS · MEETING"}[who]
        stamp = datetime.datetime.now().strftime("%H:%M")
        self.log.configure(state="normal")
        self.log.insert("end", f"{name}  ·  {stamp}\n", f"h_{who}")
        self.log.insert("end", f"{text}\n", f"b_{who}")
        self.log.configure(state="disabled")
        self.log.see("end")

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    # ── input ──
    def submit(self, text):
        text = text.strip()
        if not text:
            return
        if self.answer_q is not None:            # Jarvis is waiting for a yes/no
            self.post("you", text)
            self.answer_q.put(text)
            return
        self.post("you", text)
        m = self.jarvis.wake_re.search(text.lower())
        cmd = text.lower()[m.end():].strip() if m and m.start() == 0 else text
        self.cmd_q.put(cmd or "hello")

    def on_enter(self):
        if getattr(self, "_ph", False):
            return
        text = self.entry.get()
        self.entry.delete(0, "end")
        self.submit(text)

    def wait_for_typed(self, timeout):
        q = queue.Queue()
        self.answer_q = q
        try:
            return q.get(timeout=timeout).lower()
        except queue.Empty:
            return ""
        finally:
            self.answer_q = None

    def toggle_wake(self):
        if not self.mic_ok:
            self.post("system", "No microphone detected, so wake word mode is unavailable.")
            return
        self.wake_enabled = not self.wake_enabled
        self._refresh_toggles()

    def _show_banner(self, show):
        if show and not self.banner.winfo_ismapped():
            self.banner.pack(side="bottom", fill="x", padx=18, pady=(8, 0), after=self._chips_frame)
        elif not show and self.banner.winfo_ismapped():
            self.banner.pack_forget()

    def toggle_meeting(self):
        self.submit("stop meeting notes" if self.jarvis.meeting.active else "start meeting notes")

    def _discord_watch(self):
        """Notices when you join a Discord voice call and offers to take minutes."""
        cfg = J.CFG.get("meeting", {})
        if not (J.IS_WIN and cfg.get("detect_discord_calls", True)):
            return
        try:
            import comtypes
            comtypes.CoInitialize()
            from meeting import discord_audio_active
        except Exception:
            return
        on_for = off_for = 0
        offered = from_discord = False
        while self.alive:
            st = discord_audio_active()
            if st is None:
                return                                          # pycaw missing: feature off
            mtg = self.jarvis.meeting
            on_for, off_for = (on_for + 2, 0) if st else (0, off_for + 2)
            if st and mtg.active:
                from_discord = True
            if on_for >= 10 and not offered and not mtg.active:   # 10 s of call audio, not just a ping
                offered = True
                if cfg.get("auto_start", False):
                    self.cmd_q.put("start meeting notes")
                else:
                    self.ui_q.put(("banner", True))
                    self.post("system", "Discord call detected. Press START on the banner to take meeting minutes.")
            if off_for >= 30:                                     # call ended
                if offered:
                    offered = False
                    self.ui_q.put(("banner", False))
                if mtg.active and from_discord and cfg.get("auto_stop_when_call_ends", True):
                    self.post("system", "Discord call ended. Stopping the recording.")
                    self.cmd_q.put("stop meeting notes")
                from_discord = False
            time.sleep(2)

    def toggle_voice(self):
        self.voice_enabled = not self.voice_enabled
        self.voice.muted = not self.voice_enabled
        self._refresh_toggles()

    # ── mic ──
    def _on_level(self, rms):
        if self.listener:
            self.level = min(1.0, rms / (self.listener.threshold * 4))

    def capture(self, timeout=7):
        """Record one phrase. Safe to call from any worker thread."""
        with self.mic_lock:
            self.voice.wait_until_quiet()
            self.set_state("listening")
            try:
                text = self.listener.listen(timeout=timeout)
            finally:
                self.level = 0.0
        if text:
            self.post("you", text)
        return text

    def on_mic(self, *_):
        if not self.mic_ok:
            self.post("system", "Microphone not available. Check Windows sound settings, then restart Jarvis.")
            return
        if self.manual_listening:
            return
        self.manual_listening = True

        def run():
            try:
                text = self.capture(timeout=7)
                if text:
                    m = self.jarvis.wake_re.search(text)
                    cmd = text[m.end():].strip() if m else text
                    self.cmd_q.put(cmd or "hello")
                else:
                    if not self.busy:
                        self.set_state("idle")
                    self.post("system", "I didn't catch that. Try again.")
            finally:
                self.manual_listening = False

        threading.Thread(target=run, daemon=True).start()

    def _wake_loop(self):
        """Background ears: waits for 'Jarvis …' while wake word mode is ON."""
        while self.alive:
            if (not (self.wake_enabled and self.mic_ok) or self.busy or self.manual_listening
                    or self.jarvis.meeting.active):
                time.sleep(0.2)
                continue
            with self.mic_lock:
                if self.busy or self.manual_listening:
                    continue
                self.voice.wait_until_quiet()
                awake = time.time() < self.jarvis.awake_until
                if awake:
                    self.set_state("listening")
                try:
                    text = self.listener.listen(timeout=1.0)
                except Exception as e:
                    self.post("system", f"Mic error: {e}")
                    self.mic_ok = False
                    continue
                finally:
                    self.level = 0.0
            if not text:
                if awake and time.time() >= self.jarvis.awake_until and not self.busy:
                    self.set_state("idle")
                continue
            m = self.jarvis.wake_re.search(text)
            if m:
                cmd = text[m.end():].strip()
            elif time.time() < self.jarvis.awake_until + 1.5:
                cmd = text
            else:
                continue                                  # not talking to Jarvis
            self.post("you", text)
            if not cmd:
                self.voice.say(random.choice([f"Yes, {J.TITLE}?", "At your service.", "I'm listening."]))
                cmd = self.capture(timeout=6)
                if not cmd:
                    self.set_state("idle")
                    continue
            self.cmd_q.put(cmd)

    # ── workers ──
    def _boot(self, startup):
        try:
            lst = J.Listener()
            lst.level_cb = self._on_level
            lst.calibrate()
            self.listener = lst
            self.jarvis.listener = lst
            self.mic_ok = True
        except Exception as e:
            self.wake_enabled = False
            self.post("system", f"No microphone ({e}). You can still type commands.")
        self.ui_q.put(("toggles",))
        self.cmd_q.put("__startup__" if startup else "__online__")

    def _command_worker(self):
        while self.alive:
            item = self.cmd_q.get()
            self.busy = True
            try:
                if item == "__startup__":
                    self.jarvis.startup_greeting()
                elif item == "__online__":
                    self.jarvis.say(f"JARVIS online. {J.greeting_for_hour()}, {J.TITLE}.")
                else:
                    self.set_state("thinking")
                    self.jarvis.handle(item)
            except Exception as e:
                self.post("system", f"Error: {e}")
            finally:
                self.voice.wait_until_quiet()
                self.busy = False
                if item.startswith("__"):
                    self.jarvis.awake_until = 0
                    self.set_state("idle")
                else:
                    self.jarvis.awake_until = time.time() + J.CFG.get("follow_up_seconds", 8)
                    self.set_state("listening" if (self.wake_enabled and self.mic_ok) else "idle")

    # ── clock & stats ──
    def _tick_clock(self):
        now = datetime.datetime.now()
        self.clock_lbl.configure(text=now.strftime("%I:%M:%S %p").lstrip("0"))
        if self.jarvis.meeting.active:
            self._refresh_toggles()
        if self.alive:
            self.root.after(1000, self._tick_clock)

    def _tick_stats(self):
        parts = [datetime.datetime.now().strftime("%a %d %b %Y").upper()]
        if psutil:
            parts.append(f"CPU {psutil.cpu_percent(None):>3.0f}%")
            parts.append(f"RAM {psutil.virtual_memory().percent:>3.0f}%")
            try:
                b = psutil.sensors_battery()
                if b:
                    parts.append(f"BAT {b.percent:.0f}%{' ⚡' if b.power_plugged else ''}")
            except Exception:
                pass
        self.stats_lbl.configure(text="   ".join(parts))
        if self.alive:
            self.root.after(1500, self._tick_stats)

    # ── animation ──
    def _animate(self):
        t = time.time() - self.t0
        if self.state == "speaking" and self.voice.pending == 0 and not self.busy:
            self.state = "idle"
        mtg = self.jarvis.meeting
        color, label = STATES.get(self.state, STATES["idle"])
        if self.state == "idle" and mtg.active:
            e = int(mtg.elapsed())
            color, label = RED, f"● RECORDING MEETING  {e // 60:02d}:{e % 60:02d}"
        elif self.state == "idle" and self.wake_enabled and self.mic_ok:
            label = "STANDING BY  ·  SAY “JARVIS”"

        if self.state == "listening":
            target = 0.08 + self.level
        elif self.state == "speaking":
            target = 0.35 + 0.4 * abs(math.sin(t * 9)) * (0.6 + 0.4 * random.random())
        elif self.state in ("thinking", "booting"):
            target = 0.25 + 0.1 * math.sin(t * 6)
        elif mtg.active:
            target = 0.08 + min(1.0, max(mtg.levels.values()) * 6)
        else:
            target = 0.06 + 0.03 * math.sin(t * 2)
        self.smooth += (target - self.smooth) * 0.25

        self._draw_hud(t, color)
        self._draw_mic(t)
        self.state_lbl.configure(text=label, fg=color)
        if self.alive:
            self.root.after(33, self._animate)

    def _draw_hud(self, t, color):
        cv, c = self.hud, 170
        cv.delete("all")
        dim = mix(color, BG, 0.62)
        faint = mix(color, BG, 0.85)
        spd = {"thinking": 3.0, "booting": 3.0, "listening": 1.6, "speaking": 1.3}.get(self.state, 1.0)
        a0 = t * 18 * spd

        for r, col in ((165, faint), (158, dim)):
            cv.create_oval(c - r, c - r, c + r, c + r, outline=col, width=1)

        for i in range(72):                                    # rotating tick ring
            ang = math.radians(a0 + i * 5)
            r1 = 148
            r2 = r1 - (12 if i % 6 == 0 else 5)
            cv.create_line(c + r1 * math.cos(ang), c + r1 * math.sin(ang),
                           c + r2 * math.cos(ang), c + r2 * math.sin(ang),
                           fill=color if i % 6 == 0 else dim, width=1)

        r = 128
        for k in range(3):                                     # main arcs
            cv.create_arc(c - r, c - r, c + r, c + r, start=-a0 * 1.6 + k * 120, extent=70,
                          style="arc", outline=color, width=3)
        r = 114
        for k in range(4):                                     # thick counter-arcs
            cv.create_arc(c - r, c - r, c + r, c + r, start=a0 * 2.2 + k * 90, extent=28,
                          style="arc", outline=dim, width=8)

        n = 64                                                 # audio-reactive bars
        for i in range(n):
            ang = 2 * math.pi * i / n + t * 0.25
            wob = 0.5 + 0.5 * math.sin(t * 6 + i * 0.7) * math.cos(t * 2.3 + i * 0.31)
            length = 4 + self.smooth * 38 * (0.3 + 0.7 * wob)
            r1 = 62
            r2 = r1 + length
            cv.create_line(c + r1 * math.cos(ang), c + r1 * math.sin(ang),
                           c + r2 * math.cos(ang), c + r2 * math.sin(ang),
                           fill=mix(color, BG, 0.1 + 0.55 * (1 - wob)), width=2)

        cv.create_oval(c - 56, c - 56, c + 56, c + 56, outline=color, width=2)
        pulse = 0.5 + 0.5 * math.sin(t * 3)
        glow = 0.55 + 0.25 * pulse + 0.3 * self.smooth
        steps = list(range(50, 0, -5))
        for j, rr in enumerate(steps):                         # core glow
            tt = j / (len(steps) - 1)
            cv.create_oval(c - rr, c - rr, c + rr, c + rr, outline="",
                           fill=mix(BG, mix(color, WHITE, tt * 0.55), (0.12 + 0.88 * tt) * glow))
        cv.create_oval(c - 26, c - 26, c + 26, c + 26, outline=mix(color, WHITE, 0.6), width=1)
        for k in range(8):                                     # reactor segments
            cv.create_arc(c - 19, c - 19, c + 19, c + 19, start=k * 45 - a0 * 0.8, extent=30,
                          style="arc", outline=mix(color, WHITE, 0.8), width=3)
        cv.create_oval(c - 7, c - 7, c + 7, c + 7, fill=mix(color, WHITE, 0.85), outline="")

    def _draw_mic(self, t):
        m, cc = self.mic, 45
        m.delete("all")
        active = self.state == "listening" and (self.manual_listening or time.time() < self.jarvis.awake_until
                                                 or self.answer_q is not None or self.busy)
        col = GREEN if active else (CYAN if self.mic_ok else MUTED)
        if active:
            for k in range(2):
                p = ((t * 1.2 + k * 0.5) % 1.0)
                rr = 36 + p * 8
                m.create_oval(cc - rr, cc - rr, cc + rr, cc + rr, outline=mix(col, BG, p), width=2)
        fill = mix(col, BG, 0.68 if (self.hover_mic or active) else 0.82)
        m.create_oval(cc - 33, cc - 33, cc + 33, cc + 33, fill=fill, outline=col, width=2)
        m.create_oval(cc - 8, cc - 22, cc + 8, cc - 6, fill=col, outline="")
        m.create_rectangle(cc - 8, cc - 14, cc + 8, cc, fill=col, outline="")
        m.create_oval(cc - 8, cc - 8, cc + 8, cc + 8, fill=col, outline="")
        m.create_arc(cc - 14, cc - 12, cc + 14, cc + 14, start=180, extent=180,
                     style="arc", outline=col, width=2)
        m.create_line(cc, cc + 14, cc, cc + 20, fill=col, width=2)
        m.create_line(cc - 7, cc + 20, cc + 7, cc + 20, fill=col, width=2)

    def close(self):
        self.alive = False
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def main():
    ap = argparse.ArgumentParser(description="J.A.R.V.I.S. window")
    ap.add_argument("--startup", action="store_true", help="greet with 'Welcome, master'")
    args = ap.parse_args()
    try:                                                       # crisp text on high-DPI screens
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    App(root, startup=args.startup)
    root.mainloop()


if __name__ == "__main__":
    main()
