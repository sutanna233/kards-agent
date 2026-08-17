import sys
sys.path.insert(0, ".")
import cv2, numpy as np
from kards_agent.matcher import _imread, _imwrite

img = _imread("logs/final_state.png")
unit = img[270:410, 588:692]
bottom = unit[95:140, :]
hsv = cv2.cvtColor(bottom, cv2.COLOR_BGR2HSV)
# 亮绿色数字
mask = cv2.inRange(hsv, np.array([40, 100, 100]), np.array([85, 255, 255]))
_imwrite("logs/green_digits.png", mask)
# 连通域分离单个数字
cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
boxes = [cv2.boundingRect(c) for c in cnts if cv2.contourArea(c) > 20]
boxes.sort()
print("绿色数字块:", boxes)
for i, (x, y, w, h) in enumerate(boxes):
    _imwrite(f"logs/gdigit_{i}.png", mask[y:y+h, x:x+w])
