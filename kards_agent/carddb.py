"""
卡牌数据库加载器:把 researcher 产出的 cards.json 桥接到 engine.state.Card。
处理字段映射与大小写/命名差异。
"""
from __future__ import annotations
import json, os
from typing import List, Dict
from .engine.state import Card, CardType, UnitKind, Nation

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cards", "cards.json")
_cache: Dict[str, Card] | None = None


def _map_type(t: str) -> CardType:
    t = (t or "").lower()
    if "counter" in t: return CardType.COUNTER
    if "order" in t: return CardType.ORDER
    if "unit" in t: return CardType.UNIT
    return CardType.UNKNOWN


def _map_kind(k: str) -> UnitKind:
    k = (k or "").lower()
    return {
        "infantry": UnitKind.INFANTRY, "tank": UnitKind.TANK,
        "artillery": UnitKind.ARTILLERY, "fighter": UnitKind.FIGHTER,
        "bomber": UnitKind.BOMBER,
    }.get(k, UnitKind.NONE if not k else UnitKind.UNKNOWN)


def _map_nation(n: str) -> Nation:
    n = (n or "").lower()
    for m in Nation:
        if m.value == n: return m
    return Nation.UNKNOWN


def _norm_abilities(abs_list) -> List[str]:
    """把 ability 关键词归一化到 state.KEYWORDS 的小写形式。"""
    m = {"blitz": "blitz", "fury": "fury", "guard": "guard",
         "smokescreen": "smoke", "smoke": "smoke"}
    out = []
    for a in abs_list or []:
        key = m.get(str(a).lower(), str(a).lower())
        if key not in out: out.append(key)
    return out


def load(path: str | None = None) -> Dict[str, Card]:
    """加载卡牌数据库,返回 id->Card 与 name->Card 索引。"""
    global _cache
    if _cache is not None:
        return _cache
    p = path or _DB_PATH
    db: Dict[str, Card] = {}
    if not os.path.exists(p):
        _cache = db
        return db
    with open(p, encoding="utf-8") as f:
        rows = json.load(f)
    for r in rows:
        c = Card(
            cid=str(r.get("id", "")),
            name=r.get("name", ""),
            nation=_map_nation(r.get("nation", "")),
            ctype=_map_type(r.get("type", "")),
            kind=_map_kind(r.get("unitType", "")),
            cost=int(r.get("cost", 0) or 0),
            attack=int(r.get("attack", 0) or 0),
            defense=int(r.get("defense", 0) or 0),
            abilities=_norm_abilities(r.get("abilities", [])),
            text=r.get("abilityText", "") or "",
        )
        db[c.cid] = c
        db["name:" + c.name.lower()] = c
    _cache = db
    return db


def find_by_name(name: str) -> Card | None:
    return load().get("name:" + (name or "").lower())
