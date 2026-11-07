"""
Checks that everything JARVIS needs is installed, installs what's missing,
and explains problems in plain words. Run by Jarvis.bat before opening the window.
"""
import importlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# (import name, pip name, what breaks without it)
PACKAGES = [
    ("numpy", "numpy", "microphone"),
    ("sounddevice", "sounddevice", "microphone"),
    ("speech_recognition", "SpeechRecognition", "voice commands"),
    ("pyttsx3", "pyttsx3", "Jarvis's voice (will use Windows fallback)"),
    ("psutil", "psutil", "CPU / RAM / battery info"),
    ("PIL", "pillow", "screenshots"),
    ("google.genai", "google-genai", "Gemini AI answers and meeting summaries"),
    ("soundcard", "soundcard", "meeting recording"),
    ("pycaw", "pycaw", "Discord call detection"),
    ("docx", "python-docx", "Word document for meeting minutes"),
]


def missing():
    out = []
    for mod, pip_name, feature in PACKAGES:
        try:
            importlib.import_module(mod)
        except Exception as e:
            out.append((mod, pip_name, feature, e))
    return out


def main():
    print(f"Python {sys.version.split()[0]}  ({sys.executable})")

    if not os.path.exists(os.path.join(HERE, "config.json")):
        print("\n[X] config.json not found. Extract the WHOLE zip first:")
        print("    Right-click Jarvis.zip > Extract All, then run Jarvis.bat inside the extracted folder.")
        return 1

    try:
        import tkinter  # noqa: F401
    except Exception:
        print("\n[X] tkinter is missing, so the Jarvis window can't open.")
        print("    Reinstall Python from python.org and tick 'tcl/tk and IDLE' in the installer.")
        return 1

    todo = missing()
    if todo:
        print(f"\nInstalling {len(todo)} missing package(s): " + ", ".join(p for _, p, _, _ in todo))
        subprocess.call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.call([sys.executable, "-m", "pip", "install", "-r", os.path.join(HERE, "requirements.txt")])
        importlib.invalidate_caches()
        todo = missing()

    if todo:
        print("\n[!] These couldn't be installed. Jarvis still opens, but these features are off:")
        for mod, pip_name, feature, err in todo:
            print(f"    - {pip_name:18} -> {feature}   ({type(err).__name__}: {err})")
        print("    Send this list to get help fixing it.")
    else:
        print("All packages OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
