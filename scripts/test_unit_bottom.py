import sys
sys.path.insert(0, ".")
import cv2, numpy as np
from rapidocr_onnxruntime import RapidOCR
from kards_agent.matcher import _imread, _imwrite

ocr = RapidOCR()
img = _imread("logs/final_state.png")
unit = img[270:410, 588:692]  # 敌方前线 4/4 单位
# 底部攻防数字区(卡高约140, 数字在底部 y95-135)
bottom = unit[95:140, :]
bottom = cv2.resize(bottom, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)
_imwrite("logs/unit_bottom.png", bottom)
# 提取亮绿色数字
hsv = cv2.cvtColor(bottom, cv2.COLOR_BGR2HSV)
mask = cv2.inRange(hsv, np.array([35, 80, 80]), np.array([90, 255, 255]))
_imwrite("logs/unit_bottom_green.png", mask)
r, _ = ocr(bottom)
print("底部直接OCR:", [t for _, t, c in (r or [])])
rm, _ = ocr(cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR))
print("绿色通道OCR:", [t for _, t, c in (rm or [])])
