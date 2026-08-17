"""快速 game_over 胜负检测:模板匹配中央"胜利/失败"大字。"""
from __future__ import annotations
import os
import numpy as np

try:
    import cv2
except Exception:
    cv2 = None

TPL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")


def _imread(p):
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)


def _gray(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def detect_gameover(img) -> str | None:
    """检测是否结算画面,返回 'win'/'lose'/None。
    前置:中央区域必须有大面积亮白色文字(失败/胜利大字是亮白),否则不是结算。
    """
    if cv2 is None or img is None:
        return None
    region = img[420:580, 480:820]
    gray = _gray(region)
    # 结算大字是亮白色:亮像素占比要够高,排除黑暗加载画面
    bright = (gray > 180).mean()
    if bright < 0.03:
        return None
    center = gray
    for name, res in (("gameover_win", "win"), ("gameover_lose", "lose")):
        tp = os.path.join(TPL, name + ".png")
        if not os.path.exists(tp):
            continue
        tpl = _gray(_imread(tp))
        if tpl is None:
            continue
        for s in (1.0, 0.9, 1.1, 0.8, 1.2):
            t = cv2.resize(tpl, (int(tpl.shape[1] * s), int(tpl.shape[0] * s)))
            if t.shape[0] > center.shape[0] or t.shape[1] > center.shape[1]:
                continue
            r = cv2.matchTemplate(center, t, cv2.TM_CCOEFF_NORMED)
            if r.max() > 0.6:
                return res
    return None


def click_continue(serial):
    """结算后连点"继续"两次(结算页→奖励页→卡组详情页)。"""
    from . import adbc
    import time
    for _ in range(2):
        adbc.tap(serial, 640, 660)
        time.sleep(2.5)
