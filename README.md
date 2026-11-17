# J.A.R.V.I.S. — PC + iPhone

## 💻 PART 1 — Windows PC

### Setup (isa ra ka higayon)
1. **Right-click sa `Jarvis.zip` → Extract All.** Ayaw i-run sulod sa zip.
2. I-double-click ang **`Jarvis.bat`**.
   - Automatic niya i-check ug i-install ang tanang kulang nga packages. Unang run lang ni, mga 1–3 minutos.
   - Human ana, moabli na ang Jarvis window.
3. Kung naay problema, i-run ang **`Jarvis_debug.bat`**. Makita didto ang error, i-screenshot ug i-send.

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
| Jarvis, lock my laptop | Lock |
| Jarvis, shutdown my laptop / turn off my laptop | **Mopalong dayon** (walay pangutana) |
| Jarvis, restart my laptop / sleep my laptop | Restart / Sleep dayon |
| Jarvis, cancel shutdown | I-cancel ang shutdown |
| Jarvis, screen off / go dark | **Screen Off mode**: lock + itom ang screen, pero buhi pa si Jarvis |
| Jarvis, wake up | Pasigaon balik ang screen |
| Jarvis, phone remote | Ipakita ang QR code para sa iPhone |
| Jarvis, tell me a joke / flip a coin / roll a dice | Fun |
| Jarvis, goodbye | Mo-offline |
| Bisan unsang pangutana | Tubagon sa Gemini AI (tan-awa ubos) |

### ▶️ YouTube, 🎵 Playlists, ✉️ Email, 📄 Docs

| Isulti / i-type | Buhaton ni Jarvis |
|---|---|
| *play Buwan by Juan Karlos* / *watch the Avengers trailer* | Moabli ug mo-play dayon sa YouTube |
| *create a playlist of chill OPM songs* | YouTube playlist (instant, walay login) |
| *make a 20 songs workout playlist* | Pwede nimo isulti pila ka kanta (max 50) |
| *make a Spotify playlist for studying* | Tinuod nga playlist sa imong Spotify account (setup sa ubos) |
| *write an email to my professor asking for an extension* | Si Gemini mosulat, moabli sa Gmail para imong i-review ug i-send |
| *draft an email to name@school.edu about our project* | Automatic ma-fill ang "To" |
| *create a document about the history of science* | Word file sa `Documents\Jarvis Docs`, automatic moabli |
| *write an essay / report / letter / reviewer about …* | Parehas, Word file |

- **Playlists:** si Gemini ang mopili sa mga kanta. Kung walay Gemini key, ang top YouTube results ang gamiton. Ang lista ma-save sa `Documents\Jarvis Playlists`. Sa YouTube, i-click ang **Save** aron ma-keep ang playlist.
- **Email:** dili gyud mo-send si Jarvis nga wala nimo makita. Moabli ra ang draft. Para Outlook, ilisi ang `"email_client"` sa `config.json` ngadto sa `"outlook"`, o `"default"` para sa imong mail app.
- **Contacts:** idugang sa `config.json` → `"contacts": { "mama": "mama@gmail.com", "professor": "prof@liceo.edu.ph" }`. Dayon pwede na ang *"write an email to mama …"*.
- **Google Docs:** Word file ang himoon. I-upload sa Google Drive, dayon **Open with → Google Docs**.
- Kinahanglan ang **Gemini API key** sa email ug docs content.

#### 🟢 I-connect ang Spotify (isa ra ka higayon)
1. Adto sa https://developer.spotify.com/dashboard → **Create app**.
2. Redirect URI: `http://127.0.0.1:8888/callback`. I-check ang **Web API**.
3. Kopyaha ang **Client ID** ug **Client Secret** ngadto sa `config.json` → `"spotify"`.
4. Sa unang Spotify playlist, moabli ang browser para mo-login ka ug mo-Agree. Human ana, automatic na.

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

### 🎙️ Tingog ni Jarvis
Matag tubag, **mosulti si Jarvis** gamit ang realistic nga neural voice. Default kay British male, parehas sa Jarvis sa movie. Pananglitan, kung moingon ka og *"Jarvis, what time is it?"*, motubag siya og *"It's 8:52 PM, master."* gamit iyang tingog.

**Ilisi ang tingog:** isulti o i-type ang *"change voice to …"*

| Ngalan | Tingog |
|---|---|
| `jarvis` | British male (default) |
| `british` | Lain nga British male |
| `american` | American male |
| `filipino` | Filipino English male |
| `australian` | Australian male |
| `friday` | British female (parehas ni F.R.I.D.A.Y.) |

- *"change your voice"* = sunod nga tingog sa lista
- *"list your voices"* = isulti niya ang tanang pilian
- Ang imong pili kay ma-save sa `config.json`.

**Kinahanglan og internet** ang neural voice. Kung walay internet, automatic siya mobalik sa Windows voice. Para sa mas nindot nga offline voice: Settings → Time & Language → Speech → **Add voices** → English (United Kingdom).

Para i-mute: i-click ang **VOICE ● ON** sa window.

### Problema?
- **Wala kadungog** → check sa Windows Sound settings nga sakto ang default mic. Hilom una pag-start (nag-calibrate siya sa saba).
- **"Can't reach speech service"** → kinahanglan og internet ang voice recognition.
- **Dili maka-connect ang iPhone** → parehas ba og Wi-Fi? Sa Windows: Settings → Network → imong Wi-Fi → **Private network**. I-allow ang Python sa Windows Firewall.
- **Wala'y tingog** → i-check nga ON ang **VOICE** button ug naa'y sound ang speakers. I-run ang `Jarvis.bat` para ma-install ang `edge-tts`.

---

## 📱 PART 2 — iPhone

### ⚡ Jarvis Remote: i-ON ug i-OFF ang laptop gikan sa iPhone

> Kinahanglan nga **parehas og Wi-Fi** ang iPhone ug ang laptop.
> Gusto nimo nga ma-shutdown dayon nga walay "Are you sure?"? Default na kana. Kung gusto nimo og pangutana, i-set ang `"confirm_power": true` sa `config.json`.

#### 1) Control panel sa iPhone (Lock · Sleep · Restart · Shutdown · Commands)
1. Sa Jarvis window, i-click ang **📱 PHONE**. Mogawas ang QR code.
2. I-scan gamit ang **iPhone Camera** ug ablihi ang link.
3. Sa Safari: **Share ⬆︎ → Add to Home Screen**. Mahimo na ni nga "Jarvis" app sa imong Home Screen.
4. Sa unang run, mangutana ang Windows Firewall. I-check ang **Private networks** ug i-click ang **Allow**.

Sa panel, kaduha i-tap ang Shutdown, Restart, o Sleep para dili ma-accidental. Pwede pud ka mo-type og command (pananglitan *"open youtube"*, *"what time is it"*), ug ang tubag ni Jarvis mogawas sa phone.

#### 2) ⭐ Turn ON / Turn OFF (mo-work sa TANANG laptop, bisan Wi-Fi ra)
Sa iPhone panel, gamita ang **Turn OFF** ug **Turn ON** buttons sa taas:
- **Turn OFF**: ma-lock ang laptop ug mahimong itom ang screen (0% brightness). Pero magpabilin nga buhi si Jarvis.
- **Turn ON**: mosiga balik ang screen ug moingon si Jarvis og *"Welcome back, master."* Dayon i-unlock nimo.
- Kung hilabtan nimo ang keyboard o mouse, automatic mobalik ang screen.
- Kung kulang na sa 15% ang battery ug wala naka-charge, automatic siya mo-normal aron dili maubos ang battery.
- Pwede pud gamit voice: *"Jarvis, screen off"* ug *"Jarvis, wake up"*.

> Ngano dili tinuod nga Sleep? Kadaghanan sa Wi-Fi laptops dili mapukaw gikan sa Sleep o Shutdown pinaagi sa network. Ang Screen Off mode ang paagi nga mo-work bisan unsang laptop. Gamay ra ang gamit niini nga battery kay patay ang screen, pero mas maayo kung naka-charge.
> ⚠️ Ayaw **isira ang lid**. Mo-sleep ang laptop kung isira.

#### 3) I-ON gikan sa tinuod nga Sleep/Shutdown (Wake-on-LAN, advanced)
Kung patay ang laptop, wala na si Jarvis, so ang iPhone mismo ang mopadala og "magic packet" aron mo-on ang laptop.

**Sa laptop (isa ra ka higayon):**
1. Right-click sa **`Enable_Wake_On_LAN.bat` → Run**, dayon i-click ang Yes. Iyang:
   - i-off ang Fast Startup,
   - i-on ang Wake-on-LAN sa network adapter,
   - ug ipakita ang imong MAC address.
2. **BIOS:** i-restart ang laptop, pindota ang F2, F10, F12 o Del samtang nag-boot, dayon i-enable ang **Wake on LAN**. Mahimong lain ang ngalan, sama sa *Power On by PCI-E* o *Wake from S4/S5*. Kini nga step, ikaw ra gyud ang makahimo.
3. Kung i-shutdown nimo ang laptop, kinahanglan **naka-plug ang charger ug Ethernet cable**.

**Sa iPhone:**
1. I-install ang libre nga app nga **Wake Me Up – Wake-on-LAN** gikan sa App Store.
2. Add device. Gamita ang **MAC address**, **Broadcast address**, ug **Port 9** nga makita sa **📱 PHONE** window o sa phone panel (⚡ setup).
3. I-test: i-shutdown ang laptop, dayon i-tap ang device sa app.

> ⚠️ **Importante:** Kadaghanan sa laptops **dili mo-on gikan sa Shutdown kung Wi-Fi ra**. Ethernet cable ang kinahanglan. Kung walay Ethernet port ang imong laptop, gamita ang **"Jarvis, sleep my laptop"** imbes nga shutdown. Ang ubang laptops mo-wake gikan sa sleep pinaagi sa Wi-Fi. O mopalit og USB-to-Ethernet adapter nga naay Wake-on-LAN.

#### 4) Himoang tinuod nga "app" + Siri: ang **Jarvis Remote** Shortcut
Shortcuts app → **+** → ngalan: **Jarvis Remote** → idugang kini nga mga action:

1. **Choose from Menu** nga naay: `⚡ Turn ON`, `⏻ Shutdown`, `🌙 Sleep`, `🔒 Lock`, `🔄 Restart`, `🎙️ Command`
2. Sa **⚡ Turn ON**: **Get Contents of URL** gamit ang *WAKE* link, dayon **Speak Text**. Kung naka-setup ang Wake-on-LAN, pwede pud gamiton ang **Wake Me Up** action.
3. Sa **⏻ Shutdown**: **Get Contents of URL**, i-paste ang *SHUTDOWN* link gikan sa phone panel (🔗 Links), dayon **Speak Text** → *Contents of URL*.
4. Parehas sa **Sleep**, **Lock**, ug **Restart**, gamit ang ilang tagsa-tagsa ka link.
5. Sa **🎙️ Command**:
   - **Dictate Text**
   - **URL Encode**
   - **Text**: i-paste ang *COMMAND* link, dayon idugang ang *URL Encoded Text* sa katapusan
   - **Get Contents of URL**
   - **Speak Text**
6. **Share → Add to Home Screen** → pili-i og icon. Mahimo na ni nga Jarvis app nga mo-on ug mo-off sa imong laptop.

Siri: *"Hey Siri, Jarvis Remote"*. Pwede pud ka maghimo og tagsa-tagsa ka shortcut, pananglitan **Wake Laptop** ug **Shutdown Laptop**, para *"Hey Siri, wake laptop"*.

> 💡 Kung mausab ang IP sa laptop (pananglitan `192.168.1.5` → `.7`), dili na mo-work ang mga link. Para dili mausab, i-set og **DHCP reservation** sa imong router. O i-click balik ang **📱 PHONE** para makita ang bag-ong link.

---

### Uban pang iPhone Shortcuts

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
