"""
界面导航状态机:识别当前在哪个界面,导航到目标(训练模式对局)。
处理所有已知界面:主菜单/每日奖励/对战页/卡组页/对局/结算/奖励页/断线页。
用多模态识别当前界面(通用、鲁棒),比CV模板更能应对各种过渡页。
"""
from __future__ import annotations
import re, json, base64, urllib.request, os, time
import numpy as np

try:
    import cv2
except Exception:
    cv2 = None

from . import adbc

CRED = r"C:\Users\User\.dsh\.credentials.yaml"
BASE = "http://ai.sunjun3773.top:62222/v1"
MODEL = "Qwen3.6-35B-A3B.gguf"
_KEY = None
SERIAL = adbc.DEFAULT_SERIAL

# 各界面按钮坐标(1280x720)
BTN = {
    "main_start": (75, 200),      # 主菜单"开始"
    "training": (335, 260),       # 训练模式
    "deck_first": (620, 260),     # 第一个卡组
    "deck_start": (1077, 600),    # 卡组详情"开始"
    "continue": (640, 660),       # 结算/奖励"继续"
    "anywhere": (640, 400),       # 每日奖励"单击任意位置"
    "reconnect": (640, 437),      # 断线"重新连接"
    "end_turn": (1148, 516),      # 结束回合
}


def _key():
    global _KEY
    if _KEY is None:
        txt = open(CRED, encoding="utf-8", errors="ignore").read()
        _KEY = re.search(r"SUNJUN3773_API_KEY['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]+)", txt).group(1)
    return _KEY


def _imread(p):
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)


def identify_screen(img_path: str) -> str:
    """识别当前界面类型。先用CV规则区分易混淆的,再用多模态兜底。"""
    img = _imread(img_path)
    if img is None:
        return "unknown"
    # CV 规则1:卡组详情页右下有白色"开始"大按钮(亮白矩形)
    deck_btn = img[560:645, 990:1180]
    if deck_btn.size and deck_btn.mean() > 130:  # 开始按钮是亮白色
        return "deck_detail"
    # CV 规则2:用 RapidOCR 读左侧菜单文字区分 main_menu / play_menu
    menu = _menu_text(img)
    if menu:
        if "训练模式" in menu or "竞技场" in menu or "战役模式" in menu:
            return "play_menu"
        if "卡牌" in menu and "商店" in menu and "训练模式" not in menu:
            return "main_menu"
    # 多模态兜底
    return _identify_multimodal(img)


_ocr_inst = None
def _menu_text(img) -> str:
    """RapidOCR 读左侧菜单区文字。"""
    global _ocr_inst
    try:
        from rapidocr_onnxruntime import RapidOCR
        if _ocr_inst is None:
            _ocr_inst = RapidOCR()
        menu = img[100:640, 0:520]  # 左侧菜单区
        r, _ = _ocr_inst(menu)
        return "".join(t for _, t, _ in (r or []))
    except Exception:
        return ""


def _identify_multimodal(img) -> str:
    small = cv2.resize(img, (640, 360))  # 缩半省token
    ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])
    b64 = base64.b64encode(buf.tobytes()).decode()
    p = ("这是 KARDS 游戏界面截图。判断当前是哪个界面,只回答一个词: "
         "main_menu(主菜单,左侧有开始/卡牌/商店) / daily_reward(每日登录奖励) / "
         "play_menu(对战模式选择,有训练模式/竞技场等列表) / deck_detail(卡组详情,右下有开始按钮) / "
         "battle(对局中,能看到战场和手牌) / mulligan(换牌阶段,选择要替换的卡牌) / "
         "result(对局结算,中央有胜利/失败大字) / rank_reward(军衔奖励进度页) / "
         "disconnect(断开连接提示) / loading(加载画面) / unknown。只回答一个词。")
    body = {"model": MODEL, "messages": [{"role": "user", "content": [
        {"type": "text", "text": p},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}}]}],
        "max_tokens": 20, "temperature": 0.0}
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(body).encode(),
        method="POST", headers={"Content-Type": "application/json", "Authorization": "Bearer " + _key()})
    try:
        resp = json.load(urllib.request.urlopen(req, timeout=60))
        out = resp["choices"][0]["message"]["content"].strip().lower()
        for k in ("main_menu", "daily_reward", "play_menu", "deck_detail", "battle",
                  "mulligan", "result", "rank_reward", "disconnect", "loading"):
            if k in out:
                return k
        return "unknown"
    except Exception:
        return "unknown"


def current_screen() -> str:
    p = "logs/_nav.png"
    adbc.screenshot(SERIAL, p)
    return identify_screen(p)


def tap(name, wait=1.5):
    adbc.tap(SERIAL, BTN[name][0], BTN[name][1])
    time.sleep(wait)


def navigate_to_battle(max_steps=25) -> bool:
    """从任意界面导航到对局(battle/mulligan)。返回是否成功。"""
    for i in range(max_steps):
        scr = current_screen()
        print(f"  导航[{i}] 当前界面: {scr}")
        if scr in ("battle", "mulligan"):
            return True
        if scr == "main_menu":
            tap("main_start", 1.8)
        elif scr == "daily_reward":
            tap("anywhere", 2.5)
        elif scr == "play_menu":
            # 必须先点训练模式选中(高亮),再点第一个卡组进详情页
            tap("training", 1.2)
            tap("deck_first", 2.2)
        elif scr == "deck_detail":
            tap("deck_start", 2.0)
        elif scr in ("result", "rank_reward"):
            tap("continue", 2.5)
        elif scr == "disconnect":
            tap("reconnect", 4.0)
        elif scr == "loading":
            time.sleep(3)
        else:
            time.sleep(2)
    return False
