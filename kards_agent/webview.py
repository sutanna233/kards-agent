"""
极简 WebUI:实时看 agent 对局思维链。
- GET /         页面(2.5s 自动刷新):左最新截图,右事件流
- GET /shot.png 最新对局截图(logs/_live.png)
- GET /events   最近事件 JSON(logs/agent_events.jsonl 尾部)
启动:webview.start_server(8399) (daemon 线程,随主程序退出)
"""
from __future__ import annotations
import json, os, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG = "logs"
LIVE = os.path.join(LOG, "_live.png")
EVENTS = os.path.join(LOG, "agent_events.jsonl")

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>KARDS Agent 实况</title>
<style>
body{margin:0;background:#141414;color:#ddd;font:14px/1.5 monospace;display:flex;height:100vh}
#left{flex:0 0 auto;padding:8px}#left img{max-width:62vw;max-height:94vh;border:1px solid #444}
#right{flex:1;padding:8px;overflow-y:auto;background:#1b1b1b}
.ev{margin:4px 0;padding:6px 8px;border-left:3px solid #555;white-space:pre-wrap;word-break:break-all}
.ev .t{color:#777;margin-right:6px}
.k-state{border-color:#3a6ea5}.k-hand{border-color:#8a6d3b}.k-decision{border-color:#3aa56a;background:#15271c}
.k-exec{border-color:#6a3aa5}.k-game{border-color:#a53a3a;background:#2b1515;font-weight:bold}
.say{color:#e8c46a}
</style></head><body>
<div id="left"><img id="shot" src="/shot.png"></div>
<div id="right"></div>
<script>
async function tick(){
  try{
    const r = await fetch('/events'); const evs = await r.json();
    const el = document.getElementById('right');
    el.innerHTML = evs.map(e=>{
      const d = typeof e.data==='string'? e.data : JSON.stringify(e.data);
      return `<div class="ev k-${e.kind}"><span class="t">${e.ts}</span>${esc(d)}</div>`;
    }).join('');
    el.scrollTop = el.scrollHeight;
    document.getElementById('shot').src = '/shot.png?t='+Date.now();
  }catch(e){}
  setTimeout(tick, 2500);
}
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\"/g,'"');}
tick();
</script></body></html>"""


def emit(kind: str, data):
    """agent 各模块调用:追加一条事件(供 WebUI 拉取)。"""
    try:
        os.makedirs(LOG, exist_ok=True)
        import datetime
        rec = {"ts": datetime.datetime.now().strftime("%H:%M:%S"), "kind": kind, "data": data}
        with open(EVENTS, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


class _H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/shot.png"):
            self._file(LIVE, "image/png")
        elif self.path.startswith("/events"):
            self._events()
        else:
            self._html()

    def _html(self):
        b = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _file(self, path, ctype):
        if not os.path.exists(path):
            self.send_response(404); self.end_headers(); return
        with open(path, "rb") as f:
            b = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def _events(self, tail=80):
        lines = []
        if os.path.exists(EVENTS):
            with open(EVENTS, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()[-tail:]
        out = []
        for ln in lines:
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
        b = json.dumps(out, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


def _live_mirror(interval: float = 2.0):
    """实时镜像线程:每 ~2s 截一次模拟器画面写 logs/_live.png,
    与 agent 主循环解耦,WebUI 画面始终新鲜。"""
    from . import adbc
    while True:
        try:
            adbc.screenshot(adbc.DEFAULT_SERIAL, LIVE)
        except Exception:
            pass
        time_sleep(interval)


def time_sleep(s):
    import time
    time.sleep(s)


def start_server(port: int = 8399, mirror: bool = True) -> int:
    """后台线程起 HTTP 服务 + 实时截图镜像,返回端口。"""
    srv = ThreadingHTTPServer(("127.0.0.1", port), _H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    if mirror:
        threading.Thread(target=_live_mirror, daemon=True).start()
    return port


if __name__ == "__main__":
    port = start_server()
    print(f"WebUI: http://127.0.0.1:{port}")
    import time
    while True:
        time.sleep(3600)
