"""
Makes JARVIS start automatically when you log in to Windows (says "Welcome, master").

  python install_startup.py           install
  python install_startup.py --remove  uninstall
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STARTUP = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
VBS_PATH = os.path.join(STARTUP, "Jarvis.vbs")


def install():
    # pythonw = runs without the black command prompt window
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    python = pyw if os.path.exists(pyw) else sys.executable
    script = os.path.join(BASE_DIR, "gui.py")
    vbs = (
        'Set sh = CreateObject("WScript.Shell")\n'
        f'sh.CurrentDirectory = "{BASE_DIR}"\n'
        f'sh.Run """{python}"" ""{script}"" --startup", 1, False\n'
    )
    with open(VBS_PATH, "w", encoding="utf-8") as f:
        f.write(vbs)
    print(f"Installed! JARVIS will greet you at every login.\n  -> {VBS_PATH}")


def remove():
    if os.path.exists(VBS_PATH):
        os.remove(VBS_PATH)
        print("Removed JARVIS from startup.")
    else:
        print("JARVIS was not in startup.")


if __name__ == "__main__":
    remove() if "--remove" in sys.argv else install()
