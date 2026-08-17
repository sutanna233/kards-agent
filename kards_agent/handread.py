"""
手牌精确识别:逐张点开手牌 → 详情弹窗大字 OCR → 卡库匹配 → 点空白关闭。
比扇形小字识别可靠得多(扇形遮挡时名字根本不全)。

实测要点:
- 点手牌弹出详情大卡;弹窗开着时点扇形无效,必须点空白(1100,300)关闭再点下一张。
- 扇形是弧形的:两侧的卡位置更低,点击 y 要随 |x-640| 下移(hand_tap_y)。
- 详情弹窗两种布局:指令卡卡名在中央(y≈505),单位卡卡名在顶部横条(y≈140)。

速度:每张卡 ≈ tap + 0.55s + 截图 + 一次 OCR ≈ 1.5-2s,6 张约 10s。

用法:
    from kards_agent import handread
    hand = handread.read_hand(deck=handread.load_deck("decklists/deying_kongding.txt"))
    # -> [{"index":0,"name":"溃敌","cost":1,"type":"order","effect":"...", "cx":330, "ok":True}, ...]
"""
from __future__ import annotations
import os, re, time
import numpy as np

try:
    import cv2
    from rapidocr_onnxruntime import RapidOCR
except Exception:
    cv2 = None
    RapidOCR = None

from . import adbc, card_effects
from .matcher import _imread

SERIAL = adbc.DEFAULT_SERIAL
LOG = "logs"

CLOSE_PT = (1100, 300)          # 点这里关闭详情弹窗
HAND_TAP_Y = 655                # 手牌扇形点击基准高度(扇形中央)
CARD_W = 150                    # 单卡宽度(1280x720 基准)
FAN_STRIP = (600, 640)          # 手牌扇形费用徽章所在的 y 范围
# 背景文本黑名单:这些不是卡名,是HQ/按钮/玩家名
_BG_TEXTS = {"CHERBOURG", "DANZIG", "STALINGRAD", "TRUK", "BERLIN", "LONDON",
             "WASHINGTON", "TOKYO", "ROME", "PARIS", "WARSAW",
             "结束回合", "Johnson", "LK021", "Cherbourg", "Danzig"}

TAP_WAIT = 0.35                 # 点开后的等待(弹窗动画)
CLOSE_WAIT = 0.2                # 关闭后的等待

_ocr = None


def _get_ocr():
    global _ocr
    if _ocr is None:
        _ocr = RapidOCR()
    return _ocr


def hand_tap_y(x: int) -> int:
    """扇形是弧形的:越靠边的卡位置越低,点击 y 要随 |x-640| 下移。
    实测:x=330(最左) y=680 可点开,y=655/700 不行;中央 y=655 可。"""
    return HAND_TAP_Y + int(28 * ((x - 640) / 330.0) ** 2)


def hand_x_positions(n: int) -> list[int]:
    """手牌扇形各卡中心 x(与 agent_full 同一实测公式)。"""
    if n <= 1:
        return [640]
    step = min(135, 620 // (n - 1))
    start = 640 - step * (n - 1) // 2
    return [int(start + step * i) for i in range(n)]


def find_hand_badges(img) -> list[int]:
    """从扇形条带检测每张卡的费用徽章(NK 金色小方块),返回各卡中心 x 列表。
    比宽度估计更可靠:直接数徽章个数。"""
    if img is None or cv2 is None:
        return []
    strip = img[FAN_STRIP[0]:FAN_STRIP[1], 200:1150]
    hsv = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
    # 金色/黄色徽章: hue 15-40, 高饱和
    mask = cv2.inRange(hsv, np.array([12, 120, 120]), np.array([40, 255, 255]))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if 8 <= w <= 50 and 8 <= h <= 50 and cv2.contourArea(c) > 40:
            boxes.append(x + w // 2 + 200)  # 回原图坐标
    boxes.sort()
    # 合并相近的(同一徽章多个碎片)
    merged = []
    for bx in boxes:
        if merged and bx - merged[-1] < 30:
            continue
        merged.append(bx)
    return merged


def estimate_hand_count(img) -> int:
    """兼容接口:优先徽章计数,退化为宽度估计。"""
    badges = find_hand_badges(img)
    if badges:
        return len(badges)
    # 退化:从扇形亮区宽度反推
    if cv2 is None:
        return 0
    hand = img[600:720, 200:1150]
    gray = cv2.cvtColor(hand, cv2.COLOR_BGR2GRAY)
    _, m = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY)
    colsum = (m > 0).sum(axis=0)
    cols = np.where(colsum > 25)[0]
    if len(cols) < 10:
        return 0
    width = int(cols[-1] - cols[0])
    best_n, best_d = 0, 1e9
    for n in range(1, 10):
        step = min(135, 620 // max(1, n - 1)) if n > 1 else 0
        expect = CARD_W + step * (n - 1)
        d = abs(expect - width)
        if d < best_d:
            best_d, best_n = d, n
    return best_n


def _decode(png: bytes):
    return cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)


def _ocr_name_candidates(img) -> list[str]:
    """OCR 卡片本体区域(排除左侧词条面板),按 y 坐标定位卡名。
    单位卡:名字在顶部横条 y≈120-170;指令卡:名字在中央 y≈480-540。
    返回候选文本(优先卡名,剔除词条/效果文本)。"""
    # 卡片本体: x 445-835(排除左侧词条 x<440)
    card_body = img[100:650, 445:835]  # y100-650, x445-835
    if card_body is None or card_body.size == 0:
        return []
    big = cv2.resize(card_body, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    r, _ = _get_ocr()(big)
    if not r:
        return []
    # 按 y 坐标分组:单位名 band (y 120-170→放大后 240-340),指令名 band (y 480-540→放大后 960-1080)
    unit_texts = []  # 顶部名字
    order_texts = []  # 中部名字
    other_texts = []  # 其他(效果/词条)
    for box, txt, conf in r:
        t = re.sub(r"[\s\.\,，。]", "", txt or "")
        if len(t) < 2:
            continue
        ys = [p[1] for p in box]
        cy = (min(ys) + max(ys)) / 2  # 原图坐标(卡身体区域内的相对坐标→实际全局y = cy+100)
        # 裁剪区域是 img[100:650, 445:835],OCR 在 2x 放大图上运行,实际全局y = cy/2+100
        abs_y = cy / 2 + 100
        if 115 <= abs_y <= 175:
            unit_texts.append(t)
        elif 475 <= abs_y <= 545:
            order_texts.append(t)
        else:
            other_texts.append(t)
    # 单位卡名优先(顶部),指令卡名次之
    return unit_texts + order_texts


def _match_card(name: str | None, deck: list[dict] | None):
    """OCR 卡名 → 卡数据。优先卡组内匹配(区分度极高),再全库模糊。"""
    if not name:
        return None
    norm = card_effects._norm(name)
    pool = deck if deck else []
    # 1) 卡组内:规范化相等 / 互相包含
    for c in pool:
        zh = card_effects._norm(c.get("title_zh", ""))
        en = card_effects._norm(c.get("title_en", ""))
        if norm and (norm == zh or norm == en or norm in zh or zh in norm or norm in en):
            return c
    # 2) 卡组内模糊:字符重合率
    if pool:
        best, bs = None, 0.0
        for c in pool:
            zh = card_effects._norm(c.get("title_zh", ""))
            sc = len(set(norm) & set(zh)) / max(len(set(norm) | set(zh)), 1)
            if sc > bs:
                bs, best = sc, c
        if bs > 0.5:
            return best
        # 给了卡组就绝不落到全库:卡组外的卡不可能在我手里,宁可是 None
        return None
    # 3) 无卡组约束时才全库兜底
    return card_effects.find(name)


def _pick(cands: list[str], deck: list[dict] | None):
    """从候选文本里挑第一个能匹配到卡的,返回 (匹配数据, 原文)。"""
    for t in cands:
        d = _match_card(t, deck)
        if d:
            return d, t
    return None, (cands[0] if cands else None)


def load_deck(decklist_path: str) -> list[dict]:
    """解析卡组文件 → 卡数据列表(去重,带 count)。"""
    cards = {}
    for line in open(decklist_path, encoding="utf-8"):
        m = re.match(r"^\s*(\d+)x\s+\((\d+)K\)\s+(.+?)\s*$", line)
        if not m:
            continue
        cnt, cost, name = int(m.group(1)), int(m.group(2)), m.group(3)
        c = card_effects.find(name) or {}
        c = dict(c)
        c.setdefault("title_zh", name)
        c["count"] = cnt
        c.setdefault("kredits", cost)
        cards[c["title_zh"]] = c
    return list(cards.values())


def _is_bg_text(txt: str) -> bool:
    """判断是否背景文本(HQ名/按钮/玩家名)而非卡名。"""
    t = txt.strip()
    for bg in _BG_TEXTS:
        if bg.lower() in t.lower() or t.lower() in bg.lower():
            return True
    return False


def _popup_opened(img) -> bool:
    """检测详情弹窗是否弹出。
    实测:中心卡区(200:400,500:780) 无弹窗≈72, 有弹窗≈124 → 阈值 95。
    (原来还查扇形变暗,但手牌多时扇形即使变暗也偏亮,会误判成没弹窗,已去掉)"""
    if img is None or cv2 is None:
        return False
    center = img[200:400, 500:780]
    return float(center.mean()) > 95


def _find_card_edges(img) -> list[int]:
    """从扇形条带的列投影找每张卡的左边缘(暗→亮跳变),返回各卡中心 x。"""
    if img is None or cv2 is None:
        return []
    strip = img[605:640, 250:1050]
    gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
    colmean = gray.mean(axis=0)  # 每列平均亮度
    # 平滑
    kernel = np.ones(5) / 5
    smooth = np.convolve(colmean, kernel, mode='same')
    # 找上升沿:亮度从低到高的跳变
    edges = []
    threshold = smooth.mean() * 0.7
    in_card = False
    for i in range(1, len(smooth)):
        if not in_card and smooth[i] > threshold and smooth[i-1] <= threshold:
            edges.append(i + 250)  # 左边缘(原图坐标)
            in_card = True
        elif in_card and smooth[i] <= threshold:
            in_card = False
    # 每张卡宽约80-150px,左边缘间距应>50;合并过近的
    merged = []
    for e in edges:
        if merged and e - merged[-1] < 50:
            continue
        merged.append(e)
    # 左边缘→中心: +40(徽章在左侧,中心在徽章右~40)
    return [e + 40 for e in merged]


def _banner_ocr(img, x: int, deck: list[dict] | None) -> dict | None:
    """对单张卡的名字条带做 RapidOCR + 卡组模糊匹配,作为 LLM 的交叉验证。
    条带斜且可能被右侧卡遮挡,读不出返回 None(不算冲突)。"""
    strip = img[605:652, max(0, x - 75):min(1280, x + 75)]
    if strip.size == 0:
        return None
    big = cv2.resize(strip, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    r, _ = _get_ocr()(big)
    if not r:
        return None
    txt = max((t for _, t, _ in r), key=len, default="")
    txt = re.sub(r"[\s\.\,，。]", "", txt or "")
    if len(txt) < 2:
        return None
    return _match_card(txt, deck), txt


def read_hand_llm(serial: str = SERIAL, deck: list[dict] | None = None,
                  verbose: bool = True, crosscheck: bool = True,
                  img=None) -> list[dict]:
    """多模态读整张扇形 + 卡组约束匹配 + 条带OCR交叉验证。
    要点:让 LLM 逐字读顶部文字(禁止按图案猜),再和 RapidOCR 条带结果对账;
    两者冲突的卡标 unsure=True,交给 read_hand_smart 点开仲裁。
    返回手牌列表,ok=True 表示卡组内匹配成功。"""
    from . import brain
    if img is None:
        png = adbc.screenshot_bytes(serial)
        if not png:
            return []
        img = _decode(png)
    fan = img[590:720, 250:1050]
    big = cv2.resize(fan, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    ok, buf = cv2.imencode(".jpg", big, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        return []
    import base64
    b64 = base64.b64encode(buf.tobytes()).decode()
    deck_names = ""
    if deck:
        names = [f"{c.get('title_zh','?')}({c.get('kredits','?')}K)" for c in deck]
        deck_names = "\n我方卡组列表(匹配参考):" + ", ".join(names)
    prompt = ("这是 KARDS 手牌扇形特写(已放大2倍,对应原图x250-1050,y590-720)。"
              "【任务】从左到右,对每张手牌:1)逐字读出卡名横条上能看到的文字(可能被右边的卡遮住一部分,"
              "看到几个字就读几个字);2)读费用徽章数字;3)估计该卡中心在原图的x坐标(0-1280,±40)。"
              "【严禁】按卡牌图案/颜色猜卡名!只能根据读到的文字,去卡组列表里找包含这些文字的卡。"
              + deck_names +
              "\n只输出JSON数组: [{\"text\":\"读到的原字\",\"name\":\"卡组列表里最匹配的卡名\",\"cost\":费,\"x\":中心x}, ...]")
    import json as _json
    body = {"model": brain.MODEL, "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}}]}],
        "max_tokens": 500, "temperature": 0.0}
    import urllib.request
    req = urllib.request.Request(brain.BASE + "/chat/completions",
        data=_json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + brain._key()})
    try:
        resp = _json.load(urllib.request.urlopen(req, timeout=60))
        out = resp["choices"][0]["message"]["content"]
        m = re.search(r"\[.*\]", out, re.S)
        if not m:
            return []
        items = _json.loads(m.group(0))
    except Exception as e:
        if verbose:
            print("  LLM读手牌出错:", e)
        return []
    result = []
    for i, item in enumerate(items):
        name = item.get("name", "")
        text = item.get("text", "")
        cost = item.get("cost")
        cx = item.get("x")
        # 优先按读到的原字匹配(更诚实),原字匹配不上再用它选的卡名
        data = _match_card(text, deck) if text else None
        if data is None:
            data = _match_card(name, deck)
        rec = {
            "index": i,
            "name": (data or {}).get("title_zh") or name,
            "cost": (data or {}).get("kredits") or cost,
            "type": (data or {}).get("type"),
            "effect": (data or {}).get("text_zh", ""),
            "attack": (data or {}).get("attack"),
            "defense": (data or {}).get("defense"),
            "cx": int(cx) if isinstance(cx, (int, float)) else None,
            "ok": data is not None,
            "ocr": text or name,
            "unsure": False,
        }
        result.append(rec)
        if verbose:
            print(f"  手牌[{i}]: LLM字={text!r} 选={name!r} -> {rec['name']} ({rec['cost']}K {rec['type']}) x={rec['cx']}")
    # 条带 OCR 交叉验证:与 LLM 结果冲突的标 unsure
    if crosscheck and deck:
        for rec in result:
            if rec["cx"] is None:
                rec["unsure"] = True
                continue
            try:
                cc = _banner_ocr(img, rec["cx"], deck)
            except Exception:
                cc = None
            if cc and cc[0]:
                ocr_card, ocr_txt = cc
                if ocr_card.get("title_zh") != (rec["name"] or ""):
                    if verbose:
                        print(f"    冲突: LLM={rec['name']} vs 条带OCR={ocr_card.get('title_zh')}({ocr_txt!r}) → 标记待仲裁")
                    rec["unsure"] = True
                else:
                    if verbose:
                        print(f"    条带OCR确认: {ocr_txt!r} ✓")
    return result


def read_hand(serial: str = SERIAL, n: int | None = None,
              deck: list[dict] | None = None, verbose: bool = True,
              debug: bool = False) -> list[dict]:
    """读手牌:先截图定位卡片位置,再逐张点开读详情。"""
    if cv2 is None or _get_ocr() is None:
        return []
    # 1. 截图定位
    png = adbc.screenshot_bytes(serial)
    if not png:
        return []
    img0 = _decode(png)
    xs = _find_card_edges(img0)
    if not xs:
        # 退化:用扇形公式
        n_est = estimate_hand_count(img0)
        if n_est <= 0:
            return []
        xs = hand_x_positions(n_est)
    if verbose:
        print(f"  定位到 {len(xs)} 张手牌: {xs}")
    # 2. 逐张点开读详情
    out = []
    for idx, x in enumerate(xs):
        y0 = hand_tap_y(x)
        adbc.tap(serial, x, y0)
        time.sleep(TAP_WAIT)
        png = adbc.screenshot_bytes(serial)
        if not png:
            continue
        img = _decode(png)
        if not _popup_opened(img):
            # 没弹出来,右移重试一次
            adbc.tap(serial, x + 30, y0)
            time.sleep(TAP_WAIT)
            png = adbc.screenshot_bytes(serial)
            if not png:
                continue
            img = _decode(png)
            if not _popup_opened(img):
                adbc.tap(serial, *CLOSE_PT)
                time.sleep(CLOSE_WAIT)
                continue
        cands = _ocr_name_candidates(img)
        cands = [c for c in cands if not _is_bg_text(c)]
        data, ocr_txt = _pick(cands, deck)
        rec = {
            "index": idx,
            "name": (data or {}).get("title_zh") or ocr_txt,
            "cost": (data or {}).get("kredits"),
            "type": (data or {}).get("type"),
            "effect": (data or {}).get("text_zh", ""),
            "attack": (data or {}).get("attack"),
            "defense": (data or {}).get("defense"),
            "cx": x,
            "ok": data is not None,
            "ocr": ocr_txt,
        }
        out.append(rec)
        if verbose:
            print(f"  手牌[{idx}] x={x}: OCR={ocr_txt!r} -> {rec['name']} ({rec['cost']}K {rec['type']})")
        adbc.tap(serial, *CLOSE_PT)
        time.sleep(CLOSE_WAIT)
    return out


def hand_to_text(hand: list[dict]) -> str:
    """手牌列表转紧凑文本(喂给决策)。"""
    parts = []
    for c in hand:
        s = f"[{c['index']}]{c.get('name') or '?'}({c.get('cost')}K"
        if c.get("type"):
            s += f" {c['type']}"
        if c.get("attack") is not None:
            s += f" {c['attack']}/{c['defense']}"
        s += ")"
        parts.append(s)
    return " ".join(parts)


def _fan_positions(img, n: int) -> list[int]:
    """手牌扇形亮区横跨范围均分成 n 张,返回各卡中心 x。
    用扇形最底部 20 行(y695-715):每张卡都顶到屏幕底边,暗色卡面也不会漏。
    实测:n=6 时均分位置与实际点开位置完全吻合。"""
    if n <= 0:
        return []
    strip = img[695:715, 250:1050]   # 扇形贴底部分,每张卡都覆盖到
    gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
    colmean = gray.mean(axis=0)
    thresh = max(18.0, float(colmean.mean()) * 0.35)
    cols = np.where(colmean > thresh)[0]
    if len(cols) < 20:
        return hand_x_positions(n)
    left, right = int(cols[0]) + 250, int(cols[-1]) + 250
    if right - left < 100:
        return hand_x_positions(n)
    w = (right - left) / n
    return [int(left + w * (i + 0.5)) for i in range(n)]


def read_hand_walk(serial: str = SERIAL, deck: list[dict] | None = None,
                   verbose: bool = True, time_budget: float = 20.0,
                   llm_fallback: list[dict] | None = None,
                   img0=None, debug: bool = False) -> list[dict]:
    """走查式读手牌(权威):从扇形左端起逐张点开,不需要预知张数,天然不漏牌。
    - 点开成功 → 右移 95(小于最小卡间距,靠去重防重复)
    - 点不开   → 右移 25 继续探;连续 6 次点不开 = 已出扇形,结束
    - 与上一张同名且位移<60 → 判定同一张,不重复记录
    - 截图走 raw screencap(快),每卡约 2s
    llm_fallback: LLM 猜测列表,点不开的卡用它兜底。"""
    t0 = time.time()
    if img0 is None:
        img0 = adbc.screenshot_cv(serial)
    if img0 is None:
        return []
    # 扇形左右边界
    strip = img0[695:715, 250:1050]
    gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
    colmean = gray.mean(axis=0)
    thresh = max(18.0, float(colmean.mean()) * 0.35)
    cols = np.where(colmean > thresh)[0]
    if len(cols) < 20:
        return list(llm_fallback or [])
    left, right = int(cols[0]) + 250, int(cols[-1]) + 250
    out = []
    x = left + 30
    fails = 0
    while x < right + 40 and time.time() - t0 < time_budget:
        y0 = hand_tap_y(x)
        adbc.tap(serial, x, y0)
        time.sleep(TAP_WAIT)
        img = adbc.screenshot_cv(serial)
        if img is None:
            x += 25; fails += 1
            if fails >= 6: break
            continue
        if not _popup_opened(img):
            x += 25; fails += 1
            if fails >= 6: break
            continue
        fails = 0
        cands = [c for c in _ocr_name_candidates(img) if not _is_bg_text(c)]
        data, ocr_txt = _pick(cands, deck)
        if debug:
            cv2.imwrite(os.path.join(LOG, f"_walk_{len(out)}_{int(x)}.png"), img)
            print(f"    [walk] x={x} 弹窗开 cands={cands} -> {data and data.get('title_zh')}")
        adbc.tap(serial, *CLOSE_PT)
        time.sleep(CLOSE_WAIT)
        # 去重:同名且位移小 = 同一张
        if out and data and out[-1].get("name") == data.get("title_zh") and x - out[-1]["cx"] < 60:
            x += 45
            continue
        if data:
            rec = {"index": len(out), "name": data.get("title_zh"), "cost": data.get("kredits"),
                   "type": data.get("type"), "effect": data.get("text_zh", ""),
                   "attack": data.get("attack"), "defense": data.get("defense"),
                   "cx": x, "ok": True, "ocr": ocr_txt, "unsure": False}
            out.append(rec)
            if verbose:
                print(f"  手牌[{rec['index']}] x={x}: {rec['name']} ({rec['cost']}K {rec['type']})")
        x += 95
    # LLM 兜底:走查张数 < LLM 张数时,缺的用猜测补(标 unsure)
    if llm_fallback and len(out) < len(llm_fallback):
        for g in llm_fallback[len(out):]:
            g = dict(g)
            g["index"] = len(out)
            g["unsure"] = True
            out.append(g)
    if verbose:
        print(f"  走查读手牌 {len(out)} 张,耗时 {time.time()-t0:.1f}s")
    return out


def read_hand_smart(serial: str = SERIAL,
                    deck: list[dict] | None = None, verbose: bool = True,
                    img0=None) -> list[dict]:
    """权威读手牌 = 走查式逐张点开。不再先调 LLM(慢且会漏牌),
    点不开的卡才叫 LLM 兜底(罕见)。"""
    hand = read_hand_walk(serial, deck, verbose=verbose, img0=img0)
    if hand and all(c.get("ok") for c in hand):
        return hand
    # 有没点开的:快速 LLM 读一遍扇形做兜底
    try:
        guesses = read_hand_llm(serial, deck, verbose=False, crosscheck=False, img=img0)
    except Exception:
        guesses = []
    if not guesses:
        return hand
    if not hand:
        return guesses
    # 用手牌数对齐:LLM 多出来的补在尾部(标 unsure)
    if len(guesses) > len(hand):
        for g in guesses[len(hand):]:
            g = dict(g); g["index"] = len(hand); g["unsure"] = True
            hand.append(g)
    return hand


if __name__ == "__main__":
    import sys
    deck = None
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        deck = load_deck(sys.argv[1])
        print(f"卡组加载: {len(deck)} 种卡")
    t0 = time.time()
    hand = read_hand_smart(deck=deck)
    print(f"\n总耗时 {time.time()-t0:.1f}s,完整手牌:", hand_to_text(hand))
    for c in hand:
        if not c["ok"]:
            print("  未识别:", c)
