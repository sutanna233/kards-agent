"""
整局自动对局 runner:
导航进训练模式 → 循环(识别→Qwen35B决策→adb执行)→ 检测胜负 → 可选自动开新局 → 统计胜率。
明早验收核心。
"""
from __future__ import annotations
import os, time, json, datetime
from . import adbc
from . import brain
from . import perceive
from . import gameover
from . import nav
from .loop import GameLoop, state_to_text

SERIAL = adbc.DEFAULT_SERIAL
LOG = "logs"
RESULTS = os.path.join(LOG, "results.jsonl")


# 界面导航坐标(1280x720)
PT_MAIN_START = (75, 200)        # 主菜单"开始"
PT_MODE_TRAINING = (335, 260)    # "训练模式"
PT_DECK_FIRST = (620, 260)       # 对战模式页/卡组选择 第一个卡组(德国卡组)
PT_DECK_START = (1077, 600)      # 卡组详情页右下"开始"
PT_CONTINUE = (640, 660)         # 结算/奖励页"继续"
PT_END_TURN = (1148, 516)


def tap(p, wait=1.2):
    adbc.tap(SERIAL, p[0], p[1]); time.sleep(wait)


def log_result(rec: dict):
    os.makedirs(LOG, exist_ok=True)
    rec["ts"] = datetime.datetime.now().isoformat()
    with open(RESULTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def start_match():
    """用导航状态机从任意界面进入训练模式对局(处理所有过渡页)。"""
    ok = nav.navigate_to_battle()
    if not ok:
        print("导航进对局失败")
    return ok


def back_to_menu(max_clicks=5):
    """结算/奖励页连点继续,直到回到对战模式选择页(画面出现训练模式菜单)。"""
    for _ in range(max_clicks):
        tap(PT_CONTINUE, 2.5)
        if _at_play_menu():
            return True
    return False


def _at_play_menu() -> bool:
    """判断是否在对战模式选择页(检测'训练模式'菜单文字区域有内容)。"""
    import numpy as np
    from .matcher import _imread
    p = os.path.join(LOG, "_menu.png")
    adbc.screenshot(SERIAL, p)
    img = _imread(p)
    if img is None:
        return False
    # 对战模式选择页:左侧菜单区(200-500 x, 130-620 y)较亮且有菜单项
    region = img[130:640, 230:490]
    return region.mean() > 40


def wait_loaded(timeout=40):
    """等对局加载完成:画面中央变亮(出现对局元素)或检测到换牌/手牌。"""
    import numpy as np
    from .matcher import _imread
    t0 = time.time()
    while time.time() - t0 < timeout:
        p = os.path.join(LOG, "_loading.png")
        adbc.screenshot(SERIAL, p)
        img = _imread(p)
        if img is not None:
            # 对局画面中央(战场/手牌)较亮;加载画面整体很暗
            bright = (img[300:600, 300:1000].mean())
            if bright > 40:  # 对局画面有一定亮度
                return True
        time.sleep(1.5)
    return False


def play_one_match(max_steps=60, verbose=True) -> dict:
    """打一整局,返回结果 dict(win/lose/unknown, turns)。"""
    g = GameLoop()
    g.turn = 0
    last_phase = None
    stall = 0
    for step in range(max_steps):
        img = g.capture(f"m{step}")
        # 先用 CV 快速检测结算画面(快),命中则直接用其结果
        from .matcher import _imread as _mr
        go = gameover.detect_gameover(_mr(img))
        if go:
            print(f"[步{step}] 对局结束 CV判定: {go}")
            res = {"result": go, "turns": step}
            log_result(res)
            back_to_menu()
            return res
        try:
            st = g.recognize_state(img)
        except Exception as e:
            print("识别出错:", e); time.sleep(2); continue
        phase = st.get("phase")
        if verbose:
            print(f"[步{step}] phase={phase} 费{st.get('my_kredits')}/{st.get('my_kredits_max')} HQ{st.get('my_hq')}v{st.get('enemy_hq')}")
        # 多模态也检测到 game_over 时
        if phase == "game_over":
            res = {"result": st.get("result") or detect_result(img, st), "turns": step}
            log_result(res)
            back_to_menu()
            return res
        if phase == "my_turn":
            text = state_to_text(st)
            # 防卡死:费用不足且无单位 → 强制结束
            fee = st.get("my_kredits")
            hand = st.get("my_hand") or []
            min_cost = min([c.get("cost") for c in hand if c.get("cost") is not None], default=None)
            if fee is not None and min_cost is not None and fee < min_cost and not st.get("my_units"):
                action = {"action": "end", "reason": "防卡死:费不足"}
            else:
                try:
                    action = brain.decide(text)
                except Exception as e:
                    print("决策出错:", e); action = {"action": "end"}
            if verbose:
                print("   决策:", json.dumps(action, ensure_ascii=False)[:150])
            g._last_hand_count = len(hand)
            g._last_fee = fee
            g.execute(action)
        else:
            # 非我方回合(敌方/换牌/过渡):换牌要处理,其他等待
            if phase == "mulligan":
                text = state_to_text(st)
                action = brain.decide(text)
                g._last_hand_count = len(st.get("my_hand") or [])
                g.execute(action)
            else:
                time.sleep(2)
        # 停滞检测
        if phase == last_phase:
            stall += 1
            if stall > 12:
                time.sleep(2)
        else:
            stall = 0
        last_phase = phase
        time.sleep(1.5)
    res = {"result": "timeout", "turns": max_steps}
    log_result(res)
    return res


def detect_result(img_path, st) -> str:
    """对局结束时判断胜负:HQ血量或结算画面。"""
    if (st.get("enemy_hq") or 99) <= 0:
        return "win"
    if (st.get("my_hq") or 99) <= 0:
        return "lose"
    return "unknown"


def winrate():
    if not os.path.exists(RESULTS):
        return "暂无对局记录"
    W = L = U = 0
    for line in open(RESULTS, encoding="utf-8"):
        r = json.loads(line).get("result")
        if r == "win": W += 1
        elif r == "lose": L += 1
        else: U += 1
    tot = W + L
    return f"胜{W} 负{L} 未知{U}  胜率(已知)={W/tot*100:.0f}%" if tot else f"未知结果{U}局"


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    for i in range(n):
        print(f"\n===== 第 {i+1} 局 =====")
        start_match()
        r = play_one_match()
        print("本局结果:", r)
        print("累计:", winrate())
        time.sleep(4)
