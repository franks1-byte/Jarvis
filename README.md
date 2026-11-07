# J.A.R.V.I.S. — PC + iPhone

## 💻 PART 1 — Windows PC

### Setup (isa ra ka higayon)
1. I-extract ang folder (pananglitan `C:\Jarvis`).
2. Ablihi ang **Command Prompt** sulod sa folder, dayon:
   ```
   pip install -r requirements.txt
   ```
3. I-double-click ang **`Jarvis.bat`**. Moabli ang Jarvis window (walay command prompt).

### 🖥️ Ang Jarvis window
- **🎙️ Mic button** (o **Ctrl+Space**): i-click, dayon isulti ang command. Mo-green ang reactor samtang naminaw siya ug mosayaw ang mga bar sumala sa imong tingog.
- **Type box**: pwede pud i-type ang command, dayon Enter.
- **Quick buttons**: Status, Weather, Time, Screenshot, Notes, Joke.
- **WAKE WORD ON/OFF**: kung ON, kanunay siyang naminaw. Isulti lang ang "Jarvis, …" bisan dili mo-click.
- **VOICE ON/OFF**: i-off kung dili nimo gusto nga mosulti siya (text lang).
- Kolor sa reactor: **asul** = standby, **berde** = naminaw, **orange** = nag-process.

> Gusto gihapon og command prompt version? I-double-click ang `start_jarvis_console.bat`.

### "Welcome, master" pag-open sa PC
```
python install_startup.py
```
Matag log-in nimo, moabli ang Jarvis window ug moingon siya og "Welcome, master", dayon ang time, battery, ug "All systems online".
Para tangtangon: `python install_startup.py --remove`

### Unsaon pag-command
Sugdi sa **"Jarvis"**. Human sa usa ka command, 8 seconds nga dili na kinahanglan moingon og "Jarvis" para sa sunod.

| Isulti | Buhaton |
|---|---|
| Jarvis, open chrome / spotify / roblox studio / blender | Abri app (makita bisan unsang app nga naa sa Start Menu) |
| Jarvis, open youtube / facebook / gmail | Abri website |
| Jarvis, close chrome | Sirado app |
| Jarvis, play *[kanta]* | Patugtog sa YouTube |
| Jarvis, search *[bisan unsa]* | Google search |
| Jarvis, what time is it / what's the date | Oras / petsa |
| Jarvis, weather / weather in Cagayan de Oro | Panahon |
| Jarvis, set a timer for 5 minutes | Timer |
| Jarvis, remind me to study in 30 minutes | Reminder |
| Jarvis, take a note *[...]* / read my notes | Notes |
| Jarvis, volume up / volume down / mute | Volume |
| Jarvis, pause / next / previous | Music controls |
| Jarvis, take a screenshot | Mo-save sa Pictures\Jarvis Screenshots |
| Jarvis, system status | CPU, RAM, battery |
| Jarvis, lock the computer | Lock |
| Jarvis, shut down / restart the computer | Mangutana una "Are you sure?" |
| Jarvis, tell me a joke / flip a coin / roll a dice | Fun |
| Jarvis, goodbye | Mo-offline |
| Bisan unsang pangutana | Tubagon sa Gemini AI (tan-awa ubos) |

### 📋 Meeting Minutes (Discord, Zoom, Google Meet…)
Gi-record ni Jarvis ang **imong mic** ug ang **tingog sa imong mga kauban** (bisan unsa nga madungog sa imong speakers o headset). Human sa meeting, si Gemini ang mosulat sa minutes.

**Pagsugod:**
- I-click ang **● RECORD MEETING MINUTES**, o isulti/i-type ang *"start meeting notes"*.
- **Auto-detect:** kung mo-join ka sa Discord voice call, mogawas ang banner nga *"Discord call detected. Take meeting minutes?"*. I-click ang **START**.
- Pag-end sa Discord call, automatic mo-stop ang recording.

**Pag-stop:** i-click ang **■ STOP MEETING**, o i-type ang *"stop meeting notes"*.

**Unsay makuha nimo**: automatic mo-create si Jarvis og **Word document** (`Documents\Jarvis Meetings\…_minutes.docx`) ug automatic pud kini moabli. Pwede nimo i-upload sa Google Drive para ma-edit sa Google Docs, o i-share sa imong groupmates. Naa pud `.md` copy. Ang sulod:
- **TL;DR** nga basahon ni Jarvis
- **Summary**
- **Highlights** nga naay timestamps `[mm:ss]`
- **Decisions**
- **Action Items**: kinsa, unsa, kanus-a
- **Open Questions**
- **Full transcript** sa original nga pinulongan (Bisaya, Tagalog, English) uban sa speaker labels

Ang highlights ug action items makita pud dayon sa Jarvis window. Para ablihan ang pinakaulahi: *"open my last meeting"*.

> ⚠️ Kinahanglan ang **Gemini API key** para sa summary, highlights ug speaker labels. Kung wala, transcript ra ug keyword-based highlights ang makuha.
> 🙏 **Pahibaloa ang mga kauban** nimo sa call nga gi-record ang meeting.

Settings sa `config.json` → `"meeting"`:
- `auto_start: true` = mo-record dayon nga walay pangutana
- `minutes_language` = pinulongan sa minutes, e.g. `"Filipino"`
- `keep_audio: false` = i-delete ang .wav human sa summary
- `create_docx: false` = dili na mo-create og Word file (.md ra)

### 🧠 Himoang smart (Gemini AI) — optional
1. Kuha og libre nga API key sa https://aistudio.google.com/apikey
2. I-paste sa `config.json` → `"gemini": { "api_key": "IMONG_KEY" }`
3. Karon pwede na: *"Jarvis, explain photosynthesis"*, *"Jarvis, unsay pasabot sa SDG 4?"* — motubag siya sa iyang tingog ug makahinumdom sa conversation.

### ⚙️ Customize sa `config.json`
- `user_title` — ilisi ang "master" (e.g. "boss", "sir")
- `greeting` — unsay iyang isulti pag-open sa PC
- `apps` / `websites` — dugangi og imong kaugalingong shortcut
- `city` — default city sa weather
- `language` — `"fil-PH"` kung Tagalog/Filipino ang imong ika-command (pero English nga keywords gihapon ang "open", "play", etc.)

### 🎙️ Tingog nga British (parehas sa Jarvis sa movie)
Settings → Time & Language → Speech → **Add voices** → English (United Kingdom). Mopili dayon si Jarvis og "George" o "Ryan" nga voice. Kung wala, David ang gamiton.

### Problema?
- **Wala kadungog** → check sa Windows Sound settings nga sakto ang default mic. Hilom una pag-start (nag-calibrate siya sa saba).
- **"Can't reach speech service"** → kinahanglan og internet ang voice recognition.
- **Wala'y tingog** → `pip install pyttsx3` balik; naa'y automatic fallback sa Windows voice.

---

## 📱 PART 2 — iPhone (Siri Shortcuts)

Dili pwede mag-run og Python app sa iPhone, pero mahimo nato si Jarvis gamit **Shortcuts** app ug Siri.

### A. "Welcome, master" pag-gamit sa phone
Shortcuts → **Automation** → **+** → pili-a ang trigger:
- **Charger → Is Connected** (pag-charge), o
- **Time of Day** (e.g. 6:00 AM, alarm style), o
- **App → Is Opened** (e.g. pag-abli nimo sa Spotify)

Action: **Speak Text** → isulat `Welcome, master. All systems online.` → i-set ang **Run Immediately**.

> Note: Walay trigger ang iOS para sa "pag-unlock" o "pag-on" sa phone — kini ang pinakaduol.

### B. "Hey Siri, Jarvis" — voice command para mo-open og apps
1. Shortcuts → **+** → ngalan: **Jarvis**
2. Actions:
   - **Speak Text**: `Yes, master?`
   - **Dictate Text**
   - **If** *Dictated Text* **contains** `youtube` → **Open App: YouTube**
   - **Otherwise If** contains `spotify` → **Open App: Spotify**
   - **Otherwise If** contains `facebook` → **Open App: Facebook**
   - *(dugangi og daghang If para sa imong apps)*
   - **Otherwise** → **Speak Text**: `Sorry master, I don't know that app.`
   - **End If**
3. Isulti: **"Hey Siri, Jarvis"** → "Yes, master?" → "open YouTube".

### C. Jarvis nga naay AI utok sa iPhone (Gemini)
Shortcut ngalan **Ask Jarvis**:
1. **Dictate Text**
2. **Get Contents of URL**
   - URL: `https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key=IMONG_KEY`
   - Method: **POST**, Request Body: **JSON**
   - Field `contents` (Array) → Dictionary → `parts` (Array) → Dictionary → `text` = *Dictated Text*
3. **Get Dictionary Value**: `candidates` → **Get Item from List** (First) → **Get Dictionary Value** `content.parts` → First item → `text`
4. **Speak Text** (ang resulta)

Isulti: **"Hey Siri, Ask Jarvis"** → pangutana → motubag sa tingog.

### D. Extra chada
- **Back Tap**: Settings → Accessibility → Touch → Back Tap → Double Tap → **Jarvis**. Tuktoki kaduha ang likod sa phone para ma-activate.
- Ilisan ang Siri voice: Settings → Siri → Voice → **British** para Jarvis vibes.
