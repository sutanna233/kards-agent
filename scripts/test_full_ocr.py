import sys
sys.path.insert(0, ".")
from rapidocr_onnxruntime import RapidOCR
from kards_agent.matcher import _imread

ocr = RapidOCR()
img = _imread("logs/final_state.png")  # 敌方场上有多个单位
r, _ = ocr(img)
print("=== 整图识别(带坐标) ===")
for box, txt, conf in (r or []):
    ys = [p[1] for p in box]; xs = [p[0] for p in box]
    cx = (min(xs)+max(xs))//2; cy = (min(ys)+max(ys))//2
    zone = "敌方区" if cy < 360 else ("我方区" if cy > 360 else "中")
    print(f"  [{zone}] {txt!r}  @x{cx} y{cy} conf={conf}")
