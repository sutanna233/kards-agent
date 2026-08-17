"""
导航模块:在 KARDS 菜单间移动,进入训练模式对局。
坐标基于 1280x720 横屏 golden 样本标定。
"""
from __future__ import annotations
import time
from . import adbc

SERIAL = adbc.DEFAULT_SERIAL

# 菜单坐标(1280x720 横屏)
PT_MAIN_START = (75, 200)      # 主菜单"开始"
PT_MODE_TRAINING = (335, 260)  # "训练模式"
PT_DECK_FIRST = (620, 260)     # 第一个卡组(德国卡组)
PT_DECK_START = (1077, 600)    # 卡组详情页右下"开始"
PT_CONFIRM = (640, 645)        # 换牌"确认"按钮


def tap(p, wait=1.2):
    adbc.tap(SERIAL, p[0], p[1])
    time.sleep(wait)


def goto_training_match(serial: str = SERIAL, deck_pt=PT_DECK_FIRST):
    """从主菜单进入训练模式对局。返回是否已到加载/换牌阶段。"""
    tap(PT_MAIN_START, 1.5)
    tap(PT_MODE_TRAINING, 1.2)
    tap(deck_pt, 1.5)
    tap(PT_DECK_START, 5.0)   # 点开始,等加载
    return True
