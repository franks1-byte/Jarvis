"""
JARVIS iPhone remote.

A tiny web server (same Wi-Fi only, protected by a secret token) so your iPhone can:
  • open a JARVIS control panel (Lock / Sleep / Restart / Shutdown / send commands)
  • be driven by Siri Shortcuts:  /api/shutdown, /api/sleep, /api/lock, /api/restart, /api/command?q=…
Turning the laptop ON is done with Wake-on-LAN from the phone (the PC's server is off then);
this module shows the MAC/broadcast address the iPhone wake app needs.
"""
import io
import json
import os
import secrets
import socket
import string
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

POWER_ACTIONS = ("shutdown", "restart", "sleep", "lock", "cancel")
SKIP_ADAPTERS = ("loopback", "vethernet", "virtual", "vmware", "vbox", "bluetooth", "hyper-v",
                 "tailscale", "zerotier", "wsl", "docker", "npcap", "teredo", "isatap", "pseudo")


def new_token(n=10):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def local_ip():
    """IP of the adapter used for the internet/LAN (no packet is actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def network_info():
    """Adapters with MAC + IPv4 + broadcast, the active one first. Needs psutil."""
    ip = local_ip()
    info = {"ip": ip, "hostname": socket.gethostname(), "adapters": [], "active": None}
    try:
        import psutil
    except ImportError:
        return info
    stats = psutil.net_if_stats()
    for name, addrs in psutil.net_if_addrs().items():
        if any(k in name.lower() for k in SKIP_ADAPTERS):
            continue
        mac = next((a.address for a in addrs if a.family == getattr(psutil, "AF_LINK", -1)), "")
        mac = mac.replace("-", ":").upper()
        if not mac or mac == "00:00:00:00:00:00" or len(mac) != 17:
            continue
        v4 = next((a for a in addrs if a.family == socket.AF_INET), None)
        bcast = ""
        if v4 and v4.netmask:
            ipn = [int(x) for x in v4.address.split(".")]
            msk = [int(x) for x in v4.netmask.split(".")]
            bcast = ".".join(str(i | (255 - m)) for i, m in zip(ipn, msk))
        low = name.lower()
        kind = "wifi" if any(k in low for k in ("wi-fi", "wifi", "wlan", "wireless")) else \
               "ethernet" if any(k in low for k in ("ethernet", "eth", "lan")) else "other"
        a = {"name": name, "mac": mac, "kind": kind, "ip": v4.address if v4 else "",
             "broadcast": bcast, "up": bool(stats.get(name) and stats[name].isup)}
        info["adapters"].append(a)
        if v4 and v4.address == ip:
            info["active"] = a
    # Ethernet first: laptops usually only wake from shutdown over a cable
    info["adapters"].sort(key=lambda a: (a["kind"] != "ethernet", a is not info["active"]))
    return info


def status():
    out = {"online": True, "hostname": socket.gethostname(), "time": time.strftime("%I:%M %p").lstrip("0")}
    try:
        import psutil
        out["cpu"] = round(psutil.cpu_percent(interval=0.3))
        out["ram"] = round(psutil.virtual_memory().percent)
        b = psutil.sensors_battery()
        if b:
            out["battery"] = int(b.percent)
            out["plugged"] = bool(b.power_plugged)
        out["uptime_min"] = int((time.time() - psutil.boot_time()) // 60)
    except Exception:
        pass
    return out


def app_icon_png():
    """Home-screen icon drawn with Pillow (cyan reactor on black)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    s = 360
    img = Image.new("RGB", (s, s), (3, 6, 11))
    d = ImageDraw.Draw(img)
    c = s // 2
    for r, w, col in ((140, 6, (20, 70, 100)), (118, 10, (43, 216, 255)), (84, 4, (30, 120, 160))):
        d.ellipse((c - r, c - r, c + r, c + r), outline=col, width=w)
    for k in range(3):
        d.arc((c - 100, c - 100, c + 100, c + 100), start=k * 120 + 15, end=k * 120 + 85, fill=(43, 216, 255), width=12)
    for i, r in enumerate(range(58, 0, -6)):
        t = i / 9
        col = tuple(int(a + (b - a) * t) for a, b in zip((8, 50, 70), (225, 250, 255)))
        d.ellipse((c - r, c - r, c + r, c + r), fill=col)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


class RemoteServer:
    """
    jarvis       – the Jarvis engine (needs .power(action, source) and .run_captured(text))
    run_command  – callable(text, timeout) -> list of reply strings (lets the GUI queue it)
    """

    def __init__(self, jarvis, cfg, run_command, on_event=None):
        self.jarvis = jarvis
        self.cfg = cfg
        self.run_command = run_command
        self.on_event = on_event or (lambda kind, text: None)
        self.port = int(cfg.get("port", 8765))
        self.token = cfg["token"]
        self.httpd = None
        self.error = None
        self._icon = None

    # ── urls ──
    def base_url(self, ip=None):
        return f"http://{ip or local_ip()}:{self.port}"

    def panel_url(self, ip=None):
        return f"{self.base_url(ip)}/?t={self.token}"

    def api_url(self, action, ip=None):
        return f"{self.base_url(ip)}/api/{action}?t={self.token}"

    # ── lifecycle ──
    def start(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body, ctype="text/plain; charset=utf-8", cache=False):
                data = body if isinstance(body, bytes) else body.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "max-age=86400" if cache else "no-store")
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                server._route(self, "GET")

            def do_POST(self):
                server._route(self, "POST")

        try:
            self.httpd = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        except OSError as e:
            self.error = f"port {self.port} unavailable ({e})"
            print(f"[remote] Phone remote off: {self.error}")
            return False
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        print(f"[remote] iPhone remote ready: {self.panel_url()}")
        return True

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()

    # ── routing ──
    def _route(self, h, method):
        url = urllib.parse.urlparse(h.path)
        qs = urllib.parse.parse_qs(url.query)
        path = url.path.rstrip("/") or "/"

        if path in ("/icon.png", "/apple-touch-icon.png", "/favicon.ico"):
            if self._icon is None:
                self._icon = app_icon_png() or b""
            return h._send(200, self._icon, "image/png", cache=True) if self._icon else h._send(404, "")
        if path == "/manifest.json":
            return h._send(200, json.dumps({
                "name": "J.A.R.V.I.S. Remote", "short_name": "Jarvis", "display": "standalone",
                "background_color": "#03060b", "theme_color": "#03060b",
                "start_url": f"/?t={self.token}", "icons": [{"src": "/icon.png", "sizes": "360x360", "type": "image/png"}],
            }), "application/manifest+json")

        token = (qs.get("t") or [""])[0] or h.headers.get("X-Jarvis-Token", "")
        if not secrets.compare_digest(token, self.token):
            return h._send(403, "Wrong or missing Jarvis token.")

        if path == "/":
            return h._send(200, self._panel_html(), "text/html; charset=utf-8")
        if path == "/api/status":
            return h._send(200, json.dumps(status()), "application/json")
        if path == "/api/info":
            return h._send(200, json.dumps(self._setup_info()), "application/json")

        action = path[len("/api/"):] if path.startswith("/api/") else ""
        if action in POWER_ACTIONS:
            src = (qs.get("from") or ["iPhone"])[0][:20]
            msg = {"shutdown": "Shutting down your laptop now.", "restart": "Restarting your laptop now.",
                   "sleep": "Putting your laptop to sleep.", "lock": "Laptop locked.",
                   "cancel": "Shutdown cancelled."}[action]
            self.on_event("remote", f"📱 {src}: {action}")
            h._send(200, msg)
            threading.Thread(target=lambda: (time.sleep(0.4), self.jarvis.power(action, source=src)),
                             daemon=True).start()
            return
        if action == "command":
            text = (qs.get("q") or [""])[0]
            if method == "POST" and not text:
                n = int(h.headers.get("Content-Length") or 0)
                raw = h.rfile.read(min(n, 4000)).decode("utf-8", "ignore") if n else ""
                try:
                    text = json.loads(raw).get("q", "")
                except (ValueError, AttributeError):
                    text = raw
            text = text.strip()[:300]
            if not text:
                return h._send(400, "Say or type a command.")
            self.on_event("remote", f"📱 {text}")
            replies = self.run_command(text, 25)
            reply = " ".join(r for r in replies if r).strip() or "Done."
            return h._send(200, reply)
        return h._send(404, "Unknown Jarvis remote command.")

    def _setup_info(self):
        net = network_info()
        ip = net["ip"]
        return {"hostname": net["hostname"], "ip": ip, "port": self.port, "adapters": net["adapters"],
                "active": net["active"], "panel": self.panel_url(ip),
                "links": {a: self.api_url(a, ip) for a in ("shutdown", "sleep", "lock", "restart", "cancel")},
                "command": self.api_url("command", ip) + "&q="}

    # ── phone web app ──
    def _panel_html(self):
        return PANEL_HTML.replace("__TOKEN__", self.token)


PANEL_HTML = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Jarvis">
<meta name="theme-color" content="#03060b">
<link rel="apple-touch-icon" href="/icon.png">
<link rel="manifest" href="/manifest.json">
<title>J.A.R.V.I.S. Remote</title>
<style>
:root{--bg:#03060b;--panel:#07101d;--panel2:#0b1829;--line:#14324d;--cyan:#2bd8ff;--text:#d4f3ff;
--muted:#5b86a3;--green:#38ffa5;--amber:#ffb53d;--red:#ff4d6d}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;background:var(--bg);color:var(--text);font:15px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
body{padding:calc(env(safe-area-inset-top) + 14px) 16px calc(env(safe-area-inset-bottom) + 24px);max-width:520px;margin:auto}
.mono{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;letter-spacing:.08em}
header{display:flex;justify-content:space-between;align-items:flex-start}
h1{margin:0;font-size:20px;font-weight:600;color:var(--cyan);letter-spacing:.32em}
.sub{font-size:9px;color:var(--muted);margin-top:2px}
.pill{display:flex;align-items:center;gap:6px;font-size:11px;padding:6px 10px;border:1px solid var(--line);border-radius:99px;background:var(--panel)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--muted)}
.on .dot{background:var(--green);box-shadow:0 0 10px var(--green)}
.off .dot{background:var(--red)}
.hero{position:relative;margin:18px auto 6px;width:220px;height:220px}
.hero svg{width:100%;height:100%}
.spin{transform-origin:110px 110px;animation:spin 14s linear infinite}
.spin2{transform-origin:110px 110px;animation:spin 9s linear infinite reverse}
@keyframes spin{to{transform:rotate(360deg)}}
.offline .spin,.offline .spin2{animation-play-state:paused}
.stats{display:flex;justify-content:center;gap:18px;font-size:11px;color:var(--muted);margin-bottom:18px}
.stats b{color:var(--text);font-weight:600}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
button{font:inherit;color:inherit;border:1px solid var(--line);background:var(--panel);border-radius:16px;cursor:pointer}
.pw{padding:16px 12px;display:flex;flex-direction:column;align-items:center;gap:8px;min-height:92px;transition:background .15s,border-color .15s}
.pw svg{width:26px;height:26px;stroke:var(--cyan);fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.pw span{font-size:13px}
.pw:active{background:var(--panel2)}
.pw.danger svg{stroke:var(--red)}
.pw.arm{border-color:var(--amber);background:#1a1407}
.pw.arm span{color:var(--amber)}
.card{margin-top:16px;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:14px}
.label{font-size:10px;color:var(--muted);margin-bottom:8px}
.row{display:flex;gap:8px}
input{flex:1;min-width:0;font:inherit;font-size:16px;color:var(--text);background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:12px}
input:focus{outline:none;border-color:var(--cyan)}
.send{padding:0 16px;background:var(--cyan);color:var(--bg);font-weight:700;border:0}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.chips button{font-size:12px;padding:7px 11px;border-radius:99px;background:var(--panel2)}
.reply{margin-top:10px;font-size:14px;min-height:20px;color:var(--text)}
.reply.wait{color:var(--muted)}
details{margin-top:16px;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:12px 14px}
summary{cursor:pointer;font-size:13px;color:var(--cyan);list-style:none}
summary::-webkit-details-marker{display:none}
.kv{margin-top:10px}
.kv .k{font-size:10px;color:var(--muted);margin:10px 0 4px}
.copy{display:flex;gap:6px}
.copy input{font-size:12px;padding:9px;font-family:ui-monospace,Menlo,monospace}
.copy button{font-size:11px;padding:0 10px;border-radius:10px}
.note{font-size:12px;color:var(--muted);margin-top:8px}
.warn{color:var(--amber)}
.toast{position:fixed;left:50%;bottom:calc(env(safe-area-inset-bottom) + 20px);transform:translateX(-50%) translateY(30px);
opacity:0;background:var(--panel2);border:1px solid var(--line);padding:10px 16px;border-radius:99px;font-size:13px;transition:.25s;pointer-events:none}
.toast.show{opacity:1;transform:translateX(-50%)}
</style></head>
<body>
<header>
  <div><h1>JARVIS</h1><div class="sub mono">IPHONE REMOTE</div></div>
  <div id="pill" class="pill mono"><span class="dot"></span><span id="pilltext">CONNECTING</span></div>
</header>

<div class="hero" id="hero">
<svg viewBox="0 0 220 220" aria-hidden="true">
  <circle cx="110" cy="110" r="104" fill="none" stroke="#0e2335" stroke-width="1"/>
  <g class="spin"><circle cx="110" cy="110" r="92" fill="none" stroke="#2bd8ff" stroke-width="3" stroke-dasharray="70 26"/></g>
  <g class="spin2"><circle cx="110" cy="110" r="76" fill="none" stroke="#14506b" stroke-width="8" stroke-dasharray="18 30"/></g>
  <circle cx="110" cy="110" r="56" fill="none" stroke="#2bd8ff" stroke-width="2"/>
  <circle cx="110" cy="110" r="46" fill="#0a2a3a"/><circle cx="110" cy="110" r="34" fill="#1a6f8f"/>
  <circle cx="110" cy="110" r="22" fill="#7fe6ff"/><circle cx="110" cy="110" r="10" fill="#eafcff"/>
</svg></div>
<div class="stats mono" id="stats"><span>—</span></div>

<div class="grid">
  <button class="pw" data-act="lock"><svg viewBox="0 0 24 24"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg><span>Lock</span></button>
  <button class="pw" data-act="sleep" data-confirm="1"><svg viewBox="0 0 24 24"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/></svg><span>Sleep</span></button>
  <button class="pw" data-act="restart" data-confirm="1"><svg viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.3-5.6"/><path d="M20 4v5h-5"/></svg><span>Restart</span></button>
  <button class="pw danger" data-act="shutdown" data-confirm="1"><svg viewBox="0 0 24 24"><path d="M12 3v9"/><path d="M6.3 6.8a8 8 0 1 0 11.4 0"/></svg><span>Shutdown</span></button>
</div>

<div class="card">
  <div class="label mono">COMMAND JARVIS</div>
  <form class="row" id="cmdform"><input id="cmd" placeholder="e.g. open youtube" autocomplete="off" enterkeyhint="send"><button class="send" type="submit">SEND</button></form>
  <div class="chips">
    <button data-q="what time is it">Time</button><button data-q="system status">Status</button>
    <button data-q="weather">Weather</button><button data-q="play lofi hip hop">Lofi</button>
    <button data-q="volume up">Vol +</button><button data-q="volume down">Vol −</button>
    <button data-q="pause">Play/Pause</button><button data-q="take a screenshot">Screenshot</button>
  </div>
  <div class="reply" id="reply"></div>
  <div class="note">Tip: tap the 🎤 on your iPhone keyboard to speak your command.</div>
</div>

<details id="setup">
  <summary>⚡ Turn the laptop ON from iPhone — setup</summary>
  <div class="note">When the laptop is off this page can't load, so waking it uses Wake-on-LAN from the free
  <b>Wake Me Up – Wake-on-LAN</b> app. Add a device in that app with these values:</div>
  <div class="kv" id="wake"></div>
  <div class="note warn" id="wakewarn"></div>
</details>

<details>
  <summary>🔗 Links for Siri Shortcuts</summary>
  <div class="note">In Shortcuts use <b>Get Contents of URL</b> with these, then <b>Speak Text</b>.</div>
  <div class="kv" id="links"></div>
</details>

<div class="note" style="text-align:center;margin-top:18px">Add to Home Screen: Share ⬆︎ → <b>Add to Home Screen</b></div>
<div class="toast" id="toast"></div>

<script>
const T = new URLSearchParams(location.search).get("t") || "__TOKEN__";
const $ = s => document.querySelector(s);
const api = (p, extra="") => `/api/${p}?t=${encodeURIComponent(T)}${extra}`;
function toast(msg){const t=$("#toast");t.textContent=msg;t.classList.add("show");clearTimeout(t._h);t._h=setTimeout(()=>t.classList.remove("show"),2600)}
function online(on, text){const p=$("#pill");p.className="pill mono "+(on?"on":"off");$("#pilltext").textContent=text;
  $("#hero").classList.toggle("offline",!on)}

async function poll(){
  try{
    const r = await fetch(api("status"),{cache:"no-store"}); if(!r.ok) throw 0;
    const s = await r.json(); online(true,"ONLINE");
    const parts=[`<span><b>${s.hostname}</b></span>`];
    if(s.battery!=null) parts.push(`<span>BAT <b>${s.battery}%</b>${s.plugged?" ⚡":""}</span>`);
    if(s.cpu!=null) parts.push(`<span>CPU <b>${s.cpu}%</b></span>`);
    if(s.ram!=null) parts.push(`<span>RAM <b>${s.ram}%</b></span>`);
    $("#stats").innerHTML=parts.join("");
  }catch(e){ online(false,"OFFLINE"); $("#stats").innerHTML="<span>Laptop is off or not on this Wi-Fi</span>"; }
}

document.querySelectorAll(".pw").forEach(b=>{
  b.addEventListener("click", async ()=>{
    const act=b.dataset.act;
    if(b.dataset.confirm && !b.classList.contains("arm")){
      document.querySelectorAll(".pw.arm").forEach(x=>{x.classList.remove("arm");x.querySelector("span").textContent=x._label});
      b._label=b._label||b.querySelector("span").textContent;
      b.classList.add("arm"); b.querySelector("span").textContent="Tap again";
      clearTimeout(b._h); b._h=setTimeout(()=>{b.classList.remove("arm");b.querySelector("span").textContent=b._label},3000);
      return;
    }
    if(b._label){b.classList.remove("arm");b.querySelector("span").textContent=b._label}
    try{ const r=await fetch(api(act)); toast(await r.text()); if(act!=="lock") setTimeout(poll,4000);}
    catch(e){ toast("Can't reach the laptop"); }
  });
});

async function send(q){
  q=q.trim(); if(!q) return;
  const out=$("#reply"); out.className="reply wait"; out.textContent="Jarvis is working…";
  try{ const r=await fetch(api("command","&q="+encodeURIComponent(q))); out.className="reply"; out.textContent=await r.text(); }
  catch(e){ out.className="reply"; out.textContent="Can't reach the laptop."; }
}
$("#cmdform").addEventListener("submit",e=>{e.preventDefault();send($("#cmd").value);$("#cmd").value="";$("#cmd").blur()});
document.querySelectorAll(".chips button").forEach(b=>b.addEventListener("click",()=>send(b.dataset.q)));

function copyRow(label, value){
  const id="c"+Math.random().toString(36).slice(2,8);
  return `<div class="k mono">${label}</div><div class="copy"><input id="${id}" readonly value="${value}"><button onclick="copyIt('${id}')">Copy</button></div>`;
}
window.copyIt = id => { const el=document.getElementById(id); el.focus(); el.select(); el.setSelectionRange(0,9999);
  let ok=false; try{ ok=document.execCommand("copy"); }catch(e){}
  toast(ok?"Copied":"Selected — tap and hold to copy"); el.blur(); };

async function loadInfo(){
  try{
    const i = await (await fetch(api("info"))).json();
    const eth = i.adapters.find(a=>a.kind==="ethernet");
    const pick = eth || i.active || i.adapters[0];
    let html = "";
    if(pick){
      html += copyRow(`MAC ADDRESS (${pick.name})`, pick.mac);
      html += copyRow("BROADCAST ADDRESS", pick.broadcast || (i.ip.split(".").slice(0,3).join(".")+".255"));
      html += copyRow("PORT", "9");
    }
    const others = i.adapters.filter(a=>a!==pick);
    if(others.length) html += `<div class="note">Other adapters: ${others.map(a=>`${a.name} ${a.mac}`).join(" · ")}</div>`;
    $("#wake").innerHTML = html;
    $("#wakewarn").textContent = eth
      ? "Waking from Shutdown works best with the Ethernet cable plugged in and the charger connected. Run Enable_Wake_On_LAN.bat on the laptop once."
      : "No Ethernet port found. Most laptops can't wake from Shutdown over Wi-Fi — use Sleep instead, or a USB/Ethernet adapter that supports Wake-on-LAN.";
    $("#links").innerHTML = Object.entries(i.links).map(([k,v])=>copyRow(k.toUpperCase(), v)).join("")
      + copyRow("COMMAND (add your text after q=)", i.command);
  }catch(e){}
}
poll(); loadInfo(); setInterval(poll, 6000);
</script>
</body></html>
"""
