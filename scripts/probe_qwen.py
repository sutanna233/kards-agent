"""探测 sunjun3773/Qwen3.6 端点:从 DSH credentials 读 key,调用一次最小推理,不回显 key 明文。"""
import re, json, urllib.request

CRED = r"C:\Users\User\.dsh\.credentials.yaml"
BASE = "http://ai.sunjun3773.top:62222/v1"
MODEL = "Qwen3.6-35B-A3B.gguf"


def load_key():
    txt = open(CRED, encoding="utf-8", errors="ignore").read()
    # 找 SUNJUN3773_API_KEY: xxxx 或 sunjun3773: ... apiKey: 之类
    m = re.search(r"SUNJUN3773_API_KEY['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]+)", txt)
    if m:
        return m.group(1)
    # 尝试 provider 块下 apiKey
    m = re.search(r"sunjun3773:.*?apiKey['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]+)", txt, re.S)
    if m:
        return m.group(1)
    return None


key = load_key()
print("key loaded:", ("yes len=%d" % len(key)) if key else "NO")

if key:
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "你是 KARDS 卡牌游戏专家。"},
            {"role": "user", "content": "KARDS 里步兵、坦克、炮兵三类单位,谁能直接攻击敌方 HQ?一句话回答。"}
        ],
        "temperature": 0.2,
        "max_tokens": 120,
    }
    req = urllib.request.Request(BASE + "/chat/completions",
        data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.load(r)
        print("RESP:", resp["choices"][0]["message"]["content"][:300])
    except Exception as e:
        print("call ERR:", e)
