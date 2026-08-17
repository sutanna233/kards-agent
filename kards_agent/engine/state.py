"""
KARDS 游戏状态模型与合法动作。
这是 视觉识别层(把屏幕识别成这个结构) 与 决策层(基于这个结构出招) 共用的契约。
只建模主干规则:HQ、三条战线、单位、手牌、Kredits、回合阶段。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Nation(str, Enum):
    GERMANY = "germany"
    BRITAIN = "britain"
    SOVIET = "soviet"
    USA = "usa"
    JAPAN = "japan"
    ITALY = "italy"      # 扩展/同盟国
    FRANCE = "france"
    POLAND = "poland"
    UNKNOWN = "unknown"


class CardType(str, Enum):
    UNIT = "unit"               # 单位(步兵/坦克/炮兵/战斗机/轰炸机)
    ORDER = "order"             # 指令(一次性效果)
    COUNTER = "counter"         # 反制措施(隐藏、敌方回合触发)
    UNKNOWN = "unknown"


class UnitKind(str, Enum):
    INFANTRY = "infantry"   # 步兵
    TANK = "tank"           # 坦克
    ARTILLERY = "artillery" # 炮兵(远程)
    FIGHTER = "fighter"     # 战斗机
    BOMBER = "bomber"       # 轰炸机
    NONE = "none"
    UNKNOWN = "unknown"


class Line(str, Enum):
    HQ = "hq"           # 总部
    SUPPORT = "support" # 支援线
    FRONT = "front"     # 前线(只能由地面单位推进)
    DEFENSE = "defense" # 防御线(预备/撤退区)
    UNKNOWN = "unknown"


# 单位可能持有的关键词/技能(主干)
KEYWORDS = {
    "blitz",      # 闪袭:部署当回合即可行动
    "fury",       # 奋战:同一回合可行动两次
    "guard",      # 守护:相邻单位不被轰炸/火炮之外攻击
    "smoke",      # 烟幕:移动/攻击前不可被攻击
    "fury2",      # 预留
}


@dataclass
class Card:
    """一张卡(手牌或场上的卡牌定义)。"""
    cid: str = ""                  # 唯一id
    name: str = ""
    nation: Nation = Nation.UNKNOWN
    ctype: CardType = CardType.UNKNOWN
    kind: UnitKind = UnitKind.NONE # 单位子类型(非单位为 NONE)
    cost: int = 0                  # Kredits 花费(部署)
    action_cost: int = 0           # 行动花费(移动/攻击)
    attack: int = 0
    defense: int = 0
    abilities: List[str] = field(default_factory=list)   # 关键词: blitz/fury/guard/smoke
    text: str = ""                 # 技能描述


@dataclass
class Unit:
    """战场上一个已部署的单位实例。"""
    card: Card
    line: Line = Line.UNKNOWN
    cur_defense: int = 0           # 当前防御(被打会减)
    can_act: bool = True           # 本回合是否可行动(闪袭/奋战影响)
    acted: int = 0                 # 本回合已行动次数
    exhausted: bool = False


@dataclass
class PlayerState:
    hq_defense: int = 20           # 总部血量(默认20,KARDS 通常 20)
    kredits: int = 0               # 当前可用指挥点
    kredits_max: int = 0           # 本回合上限
    hand: List[Card] = field(default_factory=list)
    deck_count: int = 0            # 牌库剩余
    hand_count: int = 0            # 手牌数量(对手只知数量)
    # 三条战线上的单位
    support: List[Unit] = field(default_factory=list)
    front: List[Unit] = field(default_factory=list)
    defense: List[Unit] = field(default_factory=list)

    def all_units(self) -> List[Unit]:
        return self.support + self.front + self.defense


class Phase(str, Enum):
    MENU = "menu"             # 主菜单/未在对局
    LOADING = "loading"       # 加载/抽卡/过渡画面
    MY_TURN = "my_turn"       # 我方回合
    ENEMY_TURN = "enemy_turn" # 敌方回合
    GAME_OVER = "game_over"   # 对局结束(胜负结算)
    UNKNOWN = "unknown"


@dataclass
class GameState:
    """视觉层识别 + 内部维护的完整对局状态。"""
    phase: Phase = Phase.UNKNOWN
    me: PlayerState = field(default_factory=PlayerState)
    enemy: PlayerState = field(default_factory=PlayerState)
    turn: int = 0
    # 我方 HQ 是哪个、在哪,由视觉识别确认(me/enemy 在屏幕上下)
    raw_notes: List[str] = field(default_factory=list)   # 识别备注/置信度

    def is_my_turn(self) -> bool:
        return self.phase == Phase.MY_TURN


# ---------------- 合法动作 ----------------
class ActionKind(str, Enum):
    PLAY_CARD = "play_card"     # 出手牌到某线/某目标
    ATTACK = "attack"           # 用某单位攻击某目标(单位或HQ)
    MOVE = "move"               # 单位换线(推进/撤退)
    PLAY_ORDER = "play_order"   # 使用指令
    END_TURN = "end_turn"
    NONE = "none"


@dataclass
class Action:
    kind: ActionKind = ActionKind.NONE
    hand_index: int = -1          # 出哪张手牌
    line: Line = Line.UNKNOWN     # 放到/移动到 哪条线
    attacker: int = -1            # 攻击者索引(在 all_units 中)
    target: int = -1              # 攻击目标索引(-1=HQ 之类用 target_hq)
    target_hq: bool = False
    reason: str = ""              # 决策理由(可解释)


def legal_actions(state: GameState) -> List[Action]:
    """根据当前状态枚举合法动作(主干规则)。
    只在我方回合调用。不追求覆盖全部边缘规则,先覆盖主干。
    """
    acts: List[Action] = []
    if not state.is_my_turn():
        return acts

    me, enemy = state.me, state.enemy

    # 1) 出手牌(单位卡 -> 防御线;指令卡 -> 释放)
    for i, card in enumerate(me.hand):
        if card.cost > me.kredits:
            continue
        if card.ctype == CardType.UNIT:
            # 单位默认部署到防御线(ground units);战斗机/轰炸机可视规则放支援
            acts.append(Action(kind=ActionKind.PLAY_CARD, hand_index=i,
                               line=Line.DEFENSE, reason=f"部署单位 {card.name}"))
        elif card.ctype == CardType.ORDER:
            acts.append(Action(kind=ActionKind.PLAY_ORDER, hand_index=i,
                               reason=f"使用指令 {card.name}"))

    # 2) 攻击:每个可行动单位尝试攻击敌方单位或HQ
    for ai, u in enumerate(me.all_units()):
        if not u.can_act or u.exhausted:
            continue
        # 敌方单位为目标
        for ti, eu in enumerate(enemy.all_units()):
            acts.append(Action(kind=ActionKind.ATTACK, attacker=ai, target=ti,
                               reason=f"{u.card.name} 攻击 {eu.card.name}"))
        # 直接攻击敌方 HQ
        acts.append(Action(kind=ActionKind.ATTACK, attacker=ai, target_hq=True,
                           reason=f"{u.card.name} 攻击敌方HQ"))

    # 3) 推进:防御线地面单位推进到前线/支援线
    for ai, u in enumerate(me.all_units()):
        if u.line == Line.DEFENSE and u.card.kind in (UnitKind.INFANTRY, UnitKind.TANK):
            acts.append(Action(kind=ActionKind.MOVE, attacker=ai, line=Line.FRONT,
                               reason=f"推进 {u.card.name} 到前线"))

    # 4) 结束回合
    acts.append(Action(kind=ActionKind.END_TURN, reason="结束回合"))
    return acts
