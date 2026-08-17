"""可靠的数字读取:特征定位(找元素锚点)+ 相对偏移裁数字框 + 放大 + 多模态读。
不依赖固定坐标(元素位置变动也不怕,先找锚点),裁干净后多模态读准。
"""
from __future__ import annotations
import re, json, base64, urllib.request, os
import numpy as np

try:
    import cv2
except Exception:
    cv2 = None

from .matcher import Matcher, _imread

CRED = r"C:\Users\User\.dsh\.credentials.yaml"
BASE = "http://ai.sunjun3773.top:62222/v1"
MODEL = "Qwen3.6-35B-A3B.gguf"
_KEY = None


def _key():
    global _KEY
    if _KEY is None:
        _KEY = re.search(r"SUNJUN3773_API_KEY['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]+)",
                         open(CRED, encoding="utf-8", errors="ignore").read()).group(1)
    return _KEY


def _read_num(png_bytes, prompt) -> int | None:
    b64 = base64.b64encode(png_bytes).decode()
    body = {"model": MODEL, "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}}]}],
        "max_tokens": 15, "temperature": 0.0}
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(body).encode(),
        method="POST", headers={"Content-Type": "application/json", "Authorization": "Bearer " + _key()})
    try:
        out = json.load(urllib.request.urlopen(req, timeout=60))["choices"][0]["message"]["content"]
        m = re.search(r"\d+", out)
        return int(m.group(0)) if m else None
    except Exception:
        return None


def _crop_num(img, box, scale=6):
    x, y, w, h = box
    roi = img[y:y+h, x:x+w]
    if roi is None or roi.size == 0:
        return None
    roi = cv2.resize(roi, (w*scale, h*scale), interpolation=cv2.INTER_CUBIC)
    ok, buf = cv2.imencode(".png", roi)
    return buf.tobytes() if ok else None


# 锚点模板与相对偏移(在 1280x720 基准上标定)
# HQ 徽章位置 -> 血量数字框的相对偏移
_matcher = None


def _m():
    global _matcher
    if _matcher is None:
        _matcher = Matcher()
    return _matcher


def find_hq_hp(img, my: bool) -> int | None:
    """用 HQ 徽章特征定位 HQ,再从相对偏移读血量。"""
    tpl = _m().load_template("hq_my_badge" if my else "hq_enemy_badge")
    if tpl is None:
        return None
    hits = _m().find_template(img, tpl, thresh=0.55)
    if not hits:
        return None
    bx, by, bw, bh, _ = hits[0]
    # 血量数字在徽章下方中央(相对偏移,标定值)
    # 徽章 box (x,y,w,h);血量框约在徽章中心下方 +55..+100
    cx = bx + bw // 2
    hp_box = (cx - 30, by + bh + 18, 60, 40)
    png = _crop_num(img, hp_box)
    if png is None:
        return None
    return _read_num(png, "这是卡牌游戏总部(HQ)血量数字特写。只回答这个数字(整数)。")


def read_fee_cv(img) -> int | None:
    """纯 CV 读我方当前费用(左下橙色大数字),不走路多模态,~0.1s。
    与 loop._read_fee 同一套 HSV 阈值(已实战验证),但直接吃解码图,不再截图。"""
    if cv2 is None or img is None:
        return None
    try:
        roi = img[495:560, 30:120]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([8, 150, 150]), np.array([30, 255, 255]))
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = [c for c in cnts if cv2.contourArea(c) > 30]
        if not cnts:
            return None
        cnts.sort(key=lambda c: cv2.boundingRect(c)[0])
        from .digits import DigitReader
        dr = DigitReader()
        digits = []
        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            cell = mask[y:y + h, x:x + w]
            d = dr._match(cell)
            if d:
                digits.append(d)
        return int("".join(digits)) if digits else None
    except Exception:
        return None


def read_state_numbers(img_path: str) -> dict:
    """读关键数字:双方HQ血量(徽章定位) + 我方费用(固定区放大读)。"""
    img = _imread(img_path)
    if img is None:
        return {}
    out = {}
    out["my_hq"] = find_hq_hp(img, True)
    out["enemy_hq"] = find_hq_hp(img, False)
    # 我方费用:左下固定区,大数字当前费
    fee_png = _crop_num(img, (28, 495, 90, 65), scale=5)
    if fee_png:
        out["my_kredits"] = _read_num(fee_png, "这是指挥点显示。左边大数字是当前可用指挥点。只回答这个大数字。")
    return out
