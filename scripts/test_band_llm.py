"""测试:只给多模态看文字条带(去掉卡面图案),读徽章+卡名。"""
import sys, base64, json, re, urllib.request
sys.path.insert(0, ".")
import cv2
from kards_agent import adbc, brain
from kards_agent.matcher import _imread

img = _imread("logs/_now6.png")
band = img[600:655, 250:1050]
big = cv2.resize(band, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
ok, buf = cv2.imencode(".jpg", big, [cv2.IMWRITE_JPEG_QUALITY, 90])
b64 = base64.b64encode(buf.tobytes()).decode()

prompt = ("这是 KARDS 手牌的费用徽章+卡名横条特写(3倍放大,只有文字条带,没有卡面图案)。"
          "从左到右逐张读:每张卡有一个金色徽章(数字+K)和紧跟的卡名文字。"
          "卡名可能被右边的卡遮住一部分,看到几个字就报几个字,不要猜。"
          '只输出JSON数组: [{"badge":"4K","text":"看到的卡名原字"}, ...]')
body = {"model": brain.MODEL, "messages": [{"role": "user", "content": [
    {"type": "text", "text": prompt},
    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}}]}],
    "max_tokens": 400, "temperature": 0.0}
req = urllib.request.Request(brain.BASE + "/chat/completions", data=json.dumps(body).encode(),
    method="POST", headers={"Content-Type": "application/json",
                            "Authorization": "Bearer " + brain._key()})
resp = json.load(urllib.request.urlopen(req, timeout=60))
print(resp["choices"][0]["message"]["content"])
