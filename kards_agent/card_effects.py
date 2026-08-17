"""
完整卡牌效果数据库:基于 kards_api_cards.json(1613张,带中文名/效果/费用/类型/卡图URL)。
支持按中文名/英文名查找,模糊匹配容错。
"""
from __future__ import annotations
import os, json, re
from typing import Optional

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "cards", "kards_api_cards.json")
_db = None
_by_zh = None
_by_en = None


def _load():
    global _db, _by_zh, _by_en
    if _db is None:
        _db = json.load(open(_DB_PATH, encoding="utf-8-sig"))
        _by_zh = {}
        _by_en = {}
        for cid, c in _db.items():
            zh = c.get("title_zh")
            en = c.get("title_en")
            if zh:
                _by_zh[_norm(zh)] = c
            if en:
                _by_en[_norm(en)] = c
    return _db


def _norm(s: str) -> str:
    return re.sub(r"[\s\-\.\,\(\)（）]", "", (s or "").lower())


def find(name: str) -> Optional[dict]:
    """按中文名或英文名找卡,模糊容错。"""
    _load()
    n = _norm(name)
    if n in _by_zh:
        return _by_zh[n]
    if n in _by_en:
        return _by_en[n]
    # 模糊:去空格包含匹配
    best, bs = None, 0
    for k, c in list(_by_zh.items()) + list(_by_en.items()):
        if n and (n in k or k in n):
            sc = len(set(n) & set(k)) / max(len(set(n)), 1)
            if sc > bs:
                bs, best = sc, c
    return best if bs > 0.55 else None


def effect_of(name: str) -> str:
    """返回卡的中文效果文本。"""
    c = find(name)
    return c.get("text_zh", "") if c else ""


def all_cards():
    _load()
    return _db
