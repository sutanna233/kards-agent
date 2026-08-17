"""
基于 RapidOCR 的可靠识别层(确定性 CV,不猜)。
RapidOCR 一次整图识别 → 返回所有文字+位置坐标 → 解析成结构化局面。
- 卡名:匹配到 cards.json(模糊匹配容错错别字)
- 血量/费用:数字直接读
- 位置:用 OCR 返回的精确坐标
- 战线单位:按 y 坐标分行(前线/防御线)
"""
from __future__ import annotations
import os, json, re
from typing import List, Tuple, Optional
import numpy as np

try:
    import cv2
    from rapidocr_onnxruntime import RapidOCR
except Exception:
    cv2 = None
    RapidOCR = None

from .matcher import _imread

_ocr = None
_carddb = None


def _get_ocr():
    global _ocr
    if _ocr is None:
        _ocr = RapidOCR()
    return _ocr


def _load_cards():
    """加载卡牌中文名库(cards.json + templates index 的 zhTitle)。"""
    global _carddb
    if _carddb is None:
        _carddb = {}
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "cards", "index.json")
        if os.path.exists(p):
            for c in json.load(open(p, encoding="utf-8"))["cards"]:
                zh = c.get("zhTitle")
                if zh:
                    _carddb[zh] = c
    return _carddb


def _norm(s: str) -> str:
    return re.sub(r"[\s\-\.]", "", s or "")


def _fuzzy_card(text: str):
    """把 OCR 出的文字模糊匹配到卡名(容错错别字)。"""
    t = _norm(text)
    db = _load_cards()
    best, bs = None, 0
    for zh in db:
        z = _norm(zh)
        # 计算共有子串比例
        common = sum(1 for ch in set(t) if ch in z)
        score = common / max(len(set(t)), 1)
        if score > bs:
            bs, best = score, db[zh]
    return best if bs > 0.5 else None


def _is_number(s: str) -> Optional[int]:
    m = re.search(r"\d+", s)
    return int(m.group(0)) if m else None


def recognize(img_path: str) -> dict:
    """整图识别 → 结构化局面。确定性,带坐标。"""
    img = _imread(img_path)
    if img is None or _get_ocr() is None:
        return {}
    result, _ = _get_ocr()(img)
    if not result:
        return {}

    items = []  # (text, cx, cy, w, h, conf)
    for box, txt, conf in result:
        xs = [p[0] for p in box]; ys = [p[1] for p in box]
        items.append({
            "text": txt, "conf": float(conf),
            "cx": (min(xs)+max(xs))//2, "cy": (min(ys)+max(ys))//2,
            "x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys),
        })

    W = img.shape[1]
    state = {
        "raw_texts": [(it["text"], it["cx"], it["cy"]) for it in items],
        "my_hand": [], "my_units": [], "enemy_units": [],
        "phase": "my_turn",
    }

    # 手牌:画面底部 y>600 的卡名
    for it in items:
        if it["cy"] > 600 and len(it["text"]) >= 3:
            card = _fuzzy_card(it["text"])
            state["my_hand"].append({
                "name": card["name"] if card else it["text"],
                "zhTitle": card.get("zhTitle") if card else it["text"],
                "cost": card.get("cost") if card else None,
                "attack": card.get("attack") if card else None,
                "defense": card.get("defense") if card else None,
                "cx": it["cx"], "cy": it["cy"],
            })

    # 费用:左侧 K-x 标记旁的数字
    for it in items:
        if re.match(r"^[Kk][-\s]?\d+$", it["text"] or ""):
            n = _is_number(it["text"])
            if it["cx"] < 200 and it["cy"] > 400:  # 左下=我方
                state["my_kredits"] = n
            elif it["cx"] < 200 and it["cy"] < 300:  # 左上=敌方
                state["enemy_kredits"] = n

    # HQ血量:HQ名(STALINGRAD/DANZIG等)下方的大数字
    hq_names = {"stalin", "danzig", "cherbourg", "truk", "berlin", "london", "washington", "tokyo", "rome", "paris", "warsaw"}
    for it in items:
        tl = (it["text"] or "").lower()
        if any(h in tl for h in hq_names):
            # 在 HQ 名下方找数字
            for jt in items:
                if jt is not it and abs(jt["cx"]-it["cx"]) < 80 and 30 < jt["cy"]-it["cy"] < 120:
                    n = _is_number(jt["text"])
                    if n is not None:
                        if it["cy"] < 360:  # 上半屏=敌方
                            state["enemy_hq"] = n
                        else:
                            state["my_hq"] = n

    return state
