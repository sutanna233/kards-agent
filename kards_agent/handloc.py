"""
手牌定位:用卡图模板匹配,在对局画面里精确找到每张手牌的位置。
解决扇形重叠/张数变化导致的坐标漂移。
"""
from __future__ import annotations
import os, json
import numpy as np

try:
    import cv2
except Exception:
    cv2 = None

from .matcher import Matcher, _imread

TPL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "cards")
INDEX = os.path.join(TPL_DIR, "index.json")

_index = None
_matcher = None


def _load_index():
    global _index
    if _index is None:
        _index = {c["name"]: c["id"] for c in json.load(open(INDEX, encoding="utf-8"))["cards"] if c.get("downloaded")}
        # 也建 zhTitle 索引
        for c in json.load(open(INDEX, encoding="utf-8"))["cards"]:
            zh = c.get("zhTitle")
            if zh and c.get("downloaded"):
                _index[zh] = c["id"]
    return _index


def _get_matcher():
    global _matcher
    if _matcher is None:
        _matcher = Matcher()
    return _matcher


def card_art_template(card_id: str):
    """加载卡图的中央画面部分(去边框/文字,更稳)。"""
    p = os.path.join(TPL_DIR, card_id + ".png")
    if not os.path.exists(p):
        return None
    img = _imread(p)
    h, w = img.shape[:2]
    return img[int(h * 0.28):int(h * 0.60), int(w * 0.14):int(w * 0.86)]


def find_hand_card(full_img, card_name: str, hand_region=(250, 590, 1000, 130)):
    """在手牌区找 card_name 对应的卡,返回原图坐标 (cx, cy) 或 None。"""
    idx = _load_index()
    cid = idx.get(card_name)
    if not cid:
        return None
    art = card_art_template(cid)
    if art is None:
        return None
    x0, y0, w0, h0 = hand_region
    hand = full_img[y0:y0 + h0, x0:x0 + w0]
    m = _get_matcher()
    # 手牌卡很小,多尺度匹配小尺寸
    hits = m.find_template(hand, art, thresh=0.45, scales=(0.13, 0.15, 0.17, 0.19, 0.21, 0.11))
    if not hits:
        return None
    # 取最靠左/最高的命中(手牌)
    x, y, w, h, s = max(hits, key=lambda h: h[4])
    return (x0 + x + w // 2, y0 + y + h // 2)


def locate_hand_cards(full_img, hand_names: list, hand_region=(250, 590, 1000, 130)):
    """对手牌每张卡名,模板匹配找位置。返回 [(cx,cy),...](None表示没找到)。"""
    return [find_hand_card(full_img, n, hand_region) for n in hand_names]
