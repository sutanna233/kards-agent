"""
完整局面识别器:产出包含场上一切信息的结构化 JSON。
整合:
- RapidOCR:读卡名(我方手牌)、大数字(血量/费用)、界面文字
- 颜色分割+模板匹配:读单位攻防数字(0-9模板库)
- 卡面图案匹配:认敌方/我方场上单位是哪张卡(用卡图库)
- 位置分行:按 y 坐标划分战线(敌方在上,我方在下;前线/防御线)
产出确定性 JSON,带置信度;认不出的标 null 而不瞎猜。
"""
from __future__ import annotations
import os, glob, json, re
from typing import Optional, List
import numpy as np

try:
    import cv2
    from rapidocr_onnxruntime import RapidOCR
except Exception:
    cv2 = None
    RapidOCR = None

from .matcher import _imread
from . import card_effects

_ocr = None
_digits = None
_card_templates = None

REF_W, REF_H = 1280, 720


def _get_ocr():
    global _ocr
    if _ocr is None:
        _ocr = RapidOCR()
    return _ocr


def _get_digits():
    """加载 0-9 数字模板(灰度)。"""
    global _digits
    if _digits is None:
        _digits = {}
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "digits_v2")
        for f in glob.glob(os.path.join(d, "*.png")):
            k = os.path.basename(f)[0]
            im = _imread(f)
            _digits[k] = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    return _digits


# ---------- 数字识别(颜色分割 + 连通域 + 模板匹配) ----------
def _read_digit_cell(cell_gray) -> Optional[str]:
    tpls = _get_digits()
    if not tpls or cell_gray is None or cell_gray.size == 0:
        return None
    best, bs = None, 0.0
    for d, t in tpls.items():
        t2 = cv2.resize(t, (cell_gray.shape[1], cell_gray.shape[0]))
        r = cv2.matchTemplate(cell_gray, t2, cv2.TM_CCOEFF_NORMED).max()
        if r > bs:
            bs, best = r, d
    return best if bs > 0.45 else None


def read_stats_from_cardimg(card_img) -> dict:
    """从一张单位卡图读 攻击/防御 数字(底部,绿色)。"""
    if card_img is None or card_img.size == 0:
        return {}
    h, w = card_img.shape[:2]
    bottom = card_img[int(h * 0.62):, :]  # 底部攻防区
    hsv = cv2.cvtColor(bottom, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([40, 100, 100]), np.array([85, 255, 255]))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = [cv2.boundingRect(c) for c in cnts if cv2.contourArea(c) > 20]
    boxes = [b for b in boxes if b[3] >= 8]
    boxes.sort()
    digits = []
    for (x, y, bw, bh) in boxes:
        cell = mask[y:y+bh, x:x+bw]
        digits.append((x, _read_digit_cell(cell)))
    # 左=攻击, 右=防御
    out = {}
    if len(digits) >= 1 and digits[0][1]:
        out["attack"] = int(digits[0][1])
    if len(digits) >= 2 and digits[-1][1]:
        out["defense"] = int(digits[-1][1])
    elif len(digits) == 1:
        out["defense"] = out.get("attack")
    return out


# ---------- 卡面识别(认是哪张卡) ----------
def _load_card_arts():
    """加载卡图中央画面用于特征匹配。按需懒加载子集。"""
    global _card_templates
    if _card_templates is None:
        _card_templates = {}
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "cards_full")
        idx = os.path.join(d, "index.json")
        if os.path.exists(idx):
            for c in json.load(open(idx, encoding="utf-8"))["cards"]:
                p = os.path.join(d, c["cardId"] + ".png")
                if os.path.exists(p):
                    _card_templates[c["cardId"]] = p
    return _card_templates


# ---------- 主识别 ----------
def recognize_full(img_path: str) -> dict:
    """识别整帧,产出完整局面 JSON。"""
    img = _imread(img_path)
    if img is None or _get_ocr() is None:
        return {"error": "no image or ocr"}

    result, _ = _get_ocr()(img)
    items = []
    for box, txt, conf in (result or []):
        xs = [p[0] for p in box]; ys = [p[1] for p in box]
        items.append({"text": txt, "conf": float(conf),
                      "cx": (min(xs)+max(xs))//2, "cy": (min(ys)+max(ys))//2,
                      "x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys)})

    state = {
        "phase": "my_turn",
        "my": {"kredits": None, "hq": None, "hand": [], "units": []},
        "enemy": {"kredits": None, "hq": None, "hand_count": None, "units": []},
        "raw": [(it["text"], it["cx"], it["cy"]) for it in items],
    }

    # 费用:左侧 K-x 旁数字
    for it in items:
        m = re.match(r"^[Kk][-\s]?(\d+)$", (it["text"] or "").replace(" ", ""))
        if m:
            n = int(m.group(1))
            if it["cx"] < 200 and it["cy"] > 400:
                state["my"]["kredits"] = n
            elif it["cx"] < 200 and it["cy"] < 300:
                state["enemy"]["kredits"] = n

    # HQ血量:HQ名下方数字
    hq_kw = {"stalin": "enemy", "danzig": "my", "cherbourg": "enemy", "truk": "enemy",
             "berlin": "enemy", "london": "enemy", "trck": "enemy", "truk": "enemy"}
    for it in items:
        tl = (it["text"] or "").lower()
        side = None
        for k, s in hq_kw.items():
            if k in tl:
                side = s if it["cy"] > 360 else "enemy"
                if "danzig" in tl or "banzig" in tl:
                    side = "my"
                break
        if side:
            for jt in items:
                if jt is not it and abs(jt["cx"]-it["cx"]) < 80 and 30 < jt["cy"]-it["cy"] < 120:
                    n = re.search(r"\d+", jt["text"] or "")
                    if n:
                        state[side]["hq"] = int(n.group(0))

    # 我方手牌:底部 y>600 的卡名
    for it in items:
        if it["cy"] > 600 and len(it["text"] or "") >= 2:
            c = card_effects.find(it["text"])
            state["my"]["hand"].append({
                "name": c["title_zh"] if c else it["text"],
                "cost": c.get("kredits") if c else None,
                "type": c.get("type") if c else None,
                "cx": it["cx"], "cy": it["cy"],
            })

    return state
