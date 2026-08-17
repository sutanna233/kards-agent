"""一次性建全 KARDS 0-9 数字模板库。
从对局截图分离所有数字块(绿色攻防/白色血量费用),多模态标注真值,存模板。
之后运行时用模板匹配读数(快/准/免费,不用再调多模态)。
"""
import sys, os, glob, json, base64, re, urllib.request
sys.path.insert(0, ".")
import cv2, numpy as np
from kards_agent.matcher import _imread, _imwrite

OUT = "templates/digits_v2"
os.makedirs(OUT, exist_ok=True)
CRED = r"C:\Users\User\.dsh\.credentials.yaml"
KEY = re.search(r"SUNJUN3773_API_KEY['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]+)",
                open(CRED, encoding="utf-8", errors="ignore").read()).group(1)


def ask_digit(png_bytes):
    b64 = base64.b64encode(png_bytes).decode()
    body = {"model": "Qwen3.6-35B-A3B.gguf", "messages": [{"role": "user", "content": [
        {"type": "text", "text": "这是一个游戏数字特写(0-9单个数字,白色笔画黑底)。只回答这个数字,一个字符。"},
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


def digit_cells(img):
    """从整图提取所有数字块(多颜色:绿/白/橙)。"""
    cells = []
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    masks = [
        cv2.inRange(hsv, np.array([40, 100, 100]), np.array([85, 255, 255])),  # 绿(攻防)
        cv2.inRange(hsv, np.array([8, 150, 150]), np.array([30, 255, 255])),   # 橙(费用)
        cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)[1],                    # 白(血量)
    ]
    for mask in masks:
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            if 8 <= h <= 60 and 3 <= w <= 45 and cv2.contourArea(c) > 15:
                cells.append(mask[y:y+h, x:x+w])
    return cells


collected = {}
shots = sorted(glob.glob("logs/*.png"), key=os.path.getmtime)
print("扫描截图:", len(shots))
import time
t0 = time.time()
for sp in shots:
    if len(collected) >= 10 or time.time() - t0 > 240:
        break
    img = _imread(sp)
    if img is None:
        continue
    for cell in digit_cells(img):
        if len(collected) >= 10 or time.time() - t0 > 240:
            break
        ok, buf = cv2.imencode(".png", cell)
        d = ask_digit(buf.tobytes())
        if d and d not in collected:
            _imwrite(os.path.join(OUT, f"{d}.png"), cell)
            collected[d] = True
            print(f"  新数字 {d}", flush=True)
print("已建:", sorted(collected.keys()), "用时%.0fs" % (time.time()-t0))
