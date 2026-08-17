"""把 templates/cards_full 里的 avif 批量转成 png(OpenCV 可用)。"""
import sys, os
sys.path.insert(0, ".")
import PIL.Image
import concurrent.futures

SRC = "templates/cards_full"


def conv(fn):
    if not fn.endswith(".avif"):
        return None
    cid = fn[:-5]
    dst = os.path.join(SRC, cid + ".png")
    if os.path.exists(dst):
        return True
    try:
        im = PIL.Image.open(os.path.join(SRC, fn)).convert("RGB")
        im.save(dst, "PNG")
        return True
    except Exception:
        return False


files = [f for f in os.listdir(SRC) if f.endswith(".avif")]
print("待转换 avif:", len(files))
ok = 0
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    for i, r in enumerate(ex.map(conv, files)):
        if r:
            ok += 1
        if (i + 1) % 300 == 0:
            print(f"  {i+1}/{len(files)} 成功{ok}", flush=True)
print(f"转换完成: {ok}/{len(files)}")
