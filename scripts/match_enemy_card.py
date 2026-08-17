"""用敌方单位卡面图案,在卡图库里 ORB 特征匹配认卡。"""
import sys, os, glob, json
sys.path.insert(0, ".")
import cv2, numpy as np
from kards_agent.matcher import _imread

art = _imread("logs/enemy_unit_art.png")
orb = cv2.SIFT_create() if hasattr(cv2, "SIFT_create") else cv2.ORB_create(nfeatures=500)
kp1, d1 = orb.detectAndCompute(art, None)
print("查询图特征点:", 0 if d1 is None else len(kp1))

cards_dir = "templates/cards_full"
idx = json.load(open(os.path.join(cards_dir, "index.json"), encoding="utf-8"))["cards"]

best = []
for c in idx:
    p = os.path.join(cards_dir, c["cardId"] + ".png")
    if not os.path.exists(p):
        continue
    tpl = _imread(p)
    if tpl is None:
        continue
    # 卡图中央画面部分
    h, w = tpl.shape[:2]
    tplart = tpl[int(h*0.15):int(h*0.62), int(w*0.10):int(w*0.92)]
    kp2, d2 = orb.detectAndCompute(tplart, None)
    if d1 is None or d2 is None or len(d2) == 0:
        continue
    bf = cv2.BFMatcher(cv2.NORM_L2 if orb.__class__.__name__ == "SIFT" else cv2.NORM_HAMMING)
    matches = bf.knnMatch(d1, d2, k=2)
    good = [m for m, n in matches if m.distance < 0.75 * n.distance]
    best.append((len(good), c["cardId"], c.get("title_zh")))

best.sort(reverse=True)
print("Top匹配:")
for g, cid, zh in best[:8]:
    print(f"  {g} 匹配点 | {zh} ({cid})")
