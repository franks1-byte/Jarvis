"""
JARVIS creators: YouTube videos & playlists, Spotify playlists, email drafts, Word documents.
Gemini writes the content; this module turns it into real things you can open.
"""
import datetime
import json
import os
import re
import urllib.parse
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor

HOME_DOCS = os.path.join(os.path.expanduser("~"), "Documents")
DOCS_DIR = os.path.join(HOME_DOCS, "Jarvis Docs")
PLAYLIST_DIR = os.path.join(HOME_DOCS, "Jarvis Playlists")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept-Language": "en"}


def slug(text, n=60):
    s = re.sub(r"[^\w\s-]", "", text).strip()
    s = re.sub(r"\s+", " ", s)[:n].strip()
    return s or "Untitled"


def open_file(path):
    if os.name == "nt":
        os.startfile(path)
    else:
        print(f"[open] {path}")


def _json_from(text):
    """Pull a JSON object/array out of a model reply (tolerates ```json fences)."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    m = re.search(r"(\{.*\}|\[.*\])", text, re.S)
    return json.loads(m.group(1) if m else text)


# ─────────────────────────── YouTube ──────────────────────────────────────────
def youtube_search(query, n=1):
    """Top results for a search as [(video_id, title)] — no API key needed."""
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
    html = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=8).read().decode("utf-8", "ignore")
    out, seen = [], set()
    for m in re.finditer(r'"videoRenderer":\{"videoId":"([\w-]{11})".{0,3000}?"title":\{"runs":\[\{"text":"((?:[^"\\]|\\.)*)"', html, re.S):
        vid = m.group(1)
        if vid in seen:
            continue
        seen.add(vid)
        try:
            title = json.loads(f'"{m.group(2)}"')
        except ValueError:
            title = m.group(2)
        out.append((vid, title))
        if len(out) >= n:
            return out
    for vid in re.findall(r'"videoId":"([\w-]{11})"', html):   # fallback if YouTube changes its page layout
        if vid not in seen:
            seen.add(vid)
            out.append((vid, f"{query} #{len(out) + 1}"))
        if len(out) >= n:
            break
    return out


def youtube_ids(query, n=1):
    return [vid for vid, _ in youtube_search(query, n)]


def play_youtube(query):
    """Open the top result for a search. Returns the URL opened."""
    try:
        ids = youtube_ids(query, 1)
        url = f"https://www.youtube.com/watch?v={ids[0]}" if ids else None
    except Exception:
        url = None
    url = url or "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
    webbrowser.open(url)
    return url


def youtube_playlist_url(ids):
    """YouTube builds an instant playlist from up to 50 IDs — no login needed (save it with 'Save')."""
    return "https://www.youtube.com/watch_videos?video_ids=" + ",".join(ids[:50])


# ─────────────────────────── playlists ────────────────────────────────────────
def pick_songs(brain, request, count):
    """Ask Gemini for a song list. Returns (playlist name, [{'title','artist'}])."""
    prompt = (f"Create a music playlist for this request: \"{request}\". Return ONLY JSON: "
              f'{{"name": "<short catchy playlist name>", "songs": [{{"title": "...", "artist": "..."}}]}} '
              f"with exactly {count} real, well-known songs that exist on YouTube and Spotify. No duplicates.")
    data = _json_from(brain.write(prompt, json_mode=True))
    songs = [s for s in data.get("songs", []) if s.get("title")][:count]
    return data.get("name") or slug(request.title(), 40), songs


def build_youtube_playlist(songs=None, query=None, count=15):
    """From a song list (best) or just a search query (no Gemini). Returns (url, [(label, video_id)])."""
    found = []
    if songs:
        def first(song):
            label = f"{song['title']} — {song.get('artist', '')}".strip(" —")
            try:
                ids = youtube_ids(f"{song['title']} {song.get('artist', '')} official", 1)
                return (label, ids[0]) if ids else None
            except Exception:
                return None
        with ThreadPoolExecutor(6) as pool:
            found = [r for r in pool.map(first, songs) if r]
    elif query:
        found = [(title, vid) for vid, title in youtube_search(query, count)]
    if not found:
        raise RuntimeError("couldn't find any videos")
    return youtube_playlist_url([v for _, v in found]), found


def build_spotify_playlist(cfg, name, songs, base_dir):
    """Real playlist in your Spotify account. Needs a free Spotify developer app (see README)."""
    sc = cfg.get("spotify", {})
    if not (sc.get("client_id") and sc.get("client_secret")):
        raise PermissionError("spotify not set up")
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=sc["client_id"], client_secret=sc["client_secret"],
        redirect_uri=sc.get("redirect_uri", "http://127.0.0.1:8888/callback"),
        scope="playlist-modify-private playlist-modify-public",
        cache_path=os.path.join(base_dir, ".spotify_token"), open_browser=True))
    user = sp.current_user()["id"]
    uris, missing = [], []
    for s in songs:
        res = sp.search(q=f"track:{s['title']} artist:{s.get('artist', '')}", type="track", limit=1)
        items = res.get("tracks", {}).get("items", [])
        if not items:
            res = sp.search(q=f"{s['title']} {s.get('artist', '')}", type="track", limit=1)
            items = res.get("tracks", {}).get("items", [])
        (uris.append(items[0]["uri"]) if items else missing.append(s["title"]))
    pl = sp.user_playlist_create(user, name, public=False, description="Made by J.A.R.V.I.S.")
    for i in range(0, len(uris), 100):
        sp.playlist_add_items(pl["id"], uris[i:i + 100])
    return pl["external_urls"]["spotify"], len(uris), missing


def save_playlist_file(name, entries, url, platform):
    os.makedirs(PLAYLIST_DIR, exist_ok=True)
    path = os.path.join(PLAYLIST_DIR, f"{slug(name)}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{name}\n{platform} · {datetime.datetime.now():%B %d, %Y %I:%M %p}\n{url}\n\n")
        for i, (label, extra) in enumerate(entries, 1):
            f.write(f"{i:2d}. {label}" + (f"   https://youtu.be/{extra}" if extra else "") + "\n")
    return path


# ─────────────────────────── email ────────────────────────────────────────────
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def draft_email(brain, request, owner, contacts):
    """Gemini drafts {to, subject, body}. Recipient comes from an address or a saved contact name."""
    to = ""
    m = EMAIL_RE.search(request)
    if m:
        to = m.group(0)
    else:
        for name, addr in (contacts or {}).items():
            if re.search(rf"\b{re.escape(name.lower())}\b", request.lower()):
                to = addr
                break
    if brain is None or not getattr(brain, "client", None):
        return {"to": to, "subject": slug(request.capitalize(), 70), "body": ""}
    prompt = (f"Write an email for this request: \"{request}\". The sender's name is {owner}. "
              "Natural, polite, concise; match the tone the request implies (formal for teachers/work). "
              'Return ONLY JSON: {"subject": "...", "body": "..."} — body is plain text with line breaks, '
              "including greeting and sign-off with the sender's name. No placeholders like [Name] unless unavoidable.")
    data = _json_from(brain.write(prompt, json_mode=True))
    return {"to": to, "subject": data.get("subject", ""), "body": data.get("body", "")}


def open_email(draft, client="gmail"):
    """Open the draft in your mail app for review — Jarvis never sends on his own."""
    q = urllib.parse.quote
    if client == "outlook":
        url = (f"https://outlook.office.com/mail/deeplink/compose?to={q(draft['to'])}"
               f"&subject={q(draft['subject'])}&body={q(draft['body'])}")
    elif client == "default":
        url = f"mailto:{q(draft['to'])}?subject={q(draft['subject'])}&body={q(draft['body'])}"
    else:
        url = (f"https://mail.google.com/mail/?view=cm&fs=1&to={q(draft['to'])}"
               f"&su={q(draft['subject'])}&body={q(draft['body'])}")
    webbrowser.open(url)
    return url


# ─────────────────────────── documents ────────────────────────────────────────
def write_document(brain, request):
    """Gemini writes Markdown for the request. Returns (title, markdown)."""
    prompt = (f"Write a complete, well-structured document for this request: \"{request}\".\n"
              "Format in Markdown: first line '# <Title>', then '## ' section headings, paragraphs, '- ' bullets, "
              "'1. ' numbered lists and **bold** where useful. Aim for 500-900 words unless the request implies "
              "otherwise (a letter or short note should be short). No preamble, no closing remarks about the document.")
    md = brain.write(prompt).strip()
    md = re.sub(r"^```(?:markdown)?|```$", "", md, flags=re.M).strip()
    m = re.search(r"^#\s+(.+)$", md, re.M)
    title = m.group(1).strip() if m else slug(request.capitalize(), 70)
    return title, md


def markdown_to_docx(md, path, subtitle="Created by J.A.R.V.I.S."):
    from docx import Document
    from docx.shared import Pt, RGBColor, Cm

    accent = RGBColor(0x0B, 0x6E, 0x99)
    grey = RGBColor(0x6B, 0x7B, 0x8C)
    doc = Document()
    for sec in doc.sections:
        sec.left_margin = sec.right_margin = Cm(2.4)
        sec.top_margin = sec.bottom_margin = Cm(2.2)
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(11)
    st.paragraph_format.space_after = Pt(6)
    st.paragraph_format.line_spacing = 1.15

    def runs(par, text, **kw):
        for i, part in enumerate(re.split(r"(\*\*.+?\*\*|\*[^*\s][^*]*?\*)", text)):
            if not part:
                continue
            if part.startswith("**") and part.endswith("**"):
                r = par.add_run(part[2:-2])
                r.bold = True
            elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                r = par.add_run(part[1:-1])
                r.italic = True
            else:
                r = par.add_run(part)
            if kw.get("color"):
                r.font.color.rgb = kw["color"]
            if kw.get("size"):
                r.font.size = Pt(kw["size"])
        return par

    titled = False
    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("# ") and not titled:
            p = doc.add_paragraph()
            r = p.add_run(line[2:].strip())
            r.bold = True
            r.font.size = Pt(24)
            r.font.color.rgb = accent
            runs(doc.add_paragraph(), f"{subtitle} · {datetime.datetime.now():%B %d, %Y}", color=grey, size=9)
            titled = True
        elif re.match(r"^#{1,6}\s", line):
            level = min(3, max(1, len(line) - len(line.lstrip("#")) - 1))
            h = doc.add_heading(level=level)
            r = h.add_run(line.lstrip("#").strip())
            r.font.color.rgb = accent
        elif re.match(r"^\s*[-*]\s+", line):
            indent = (len(line) - len(line.lstrip())) // 2
            p = doc.add_paragraph(style="List Bullet 2" if indent else "List Bullet")
            runs(p, re.sub(r"^\s*[-*]\s+", "", line))
        elif re.match(r"^\s*\d+[.)]\s+", line):
            runs(doc.add_paragraph(style="List Number"), re.sub(r"^\s*\d+[.)]\s+", "", line))
        elif line.startswith(">"):
            p = runs(doc.add_paragraph(), line.lstrip("> "), color=grey)
            for r in p.runs:
                r.italic = True
        elif re.match(r"^-{3,}$|^\*{3,}$", line.strip()):
            continue
        else:
            runs(doc.add_paragraph(), line)
    doc.save(path)
    return path


def create_docx(title, md):
    os.makedirs(DOCS_DIR, exist_ok=True)
    base = os.path.join(DOCS_DIR, slug(title))
    path, n = base + ".docx", 2
    while os.path.exists(path):
        path, n = f"{base} ({n}).docx", n + 1
    return markdown_to_docx(md, path)
