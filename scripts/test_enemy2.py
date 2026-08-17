import sys
sys.path.insert(0, ".")
import cv2
from rapidocr_onnxruntime import RapidOCR
from kards_agent.matcher import _imread, _imwrite

ocr = RapidOCR()
img = _imread("logs/turn3b.png")  # 敌方防御线有 1/3 步兵
# 敌方单位区域放大2倍
zone = img[100:280, 350:950]
zone2 = cv2.resize(zone, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
_imwrite("logs/enemy_zone_2x.png", zone2)
r, _ = ocr(zone2)
print("=== 敌方区域(放大2x)识别 ===")
for box, txt, conf in (r or []):
    print(f"  {txt!r}  conf={conf}")
