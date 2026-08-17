# KARDS 安卓界面入口笔记 (Interface Entry Notes)

> 调研人：researcher (kards-agent)
> 日期：2026-08
> 数据来源：官方 KARDS FAQ (kards.com/faq)、KARDS 官网新闻 (mobile_release)、Fandom Wiki "Game modes" 页面。
> **标注约定**：凡未在真机/模拟器实测获得的确切屏幕坐标、像素布局，一律标 **[待实测]**；仅给出可靠来源得出的结论性内容才不带标注。

---

## 1. 结论速览 (Top-line)

| 项目 | 结论 | 依据 |
|------|------|------|
| 安卓版方向 | **横屏 landscape**（证据充分：Play Store 截图为 16:9 横屏、Steam 1920×1080、战场为多行横向布局） | Play Store + Steam + 布局推断 |
| 常见分辨率 | 设计定位 **16:9 横屏**，PC 端 1920×1080；手机上低端约 1280×720、高端 1920×1080，宽屏机型可能缩放/留边 [模拟器实际分辨率待实测] | Play Store/Steam 截图 |
| 人机 PvE 模式 | **存在**。入口为 **Training (PvE)**（对人 AI 练牌），位于 PLAY 子菜单；另有 **Starter Campaigns** 与 **Theaters of War**（单人战役） | 官方 FAQ |
| 休闲 Casual 模式 | **当前存在**。入口：主菜单 **PLAY** 按钮 → 子菜单选择 **Casual**（无段位压力的休闲 PvP） | 官方 FAQ + Steam 新闻 |
| 天梯 Ranked | 存在。PLAY 子菜单里选 **Ranked**；另有 **Classic**（含 Reserve 全卡池） | 官方 FAQ |
| 竞技场 | 官方名 **Draft**（轮抽），同位于 PLAY 子菜单，与 Ranked/Casual/Classic 平级 | 官方 FAQ |

---

## 2. 安卓/移动端基础事实（官方已确认）

- **发布**：KARDS Mobile 于 **2023-06-06** 在 Google Play / App Store 上线，PC / 移动全平台共用同一账号 (cross-platform)，进度互通。
- **系统要求**：Android **9.0+**（早期发布页写 Android 8，现 FAQ 为 Android 9）／ iOS 15+；推荐 **4GB+ RAM**。
- **包名**：`com.android1939.kards`（Google Play 渠道）。
- **卡牌类型设施**：官方 FAQ 明确将卡牌分为 **unit 单位 / order 指令 / countermeasure 反制措施** 三类 —— 与 `cards/cards.json` 的 `type` 字段对应。

---

## 3. 当前对局模式清单（官方 FAQ，2026 现行版）

以下均出自官方 FAQ "WHAT GAME MODES ARE AVAILABLE IN KARDS?"：

1. **Ranked（天梯）** — 爬天梯进入 "Officer Club"；用自定义套牌实时对战。
2. **Casual（休闲）** — "Test new decks or enjoy relaxed matches without risking your rank"，即不损失段位的休闲 PvP。**确认存在**。
3. **Classic（经典）** — 使用含 Reserve（轮换储备池）在内的全部卡牌对战。
4. **Draft（轮抽/竞技场）** — 随机选牌组牌、与其它玩家竞技、按战绩结算奖励。
5. **Tournament（锦标赛）** — 定期活动：Boot Camp / Blitz / Iron，规则与报名条件各异。
6. **Campaigns (PvE) 单人战役/人机：**
   - **Starter Campaigns（新手战役）** — 解锁各国初始套牌。
   - **Theaters of War（战争剧场）** — 历史单机战役，卡牌随进程演化。
   - **Training (PvE)（训练）** — **对人机 AI 练牌对战** —— 这就是本项目需要的"人机入口"。

---

## 4. 界面入口布局（已确认结构 + 坐标 [待实测]）

> **已确认的导航结构**（官方 Steam 新闻 "What's new on KARDS"）：
> 「PLAY 按钮导航至 Battle / Training / Campaigns 或其它模式；CARDS 按钮进入套牌与卡牌收藏；Top Bar 的 PACKS 按钮打开未开封卡包。」
> 移动版与 PC 使用同一客户端（全平台互通），导航模式一致。**确切像素坐标**仍需真机/模拟器实测替换。

### 4.1 主菜单 (Main Menu)
- 大型 **PLAY（对战）** 主按钮 —— 点按展开对局模式子菜单。
- 顶部栏 (Top Bar)：**PACKS**（卡包）、**CARDS**（卡牌收藏/组卡）。
- 其它入口：**Collection / Deck Builder / Shop / Missions / Progress / Campaigns** 等（相对位置 [待实测]）。

### 4.2 对战模式选单（点 PLAY 后）
模式列表（子菜单项）：
- **Ranked** — 天梯（经验×段位）
- **Casual** — 休闲（无段位压力）
- **Classic** — 经典（含 Reserve 全卡池）
- **Draft** — 轮抽（竞技场）
- **Tournament** — 锦标赛（Boot Camp / Blitz / Iron）
- **Training** — 人机训练（PvE，对人 AI）

### 4.3 单人战役入口
主菜单有独立 **Campaigns** 入口，内含 Starter Campaigns（新手战役）与 Theaters of War（战争剧场）。

### 4.4 战斗界面
- 战场为 4 行（自己支援线 / 自己前线 / 敌方前线 / 敌方支援线）+ 底部宽手牌区 + Kredits 资源条 + HQ，**横屏布局**。


---

## 5. 需要实测确认的清单 (to-verify on emulator)

- [ ] 安卓版**确凿方向**：默认横屏（已由 Play Store/Steam 截图 16:9 支持），确认模拟器为横屏且无需旋转。
- [ ] **常见分辨率与 DPI**（模拟器通常 1280×720 或 1080×1920 横置），以便坐标归一化。
- [ ] 主菜单**各按钮像素坐标**（PLAY、CARDS、PACKS、Campaigns、Shop…）。
- [ ] **PLAY 展开后的模式选单坐标**：Ranked / Casual / Classic / Draft / Tournament / Training 各按钮位置与高亮态。
- [ ] **人机 Training** 具体入口路径与像素坐标。
- [ ] Casual 在当前客户端中的**显示名与实际入口**（是否与 Ranked 并列于同一 Play 子菜单）。
- [ ] 天梯按钮标签（Ranked / 中文客户端可能显示"排位"）。
- [ ] 按钮/卡片元素占屏比例，便于后续视觉-坐标管线使用。

---

## 6. 参考来源

- KARDS 官方 FAQ：https://www.kards.com/faq
- KARDS 官网 "What is KARDS"：https://www.kards.com/what-is-kards
- 官方 Steam 游戏新闻（PLAY 导航/菜单结构）：https://store.steampowered.com/news/app/544810
- KARDS 官网移动版发布公告（俄文镜像）：https://www.kards.com/ru/news/mobile_release
- Steam 商店页（1920×1080 横屏截图）：https://store.steampowered.com/app/544810
- Google Play（16:9 横屏截图，方向证据）：https://play.google.com/store/apps/details?id=com.android1939.kards
- Fandom Wiki（战场布局/历史模式）：https://kards.fandom.com/wiki/Game_modes
