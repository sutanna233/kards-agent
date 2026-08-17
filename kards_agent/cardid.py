"""敌方/我方场上单位认卡:卡面图案特征匹配卡图库。
用 ORB/SIFT 特征匹配认"这是哪张卡",再从数据库拿效果/费用/类型。
为加速,按国家/费用缩小候选范围(可选)。
"""
from __future__ import annotations
import os, json
import numpy as np

try:
    import cv2
except Exception:
    cv2 = None

from .matcher import _imread

CARDS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "cards_full")
_index = None
_orb = None


def _load():
    global _index, _orb
    if _index is None:
        _index = json.load(open(os.path.join(CARDS_DIR, "index.json"), encoding="utf-8"))["cards"]
        _orb = cv2.SIFT_create() if hasattr(cv2, "SIFT_create") else cv2.ORB_create(nfeatures=500)
    return _index, _orb


def _art_of(card_id):
    p = os.path.join(CARDS_DIR, card_id + ".png")
    if not os.path.exists(p):
        return None
    tpl = _imread(p)
    if tpl is None:
        return None
    h, w = tpl.shape[:2]
    return tpl[int(h*0.15):int(h*0.62), int(w*0.10):int(w*0.92)]


def identify_card(unit_art_img, cand_factions=None, max_scan=1613):
    """用单位卡面图案认卡,返回 (cardId, title_zh, 匹配点数) 或 None。"""
    if cv2 is None or unit_art_img is None:
        return None
    idx, orb = _load()
    kp1, d1 = orb.detectAndCompute(unit_art_img, None)
    if d1 is None or len(kp1) < 8:
        return None
    norm = cv2.NORM_L2 if orb.__class__.__name__ == "SIFT" else cv2.NORM_HAMMING
    bf = cv2.BFMatcher(norm)
    best = []
    for c in idx:
        if cand_factions and c.get("faction") not in cand_factions:
            continue
        tpl = _art_of(c["cardId"])
        if tpl is None:
            continue
        kp2, d2 = orb.detectAndCompute(tpl, None)
        if d2 is None or len(d2) == 0:
            continue
        try:
            matches = bf.knnMatch(d1, d2, k=2)
        except Exception:
            continue
        good = [m for m, n in matches if m.distance < 0.75 * n.distance]
        best.append((len(good), c["cardId"], c.get("title_zh"), c))
    if not best:
        return None
    best.sort(reverse=True, key=lambda x: x[0])
    g, cid, zh, c = best[0]
    # 需要足够匹配点且领先第二名
    if g >= 8 and (len(best) == 1 or g > best[1][0] * 1.5):
        return {"cardId": cid, "title_zh": zh, "score": g, "data": c}
    return None
