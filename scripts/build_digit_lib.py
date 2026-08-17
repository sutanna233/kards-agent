"""多模态辅助建 0-9 数字模板库。
思路:KARDS 数字字体特殊,通用OCR(Tesseract)不准。用多模态大模型当'标注员'确认真值,
切出每个数字的干净笔画存为模板;之后运行时用模板匹配(快/准/免费)。
"""
import sys, os, glob, json, base64, re, urllib.request
sys.path.insert(0, ".")
import cv2, numpy as np
from kards_agent.matcher import _imread, _imwrite

OUT = "templates/digits"
os.makedirs(OUT, exist_ok=True)
CRED = r"C:\Users\User\.dsh\.credentials.yaml"
KEY = re.search(r"SUNJUN3773_API_KEY['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]+)",
                open(CRED, encoding="utf-8", errors="ignore").read()).group(1)


def ask_digit(png_bytes):
    b64 = base64.b64encode(png_bytes).decode()
    body = {"model": "Qwen3.6-35B-A3B.gguf", "messages": [{"role": "user", "content": [
        {"type": "text", "text": "这是一张游戏里的单个数字特写(0-9)。只回答这个数字本身,一个字符。"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}}]}],
        "max_tokens": 5, "temperature": 0.0}
    req = urllib.request.Request("http://ai.sunjun3773.top:62222/v1/chat/completions",
        data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY})
    try:
        out = json.load(urllib.request.urlopen(req, timeout=60))["choices"][0]["message"]["content"].strip()
        m = re.search(r"\d", out)
        return m.group(0) if m else None
    except Exception:
        return None


def cells_from(img, region, color):
    x, y, w, h = region
    roi = img[y:y+h, x:x+w]
    if roi is None or roi.size == 0:
        return []
    if color == "orange":
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        th = cv2.inRange(hsv, np.array([8, 150, 150]), np.array([30, 255, 255]))
    else:
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, th = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = [cv2.boundingRect(c) for c in cnts if cv2.contourArea(c) > 15]
    boxes.sort()
    cells = []
    for bx, by, bw, bh in boxes:
        if 6 <= bh and 3 <= bw and bh < h and bw < w:  # 排除整框
            cells.append(th[by:by+bh, bx:bx+bw])
    return cells


# 关键数字区域(1280x720):费用(橙)、HQ血量(白)、手牌费用角标(白)
REGIONS = [
    ((28, 495, 90, 65), "orange"),   # 我方费用
    ((28, 157, 90, 65), "orange"),   # 敌方费用
    ((548, 182, 60, 40), "white"),   # 敌方HQ血量
    ((600, 500, 60, 45), "white"),   # 我方HQ血量
]

collected = {}
shots = sorted(glob.glob("logs/*.png"), key=os.path.getmtime)
print("扫描截图:", len(shots))
for sp in shots:
    img = _imread(sp)
    if img is None:
        continue
    for reg, color in REGIONS:
        for cell in cells_from(img, reg, color):
            ok, buf = cv2.imencode(".png", cell)
            d = ask_digit(buf.tobytes())
            if d and d not in collected:
                _imwrite(os.path.join(OUT, f"{d}.png"), cell)
                collected[d] = cell.shape
                print(f"  新数字 {d} -> {cell.shape}")
    if len(collected) >= 10:
        break
print("已建模板:", sorted(collected.keys()))
