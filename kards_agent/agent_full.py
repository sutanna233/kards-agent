"""
最终整合 Agent:识别(多模态完整局面)→ 决策(卡组skill+局面JSON)→ 执行(JSON→触摸操作)。
按用户定的架构:识别给模型完整JSON,模型返回JSON决策,脚本执行具体操作。

手牌精确化(handread):每回合开始时用 read_hand_smart 权威读手牌
(LLM读扇形拿张数/位置 → 逐张点开详情OCR → 卡组约束),替换多模态的粗略手牌。
回合内出牌后本地移除,不重读。整回合预算 ≤25s。
"""
from __future__ import annotations
import os, time, json, shutil
from . import adbc, nav, brain, perceive, gameover, handread, webview
from .matcher import _imread

SERIAL = adbc.DEFAULT_SERIAL
LOG = "logs"

# ---- 战线槽位坐标(1280x720,实测/工程师标定) ----
# 我方在下半屏:HQ约(640,545),防御线y≈484,前线y≈365
# 敌方在上半屏:HQ约(640,180),前线y≈360,防御线y≈270
# 手牌扇形:底部 y≈620-680
MY_HQ = (640, 545)
ENEMY_HQ = (640, 180)
MY_DEFENSE_Y = 484
MY_FRONT_Y = 365
ENEMY_FRONT_Y = 360
ENEMY_DEFENSE_Y = 270
END_TURN = (1148, 516)

# 战线槽位 x 坐标(从左到右最多5个槽)
def _line_x(i, n):
    if n <= 1:
        return 640
    left, right = 380, 900
    return int(left + (right-left)*i/(n-1))


def state_json_text(st: dict) -> str:
    """把识别局面转成喂给模型的文本(JSON格式)。"""
    return json.dumps(st, ensure_ascii=False)


class Agent:
    def __init__(self, skill_path: str = None, decklist_path: str = None):
        self.serial = SERIAL
        self.skill = ""
        if skill_path and os.path.exists(skill_path):
            self.skill = open(skill_path, encoding="utf-8").read()
        # 卡组(手牌识别约束 + 决策参考)
        self.deck = None
        if decklist_path and os.path.exists(decklist_path):
            self.deck = handread.load_deck(decklist_path)
        # 手牌缓存:回合内不重读
        self._hand_cache: list[dict] | None = None
        self._hand_fee = None

    def capture(self, tag):
        p = os.path.join(LOG, f"agent_{tag}_{int(time.time())}.png")
        adbc.screenshot(self.serial, p)
        try:
            shutil.copyfile(p, os.path.join(LOG, "_live.png"))  # WebUI 实时画面
        except Exception:
            pass
        return p

    # ---------- 手牌精确化 ----------
    def get_hand(self, fee, img0=None) -> list[dict]:
        """每回合(费用变化)用 handread 权威读一次;回合内沿用缓存。"""
        if self._hand_cache is None or fee != self._hand_fee:
            t0 = time.time()
            webview.emit("state", "正在逐张点开读手牌...")
            hand = handread.read_hand_smart(self.serial, self.deck, verbose=True, img0=img0)
            if hand:
                self._hand_cache = hand
                self._hand_fee = fee
                print(f"  精确手牌({time.time()-t0:.1f}s):", handread.hand_to_text(hand))
                webview.emit("hand", f"手牌: {handread.hand_to_text(hand)} ({time.time()-t0:.1f}s)")
        return self._hand_cache or []

    # ---------- 决策护栏(硬规则,不信 LLM 自觉) ----------
    def guard_action(self, action: dict, st: dict) -> dict:
        """执行前校验决策合法性,非法就替换:
        1) 费用护栏:想出费用>当前费的卡 → 换成出得起的卡里费用最高的;都出不起 → end
        2) 爆牌护栏:手牌≥8 且要出抽牌卡(效果含"抽")→ 换非抽牌的可出卡;没有 → end
        """
        if action.get("action") != "play":
            return action
        hand = st.get("my_hand", [])
        fee = st.get("my_kredits")
        hi = action.get("hand_index", 0)
        if not hand or fee is None:
            return action
        if not (0 <= hi < len(hand)):
            hi = 0
        card = hand[hi]
        cost = card.get("cost")
        is_draw = "抽" in (card.get("effect") or "")
        affordable = [c for c in hand
                      if c.get("cost") is not None and c["cost"] <= fee]
        # 1) 费用护栏
        if cost is not None and cost > fee:
            if affordable:
                best = max(affordable, key=lambda c: c["cost"])
                action = dict(action, hand_index=hand.index(best),
                              reason=f"护栏:原卡{cost}费>当前{fee}费,改出{best.get('name')}")
                card = best
                is_draw = "抽" in (card.get("effect") or "")
            else:
                return {"action": "end", "reason": f"护栏:所有卡费用>{fee},结束回合"}
        # 2) 爆牌护栏
        if len(hand) >= 8 and is_draw:
            non_draw = [c for c in affordable if "抽" not in (c.get("effect") or "")]
            if non_draw:
                best = max(non_draw, key=lambda c: c["cost"])
                return dict(action, hand_index=hand.index(best),
                            reason=f"护栏:手牌{len(hand)}张将爆牌,改出{best.get('name')}")
            return {"action": "end", "reason": f"护栏:手牌{len(hand)}张,禁过牌,结束回合"}
        return action

    # ---------- 执行具体操作 ----------
    def exec_action(self, action: dict, st: dict):
        act = action.get("action")
        if act == "end":
            adbc.tap(self.serial, *END_TURN)
            return "结束回合"
        if act == "mulligan":
            for i in action.get("replace", []):
                # 换牌:点对应手牌的⊕
                xs = self._hand_x_positions(len(st.get("my_hand", [])))
                if 0 <= i < len(xs):
                    adbc.tap(self.serial, xs[i], 620); time.sleep(0.5)
            adbc.tap(self.serial, 640, 645)  # 确认
            return "换牌"
        if act == "play":
            hi = action.get("hand_index", 0)
            hand = st.get("my_hand", [])
            n = len(hand)
            # 优先用读牌时记录的中心x,没有再用扇形公式
            xs = [c.get("cx") for c in hand]
            fx = self._hand_x_positions(n)
            sx = xs[hi] if 0 <= hi < len(xs) and xs[hi] else (fx[hi] if 0 <= hi < len(fx) else 640)
            # 出牌:从手牌拖到防御线,带费用验证重试
            fee_before = st.get("my_kredits")
            from . import keynum as _kn
            for attempt, (dx, dy) in enumerate([(0, 0), (-20, 10), (20, 10), (-40, 0), (40, 0)]):
                adbc.swipe(self.serial, sx + dx, 650 + dy, 640, MY_DEFENSE_Y, 800)
                time.sleep(1.5)
                img2 = _imread(self.capture(f"verify{attempt}"))
                new_fee = _kn.read_fee_cv(img2)
                if fee_before is None or new_fee is None or new_fee < fee_before:
                    # 回合内缓存移除已出的卡
                    if self._hand_cache and 0 <= hi < len(self._hand_cache):
                        self._hand_cache.pop(hi)
                    return f"出牌 hand[{hi}]@x{sx+dx} (尝试{attempt+1}次)"
            return f"出牌 hand[{hi}] 失败(费用未扣)"
        if act == "attack":
            # 攻击:从攻击者拖到目标(HQ或单位)
            tgt = action.get("target", "hq")
            # 简化:拖到敌方HQ
            adbc.swipe(self.serial, 640, MY_FRONT_Y, ENEMY_HQ[0], ENEMY_HQ[1], 700)
            time.sleep(1.2)
            return "攻击"
        return f"动作{act}"

    def _hand_x_positions(self, n):
        """手牌扇形各卡中心x(实测:n张时左端300,步进按张数)。"""
        if n <= 0:
            return [640]
        if n == 1:
            return [640]
        step = min(135, 620 // max(1, n - 1))
        start = 640 - step * (n - 1) // 2
        return [int(start + step * i) for i in range(n)]

    # ---------- 主循环 ----------
    def play_match(self, max_steps=50):
        print("=== 进入对局,开始自动打 ===")
        last_sig = None
        stall = 0
        for step in range(max_steps):
            img = self.capture(step)
            # 先CV检测结算(快)
            go = gameover.detect_gameover(_imread(img))
            if go:
                print(f"[{step}] 对局结束: {go}")
                webview.emit("game", f"对局结束: {go}")
                nav.back_to_menu() if hasattr(nav, 'back_to_menu') else None
                return go
            # 多模态识别完整局面
            try:
                st = perceive.recognize(img)
            except Exception as e:
                print("识别出错:", e); time.sleep(2); continue
            # 费用用纯 CV 校正(多模态读费用不可靠,会导致非法出牌)
            from . import keynum as _kn
            cv_fee = _kn.read_fee_cv(_imread(img))
            if cv_fee is not None:
                st["my_kredits"] = cv_fee
            phase = st.get("phase")
            print(f"[{step}] phase={phase} 费{st.get('my_kredits')}/{st.get('my_kredits_max')} HQ{st.get('my_hq')}v{st.get('enemy_hq')}")
            webview.emit("state", {
                "step": step, "phase": phase,
                "费": f"{st.get('my_kredits')}/{st.get('my_kredits_max')}",
                "HQ": f"{st.get('my_hq')}v{st.get('enemy_hq')}",
                "我方单位": st.get("my_units"), "敌方单位": st.get("enemy_units"),
            })
            if phase == "game_over":
                res = st.get("result", "unknown")
                print(f"[{step}] 对局结束(识别): {res}")
                webview.emit("game", f"对局结束: {res}")
                return res
            if phase in ("enemy_turn", "loading"):
                time.sleep(2); continue
            # 防卡死:费用不足且无单位 → 结束回合
            fee = st.get("my_kredits")
            if phase == "my_turn":
                # 权威手牌替换多模态粗略手牌(每回合一次,回合预算内)
                precise = self.get_hand(fee, img0=_imread(img))
                if precise:
                    st["my_hand"] = [
                        {"name": c.get("name"), "cost": c.get("cost"),
                         "type": c.get("type"), "attack": c.get("attack"),
                         "defense": c.get("defense"), "effect": c.get("effect", ""),
                         "cx": c.get("cx")}
                        for c in precise
                    ]
            hand = st.get("my_hand", [])
            min_cost = min([c.get("cost") for c in hand if c.get("cost") is not None], default=None)
            if phase == "my_turn" and fee is not None and min_cost is not None and fee < min_cost and not st.get("my_units"):
                print("  防卡死:费不足,结束回合")
                webview.emit("decision", {"action": "end", "reason": "防卡死:费不足"})
                self.exec_action({"action": "end"}, st)
            else:
                # 决策:局面JSON + 卡组skill,过护栏后再执行
                action = brain.decide_with_skill(state_json_text(st), self.skill)
                action = self.guard_action(action, st)
                print("  决策:", json.dumps(action, ensure_ascii=False)[:150])
                webview.emit("decision", action)
                r = self.exec_action(action, st)
                webview.emit("exec", r)
            time.sleep(2)
        return "timeout"
