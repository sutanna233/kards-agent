"""
主循环 orchestrator:把 截图→识别→决策→执行 串成自动对局循环。
纯文本决策(快、省token);图像只在识别兜底时用(裁小图)。
"""
from __future__ import annotations
import os, time, json
from . import adbc
from . import brain

SERIAL = adbc.DEFAULT_SERIAL
LOG_DIR = "logs"


def state_to_text(st: dict) -> str:
    """把结构化状态压成紧凑文本(喂给纯文本LLM,几十token)。"""
    def cards(cs):
        return ",".join(f"{c.get('name','?')}({c.get('cost','?')}费{c.get('attack','?')}/{c.get('defense','?')})" for c in (cs or [])) or "无"
    lines = [
        f"阶段:{st.get('phase')}",
        f"我方费:{st.get('my_kredits')}/{st.get('my_kredits_max')} 敌方费:{st.get('enemy_kredits')}",
        f"我方HQ:{st.get('my_hq')} 敌方HQ:{st.get('enemy_hq')}",
        f"我方手牌:{cards(st.get('my_hand'))}",
        f"敌方手牌数:{st.get('enemy_hand_count')}",
        f"我方场上:{cards(st.get('my_units'))}",
        f"敌方场上:{cards(st.get('enemy_units'))}",
    ]
    return "\n".join(lines)


class GameLoop:
    def __init__(self, serial: str = SERIAL, use_vision_fallback: bool = True):
        self.serial = serial
        self.use_vision_fallback = use_vision_fallback
        self.turn = 0

    def capture(self, tag: str):
        path = os.path.join(LOG_DIR, f"loop_{tag}_{int(time.time())}.png")
        adbc.screenshot(self.serial, path)
        return path

    def recognize_state(self, img_path: str) -> dict:
        """识别当前画面为结构化状态。
        关键数字(费用/HQ)用 keynum 专用小图读取(准);手牌/战场用 perceive 整图(全)。
        """
        from . import perceive, keynum
        st = perceive.recognize(img_path)
        # 清洗:HQ 不是单位
        hq_names = {"danzig", "cherbourg", "stalingrad", "cherdouge"}
        for key in ("my_units", "enemy_units"):
            st[key] = [u for u in (st.get(key) or [])
                       if u and (u.get("name") or "").lower() not in hq_names]
        # 用专用数字读取校正关键数字(更准)
        kn = keynum.read_key_numbers(img_path)
        for k in ("my_kredits", "my_hq", "enemy_hq"):
            if kn.get(k) is not None:
                st[k] = kn[k]
        return st

    def execute(self, action: dict):
        """把决策 JSON 变成 adb 触摸操作。"""
        act = action.get("action")
        if act == "end":
            adbc.tap(self.serial, 1148, 516)  # 结束回合
            return "结束回合"
        if act == "mulligan":
            xs = [147, 412, 639, 866, 1093]
            for i in action.get("replace", []):
                if 0 <= i < len(xs):
                    adbc.tap(self.serial, xs[i], 558); time.sleep(0.6)
            adbc.tap(self.serial, 640, 645)  # 确认
            return f"换牌{action.get('replace')}"
        if act == "play":
            hi = action.get("hand_index")
            n = self._last_hand_count or 7
            line = action.get("line", "defense")
            tx, ty = (640, 470) if line == "defense" else (640, 360)
            fee_before = self._last_fee
            # 带验证重试:尝试多个候选起点,直到费用减少(出牌成功)
            base_x = self._hand_x(hi, n)
            for attempt, (dx, dy) in enumerate([(0, 0), (-15, 10), (15, 10), (0, -15), (-30, 0), (30, 0), (0, 20)]):
                sx = base_x + dx
                adbc.swipe(self.serial, sx, 645 + dy, tx, ty, 800)
                time.sleep(1.6)
                new_fee = self._read_fee()
                if fee_before is None or new_fee is None or new_fee < fee_before:
                    return f"出牌 hand[{hi}]@x{sx} -> {line} (尝试{attempt+1}次)"
            return f"出牌 hand[{hi}] 可能失败(费用未变)"
        if act == "attack":
            # 攻击:从攻击者拖到目标(target=hq 拖敌方HQ)
            adbc.swipe(self.serial, 640, 460, 640, 175, 600)
            time.sleep(1.0)
            return "攻击"
        return f"动作{act}待执行"

    # 手牌扇形:实测6张时中心x=[290,400,510,630,750,860](相邻~110-120)。按张数围绕中心640展开。
    _last_hand_count = None
    _last_fee = None

    def _read_fee(self):
        """快速CV读我方当前费用(橙色大数字,左下)。失败返回None。"""
        try:
            import numpy as np, cv2
            from .matcher import _imread
            p = "logs/_fee.png"
            adbc.screenshot(self.serial, p)
            img = _imread(p)
            if img is None:
                return None
            roi = img[495:560, 30:120]
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, np.array([8, 150, 150]), np.array([30, 255, 255]))
            cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cnts = [c for c in cnts if cv2.contourArea(c) > 30]
            if not cnts:
                return None
            cnts.sort(key=lambda c: cv2.boundingRect(c)[0])
            from .digits import DigitReader
            dr = DigitReader()
            digits = []
            for c in cnts:
                x, y, w, h = cv2.boundingRect(c)
                cell = mask[y:y + h, x:x + w]
                d = dr._match(cell)
                if d: digits.append(d)
            return int("".join(digits)) if digits else None
        except Exception:
            return None

    def _hand_x(self, i, n):
        # 实测:手牌扇形左端 x≈300,向右展开。第i张 ≈ 300 + i*步进
        # 步进随张数:n=5→130, n=6→114, n=8→95。近似 step = 620/(n-1)
        i = max(0, min(i or 0, max(0, n - 1)))
        if n <= 1:
            return 420
        step = 620 / (n - 1)
        step = min(step, 135)  # 单张步进上限
        return int(300 + i * step)

    def step(self):
        """一个决策步:截图→识别→决策→执行。带防卡死硬约束。"""
        img = self.capture(f"t{self.turn}")
        st = self.recognize_state(img)
        phase = st.get("phase")
        self._last_hand_count = len(st.get("my_hand") or [])
        self._last_fee = st.get("my_kredits")
        text = state_to_text(st)
        print(f"--- 步{self.turn} 阶段={phase} ---")
        print(text)
        if phase in ("game_over",):
            print("对局结束")
            return False

        # ===== 防卡死硬约束 =====
        fee = st.get("my_kredits")
        hand = st.get("my_hand") or []
        # 1) 费用不足:手牌最低费 > 当前费,且场上无可行动单位 → 强制结束回合
        min_cost = min([c.get("cost") for c in hand if c.get("cost") is not None], default=None)
        if phase == "my_turn" and fee is not None and min_cost is not None and fee < min_cost:
            has_unit = bool(st.get("my_units"))
            if not has_unit:
                print("防卡死:费不足且无单位,强制结束回合")
                self.execute({"action": "end"})
                self.turn += 1
                return True
        # 2) 每回合动作预算:同一回合连续动作超上限 → 强制结束回合
        self._turn_actions += 1
        if self._turn_actions > 6:
            print("防卡死:本回合动作超预算,强制结束回合")
            self.execute({"action": "end"})
            self._turn_actions = 0
            self.turn += 1
            return True

        action = brain.decide(text)
        print("决策:", json.dumps(action, ensure_ascii=False))
        res = self.execute(action)
        print("执行:", res)
        self.turn += 1
        return True

    _turn_actions = 0

    def run(self, max_steps: int = 40):
        print("=== 开始自动对局循环 ===")
        last_sig = None
        stall = 0
        for _ in range(max_steps):
            try:
                # 停滞检测:费用+手牌数+HQ 组成签名,连续相同=卡死
                sig = (self._last_fee, self._last_hand_count)
                if sig == last_sig and self._last_fee is not None:
                    stall += 1
                    if stall >= 4:
                        print("防卡死:连续多步无变化,强制结束回合")
                        self.execute({"action": "end"})
                        self._turn_actions = 0
                        stall = 0
                else:
                    stall = 0
                last_sig = sig
                if not self.step():
                    break
            except Exception as e:
                print("步出错:", e)
            time.sleep(3)


if __name__ == "__main__":
    GameLoop().run()
