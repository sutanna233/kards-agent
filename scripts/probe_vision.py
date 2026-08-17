"""测试 Qwen3.6-35B 是否支持图像(多模态)输入。"""
import re, json, base64, urllib.request, urllib.error, sys

CRED = r"C:\Users\User\.dsh\.credentials.yaml"
BASE = "http://ai.sunjun3773.top:62222/v1"
MODEL = "Qwen3.6-35B-A3B.gguf"

txt = open(CRED, encoding="utf-8", errors="ignore").read()
m = re.search(r"SUNJUN3773_API_KEY['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]+)", txt)
key = m.group(1)

img_path = sys.argv[1] if len(sys.argv) > 1 else "logs/dbg_my_kredits.png"
b64 = base64.b64encode(open(img_path, "rb").read()).decode()

body = {
    "model": MODEL,
    "messages": [{"role": "user", "content": [
        {"type": "text", "text": "图里的数字是几?只回答数字。"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}},
    ]}],
    "max_tokens": 50, "temperature": 0.0,
}
req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(body).encode(),
    method="POST", headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
try:
    with urllib.request.urlopen(req, timeout=90) as r:
        resp = json.load(r)
    print("MULTIMODAL OK:", resp["choices"][0]["message"]["content"][:200])
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode(errors="ignore")[:300])
except Exception as e:
    print("ERR:", e)
