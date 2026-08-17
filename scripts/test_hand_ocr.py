import sys
sys.path.insert(0, ".")
from rapidocr_onnxruntime import RapidOCR
from kards_agent.matcher import _imread

ocr = RapidOCR()
img = _imread("logs/real_check.png")
hand = img[595:720, 240:1100]
r, _ = ocr(hand)
print("手牌区识别:")
for box, txt, conf in (r or []):
    xs = [p[0] for p in box]
    cx = (min(xs) + max(xs)) // 2
    print(f"  {txt!r} @x{cx+240} conf={conf}")
