# KARDS 自玩 Agent

让 **Qwen3.6-35B-A3B**(经 sunjun3773 OpenAI 兼容服务)自主打真实 KARDS(二战卡牌游戏)。

运行形态:雷电模拟器(LDPlayer9)运行 KARDS 安卓版 → agent **读屏(adb截图)→ 识别局面 → Qwen35B 决策 → adb 注入触摸**执行。

## 运行方式

```bash
# 1. 启动雷电模拟器,装好 KARDS 并登录(账号由你自行登录)
# 2. 确保 adb 能连上(默认 serial 127.0.0.1:5555 / emulator-5554)
python scripts/smoke_adb.py        # 冒烟测试:确认 adb 连通+截图

# 3. 自动打 N 局训练模式(人机)
python -m kards_agent.runner 3     # 连打3局,自动导航+对局+统计胜率
```

## 架构

```
kards_agent/
├─ adbc.py       # adb 封装:截图(原始字节)/点击/拖拽/UI dump
├─ perceive.py   # 视觉识别:裁关键区拼小图,多模态输出结构化局面
├─ perceive_full.py    # 整图多模态读(单位/手牌/攻防)
├─ perceive_ocr.py     # RapidOCR 路线(卡名/数字/坐标)
├─ recognizer.py # 多模态识别统一入口
├─ keynum.py     # 关键数字专用读取(费用/HQ血量,徽章特征定位 + 相对偏移 + 放大,准)
├─ digits.py     # 数字模板识别(0-9 模板库,纯 CV,无多模态)
├─ matcher.py    # 自动模板匹配(多尺度/ORB),卡图/界面元素定位
├─ handloc.py    # 手牌卡图模板定位
├─ handread.py   # 手牌多模态读取(逐张裁小图喂 LLM)
├─ nav.py        # 界面导航状态机(识别10种界面,处理过渡页)
├─ navigate.py   # 导航小工具
├─ gameover.py   # 胜负结算检测(CV模板匹配)
├─ carddb.py / cardid.py / card_effects.py  # 卡牌数据库 + 效果库 + 认卡
├─ brain.py      # Qwen35B 决策大脑(提示工程,注入KARDS打法知识 + 卡组专属 skill)
├─ engine/state.py + heuristic.py  # 游戏状态模型 + 启发式评估(已写好,**当前未接入决策环**)
├─ loop.py       # 单步循环:截图→识别→决策→执行(带防卡死)
├─ agent_full.py # 整合识别→决策→执行的完整 agent(带 say 解说)
└─ runner.py     # 整局自动对局 + 多局连打 + 胜率统计

cards/cards.json         # 100张核心卡数据(五国)
templates/cards/         # 1613张简体中文卡图模板库(官方 zh-Hans CDN)
templates/digits/        # 数字模板(0-9)
templates/               # 界面/gameover/HQ徽章/结束按钮模板
logs/results.jsonl       # 每局胜负记录
logs/loop_*.png          # 每步截图(诊断用)
```

## 决策闭环(三层识别路径)

KARDS 信息密度高,**识别精度**是决策质量的命脉。当前是**三层并联**而不是单一路:

| 层 | 模块 | 用法 | 优势 | 现状 |
|---|---|---|---|---|
| L1 纯 CV 数字 | `digits.py` + `loop._read_fee` | 颜色阈值(橙色/白色) → 连通域分离 → 0-9 模板匹配 | 毫秒级,无网络 | 费用读数已在 `loop._read_fee` 用 |
| L2 特征定位 + 小图多模态 | `keynum.py` | HQ 徽章 ORB 模板定位 → 相对偏移裁血量框 → 5-6× 放大 → 多模态读 | 抗 UI 抖动,只喂裁干净的小图 | HQ 血量主力路径 |
| L3 整图多模态兜底 | `perceive.py` / `perceive_full.py` / `handread.py` | 整图或手牌逐张喂 LLM | 啥都能读 | 场上单位/手牌识别主力 |

JSON 解析层(`brain._parse_json_action`)对 LLM 输出做截断补齐 + 关键字兜底,LLM 再抽也不至于让 agent 崩。

## 已验证的能力(实测)

- ✅ adb 截图/点击/拖拽全通(雷电模拟器)
- ✅ 界面导航状态机:自动从主菜单/每日奖励/结算页/断线页 导航进训练模式对局
- ✅ 视觉识别:识别阶段/双方费用/HQ血量/手牌/场上单位
- ✅ Qwen35B 决策:换牌、出牌、攻击、结束回合,能识别斩杀机会
- ✅ 拖拽出牌成功(实测费用扣减)
- ✅ **自动打完完整对局并获胜**(识别敌方残血→轰炸机斩杀)
- ✅ `attack` 动作已实现:`loop.execute("attack")` 从攻击者拖到 (640,460) → 敌方 (640,175)
- ✅ 防卡死硬保险:费用不足强制结束、动作预算 6 步、停滞检测 4 步签名
- ✅ game_over 胜负检测 + 胜率统计

## 已知限制(基于代码事实,2026-08)

- **`attack` 是硬编码一刀切**:`(640, 460) → (640, 175)` 写死坐标,没考虑场上单位位置、攻击目标选择、自身单位存活校验。实战里 LLM 几乎不会主动触发 attack。
- **`engine/heuristic.py` 已写好但未接入**:`loop.step` 直接 `brain.decide(text)`,启发式威胁评估没参与候选动作排序。LLM 既要做理解又要做评估,负担过重。
- **识别精度的剩余瓶颈**:手牌卡名/攻防识别仍依赖整图多模态,小字识别有误差。费用偶发误读,L1 纯 CV 路径只在 `loop._read_fee` 里孤零零用着,没覆盖 HQ 血量读数路径。
- **手牌扇形定位**:张数变化时坐标仍有偏差,靠"出牌后验证费用"重试兜底(7 个候选起点)。
- **强度**:能打赢较弱的内置 AI,对强 AI 胜率未测;`attack` 不工作导致对局偏被动,常靠斩杀收尾。

## 下一步(优先级,基于代码事实)

1. **让 attack 真的能被用起来**(最高优先级)
   - 短期:在 `brain.BASE_SYSTEM` 里把 attack 的优先级提到和斩杀并列,加"敌方 HQ < N 且有前线单位即 attack"提示
   - 中期:把 `attack` 改成"指定场上单位 + 指定目标(敌方单位或 HQ)"的真实路径,而不是写死坐标
2. **接入 `engine/heuristic.py`**:`loop.step` 里 `brain.decide` 前先跑一遍启发式,生成候选动作排序喂给 LLM 做最终裁决,降低 LLM 评估负担
3. **识别精度收尾**:
   - L1 纯 CV 数字读数扩展到 HQ 血量(`digits.py` 已就绪,缺一个 `read_hp(roi)` 接口)
   - 手牌走 `handread.py` 逐张裁小图,而不是整图喂
4. **回归测试**:`tests/` 目前只有 3 张 golden 快照,没有 pytest 风格的单元测试覆盖识别阈值 / 解析容错 / 防卡死触发条件。每次调阈值都是裸奔。

## 环境

- Python 3.14, opencv-python-headless, numpy, Pillow
- 雷电模拟器 LDPlayer9 (D:\leidian\LDPlayer9)
- KARDS 安卓版(包名 com.android1939.kardsapk)
- Qwen3.6-35B 推理服务 (http://ai.sunjun3773.top:62222/v1)