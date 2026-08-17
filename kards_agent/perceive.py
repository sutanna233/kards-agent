"""
局面识别:多模态一次读出完整局面 JSON(含敌方单位攻防/兵线)。
KARDS 是回合制,每次识别独立调用(不累积上下文),几秒可接受。
这是最可靠、信息最全的识别方式。
"""
from __future__ import annotations
import re, json, base64, urllib.request, os

CRED = os.environ.get("DSH_CRED", r"C:\Users\User\.dsh\.credentials.yaml")
BASE = os.environ.get("KARDS_LLM_BASE", "http://ai.sunjun3773.top:62222/v1")
MODEL = os.environ.get("KARDS_LLM_MODEL", "Qwen3.6-35B-A3B.gguf")
_KEY = None


def _key():
    global _KEY
    if _KEY is None:
        _KEY = re.search(r"SUNJUN3773_API_KEY['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]+)",
                         open(CRED, encoding="utf-8", errors="ignore").read()).group(1)
    return _KEY


PROMPT = """这是 KARDS 对局画面(我方在下半屏,敌方在上半屏)。仔细观察,把场上一切识别成 JSON(只输出JSON,不要别的):
{
 "phase":"my_turn|enemy_turn|mulligan|game_over",
 "my_kredits":我方当前指挥点, "my_kredits_max":我方指挥点上限, "my_hq":我方HQ血量,
 "enemy_kredits":敌方指挥点, "enemy_hq":敌方HQ血量, "enemy_hand_count":敌方手牌数,
 "my_hand":[{"name":"卡名","cost":费,"attack":攻,"defense":防}],
 "my_units":[{"name":"卡名/类型","attack":攻,"defense":防,"line":"front|defense","can_act":true}],
 "enemy_units":[{"name":"卡名/类型","attack":攻,"defense":防,"line":"front|defense"}]
}
规则提示:
- 前线(front)是靠近画面中间的行;防御线(defense)是靠近本方HQ的行。
- 单位卡的攻击在左下、防御在右下(绿色数字);费用在左上(带K)。
- HQ血量是HQ卡牌中央的大数字;指挥点在屏幕左侧(大数字=当前,旁边小数字=上限)。
- 换牌阶段(中央"选择要替换的卡牌")phase 填 mulligan。
- 对局结束(中央"胜利"/"失败"大字)phase 填 game_over。
- 看不清的字段填 null。务必只输出JSON。"""


def recognize(img_path: str) -> dict:
    """整图局面识别。发缩略 JPEG(768宽,q70):比原图 PNG 快 3-5 倍,
    阶段/单位/HQ 等粗信息足够;精确费用由 keynum CV 校正,手牌由 handread 权威。"""
    import numpy as np
    try:
        import cv2
    except Exception:
        cv2 = None
    if cv2 is not None:
        img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        small = cv2.resize(img, (768, 432))
        ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])
        raw = buf.tobytes() if ok else open(img_path, "rb").read()
        mime = "image/jpeg" if ok else "image/png"
    else:
        raw = open(img_path, "rb").read()
        mime = "image/png"
    b64 = base64.b64encode(raw).decode()
    body = {"model": MODEL, "messages": [{"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64," + b64}}]}],
        "max_tokens": 1500, "temperature": 0.0}
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(body).encode(),
        method="POST", headers={"Content-Type": "application/json", "Authorization": "Bearer " + _key()})
    with urllib.request.urlopen(req, timeout=90) as r:
        resp = json.load(r)
    out = resp["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        return {"phase": "unknown", "raw": out}
    try:
        return json.loads(m.group(0))
    except Exception:
        # 截断修复
        js = m.group(0)
        if js.count("{") > js.count("}"):
            js += "}" * (js.count("{") - js.count("}"))
        last = js.rfind("}")
        try:
            return json.loads(js[:last+1])
        except Exception:
            return {"phase": "unknown", "raw": out}
