"""
数字识别:KARDS 数字(费用=橙色,血量=白色)模板匹配读数。
模板库在 templates/digits/。颜色阈值定位数字块 + 连通域分离 + 逐位模板匹配。
"""
from __future__ import annotations
import os
from typing import Optional, List, Tuple
import numpy as np

try:
    import cv2
except Exception:
    cv2 = None

DIGIT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "digits")


def _imread(path):
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)


class DigitReader:
    def __init__(self):
        if cv2 is None:
            raise RuntimeError("需要 opencv-python")
        self.templates = {}  # digit_str -> list of binary cell
        if os.path.isdir(DIGIT_DIR):
            for f in os.listdir(DIGIT_DIR):
                if f.endswith(".png"):
                    name = f[:-4]
                    d = name.replace("w", "")  # 0w->0
                    img = _imread(os.path.join(DIGIT_DIR, f))
                    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
                    _, th = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    self.templates.setdefault(d, []).append(th)

    def _cells(self, roi, color: str) -> List[np.ndarray]:
        """从 roi 分离出每个数字的二值笔画图。"""
        if color == "orange":
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, np.array([8, 150, 150]), np.array([30, 255, 255]))
            th = mask
        else:  # white
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            _, th = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)
        cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = [c for c in cnts if cv2.contourArea(c) > 8]
        cnts.sort(key=lambda c: cv2.boundingRect(c)[0])
        cells = []
        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            if h < 6 or w < 3:  # 过滤噪点
                continue
            cells.append(th[y:y + h, x:x + w])
        return cells

    def _match(self, cell) -> Optional[str]:
        best, bs = None, 0.0
        for d, tpls in self.templates.items():
            for tpl in tpls:
                t = cv2.resize(tpl, (cell.shape[1], cell.shape[0]))
                r = cv2.matchTemplate(cell, t, cv2.TM_CCOEFF_NORMED)
                if float(r.max()) > bs:
                    bs, best = float(r.max()), d
        return best if bs > 0.55 else None

    def read(self, roi, color: str = "white") -> Optional[int]:
        """读 roi 里的整数。"""
        cells = self._cells(roi, color)
        if not cells:
            return None
        digits = [self._match(c) for c in cells]
        if not digits or any(d is None for d in digits):
            return None
        try:
            return int("".join(digits))
        except Exception:
            return None
