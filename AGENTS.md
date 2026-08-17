# kards-agent 项目级指令

> 持续积累的本地记忆。修改时直接覆盖对应条目，**新学到的知识随手追加**。

## 项目是什么

让 Qwen3.6-35B-A3B（经 sunjun3773 OpenAI 兼容服务）自主打真实 KARDS（二战卡牌）。雷电模拟器 + adb 截图 → CV/多模态识别 → Qwen35B 决策 → adb 触摸注入。

## 关键路径速查

- 决策大脑：`kards_agent/brain.py`（系统提示 + JSON 解析容错）
- 主循环：`kards_agent/loop.py`（防卡死硬保险在这里）
- 整局 runner：`kards_agent/runner.py`
- 入口：`python -m kards_agent.runner 3` 连打 3 局
- 冒烟测试：`python scripts/smoke_adb.py`

## 架构分层（事实，2026-08）

```
adbc (adb 封装) → perceive/keynum/digits (识别) → brain (LLM 决策) → loop/runner (编排)
```

- `adbc.py` — adb 截图/点击/拖拽
- `perceive.py / perceive_full.py / perceive_ocr.py / recognizer.py` — 多模态识别（整图/手牌逐张/OCR）
- `keynum.py` — 关键数字（HQ 血量），特征定位 + 相对偏移 + 放大后多模态读
- `digits.py` — **纯 CV** 数字识别（0-9 模板，HSV 阈值，连通域分离）
- `matcher.py / handloc.py` — 模板匹配（卡图/界面）
- `nav.py` — 界面导航状态机（10 种界面）
- `brain.py` — LLM 决策（BASE_SYSTEM 注入 KARDS 规则，支持卡组专属 skill 注入）
- `engine/state.py + engine/heuristic.py` — 状态模型 + 启发式评估（**已写好但未接入决策环**）
- `loop.py` — 单步循环，三层防卡死（费用不足/动作预算 6/停滞 4 步签名）
- `agent_full.py` — 整合识别→决策→执行的完整 agent
- `runner.py` — 多局连打 + 胜率统计

## 决策质量瓶颈（事实）

1. `attack` 已实现但**硬编码坐标** `(640, 460) → (640, 175)`，没考虑场上单位位置。实战 LLM 几乎不主动触发。
2. `engine/heuristic.py` 写好了但 `loop.step` 没调用，LLM 既理解又评估。
3. 识别精度三层路径已铺好，但 L1 纯 CV 只覆盖费用（`loop._read_fee`），HQ 血量还在走 L2。
4. 没有 pytest 回归测试，`tests/` 只有 3 张 golden 快照。

## 资源/数据

- 卡图：`templates/cards/` 1613 张简体中文（zh-Hans CDN）
- 卡数据：`cards/cards.json` 100 张核心
- 效果库：`kards_agent/card_effects.py`
- 数字模板：`templates/digits/`
- 日志：`logs/results.jsonl`（胜负）+ `logs/loop_*.png`（每步截图）

## 环境事实

- Python 3.14
- adb 默认 serial `127.0.0.1:5555` / `emulator-5554`
- LDPlayer9 路径 `D:\leidian\LDPlayer9`
- KARDS 包名 `com.android1939.kardsapk`
- LLM base `http://ai.sunjun3773.top:62222/v1`，model `Qwen3.6-35B-A3B.gguf`
- API key 在 `C:\Users\User\.dsh\.credentials.yaml`，`brain.py` 和 `keynum.py` 各自从 `SUNJUN3773_API_KEY` 字段读取

## 用户偏好/约定（本项目）

- 中文 commit message
- 工作目录 `J:\dev\测试\233\kards-agent`
- 改阈值/识别参数时一定要跑 `scripts/smoke_adb.py` 再跑 `python -m kards_agent.runner 1`

## 踩过的坑（持续追加）

- **`loop._read_fee` 用了和 `digits.py` 不同的颜色阈值**：费用橙色 `[8,150,150]→[30,255,255]`（HSV），数字模板走的是二值化。要保持两条路径独立，混了会互相干扰。
- **手牌扇形坐标**：`loop._hand_x` 按 `300 + i*620/(n-1)` 算，但步进上限 135。张数变化时仍有偏差，靠 `loop.execute` 的 7 个候选起点 + 费用变化验证兜底。
- **LLM JSON 输出永远不可信**：`brain._parse_json_action` 必须保留截断补齐 + 关键字兜底，删了就崩。
- **HQ 血量坐标是相对偏移**：`keynum.find_hq_hp` 用 HQ 徽章 ORB 定位后再偏移，不要写绝对坐标。