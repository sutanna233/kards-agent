"""
自动模板匹配定位器。
不用手工写死坐标:用 ORB 特征匹配 + 多尺度滑窗模板匹配,自动在截图里找出元素。
用法:
  1) 从 golden 样本自动切模板(crop_and_register)
  2) 之后对任意截图 find_all(模板) 自动找出所有出现位置
"""
from __future__ import annotations
import os, json
from typing import List, Tuple, Dict, Optional
import numpy as np

try:
    import cv2
except Exception:
    cv2 = None

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
os.makedirs(TEMPLATE_DIR, exist_ok=True)


def _imread(path):
    """支持中文路径读图(OpenCV imread 不认非ASCII路径)。"""
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)


def _imwrite(path, img):
    """支持中文路径写图。"""
    ok, buf = cv2.imencode(".png", img)
    if ok:
        buf.tofile(path)
    return ok


class Matcher:
    def __init__(self):
        if cv2 is None:
            raise RuntimeError("需要 opencv-python")
        self.orb = cv2.ORB_create(nfeatures=800)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    # ---------- 模板注册 ----------
    def register(self, name: str, img, box: Tuple[int, int, int, int]):
        """把 img 中 box=(x,y,w,h) 区域存为模板 name。"""
        x, y, w, h = box
        tpl = img[y:y + h, x:x + w]
        path = os.path.join(TEMPLATE_DIR, name + ".png")
        _imwrite(path, tpl)
        return path

    def load_template(self, name: str):
        p = os.path.join(TEMPLATE_DIR, name + ".png")
        if os.path.exists(p):
            return _imread(p)
        # 支持 cards 子目录
        p2 = os.path.join(TEMPLATE_DIR, "cards", name + ".png")
        return _imread(p2) if os.path.exists(p2) else None

    def list_templates(self) -> List[str]:
        return [f[:-4] for f in os.listdir(TEMPLATE_DIR) if f.endswith(".png")]

    # ---------- 多尺度模板匹配 ----------
    def find_template(self, img, tpl, thresh: float = 0.8,
                      scales=(1.0, 0.9, 1.1, 0.8, 1.25)) -> List[Tuple[int, int, int, int, float]]:
        """在 img 中多尺度找 tpl,返回 [(x,y,w,h,score)] 已做NMS。"""
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hits = []
        th0, tw0 = tpl.shape[:2]
        for s in scales:
            rs = cv2.resize(tpl, (int(tw0 * s), int(th0 * s))) if s != 1.0 else tpl
            g = cv2.cvtColor(rs, cv2.COLOR_BGR2GRAY) if rs.ndim == 3 else rs
            if g.shape[0] > gray_img.shape[0] or g.shape[1] > gray_img.shape[1]:
                continue
            res = cv2.matchTemplate(gray_img, g, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.where(res >= thresh)
            for (x, y) in zip(xs, ys):
                hits.append((int(x), int(y), g.shape[1], g.shape[0], float(res[y, x])))
        return self._nms(hits)

    def _nms(self, hits, iou_thresh=0.3):
        if not hits:
            return []
        hits = sorted(hits, key=lambda h: -h[4])
        keep = []
        for h in hits:
            if all(self._iou(h, k) < iou_thresh for k in keep):
                keep.append(h)
        return keep

    @staticmethod
    def _iou(a, b):
        ax, ay, aw, ah = a[:4]; bx, by, bw, bh = b[:4]
        x1, y1 = max(ax, bx), max(ay, by)
        x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        union = aw * ah + bw * bh - inter
        return inter / union if union > 0 else 0

    # ---------- ORB 特征匹配(位置无关) ----------
    def find_by_features(self, img, tpl, min_matches: int = 10) -> Optional[Tuple[int, int, int, int]]:
        """用 ORB 特征把 tpl 定位到 img 中,返回外接框 (x,y,w,h) 或 None。"""
        k1, d1 = self.orb.detectAndCompute(tpl, None)
        k2, d2 = self.orb.detectAndCompute(img, None)
        if d1 is None or d2 is None or len(k1) < 4 or len(k2) < 4:
            return None
        matches = self.bf.match(d1, d2)
        matches = sorted(matches, key=lambda m: m.distance)[:60]
        if len(matches) < min_matches:
            return None
        src = np.float32([k1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        dst = np.float32([k2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
        H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
        if H is None:
            return None
        h, w = tpl.shape[:2]
        corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
        proj = cv2.perspectiveTransform(corners, H).reshape(-1, 2)
        x0, y0 = proj.min(axis=0); x1, y1 = proj.max(axis=0)
        return (int(x0), int(y0), int(x1 - x0), int(y1 - y0))
