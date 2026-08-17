import sys
sys.path.insert(0, ".")
import cv2
from rapidocr_onnxruntime import RapidOCR
from kards_agent.matcher import _imread, _imwrite

ocr = RapidOCR()
img = _imread("logs/final_state.png")
# 敌方前线 4/4 单位卡 x588-692, y270-410
unit = img[270:410, 588:692]
unit4 = cv2.resize(unit, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
_imwrite("logs/enemy_unit_4x.png", unit4)
r, _ = ocr(unit4)
print("=== 敌方前线单位(放大4x) ===")
for box, txt, conf in (r or []):
    print(f"  {txt!r} conf={conf}")

# 敌方防御线 2/3 单位 x370-465 y100-240
u2 = img[100:240, 370:465]
u2 = cv2.resize(u2, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
_imwrite("logs/enemy_unit2_4x.png", u2)
r2, _ = ocr(u2)
print("=== 敌方防御线单位1(放大4x) ===")
for box, txt, conf in (r2 or []):
    print(f"  {txt!r} conf={conf}")
