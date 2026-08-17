# KARDS 卡牌数据库 (.json)

- `cards.json` — **主种子**：从 KARDS Fandom Wiki 实时抓取整理的 100 张主流卡牌，覆盖五国（Germany / Soviet / USA / Britain / Japan）。
- `seed/*.json` — 预留的手工种子目录（当网络不可用时的回退；当前 `cards.json` 为实抓数据，无需回退）。
- `raw/*.ps1` + `raw/*.json` — 抓取与解析脚本及原始俄文/英文缓存（用 Fandom MediaWiki API 拉取，见下）。

## cards.json 字段说明 (schema)

每个条目为一个对象：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一 id，形如 `kGermany-1` |
| `name` | string | 卡牌英文名（wiki 标题） |
| `type` | string | `Unit`（单位）/ `Order`（指令）/ `Countermeasure`（反制措施） |
| `unitType` | string? | 当 `type=Unit` 时的子类型：`Infantry`/`Tank`/`Artillery`/`Fighter`/`Bomber` |
| `nation` | string | `Germany` / `Soviet` / `USA` / `Britain` / `Japan` |
| `cost` | int | 费用 (Kredits) |
| `attack` | int | 攻击（Order/Countermeasure 为 0） |
| `defense` | int | 防御（Order/Countermeasure 为 0） |
| `abilities[]` | string[] | 能力关键词（英文 token，见下方映射） |
| `abilityText` | string | 完整技能/效果文本（英文原文） |
| `rarity` | string | 稀有度（Standard/Limited/Special/Elite 等） |
| `set` | string | 所属卡包/扩展（Base/Theaters of War/Legions…） |

## ability 关键词 → 中文映射

| 关键词 (abilities[]) | 中文 | 说明 |
|---------------------|------|------|
| `Blitz` | 闪袭 | 移动到前线后可立即攻击 |
| `Guard` | 守护 | 前线须先结算守护单位 |
| `Smokescreen` | 烟幕 | 不受指向性效果/攻击指定 |
| `Ambush` | 伏击 | 支援线隐蔽 |
| `Fury` | 狂怒 | 攻击后不死亡相关强化（见原文本） |
| `Heavy Armor` | 重装甲 N | 受到的第 N 点伤害减少 |
| `Deployment` | 部署 | 落场时触发 |

> **注意**：`abilities[]` 仅收录结构化的关键词 token；完整含变数的效果见 `abilityText`（英文原文）。决策引擎若要中文展示，请用上表做映射。

## 数据来源与生成方式（可复现）

- 抓取：`J:\dev\测试\233\kards-agent\cards\raw\fetch_cards.ps1` 通过 Fandom MediaWiki API
  (`action=query&generator=categorymembers&gcmtitle=Category:<Nation>_cards&prop=revisions&rvprop=content`)
  拉取 5 国全部卡牌页 wikitext，解析 `{{Infobox card ...}}` 模板字段。
- 实测总量：Britain 123 / Germany 111 / Japan 107 / Soviet Union 129 / USA 103 ≈ 573 页。
- 整理：仅保留合法单位/指令/反制（剔除 HQ/Location、cost≤0、解析残留 `}}` 等脏卡），
  按国家均衡选取 100 张，覆盖早期/中期/后期费用曲线。

## 限制 / 已知说明

- `cards.json` 是从官方 Fandom 数据整理，非游戏内一手数据；个别卡的 `attack` 或 `defense` 可能有 wiki 录入错误，建议在后续对局中抽样复核。
- Soviet 与 Japan 在 KARDS 中**没有独立 Countermeasure 类型**（该机制主要属 Britain/Germany/USA，见 `docs/interface-notes.md`），故这两国无反制卡条目。
- 如需更多卡，可调整 `build_curated.ps1` 的选择参数（每国 unit/order/cm 数量、费用分带）。
