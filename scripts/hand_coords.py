"""问多模态:手牌每张卡的中心x坐标。验证多模态给像素坐标的准确度。"""
import re, json, base64, urllib.request, sys

CRED = r"C:\Users\User\.dsh\.credentials.yaml"
txt = open(CRED, encoding="utf-8", errors="ignore").read()
KEY = re.search(r"SUNJUN3773_API_KEY['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]+)", txt).group(1)

img = sys.argv[1] if len(sys.argv) > 1 else "logs/cur.png"
b64 = base64.b64encode(open(img, "rb").read()).decode()
p = ('这张图分辨率1280x720。屏幕底部是我方手牌扇形(若干张卡牌)。'
     '请只输出JSON: {"hand_centers":[每张手牌中心的x像素坐标,从左到右], "hand_y":手牌卡面中心y坐标, "count":张数}。只输出JSON。')
body = {"model": "Qwen3.6-35B-A3B.gguf", "messages": [{"role": "user", "content": [
    {"type": "text", "text": p},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}}]}],
    "max_tokens": 200, "temperature": 0.0}
req = urllib.request.Request("http://ai.sunjun3773.top:62222/v1/chat/completions",
    data=json.dumps(body).encode(), method="POST",
    headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY})
resp = json.load(urllib.request.urlopen(req, timeout=120))
print(resp["choices"][0]["message"]["content"])
