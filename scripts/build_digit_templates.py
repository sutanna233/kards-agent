"""自动建 0-9 数字模板库:从对局截图的费用/HQ区域切数字块,多模态确认真值后存模板。
遍历 logs 里的对局截图,提取数字块,聚类成 10 类(0-9)。"""
import sys, os, glob, json, base64, re, urllib.request
sys.path.insert(0, ".")
import cv2, numpy as np
from kards_agent.matcher import _imread, _imwrite

OUT = "templates/digits"
os.makedirs(OUT, exist_ok=True)

CRED = r"C:\Users\User\.dsh\.credentials.yaml"
txt = open(CRED, encoding="utf-8", errors="ignore").read()
KEY = re.search(r"SUNJUN3773_API_KEY['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]+)", txt).group(1)


def ask_digit(png_bytes):
    """让多模态读一张小数字图,返回数字字符。"""
    b64 = base64.b64encode(png_bytes).decode()
    body = {"model": "Qwen3.6-35B-A3B.gguf", "messages": [{"role": "user", "content": [
        {"type": "text", "text": "这是 KARDS 游戏里的一个数字(0-9)。只回答这个数字本身。"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}}]}],
        "max_tokens": 10, "temperature": 0.0}
    req = urllib.request.Request("http://ai.sunjun3773.top:62222/v1/chat/completions",
        data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY})
    try:
        resp = json.load(urllib.request.urlopen(req, timeout=60))
        out = resp["choices"][0]["message"]["content"].strip()
        m = re.search(r"\d", out)
        return m.group(0) if m else None
    except Exception as e:
        return None


def extract_digit_cells(img, region, color):
    """从区域提取单个数字的二值图块。"""
    x, y, w, h = region
    roi = img[y:y + h, x:x + w]
    if roi is None or roi.size == 0:
        return []
    if color == "orange":
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        th = cv2.inRange(hsv, np.array([8, 150, 150]), np.array([30, 255, 255]))
    else:
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, th = cv2.threshold(gray, 130, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = [c for c in cnts if cv2.contourArea(c) > 15]
    cnts.sort(key=lambda c: cv2.boundingRect(c)[0])
    cells = []
    for c in cnts:
        bx, by, bw, bh = cv2.boundingRect(c)
        if bh >= 8 and bw >= 4:
            cells.append(th[by:by + bh, bx:bx + bw])
    return cells


# 费用区(橙):我方左下 (495,30,90,65); 敌方左上 (157,30,90,65)
# HQ血量区(白): 我方中央下 (615,525,55,50); 敌方中央上 (615,155,55,50)
FEE_REGIONS = [(30, 495, 90, 65), (30, 157, 90, 65)]
HQ_REGIONS = [(615, 525, 55, 50), (615, 155, 55, 50)]

collected = {}
shots = sorted(glob.glob("logs/*.png"), key=os.path.getmtime)[-25:]
print("扫描截图数:", len(shots))
for sp in shots:
    img = _imread(sp)
    if img is None:
        continue
    for reg in FEE_REGIONS:
        for cell in extract_digit_cells(img, reg, "orange"):
            ok, buf = cv2.imencode(".png", cell)
            d = ask_digit(buf.tobytes())
            if d and d not in collected:
                _imwrite(os.path.join(OUT, f"{d}_orange.png"), cell)
                collected[d] = True
                print("  收集到数字", d)
    if len(collected) >= 10:
        break
print("已收集数字:", sorted(collected.keys()))
