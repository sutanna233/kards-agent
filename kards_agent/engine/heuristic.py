"""
启发式评估与动作打分。
核心决策逻辑由 MASTER 维护:给定 GameState 与候选 Action,打分并排序。
权重可调,后续用真实对局复盘数据做轻量参数优化。
"""
from __future__ import annotations
from typing import List
from .state import GameState, Action, ActionKind, UnitKind, Line, legal_actions

# 可调权重(后续用真实对局复盘优化)
W = {
    "hq_lethal": 1000.0,     # 能斩杀敌方HQ:最高优先
    "kill_unit": 6.0,        # 击杀敌方单位(按敌方攻击+防御价值)
    "trade_value": 2.0,      # 交换价值(我方损失 vs 敌方损失)
    "front_pressure": 3.0,   # 推进前线施压
    "hq_damage": 1.5,        # 对HQ造成的伤害价值
    "board_control": 2.5,    # 场攻/站场
    "kredit_efficiency": 1.0 # 费用利用
}


def _unit_threat(u) -> float:
    return u.card.attack + max(0, u.cur_defense) * 0.5


def score_state(state: GameState) -> float:
    """评估局面对我方的净优势(越大越好)。"""
    me, enemy = state.me, state.enemy
    score = 0.0
    # HQ 血量差
    score += (me.hq_defense - enemy.hq_defense) * W["hq_damage"]
    # 场攻/站场
    score += sum(_unit_threat(u) for u in me.all_units()) * W["board_control"]
    score -= sum(_unit_threat(u) for u in enemy.all_units()) * W["board_control"]
    # 手牌优势
    score += (len(me.hand) - enemy.hand_count) * 0.8
    # 我方 HQ 危险程度(对方场攻高则扣)
    return score


def score_action(state: GameState, act: Action) -> float:
    """给单个候选动作打分(在合法动作里选最高)。"""
    me, enemy = state.me, state.enemy
    s = 0.0

    if act.kind == ActionKind.ATTACK:
        if act.target_hq:
            # 攻击 HQ:若能斩杀则爆表
            atk = me.all_units()[act.attacker].card.attack if act.attacker >= 0 else 0
            if atk >= enemy.hq_defense:
                s += W["hq_lethal"]
            else:
                s += atk * W["hq_damage"]
        elif act.target >= 0:
            atk_u = me.all_units()[act.attacker]
            def_u = enemy.all_units()[act.target]
            # 若能击杀敌方单位
            if atk_u.card.attack >= def_u.cur_defense:
                s += W["kill_unit"] * (def_u.card.attack + def_u.card.cost)
            # 交换代价:我方会被反击,扣减
            s -= def_u.card.attack * W["trade_value"]

    elif act.kind == ActionKind.PLAY_CARD:
        card = me.hand[act.hand_index] if 0 <= act.hand_index < len(me.hand) else None
        if card:
            s += (card.attack + card.defense) * W["board_control"]
            s += card.cost * W["kredit_efficiency"] * 0.2  # 高费但物尽其用

    elif act.kind == ActionKind.MOVE and act.line == Line.FRONT:
        s += W["front_pressure"]

    elif act.kind == ActionKind.PLAY_ORDER:
        s += 3.0  # 指令基线分(具体按卡牌效果,后续接入卡牌效果表)

    elif act.kind == ActionKind.END_TURN:
        s += 0.1  # 兜底

    return s


def choose_action(state: GameState) -> Action:
    """主入口:在合法动作中选打分最高者。"""
    acts = legal_actions(state)
    if not acts:
        return Action(kind=ActionKind.END_TURN, reason="无合法动作,结束回合")
    best = max(acts, key=lambda a: score_action(state, a))
    return best
