import sys, re, json, base64, urllib.request
sys.path.insert(0, ".")

CRED = r"C:\Users\User\.dsh\.credentials.yaml"
KEY = re.search(r"SUNJUN3773_API_KEY['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]+)",
                open(CRED, encoding="utf-8", errors="ignore").read()).group(1)

img = "logs/final_state.png"
b64 = base64.b64encode(open(img, "rb").read()).decode()

PROMPT = """这是 KARDS 对局画面。请仔细观察,把场上一切识别成 JSON(只输出JSON):
{
 "my_kredits":我方当前指挥点, "my_kredits_max":我方指挥点上限, "my_hq":我方HQ血量,
 "enemy_kredits":敌方指挥点, "enemy_hq":敌方HQ血量, "enemy_hand_count":敌方手牌数,
 "my_hand":[{"name":"卡名","cost":费,"attack":攻,"defense":防}],
 "my_units":[{"name":"卡名","attack":攻,"defense":防,"line":"front|defense","can_act":true}],
 "enemy_units":[{"name":"卡名或描述","attack":攻,"defense":防,"line":"front|defense"}]
}
注意:我方在下半屏,敌方在上半屏;前线是靠近中间的行,防御线是靠近本方HQ的行。
单位卡的攻击在左下、防御在右下(绿色数字)。务必读出每个单位的攻防。只输出JSON。"""

body = {"model": "Qwen3.6-35B-A3B.gguf", "messages": [{"role": "user", "content": [
    {"type": "text", "text": PROMPT},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}}]}],
    "max_tokens": 1200, "temperature": 0.0}
req = urllib.request.Request("http://ai.sunjun3773.top:62222/v1/chat/completions",
    data=json.dumps(body).encode(), method="POST",
    headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY})
resp = json.load(urllib.request.urlopen(req, timeout=120))
out = resp["choices"][0]["message"]["content"]
print(out)
