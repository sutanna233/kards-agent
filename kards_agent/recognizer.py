"""
视觉识别层:把对局截图识别成 GameState。
分辨率基准:横屏 1280x720(KARDS 安卓横屏)。
策略:固定区域标定(坐标来自 golden 样本)+ 数字OCR + 卡图模板匹配。
所有坐标用相对比例存,便于分辨率变化时按 ui_profile 缩放。
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np

try:
    import cv2
except Exception:
    cv2 = None

from .engine.state import GameState, PlayerState, Phase, Card, Unit, CardType, UnitKind, Line


# ---- 以 1280x720 为基准的关键区域(相对坐标 0..1),量自 golden 样本 ----
# (x, y, w, h) 相对比例
REF_W, REF_H = 1280, 720

REGIONS = {
    # 换牌/对局手牌区(mulligan):5 张卡大致横向排列
    "mulligan_cards": [  # 每张卡的中心区域
        (0.115, 0.50), (0.322, 0.50), (0.499, 0.50), (0.676, 0.50), (0.853, 0.50),
    ],
    "enemy_hq_hp": (0.470, 0.24, 0.075, 0.09),     # 对手 HQ 血量数字(STALINGRAD 下方 20)
    "my_kredits": (0.020, 0.74, 0.075, 0.10),       # 我方 Kredits 大数字(左下 0)
    "confirm_btn": (0.368, 0.86, 0.26, 0.10),       # 确认按钮
    "end_turn_btn": (0.88, 0.50, 0.10, 0.12),       # 结束回合按钮(对局中)
}


def to_px(region, W=REF_W, H=REF_H) -> Tuple[int, int, int, int]:
    x, y, w, h = region
    return int(x * W), int(y * H), int(w * W), int(h * H)


def load_image(path_or_bytes):
    """从路径或字节读图为 BGR numpy。"""
    if cv2 is None:
        raise RuntimeError("需要 opencv-python")
    if isinstance(path_or_bytes, (bytes, bytearray)):
        arr = np.frombuffer(path_or_bytes, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    # 支持中文路径
    return cv2.imdecode(np.fromfile(path_or_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)


def crop(img, region) -> np.ndarray:
    x, y, w, h = to_px(region, img.shape[1], img.shape[0])
    return img[y:y + h, x:x + w]


# ---- 数字识别:固定字形的数字,用模板匹配 ----
_digit_templates = {}


def _build_digit_templates():
    """从参考区域切 0-9 模板。初次为空,运行时若未标定则回退 OCR。"""
    return _digit_templates


def read_number(img, region) -> Optional[int]:
    """识别某区域里的整数。优先模板匹配;无模板则尝试连通域分割计数,最后回退 OCR。"""
    roi = crop(img, region)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
    # 阈值化出亮色数字
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # 找数字连通域
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = [c for c in cnts if cv2.contourArea(c) > 8]
    cnts.sort(key=lambda c: cv2.boundingRect(c)[0])
    if not cnts:
        return None
    # 模板匹配逐位
    digits = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        cell = th[y:y + h, x:x + w]
        d = _match_digit(cell)
        if d is None:
            d = _ocr_digit(cell)
        digits.append(d)
    if any(d is None for d in digits):
        return None
    try:
        return int("".join(str(d) for d in digits))
    except Exception:
        return None


def _match_digit(cell) -> Optional[int]:
    if not _digit_templates:
        return None
    best, bestscore = None, 0.0
    for d, tpl in _digit_templates.items():
        t = cv2.resize(tpl, (cell.shape[1], cell.shape[0]))
        r = cv2.matchTemplate(cell, t, cv2.TM_CCOEFF_NORMED)
        if r.max() > bestscore:
            bestscore, best = r.max(), d
    return best if bestscore > 0.6 else None


def _ocr_digit(cell) -> Optional[int]:
    try:
        import pytesseract
        txt = pytesseract.image_to_string(cell, config="--psm 10 -c tessedit_char_whitelist=0123456789")
        txt = "".join(ch for ch in txt if ch.isdigit())
        return int(txt) if txt else None
    except Exception:
        return None


# ---- 主识别入口 ----
@dataclass
class RecogResult:
    state: GameState
    confidence: float = 0.0
    notes: List[str] = field(default_factory=list)


def recognize(img) -> RecogResult:
    """把一张对局截图识别成 GameState(主干)。
    目前先识别:阶段粗判、双方 HQ 血量、我方 Kredits。
    卡牌/单位识别在 mulligan 与 board 两种布局里分别做,逐步加。
    """
    state = GameState()
    notes = []

    if img is None:
        return RecogResult(state, 0.0, ["empty image"])

    # 我方 Kredits
    k = read_number(img, REGIONS["my_kredits"])
    if k is not None:
        state.me.kredits = k
        notes.append(f"kredits={k}")

    # 敌方 HQ 血量
    hp = read_number(img, REGIONS["enemy_hq_hp"])
    if hp is not None:
        state.enemy.hq_defense = hp
        notes.append(f"enemy_hq={hp}")

    state.raw_notes = notes
    return RecogResult(state, 0.5, notes)
