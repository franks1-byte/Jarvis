"""
Meeting minutes for JARVIS.

Records your microphone + everything you hear (Discord, Zoom, Google Meet…) using
Windows WASAPI loopback, then Gemini listens to the audio and writes the minutes:
summary, highlights, decisions, action items and a transcript.
"""
import datetime
import os
import re
import threading
import time
import wave

import numpy as np

RATE = 16000                 # what we store (plenty for speech, small files)
DEVICE_RATE = 48000          # what Windows devices run at; 48k / 3 = 16k
BLOCK = 4800                 # 0.1 s at 48k

MINUTES_PROMPT = """You are JARVIS, an expert meeting secretary. The attached audio is a recorded online meeting
(Discord/voice call). It is a mix of the owner's microphone ("{owner}") and the other participants.

Write meeting minutes in Markdown, in {language}. Keep names exactly as spoken. If you can't tell who said something,
use "Speaker 1", "Speaker 2", … consistently. Use [mm:ss] timestamps from the start of the audio.

Output EXACTLY this structure:

TLDR: <one sentence, max 25 words, plain text, for being read aloud>

## Summary
<3-5 sentences>

## Highlights
- [mm:ss] <the most important moments, max 8 bullets>

## Decisions
- <decisions agreed on, or "None recorded">

## Action Items
- [ ] **<who>** — <task> — <deadline if mentioned>

## Open Questions
- <unresolved questions, or "None">

## Transcript
[mm:ss] **<speaker>:** <what they said, in the ORIGINAL language spoken (Bisaya, Tagalog, English, etc.)>
"""

ACTION_WORDS = re.compile(
    r"\b(deadline|due|submit|need to|needs to|have to|has to|will|must|assign|task|todo|to-do|"
    r"by (monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|next week)|agreed|decide[d]?)\b", re.I)


def discord_audio_active():
    """True if Discord is currently playing audio (= you're in a voice call). None if we can't tell."""
    try:
        from pycaw.pycaw import AudioUtilities
    except Exception:
        return None
    try:
        for s in AudioUtilities.GetAllSessions():
            p = s.Process
            if p and p.name().lower().startswith("discord") and s.State == 1:   # 1 = AudioSessionStateActive
                return True
    except Exception:
        return None
    return False


class MeetingRecorder:
    def __init__(self, cfg):
        self.cfg = cfg.get("meeting", {})
        self.owner = cfg.get("owner_name") or "You"
        self.folder = os.path.join(os.path.expanduser("~"), "Documents", "Jarvis Meetings")
        self.active = False
        self.started = 0.0
        self.levels = {"you": 0.0, "others": 0.0}
        self.errors = []
        self._stop = threading.Event()
        self._threads = []
        self.last_minutes = None

    # ── recording ──
    def elapsed(self):
        return time.time() - self.started if self.active else 0.0

    def start(self):
        import soundcard as sc
        os.makedirs(self.folder, exist_ok=True)
        self.started_at = datetime.datetime.now()
        self.base = os.path.join(self.folder, f"meeting_{self.started_at:%Y-%m-%d_%H%M%S}")
        speaker = sc.default_speaker()
        loopback = sc.get_microphone(id=str(speaker.name), include_loopback=True)
        mic = sc.default_microphone()

        self.errors = []
        self._stop.clear()
        self.started = time.time()
        self.active = True
        self._threads = [
            threading.Thread(target=self._record, args=(loopback, self.base + "_others.raw", "others"), daemon=True),
            threading.Thread(target=self._record, args=(mic, self.base + "_you.raw", "you"), daemon=True),
            # Windows loopback delivers no frames during total silence; playing silence keeps it flowing
            threading.Thread(target=self._keep_alive, args=(speaker,), daemon=True),
        ]
        for t in self._threads:
            t.start()

    def _keep_alive(self, speaker):
        try:
            with speaker.player(samplerate=DEVICE_RATE, channels=1) as p:
                silence = np.zeros(BLOCK, dtype=np.float32)
                while not self._stop.is_set():
                    p.play(silence)
        except Exception as e:
            self.errors.append(f"keep-alive: {e}")

    def _record(self, device, path, key):
        written = 0
        try:
            with open(path, "wb") as f, device.recorder(samplerate=DEVICE_RATE, blocksize=BLOCK) as rec:
                while not self._stop.is_set():
                    data = rec.record(numframes=BLOCK)
                    mono = data.mean(axis=1) if data.ndim > 1 else data
                    mono = mono[: len(mono) // 3 * 3].reshape(-1, 3).mean(axis=1)     # 48k -> 16k
                    self.levels[key] = float(np.sqrt(np.mean(mono ** 2))) if mono.size else 0.0
                    # keep both tracks aligned to the wall clock (fill gaps with silence)
                    expected = int((time.time() - self.started) * RATE) - len(mono)
                    if expected - written > RATE // 4:
                        gap = expected - written
                        f.write(np.zeros(gap, dtype="<i2").tobytes())
                        written += gap
                    f.write((np.clip(mono, -1, 1) * 32767).astype("<i2").tobytes())
                    written += len(mono)
                    f.flush()
        except Exception as e:
            self.errors.append(f"{key}: {e}")

    def stop(self):
        """Stop recording and return (wav_path, duration_seconds)."""
        self._stop.set()
        duration = time.time() - self.started
        self.active = False
        for t in self._threads:
            t.join(timeout=3)
        self.levels = {"you": 0.0, "others": 0.0}
        return self._mix(), duration

    def _mix(self):
        tracks = []
        for name in ("_you.raw", "_others.raw"):
            p = self.base + name
            if os.path.exists(p):
                tracks.append(np.fromfile(p, dtype="<i2").astype(np.int32))
        if not tracks or max(len(t) for t in tracks) == 0:
            raise RuntimeError("Nothing was recorded. " + "; ".join(self.errors))
        n = max(len(t) for t in tracks)
        mix = np.zeros(n, dtype=np.int32)
        for t in tracks:
            mix[: len(t)] += t
        peak = int(np.abs(mix).max()) or 1
        if peak > 32000:
            mix = (mix * (32000 / peak)).astype(np.int32)
        wav = self.base + ".wav"
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(mix.astype("<i2").tobytes())
        for name in ("_you.raw", "_others.raw"):
            try:
                os.remove(self.base + name)
            except OSError:
                pass
        return wav

    # ── minutes ──
    def write_minutes(self, wav_path, duration, brain):
        """Turn the recording into a Markdown minutes file. Returns dict(path, tldr, highlights)."""
        if brain is not None and getattr(brain, "client", None):
            body, tldr = self._gemini_minutes(wav_path, brain)
        else:
            body, tldr = self._basic_minutes(wav_path)

        when = self.started_at.strftime("%A, %B %d, %Y · %I:%M %p")
        mins = max(1, round(duration / 60))
        md = (f"# Meeting Minutes\n\n**Date:** {when}  \n**Duration:** {mins} min  \n"
              f"**Recording:** `{os.path.basename(wav_path)}`\n\n{body.strip()}\n")
        path = os.path.splitext(wav_path)[0] + "_minutes.md"
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        if not self.cfg.get("keep_audio", True):
            try:
                os.remove(wav_path)
            except OSError:
                pass
        self.last_minutes = path
        return {"path": path, "tldr": tldr, "highlights": section_bullets(body, "Highlights"),
                "actions": section_bullets(body, "Action Items")}

    def _gemini_minutes(self, wav_path, brain):
        client = brain.client
        f = client.files.upload(file=wav_path)
        for _ in range(90):                                  # wait until Gemini has processed the audio
            state = getattr(getattr(f, "state", None), "name", str(getattr(f, "state", "")))
            if "PROCESSING" not in state:
                break
            time.sleep(2)
            f = client.files.get(name=f.name)
        prompt = MINUTES_PROMPT.format(owner=self.owner, language=self.cfg.get("minutes_language", "English"))
        text = client.models.generate_content(model=brain.model, contents=[f, prompt]).text or ""
        try:
            client.files.delete(name=f.name)
        except Exception:
            pass
        tldr = ""
        m = re.search(r"^\s*TLDR:\s*(.+)$", text, re.M)
        if m:
            tldr = m.group(1).strip()
            text = text[: m.start()] + text[m.end():]
        return text, tldr

    def _basic_minutes(self, wav_path):
        """No Gemini key: free Google transcription in 30 s chunks + keyword-based highlights."""
        import speech_recognition as sr
        rec = sr.Recognizer()
        lines = []
        with wave.open(wav_path, "rb") as w:
            total = w.getnframes()
            step = RATE * 30
            for start in range(0, total, step):
                w.setpos(start)
                audio = sr.AudioData(w.readframes(min(step, total - start)), RATE, 2)
                try:
                    said = rec.recognize_google(audio, language=self.cfg.get("transcribe_language", "en-US"))
                except (sr.UnknownValueError, sr.RequestError):
                    continue
                lines.append((start // RATE, said))
        transcript = "\n".join(f"[{s // 60:02d}:{s % 60:02d}] {t}" for s, t in lines) or "_(no speech recognized)_"
        hits = [f"- [{s // 60:02d}:{s % 60:02d}] {t}" for s, t in lines if ACTION_WORDS.search(t)][:8]
        body = ("> ⚠️ Basic mode: add a Gemini API key in `config.json` for a real summary, decisions and "
                "speaker labels.\n\n## Highlights\n" + ("\n".join(hits) or "- None detected") +
                "\n\n## Transcript\n" + transcript + "\n")
        tldr = f"I transcribed {len(lines)} parts of the meeting. Add a Gemini key for a full summary."
        return body, tldr


def section_bullets(md, title):
    m = re.search(rf"^##\s*{re.escape(title)}\s*$(.*?)(?=^##\s|\Z)", md, re.M | re.S)
    if not m:
        return []
    return [re.sub(r"^\s*-\s*(\[[ x]\]\s*)?", "", l).replace("**", "").strip()
            for l in m.group(1).splitlines() if l.strip().startswith("-")]
