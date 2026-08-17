"""让 Qwen35B 直接看完整对局截图,验证它能否读懂 KARDS 对局画面。"""
import re, json, base64, urllib.request, urllib.error, sys

CRED = r"C:\Users\User\.dsh\.credentials.yaml"
BASE = "http://ai.sunjun3773.top:62222/v1"
MODEL = "Qwen3.6-35B-A3B.gguf"
txt = open(CRED, encoding="utf-8", errors="ignore").read()
key = re.search(r"SUNJUN3773_API_KEY['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]+)", txt).group(1)

img_path = sys.argv[1]
b64 = base64.b64encode(open(img_path, "rb").read()).decode()

prompt = (
    "这是二战卡牌游戏 KARDS 的对局截图。请仔细观察并回答:\n"
    "1. 当前处于什么阶段?(换牌/我方回合/敌方回合/结算)\n"
    "2. 对手HQ血量是多少?我方HQ血量是多少?\n"
    "3. 我方可用的指挥点(Kredits)是多少?\n"
    "4. 我方手牌有哪几张?分别给出:卡名、费用、攻击、防御、单位类型。\n"
    "请逐条简明回答。"
)
body = {
    "model": MODEL,
    "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}},
    ]}],
    "max_tokens": 500, "temperature": 0.0,
}
req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(body).encode(),
    method="POST", headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
try:
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.load(r)
    print(resp["choices"][0]["message"]["content"])
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode(errors="ignore")[:400])
except Exception as e:
    print("ERR:", e)
