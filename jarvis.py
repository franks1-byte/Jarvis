#!/usr/bin/env python3
"""
J.A.R.V.I.S. — voice assistant for Windows.

  python jarvis.py              normal mode (mic + voice)
  python jarvis.py --startup    greeting mode used at PC login
  python jarvis.py --text       type commands instead of speaking (for testing)
  python jarvis.py --mute       no spoken replies, text only
"""
import argparse
import ctypes
import datetime
import json
import os
import queue
import random
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IS_WIN = os.name == "nt"

with open(os.path.join(BASE_DIR, "config.json"), encoding="utf-8") as f:
    CFG = json.load(f)

TITLE = CFG.get("user_title", "master")
NOTES_FILE = os.path.join(BASE_DIR, "notes.txt")


# ─────────────────────────── VOICE (text-to-speech) ───────────────────────────
VOICE_CACHE = os.path.join(BASE_DIR, "voice_cache")

# Realistic neural voices (free, need internet). Ryan = the classic British JARVIS sound.
VOICE_PRESETS = {
    "jarvis": "en-GB-RyanNeural",
    "british": "en-GB-ThomasNeural",
    "american": "en-US-GuyNeural",
    "filipino": "en-PH-JamesNeural",
    "australian": "en-AU-WilliamNeural",
    "friday": "en-GB-SoniaNeural",
}


def save_config():
    with open(os.path.join(BASE_DIR, "config.json"), "w", encoding="utf-8") as f:
        json.dump(CFG, f, indent=2, ensure_ascii=False)


def _powershell_say(text):
    t = text.replace("'", "''")
    cmd = ("Add-Type -AssemblyName System.Speech;"
           "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
           f"$s.Speak('{t}')")
    subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                   creationflags=0x08000000)  # no console window


def _play_mp3(path):
    """Play an mp3 with Windows' built-in MCI player (no extra packages). Blocks until done."""
    mci = ctypes.windll.winmm.mciSendStringW
    mci("close jarvis_tts", None, 0, None)
    err = mci(f'open "{path}" type mpegvideo alias jarvis_tts', None, 0, None)
    if err:
        raise RuntimeError(f"MCI error {err}")
    try:
        mci("play jarvis_tts wait", None, 0, None)
    finally:
        mci("close jarvis_tts", None, 0, None)


class Voice:
    """All speech goes through one worker thread.
    Order: neural voice (edge-tts, internet) → pyttsx3 (offline) → Windows PowerShell voice."""

    def __init__(self, muted=False):
        self.muted = muted
        self.backend = None
        self.q = queue.Queue()
        self.pending = 0
        self._plock = threading.Lock()
        vcfg = CFG.setdefault("voice", {})
        self.engine_name = vcfg.get("engine", "neural")
        self.neural_voice = vcfg.get("neural_voice", VOICE_PRESETS["jarvis"])
        self.neural_rate = vcfg.get("neural_rate", "+0%")
        self.neural_pitch = vcfg.get("neural_pitch", "-2Hz")
        self.neural_ok = False
        if not muted:
            ready = threading.Event()
            threading.Thread(target=self._worker, args=(ready,), daemon=True).start()
            ready.wait(8)

    # ── engines ──
    def _init_offline(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", CFG["voice"].get("rate", 175))
            voices = engine.getProperty("voices") or []
            for hint in CFG["voice"].get("prefer", []):
                match = next((v for v in voices if hint.lower() in (v.name or "").lower()), None)
                if match:
                    engine.setProperty("voice", match.id)
                    break
            return engine
        except Exception as e:
            print(f"[voice] pyttsx3 unavailable ({e}); offline fallback is the Windows voice")
            return None

    def _neural_file(self, text):
        """Synthesize to an mp3 (short phrases are cached so greetings play instantly)."""
        import asyncio
        import hashlib
        import tempfile
        import edge_tts
        key = hashlib.md5(f"{self.neural_voice}|{self.neural_rate}|{self.neural_pitch}|{text}".encode()).hexdigest()
        cache = len(text) <= 90
        if cache:
            os.makedirs(VOICE_CACHE, exist_ok=True)
            path = os.path.join(VOICE_CACHE, key + ".mp3")
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return path, False
        else:
            path = os.path.join(tempfile.gettempdir(), f"jarvis_{key}.mp3")
        comm = edge_tts.Communicate(text, self.neural_voice, rate=self.neural_rate, pitch=self.neural_pitch)
        try:
            asyncio.run(asyncio.wait_for(comm.save(path), timeout=8))
        except Exception:
            if os.path.exists(path):
                os.remove(path)
            raise
        if os.path.getsize(path) == 0:
            os.remove(path)
            raise RuntimeError("empty audio")
        return path, not cache

    def _speak_neural(self, text):
        path, temporary = self._neural_file(text)
        try:
            _play_mp3(path)
        finally:
            if temporary:
                try:
                    os.remove(path)
                except OSError:
                    pass

    def _worker(self, ready):
        engine = None
        if self.engine_name == "neural" and IS_WIN:
            try:
                import edge_tts  # noqa: F401
                self.neural_ok = True
                self.backend = "neural"
            except Exception as e:
                print(f"[voice] Neural voice unavailable ({e}). Run: pip install edge-tts")
        offline_loaded = False
        if not self.neural_ok:
            engine = self._init_offline()
            offline_loaded = True
            self.backend = "pyttsx3" if engine else ("powershell" if IS_WIN else None)
        ready.set()

        while True:
            text, done = self.q.get()
            try:
                spoken = False
                if self.neural_ok and self.engine_name == "neural":
                    try:
                        self._speak_neural(text)
                        spoken = True
                    except Exception as e:
                        print(f"[voice] neural voice failed ({e}); using offline voice")
                if not spoken:
                    if not offline_loaded:
                        engine = self._init_offline()
                        offline_loaded = True
                    if engine:
                        engine.say(text)
                        engine.runAndWait()
                    elif IS_WIN:
                        _powershell_say(text)
            except Exception as e:
                print(f"[voice error] {e}")
            finally:
                with self._plock:
                    self.pending -= 1
                done.set()

    # ── public ──
    def set_voice(self, name_or_id):
        """Switch neural voice by preset name ('jarvis', 'filipino'…) or full id; saved to config."""
        vid = VOICE_PRESETS.get(name_or_id.lower().strip(), name_or_id)
        self.neural_voice = vid
        self.engine_name = "neural"
        CFG["voice"]["neural_voice"] = vid
        CFG["voice"]["engine"] = "neural"
        save_config()
        return vid

    def say(self, text, wait=True):
        print(f"JARVIS: {text}")
        if self.muted or not self.backend:
            return
        done = threading.Event()
        with self._plock:
            self.pending += 1
        self.q.put((text, done))
        if wait:
            done.wait()

    def wait_until_quiet(self, limit=30):
        """Block until Jarvis finishes talking, so the mic doesn't hear him."""
        end = time.time() + limit
        while self.pending > 0 and time.time() < end:
            time.sleep(0.05)


# ─────────────────────────── EARS (speech-to-text) ────────────────────────────
class Listener:
    """Mic capture with sounddevice + Google speech recognition (no PyAudio needed)."""

    def __init__(self):
        import numpy as np
        import sounddevice as sd
        import speech_recognition as sr
        self.np, self.sd, self.sr = np, sd, sr
        self.rate = 16000
        self.block_sec = 0.05
        self.rec = sr.Recognizer()
        self.lang = CFG.get("language", "en-US")
        self.threshold = 400.0
        self.level_cb = None          # GUI hook: receives live mic loudness

    def _rms(self, a):
        return float(self.np.sqrt(self.np.mean(a.astype(self.np.float32) ** 2))) if a.size else 0.0

    def calibrate(self, seconds=1.2):
        print("[mic] Calibrating to room noise… stay quiet for a second.")
        data = self.sd.rec(int(seconds * self.rate), samplerate=self.rate, channels=1, dtype="int16")
        self.sd.wait()
        self.threshold = max(self._rms(data) * 2.8, 300.0)

    def _record(self, timeout=None, phrase_limit=10, silence=0.9):
        block = int(self.rate * self.block_sec)
        pre, frames = [], []
        started, quiet, t0, ts = False, 0, time.time(), 0.0
        with self.sd.InputStream(samplerate=self.rate, channels=1, dtype="int16", blocksize=block) as s:
            while True:
                chunk, _ = s.read(block)
                level = self._rms(chunk)
                if self.level_cb:
                    self.level_cb(level)
                if not started:
                    pre = (pre + [chunk])[-6:]          # keep ~0.3 s before speech starts
                    if level > self.threshold:
                        started, frames, ts = True, list(pre), time.time()
                    elif timeout and time.time() - t0 > timeout:
                        return None
                else:
                    frames.append(chunk)
                    quiet = quiet + 1 if level < self.threshold else 0
                    if quiet * self.block_sec >= silence or time.time() - ts > phrase_limit:
                        break
        if len(frames) * self.block_sec < 0.45:          # ignore clicks / coughs
            return None
        return self.sr.AudioData(self.np.concatenate(frames).tobytes(), self.rate, 2)

    def listen(self, timeout=None):
        audio = self._record(timeout=timeout)
        if audio is None:
            return ""
        try:
            return self.rec.recognize_google(audio, language=self.lang).lower()
        except self.sr.UnknownValueError:
            return ""
        except self.sr.RequestError:
            print("[mic] Can't reach the speech service — check your internet.")
            time.sleep(2)
            return ""


# ─────────────────────────── AI BRAIN (Gemini, optional) ──────────────────────
class Brain:
    def __init__(self):
        self.chat = None
        self.client = None
        self.model = CFG.get("gemini", {}).get("model", "gemini-flash-latest")
        key = os.environ.get("GEMINI_API_KEY") or CFG.get("gemini", {}).get("api_key")
        if not key:
            return
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=key)
            self.client = client
            self.chat = client.chats.create(
                model=self.model,
                config=types.GenerateContentConfig(system_instruction=(
                    f"You are J.A.R.V.I.S., a witty, loyal British AI butler. Address the user as '{TITLE}'. "
                    "Your replies are spoken aloud: keep them to 1-3 short sentences, plain text, "
                    "no markdown, no emojis, no lists.")),
            )
            print("[ai] Gemini brain online.")
        except Exception as e:
            print(f"[ai] Gemini not available: {e}")

    def ask(self, question):
        if not self.chat:
            return None
        try:
            text = self.chat.send_message(question).text or ""
            return re.sub(r"[*#_`]", "", text).strip()
        except Exception as e:
            print(f"[ai error] {e}")
            return None


# ─────────────────────────── HELPERS ──────────────────────────────────────────
VK = {"vol_up": 0xAF, "vol_down": 0xAE, "mute": 0xAD,
      "play_pause": 0xB3, "next": 0xB0, "prev": 0xB1}

WORD_NUMS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
             "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15,
             "twenty": 20, "thirty": 30, "half an": 0.5}

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "I would tell you a UDP joke, but you might not get it.",
    "There are 10 kinds of people: those who understand binary and those who don't.",
    "A SQL query walks into a bar, walks up to two tables and asks: may I join you?",
    "Why did the Java developer wear glasses? Because he couldn't C sharp.",
    "My code doesn't have bugs. It just develops random features.",
]


def press(vk, times=1):
    if not IS_WIN:
        return
    for _ in range(times):
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)


def to_number(s):
    s = s.strip()
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return float(s)
    return WORD_NUMS.get(s)


def unit_seconds(unit):
    unit = unit.rstrip("s")
    return {"second": 1, "sec": 1, "minute": 60, "min": 60, "hour": 3600}.get(unit, 60)


_start_menu_cache = None


def find_start_menu_app(name):
    """Find an installed app by its Start Menu shortcut (e.g. 'roblox studio', 'blender')."""
    global _start_menu_cache
    if _start_menu_cache is None:
        _start_menu_cache = {}
        roots = [os.path.join(os.environ.get("PROGRAMDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
                 os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")]
        for root in roots:
            for dirpath, _, files in os.walk(root):
                for f in files:
                    if f.lower().endswith((".lnk", ".url")) and "uninstall" not in f.lower():
                        _start_menu_cache[os.path.splitext(f)[0].lower()] = os.path.join(dirpath, f)
    n = name.lower().strip()
    if n in _start_menu_cache:
        return _start_menu_cache[n]
    for stem in sorted(_start_menu_cache, key=len):       # shortest match = most likely the main app
        if stem.startswith(n):
            return _start_menu_cache[stem]
    for stem in sorted(_start_menu_cache, key=len):
        if n in stem:
            return _start_menu_cache[stem]
    return None


def launch(target):
    if target.startswith("http"):
        webbrowser.open(target)
    elif IS_WIN:
        subprocess.Popen(["cmd", "/c", "start", "", target], creationflags=0x08000000)
    else:
        print(f"[launch] (Windows only) would open: {target}")


def greeting_for_hour():
    h = datetime.datetime.now().hour
    return "Good morning" if h < 12 else "Good afternoon" if h < 18 else "Good evening"


class _NoMeeting:
    """Stand-in when the meeting feature's packages are missing."""
    active = False
    levels = {"you": 0.0, "others": 0.0}
    folder = os.path.join(os.path.expanduser("~"), "Documents", "Jarvis Meetings")

    def __init__(self, reason):
        self.reason = reason

    def elapsed(self):
        return 0.0

    def start(self):
        raise RuntimeError(f"meeting packages missing: {self.reason}")

    def stop(self):
        raise RuntimeError("not recording")


# ─────────────────────────── JARVIS ───────────────────────────────────────────
class Jarvis:
    def __init__(self, voice, listener):
        self.voice = voice
        self.listener = listener
        self.brain = Brain()
        self.running = True
        self.awake_until = 0.0
        try:
            from meeting import MeetingRecorder
            self.meeting = MeetingRecorder(CFG)
        except Exception as e:                       # e.g. numpy not installed: keep Jarvis running
            print(f"[meeting] Meeting minutes disabled ({e}). Run: pip install -r requirements.txt")
            self.meeting = _NoMeeting(str(e))
        wake = "|".join(map(re.escape, CFG.get("wake_words", ["jarvis"])))
        self.wake_re = re.compile(rf"\b(?:hey |okay |ok )?(?:{wake})\b[,.!?]?\s*")

        # (pattern, handler) — first match wins, order matters
        self.commands = [
            (r"^(goodbye|bye|exit|quit|go offline|stop listening|turn yourself off)\b", self.cmd_exit),
            (r"^(hi|hello|hey|good (morning|afternoon|evening))\b", self.cmd_hello),
            (r"(who are you|what are you|your name)", self.cmd_whoami),
            (r"(?:change|switch|use)(?: your| the)? voice(?: to)?(?: (\w+))?", self.cmd_voice),
            (r"(list|what) (?:are )?(?:your |the )?voices", self.cmd_voice_list),
            (r"^(?:start|begin) (?:the |a |my )?(?:meeting|minutes|taking notes)\b|^record (?:the |this |my )?(?:meeting|call)\b|^take meeting notes", self.cmd_meeting_start),
            (r"^(?:stop|end|finish) (?:the |my )?(?:meeting|minutes|recording)\b", self.cmd_meeting_stop),
            (r"\b(?:last|latest|previous) meeting\b|^(?:open|show|read) (?:my |the )?meeting (?:minutes|notes)", self.cmd_meeting_open),
            (r"^(thanks|thank you)", lambda m, t: self.say(f"Always a pleasure, {TITLE}.")),
            (r"\bwhat can you do\b|\bhelp\b|\bcommands\b", self.cmd_help),
            (r"(what time|the time|time is it)", self.cmd_time),
            (r"(what day|the date|today's date|what's today)", self.cmd_date),
            (r"weather(?: in (.+))?", self.cmd_weather),
            (r"(?:set (?:a )?)?timer (?:for )?(\w+(?: an)?) (seconds?|secs?|minutes?|mins?|hours?)", self.cmd_timer),
            (r"remind me in (\w+(?: an)?) (seconds?|minutes?|mins?|hours?)(?: to)? (.+)", self.cmd_remind_in),
            (r"remind me to (.+) in (\w+(?: an)?) (seconds?|minutes?|mins?|hours?)", self.cmd_remind_to),
            (r"^(?:take a note|note that|make a note|remember that|write down)[,:]? (.+)", self.cmd_note),
            (r"(read|show|what are) (my )?notes", self.cmd_read_notes),
            (r"(volume up|louder|increase (the )?volume)", lambda m, t: (press(VK["vol_up"], 5), self.say("Volume up."))),
            (r"(volume down|quieter|lower (the )?volume|decrease (the )?volume)", lambda m, t: (press(VK["vol_down"], 5), self.say("Volume down."))),
            (r"^(mute|unmute)\b", lambda m, t: (press(VK["mute"]), self.say("Done."))),
            (r"^(pause|resume|play)( the)?( music| song| video)?$", lambda m, t: press(VK["play_pause"])),
            (r"^(next|skip)( song| track)?$", lambda m, t: press(VK["next"])),
            (r"^(previous|back)( song| track)?$", lambda m, t: press(VK["prev"])),
            (r"^play (.+?)(?: on youtube)?$", self.cmd_play_youtube),
            (r"(?:search youtube for|youtube search) (.+)|search (.+) on youtube", self.cmd_search_youtube),
            (r"^(?:search(?: for)?|google|look up) (.+)", self.cmd_search),
            (r"^(?:open|launch|start|run) (.+)", self.cmd_open),
            (r"^(?:close|exit|kill) (.+)", self.cmd_close),
            (r"(screenshot|screen shot|capture (the )?screen)", self.cmd_screenshot),
            (r"(system status|system report|battery|cpu|ram|memory usage|how are you)", self.cmd_status),
            (r"(lock (the |my )?(pc|computer|screen)|lock it)", self.cmd_lock),
            (r"(shut ?down|turn off) (the |my )?(pc|computer|laptop)", self.cmd_shutdown),
            (r"restart (the |my )?(pc|computer|laptop)", self.cmd_restart),
            (r"(sleep mode|put (the |my )?(pc|computer) to sleep)", self.cmd_sleep),
            (r"(joke|make me laugh)", lambda m, t: self.say(random.choice(JOKES))),
            (r"(flip a coin|coin flip)", lambda m, t: self.say(f"It's {random.choice(['heads', 'tails'])}.")),
            (r"roll a (die|dice)", lambda m, t: self.say(f"You rolled a {random.randint(1, 6)}.")),
        ]
        self.commands = [(re.compile(p), h) for p, h in self.commands]

    # ── core ──
    def split_wake(self, text):
        """Returns (addressed_to_jarvis, command).
        'jarvis open notepad' -> open notepad | 'open notepad, jarvis' -> open notepad |
        'change voice to jarvis' -> kept whole (the name is part of the command)."""
        m = self.wake_re.search(text)
        if not m:
            return False, text
        if m.start() == 0:
            return True, text[m.end():].strip()
        head = text[:m.start()].rstrip(" ,")
        if m.end() >= len(text.rstrip(" .!?")) and not re.search(r"\b(to|as|voice|called|named)$", head):
            return True, head
        return True, text

    def say(self, text, wait=True):
        self.voice.say(text, wait)

    def ask_user(self, prompt, timeout=6):
        self.say(prompt)
        if self.listener:
            return self.listener.listen(timeout=timeout)
        try:
            return input("YOU: ").lower()
        except EOFError:
            return ""

    def confirmed(self, prompt):
        ans = self.ask_user(prompt)
        return bool(re.search(r"\b(yes|yeah|yep|sure|do it|confirm|proceed|affirmative)\b", ans))

    def handle(self, text):
        text = re.sub(r"[.!?]+$", "", text.strip().lower())
        if not text:
            return
        for pattern, handler in self.commands:
            m = pattern.search(text)
            if m:
                handler(m, text)
                return
        answer = self.brain.ask(text)
        if answer:
            self.say(answer)
        else:
            self.say(f"I'm not sure about that, {TITLE}. Let me search the web.")
            webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote(text))

    def run(self):
        mode = "voice" if self.listener else "text"
        print(f"\n[jarvis] Online in {mode} mode. Say 'Jarvis, what can you do?'  (Ctrl+C to quit)\n")
        while self.running:
            try:
                self.voice.wait_until_quiet()
                heard = self.listener.listen() if self.listener else input("YOU: ")
            except (EOFError, KeyboardInterrupt):
                break
            heard = (heard or "").lower().strip()
            if not heard:
                continue
            if self.listener:
                print(f"YOU: {heard}")

            awake = time.time() < self.awake_until
            addressed, command = self.split_wake(heard)
            if addressed:
                pass
            elif awake or not self.listener or not CFG.get("require_wake_word", True):
                command = heard
            else:
                continue                                   # not talking to Jarvis

            if not command:
                command = self.ask_user(random.choice([f"Yes, {TITLE}?", "At your service.", "I'm listening."]))
                if not command:
                    continue
                if self.listener:
                    print(f"YOU: {command}")
            self.handle(command)
            self.awake_until = time.time() + CFG.get("follow_up_seconds", 8)

    # ── greeting ──
    def startup_greeting(self):
        self.say(CFG.get("greeting", f"Welcome, {TITLE}."))
        if not CFG.get("startup_report", True):
            return
        now = datetime.datetime.now()
        parts = [f"{greeting_for_hour()}. It is {now.strftime('%I:%M %p').lstrip('0')}."]
        try:
            import psutil
            b = psutil.sensors_battery()
            if b:
                parts.append(f"Battery at {int(b.percent)} percent" + (", charging." if b.power_plugged else "."))
        except Exception:
            pass
        parts.append("All systems online.")
        self.say(" ".join(parts))

    # ── meeting minutes ──
    def on_meeting_change(self):
        """Hook for the GUI (REC indicator)."""

    def cmd_meeting_start(self, m, t):
        if self.meeting.active:
            return self.say(f"I'm already taking notes, {TITLE}.")
        try:
            self.meeting.start()
        except Exception as e:
            print(f"[meeting] {e}")
            return self.say("I couldn't start the meeting recorder. Run pip install -r requirements.txt, then try again.")
        self.on_meeting_change()
        self.say("Meeting notes started. Please let everyone on the call know it's being recorded.")

    def cmd_meeting_stop(self, m, t):
        if not self.meeting.active:
            return self.say("No meeting is being recorded right now.")
        try:
            wav, duration = self.meeting.stop()
        except Exception as e:
            self.on_meeting_change()
            print(f"[meeting] {e}")
            return self.say("The recording failed, nothing was captured.")
        self.on_meeting_change()
        if duration < 5:
            return self.say("That meeting was too short to summarize.")
        mins = max(1, round(duration / 60))
        self.say(f"Meeting ended after {mins} minute{'s' if mins > 1 else ''}. "
                 "I'm writing the minutes now, I'll tell you when they're ready.")
        threading.Thread(target=self._finish_meeting, args=(wav, duration), daemon=True).start()

    def _finish_meeting(self, wav, duration):
        try:
            result = self.meeting.write_minutes(wav, duration, self.brain)
        except Exception as e:
            print(f"[meeting] {e}")
            return self.say("Sorry, I couldn't write the minutes. The recording is saved in Documents, Jarvis Meetings.")
        self.report_minutes(result)

    def report_minutes(self, result):
        print("\n=== MEETING HIGHLIGHTS ===")
        for h in result["highlights"][:8]:
            print("  •", h)
        for a in result["actions"][:8]:
            print("  ☐", a)
        print(f"Saved: {result['path']}\n")
        self.say(f"Your meeting minutes are ready, {TITLE}. {result['tldr']}".strip())
        if IS_WIN:
            os.startfile(result["path"])

    def cmd_meeting_open(self, m, t):
        folder = self.meeting.folder
        files = sorted(f for f in os.listdir(folder) if f.endswith("_minutes.md")) if os.path.isdir(folder) else []
        if not files:
            return self.say("You don't have any meeting minutes yet.")
        path = os.path.join(folder, files[-1])
        if IS_WIN:
            os.startfile(path)
        else:
            print(f"[open] {path}")
        self.say("Opening your latest meeting minutes.")

    def cmd_voice(self, m, t):
        names = list(VOICE_PRESETS)
        choice = (m.group(1) or "").lower()
        if choice not in VOICE_PRESETS:                     # no/unknown name: cycle to the next voice
            cur = next((k for k, v in VOICE_PRESETS.items() if v == self.voice.neural_voice), names[-1])
            choice = names[(names.index(cur) + 1) % len(names)]
        self.voice.set_voice(choice)
        if not self.voice.neural_ok:
            return self.say("The neural voices need the edge-tts package and internet. Run pip install edge-tts.")
        self.say(f"Voice changed to {choice}. How do I sound, {TITLE}?")

    def cmd_voice_list(self, m, t):
        self.say("I can speak as " + ", ".join(VOICE_PRESETS) + ". Say, change voice to, then the name.")

    # ── handlers ──
    def cmd_exit(self, m, t):
        self.say(f"Going offline. Goodbye, {TITLE}.")
        self.running = False

    def cmd_hello(self, m, t):
        self.say(f"{greeting_for_hour()}, {TITLE}. How may I help?")

    def cmd_whoami(self, m, t):
        self.say("I am JARVIS. Just A Rather Very Intelligent System. At your service.")

    def cmd_help(self, m, t):
        self.say("I can open or close apps and websites, take meeting minutes, play music on YouTube, search the web, "
                 "tell the time, date and weather, set timers and reminders, take notes, control volume, "
                 "take screenshots, report system status, lock or shut down the PC, and answer questions.")

    def cmd_time(self, m, t):
        self.say(f"It's {datetime.datetime.now().strftime('%I:%M %p').lstrip('0')}, {TITLE}.")

    def cmd_date(self, m, t):
        self.say(f"Today is {datetime.datetime.now().strftime('%A, %B %d, %Y')}.")

    def cmd_weather(self, m, t):
        city = (m.group(1) or CFG.get("city", "")).strip()
        try:
            url = f"https://wttr.in/{urllib.parse.quote(city)}?format=%C+%t"
            req = urllib.request.Request(url, headers={"User-Agent": "curl"})
            raw = urllib.request.urlopen(req, timeout=8).read().decode("utf-8").strip()
            cond, temp = raw.rsplit(" ", 1)
            temp = temp.replace("+", "").replace("°C", " degrees Celsius").replace("°F", " degrees")
            self.say(f"In {city.title()}, it's {cond.lower()}, {temp}.")
        except Exception:
            self.say("I couldn't reach the weather service right now.")

    def _schedule(self, seconds, message):
        def fire():
            if IS_WIN:
                try:
                    import winsound
                    winsound.MessageBeep()
                except Exception:
                    pass
            self.say(message)
        threading.Timer(seconds, fire).start()

    def cmd_timer(self, m, t):
        n = to_number(m.group(1))
        if n is None:
            return self.say("Sorry, how long should the timer be?")
        secs = n * unit_seconds(m.group(2))
        self._schedule(secs, f"{TITLE.capitalize()}, your timer is done.")
        self.say(f"Timer set for {m.group(1)} {m.group(2)}.")

    def cmd_remind_in(self, m, t):
        self._remind(m.group(1), m.group(2), m.group(3))

    def cmd_remind_to(self, m, t):
        self._remind(m.group(2), m.group(3), m.group(1))

    def _remind(self, num, unit, task):
        n = to_number(num)
        if n is None:
            return self.say("Sorry, I didn't catch when.")
        self._schedule(n * unit_seconds(unit), f"Reminder, {TITLE}: {task}.")
        self.say(f"Okay. I'll remind you in {num} {unit} to {task}.")

    def cmd_note(self, m, t):
        with open(NOTES_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M}] {m.group(1)}\n")
        self.say("Noted.")

    def cmd_read_notes(self, m, t):
        if not os.path.exists(NOTES_FILE):
            return self.say("You have no notes yet.")
        with open(NOTES_FILE, encoding="utf-8") as f:
            lines = [l.split("] ", 1)[-1].strip() for l in f if l.strip()][-5:]
        self.say("Your latest notes: " + ". ".join(lines) + ".")

    def cmd_open(self, m, t):
        name = re.sub(r"^(the|my) ", "", m.group(1)).strip()
        apps = {k.lower(): v for k, v in CFG.get("apps", {}).items()}
        sites = {k.lower(): v for k, v in CFG.get("websites", {}).items()}
        if name in apps:
            launch(apps[name])
        elif name in sites:
            launch(sites[name])
        elif IS_WIN and (lnk := find_start_menu_app(name)):
            os.startfile(lnk)
        elif re.fullmatch(r"[\w-]+(\.[\w-]+)+", name.replace(" dot ", ".")):
            launch("https://" + name.replace(" dot ", "."))
        else:
            return self.say(f"I couldn't find {name} on this computer, {TITLE}.")
        self.say(f"Opening {name}.", wait=False)

    def cmd_close(self, m, t):
        name = re.sub(r"^(the|my) ", "", m.group(1)).strip()
        if not IS_WIN:
            return self.say("Closing apps only works on Windows.")
        proc = CFG.get("process_names", {}).get(name, name.replace(" ", "") + ".exe")
        r = subprocess.run(["taskkill", "/im", proc, "/f"], capture_output=True, creationflags=0x08000000)
        self.say(f"Closed {name}." if r.returncode == 0 else f"{name.capitalize()} doesn't seem to be running.")

    def cmd_search(self, m, t):
        q = m.group(1)
        webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote(q))
        self.say(f"Searching for {q}.", wait=False)

    def cmd_search_youtube(self, m, t):
        q = m.group(1) or m.group(2)
        webbrowser.open("https://www.youtube.com/results?search_query=" + urllib.parse.quote(q))
        self.say(f"Searching YouTube for {q}.", wait=False)

    def cmd_play_youtube(self, m, t):
        q = m.group(1)
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(q)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en"})
            html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", "ignore")
            vid = re.search(r'"videoId":"([\w-]{11})"', html)
            if vid:
                url = f"https://www.youtube.com/watch?v={vid.group(1)}"
        except Exception:
            pass
        webbrowser.open(url)
        self.say(f"Playing {q}.", wait=False)

    def cmd_screenshot(self, m, t):
        try:
            from PIL import ImageGrab
            folder = os.path.join(os.path.expanduser("~"), "Pictures", "Jarvis Screenshots")
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, f"shot_{datetime.datetime.now():%Y%m%d_%H%M%S}.png")
            ImageGrab.grab(all_screens=True).save(path)
            self.say("Screenshot saved in your Pictures folder.")
        except Exception as e:
            self.say("I couldn't take a screenshot.")
            print(f"[screenshot] {e}")

    def cmd_status(self, m, t):
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.6)
            ram = psutil.virtual_memory().percent
            msg = f"All systems running, {TITLE}. CPU at {cpu:.0f} percent, memory at {ram:.0f} percent."
            b = psutil.sensors_battery()
            if b:
                msg += f" Battery at {int(b.percent)} percent" + (", charging." if b.power_plugged else ".")
            self.say(msg)
        except ImportError:
            self.say("Install psutil so I can read system stats.")

    def cmd_lock(self, m, t):
        self.say("Locking the computer.")
        if IS_WIN:
            ctypes.windll.user32.LockWorkStation()

    def cmd_shutdown(self, m, t):
        if self.confirmed(f"Are you sure you want to shut down, {TITLE}?"):
            self.say("Shutting down in ten seconds. Goodbye.")
            if IS_WIN:
                subprocess.run(["shutdown", "/s", "/t", "10"])
        else:
            self.say("Shutdown cancelled.")

    def cmd_restart(self, m, t):
        if self.confirmed("Restart the computer?"):
            self.say("Restarting in ten seconds.")
            if IS_WIN:
                subprocess.run(["shutdown", "/r", "/t", "10"])
        else:
            self.say("Restart cancelled.")

    def cmd_sleep(self, m, t):
        if self.confirmed("Put the computer to sleep?"):
            self.say("Good night.")
            if IS_WIN:
                subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])


# ─────────────────────────── MAIN ─────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="J.A.R.V.I.S. voice assistant")
    ap.add_argument("--startup", action="store_true", help="greet like at PC login")
    ap.add_argument("--text", action="store_true", help="type commands instead of using the mic")
    ap.add_argument("--mute", action="store_true", help="don't speak, print only")
    ap.add_argument("--greet-only", action="store_true", help="say the greeting then exit")
    args = ap.parse_args()

    voice = Voice(muted=args.mute)
    listener = None
    if not args.text and not args.greet_only:
        try:
            listener = Listener()
            listener.calibrate()
        except Exception as e:
            print(f"[mic] Microphone not available ({e}). Switching to text mode.")
            listener = None

    jarvis = Jarvis(voice, listener)
    if args.startup or args.greet_only:
        jarvis.startup_greeting()
    else:
        jarvis.say(f"JARVIS online. {greeting_for_hour()}, {TITLE}.")
    if args.greet_only:
        return
    if args.startup and listener is None:
        return                                            # no mic at login: greet and exit quietly
    jarvis.run()


if __name__ == "__main__":
    main()
