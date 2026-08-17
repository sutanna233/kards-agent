import sys
sys.path.insert(0, ".")
import cv2
from rapidocr_onnxruntime import RapidOCR
from kards_agent.matcher import _imread, _imwrite

ocr = RapidOCR()
# final_state 敌方场上单位(上半屏战场区 y100-420)
img = _imread("logs/final_state.png")
# 敌方战场区(不含HQ) y250-420, 全宽
zone = img[240:420, 300:980]
zone3 = cv2.resize(zone, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
_imwrite("logs/enemy_units_3x.png", zone3)
r, _ = ocr(zone3)
print("=== 敌方战场单位(放大3x) ===")
for box, txt, conf in (r or []):
    print(f"  {txt!r} conf={conf}")
