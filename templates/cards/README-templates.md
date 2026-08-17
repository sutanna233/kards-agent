# KARDS 简体中文卡面模板库 (card templates, zh-Hans)

本目录为纯 CV 模板匹配用的卡面图片库：每张卡面对应 `cards/cards.json` 里的一个 `id`，
文件名为 `k<国家>-<序号>.png`（如 `kGermany-1.png`），与真实对局画面中的简体中文卡面一致。

## 文件

- `k*.png` — 卡面图（500×702 官方渲染分辨率，Standard card face, **简体中文**）。
- `index.json` — 映射：`id -> {cardId, image, zhTitle, unitType, type, nation, cost, downloaded, ...}`。
- `../README-carddb.md` — 见卡片数据库说明（`cards/`）。

## 数据来源（官方 CDN，zh-Hans）

- 卡牌元数据：KARDS 官方 GraphQL API `https://herokuapi.kards.com/graphql`
  （查询 `cards(language:"zh"...)`，返回 `cardId`、`json.title.zh-Hans`、`image`）。
- 卡面图片：官方 CDN `https://www.kards.com/images/card/v52/zh-Hans/<image>`（AVIF → PNG），
  与游戏内简体中文客户端渲染完全一致（已对照 golden 截图确认语言为简体中文、横屏 1280×720）。

## 生成方式（可复现）

- `scripts/kards_api_fetch_cards.py` — 拉取全部卡牌元数据到 `cards/kards_api_cards.json`（1613 张）。
- `scripts/kards_build_card_templates.py` — 按 `cards.json` 名称匹配 cardId，下载 zh-Hans 卡面并转 PNG，
  写入本目录 + 生成 `index.json`。

## 现状

- 已覆盖 `cards.json` **100 张中的 99 张**（Unit/Order/Countermeasure 全覆盖）。
- 未覆盖：`kSoviet-31`「T-26」——该苏联坦克不在当前 zh-Hans 卡池（v52 卡表，疑似已轮换下架），
  CDN 无对应简体中文卡面，故未渲染占位图（`index.json` 中 `downloaded: false` 并有说明）。

## 用途提示（CV 模板匹配）

- 成局截图（golden）为 **1280×720 横屏**、简体中文；卡面标准布局：
  名称条在卡面**底部**、费用在**左上角**、攻击在**左下角**、防御在**右下角**。
- 在 1280×720 对局中，手牌卡面约缩放到 ~246px 宽，可从本库 500×702 模板按比例缩放后做模板匹配/归一化相关匹配。
