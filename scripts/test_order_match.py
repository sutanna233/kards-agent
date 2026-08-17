import sys
sys.path.insert(0, ".")
import cv2
from kards_agent.matcher import Matcher, _imread, _imwrite

m = Matcher()
img = _imread("logs/real_check.png")
hand = img[600:720, 240:1100]  # 手牌扇形区
_imwrite("logs/hand_zone.png", hand)

# 溃敌卡面中央图案
tpl = m.load_template("cards_full/rout")
if tpl is None:
    tpl = _imread("templates/cards_full/rout.png")
h, w = tpl.shape[:2]
art = tpl[int(h*0.15):int(h*0.62), int(w*0.10):int(w*0.92)]  # 中央图案
_imwrite("logs/rout_art.png", art)

hits = m.find_template(hand, art, thresh=0.3, scales=(0.10, 0.12, 0.14, 0.16, 0.18, 0.20, 0.09))
print("溃敌在手牌区匹配数:", len(hits))
for x, y, ww, hh, s in hits[:5]:
    print(f"  原图 x={x+240+ww//2} y={y+600+hh//2} score={s:.2f}")
