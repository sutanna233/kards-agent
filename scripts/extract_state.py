"""多模态状态提取:让 Qwen35B 看对局截图,输出结构化 JSON 状态。"""
import re, json, base64, urllib.request, urllib.error, sys

CRED = r"C:\Users\User\.dsh\.credentials.yaml"
BASE = "http://ai.sunjun3773.top:62222/v1"
MODEL = "Qwen3.6-35B-A3B.gguf"
txt = open(CRED, encoding="utf-8", errors="ignore").read()
KEY = re.search(r"SUNJUN3773_API_KEY['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]+)", txt).group(1)

PROMPT = """这是 KARDS 对局截图。请仔细观察画面,输出一个 JSON(只输出JSON):
{
 "phase":"mulligan|my_turn|enemy_turn|game_over",
 "my_kredits":我方当前费用数字,
 "my_kredits_max":我方费用上限,
 "my_hq":我方HQ血量,
 "enemy_hq":敌方HQ血量,
 "enemy_kredits":敌方当前费用,
 "my_hand":[{"name":"卡名","cost":费,"attack":攻,"defense":防}],
 "enemy_hand_count":敌方手牌数,
 "my_units":[{"name":"卡名","attack":攻,"defense":防,"line":"front|support|defense"}],
 "enemy_units":[{"name":"卡名","attack":攻,"defense":防,"line":"front|support|defense"}]
}
看不清的字段填 null。只输出JSON。"""


def extract_state(img_path: str) -> dict:
    b64 = base64.b64encode(open(img_path, "rb").read()).decode()
    body = {"model": MODEL, "messages": [{"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}},
    ]}], "max_tokens": 800, "temperature": 0.0}
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(body).encode(),
        method="POST", headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY})
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.load(r)
    out = resp["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", out, re.S)
    return json.loads(m.group(0)) if m else {"raw": out}


if __name__ == "__main__":
    st = extract_state(sys.argv[1])
    print(json.dumps(st, ensure_ascii=False, indent=2))
