import sys
sys.path.insert(0, ".")
from rapidocr_onnxruntime import RapidOCR
from kards_agent.matcher import _imread

ocr = RapidOCR()
img = _imread("logs/final_state.png")
r, _ = ocr(img)
print("=== 上半屏(敌方区 y<420)识别的文字 ===")
for box, txt, conf in (r or []):
    ys = [p[1] for p in box]
    xs = [p[0] for p in box]
    cy = (min(ys) + max(ys)) // 2
    cx = (min(xs) + max(xs)) // 2
    if cy < 420:
        print(f"  {txt!r}  @x{cx} y{cy} conf={conf}")
print("=== 全部文字数 ===", len(r or []))
