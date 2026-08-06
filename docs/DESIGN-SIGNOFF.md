# 华普智选 — 设计阶段签收

> 签收范围：`docs/PRD.md` §6「8 页面功能验收表」中的全部 Must  
> 依据：`docs/DESIGN.md`、`docs/FLOWS.md`、`docs/INTERACTION.md`、`docs/COMPONENT-SPEC.md`、`docs/prototypes/`  
> 结论：**有条件签收：11 项 ✅ / 4 项 ⚠️ / 1 项 ❌；❌ 需在补丁对话修复**  
> 状态说明：✅ 已由提示词与至少一张原型覆盖；⚠️ 设计已定义但需运行态验证；❌ 未覆盖

---

## 1. 页面能力映射说明

PRD 使用 P1–P8；最终信息架构使用 A0 + P1–P7。能力没有删除，而是做了以下收敛：

- A0 登录/注册是鉴权入口，不占 PRD 的业务 P1–P8。
- PRD P6「告警中心」并入 `08-inventory` 的「告警记录」Tab。
- PRD P8「数据采集配置」并入 `02-products` 的右侧配置抽屉，不新增侧栏一级页面。
- `08-inventory` 的「库存风险」Tab承接 PRD P1 Should 与模块六库存能力。
- 运营看板以 `/` 为正式首页；`/dashboard` 可重定向到 `/`。

---

## 2. PRD Must 逐项验收

### P1 运营看板 → `07-dashboard`

| Must | 状态 | 原型与提示词证据 | 签收说明 |
|------|------|------------------|----------|
| 品类趋势摘要 | ✅ | `07-dashboard.png`、`07-dashboard.md` | 「品类增长率 Top 6」柱图提供趋势摘要。 |
| 选品进度：待处理 / 已接受 / 已拒绝 | ✅ | `07-dashboard.png`、`07-dashboard.md` | 首张 KPI 明确展示 `12 / 28 / 7` 三状态。 |
| 竞品动态条数 | ✅ | `07-dashboard.png` | 「竞品动态 24」并显示「近 24 小时 5 次变价」。 |
| 未读告警数 | ✅ | `07-dashboard.png` | 「未读告警 3」，与告警记录原型角标一致。 |
| 默认近 7 天 | ✅ | `07-dashboard.png` | 数据概览顶部和折线标题均显示近 7 天。 |
| KPI 可跳对应页面 | ⚠️ | `07-dashboard.md` | 已定义四张卡的目标路由；静态 PNG 无法验证真实点击。开发按 §4 路由表验收。 |

### P2 商品管理 → `02-products`

| Must | 状态 | 原型与提示词证据 | 签收说明 |
|------|------|------------------|----------|
| 标题、价格、评分、销量排名、所属品类、最近同步 | ❌ | `02-products.png`、`02-products-collection.png`、`02-products.md` | 提示词和采集抽屉底层表已定义「所属品类」，但主默认图 `02-products.png` 表头仍缺该列；严格按 Must 判定未闭环。 |
| 关键词搜索、品类筛选 | ✅ | `02-products.png` | 顶部搜索框与左侧品类树均可见。 |
| 分页进入商品详情 | ⚠️ | `02-products.png`、`02-products.md` | 分页和「详情」入口可见；真实路由与数据加载需运行态验证。 |

### P3 市场趋势 → `03-trends`

| Must | 状态 | 原型与提示词证据 | 签收说明 |
|------|------|------------------|----------|
| 按月展示品类价格分布与增长率 | ✅ | `03-trends.png`、`03-trends.md` | 价格区间柱图 + 月度增长折线均可见。 |
| AI 可读趋势解读，增长/萎缩结论可见 | ✅ | `03-trends.png` | AI 卡给出连续增长、集中价格带和行动建议。 |

### P4 智能选品 → `04-selections`

| Must | 状态 | 原型与提示词证据 | 签收说明 |
|------|------|------------------|----------|
| 综合得分及市场需求、竞争强度、利润空间、趋势方向 | ✅ | `04-selections-default.png`、`04-selections-drawer.png` | 圆环综合分与四维条形完整。 |
| 单条接受 / 拒绝 | ✅ | `04-selections-default.png`、`04-selections-drawer.png` | 卡片与抽屉固定操作栏均提供接受/拒绝。 |
| 记录状态、操作人、操作时间 | ✅ | `04-selections-accepted.png` | 已接受列表明确展示状态、操作人和时间。 |
| 决策持久化 | ⚠️ | `04-selections.md` | 已定义确认、记录和刷新保持；需后端与运行态验证。 |

### P5 竞品监控 → `05-competitors`

| Must | 状态 | 原型与提示词证据 | 签收说明 |
|------|------|------------------|----------|
| 已绑定竞品的价格、评分、最近更新时间 | ✅ | `05-competitors-default.png` | 表格字段与示例数据完整。 |
| 为自营关注商品添加竞品 | ✅ | `05-competitors-default.png` | 顶部商品选择器与「添加竞品」可见。 |
| 移除监控竞品 | ⚠️ | `05-competitors-default.png`、`05-competitors.md` | 行内「移除」可见，确认与解绑结果需运行态验证。 |

### P6 告警中心 → `08-inventory`「告警记录」

| Must | 状态 | 原型与提示词证据 | 签收说明 |
|------|------|------------------|----------|
| 告警类型、关联商品/竞品、阈值、触发时间、已读/未读 | ✅ | `08-inventory-alerts.png`、`08-inventory.md` | 告警表列与三类示例完整。 |
| 单条标记已读 | ✅ | `08-inventory-alerts.png` | 未读行提供「标记已读」，已读行呈弱化状态。 |
| 未读数与看板、导航角标一致 | ⚠️ | `07-dashboard.png`、`08-inventory-alerts.png`、`08-inventory.png` | 看板和告警记录态为 `3`；库存默认态侧栏角标仍为 `2`，静态 Mock 未完全一致。 |
| 标记后跨区同步 | ⚠️ | `docs/INTERACTION.md` | 已定义同步规则；需接口和状态管理运行态验证。 |

### P7 Listing 优化 → `06-listing`

| Must | 状态 | 原型与提示词证据 | 签收说明 |
|------|------|------------------|----------|
| 选择目标商品并触发 AI 生成标题、描述、关键词 | ✅ | `06-listing-default.png`、`06-listing.md` | 商品选择器、参数和「生成 AI 优化稿」完整。 |
| 原文 / 优化稿双栏对比 | ✅ | `06-listing-complete.png` | 标题、五点、描述、关键词逐项对齐。 |
| 采纳为新版本 | ✅ | `06-listing-complete.png` | 唯一主操作「采纳为新版本」和版本时间线可见。 |
| 生成与采纳持久化 | ⚠️ | `06-listing.md`、`docs/INTERACTION.md` | Loading、失败不覆盖、采纳确认已定义；需运行态验证。 |

### P8 数据采集配置 → `02-products`「数据采集配置」抽屉

| Must | 状态 | 原型与提示词证据 | 签收说明 |
|------|------|------------------|----------|
| 配置关注品类与采集任务 | ✅ | `02-products-collection.png`、`02-products.md` | 平台、关注品类、频率、触发方式和启用开关完整。 |
| 展示最近采集任务状态 | ✅ | `02-products-collection.png` | 成功、进行中、失败三态同时可见。 |
| 完成率摘要 | ✅ | `02-products-collection.png` | `100% / 68% / 32%` 与进行中进度条可见。 |
| 定时执行和任务持久化 | ⚠️ | `02-products.md` | 设计已覆盖配置和状态；调度器、接口与持久化需开发验证。 |

---

## 3. 最终八张页面原型验收

| 页面 | 状态 | 关键覆盖 |
|------|------|----------|
| `01-login` | ✅ | 登录/注册 Tab、账号密码、登录入口；无 AppShell。 |
| `02-products` | ❌ | 提示词和采集配置态完整，但默认主列表缺「所属品类」列。 |
| `03-trends` | ✅ | 价格分布、月度增长、AI 解读。 |
| `04-selections` | ⚠️ | 核心 Must 已覆盖；抽屉图侧栏导航与定稿 AppShell 不一致，需补丁重出。 |
| `05-competitors` | ✅ | 商品选择、竞品表、添加/移除、涨跌与告警。 |
| `06-listing` | ✅ | 生成前态、完成双栏、关键词 Diff、版本采纳。 |
| `07-dashboard` | ✅ | 四 KPI、完整选品进度、双图、决策摘要。 |
| `08-inventory` | ⚠️ | 功能覆盖完整；默认态侧栏角标 `2` 与告警记录/看板 `3` 不一致。 |

当前有 1 项 ❌：`02-products.png` 默认主列表缺「所属品类」列。⚠️ 同时包含静态图无法证明的运行态行为，以及两处原型一致性问题。

---

## 4. 发现的问题与修改建议

### 4.1 ❌ 必须在补丁对话修复

1. **商品管理默认图缺「所属品类」列**
   - 证据：`02-products.png` 表头只有商品、平台、价格、评分、销量排名、最近同步、操作。
   - 影响：未完整覆盖 PRD P2 第 1 条 Must。
   - 最小补丁：按现有 `02-products.md` 重生成默认态，仅在销量排名前补「所属品类」列；不调整页面结构。

### 4.2 ⚠️ 原型一致性补丁

1. **未读角标不一致**
   - `07-dashboard.png` 与 `08-inventory-alerts.png` 为 `3`，`08-inventory.png` 侧栏为 `2`。
   - 最小补丁：统一侧栏未读角标为 `3`；库存统计「库存告警 2」可保留，因为它是库存风险数量，不等同全部未读告警。
2. **选品分析抽屉壳层漂移**
   - `04-selections-drawer.png` 侧栏出现首页、商品库、供应商管理、订单管理等非定稿导航。
   - 最小补丁：仅复用 `04-selections-default.png` 的 AppShell 重出抽屉态，抽屉内容不改。
3. **全局壳占位图已落后于正式看板**
   - `00-global-shell.png` 的 KPI Mock 与 `07-dashboard.png` 不同。
   - 建议：将其标注为 AppShell 结构参考，不作为业务数据验收图；或在补丁对话同步 Mock。
4. **侧栏宽度在提示词中存在 220px / 240px 两套写法**
   - 定稿以 `COMPONENT-SPEC.md` 的 240px 为准。
   - 建议：后续补丁机械统一提示词，不改变现有布局。

### 4.3 运行态验证项

- KPI 整卡跳转与筛选落地。
- 商品详情加载、竞品移除确认与解绑结果。
- 选品决策、告警已读、Listing 版本、采集任务的持久化及跨页同步。
- 401 single-flight 与安全 `returnUrl`。

---

## 5. 定稿设计决策摘要

### 信息架构

- 首页路由为 `/`；AppShell 内共 7 个一级业务入口。
- 告警中心与库存风险合并为 `/inventory-alerts` 下两个 Tab，未读数共享侧栏角标。
- 数据采集配置作为商品管理抽屉，不增加一级导航。

### 视觉系统

- 240px 深色侧栏 + 56px 白色顶栏 + `#F3F4F6` 画布；内容边距 24px。
- Primary 固定为 Indigo `#4F46E5`；一处操作区只保留一个实心主按钮。
- 告警红、预警橙、正常绿；评分按 ≥80 / 60–79 / <60 三档。
- 卡片 8px、控件 6px、Tag 4px；低阴影、细边框、高数据密度。
- 禁止页面级紫粉渐变、玻璃拟态、霓虹、营销 Hero 与 3D 图表。

### 状态与反馈

- 所有数据区实现 Loading / Empty / Error；局部刷新保留旧数据和结构。
- Drawer 240ms，Dialog 240ms，Alert Banner 160–200ms；支持 Reduced Motion。
- ElMessage 只用于短反馈；删除、拒绝、回滚、覆盖版本使用确认弹窗。
- 表格统一 Hover、选中、语义行和分页；375px 仅表格容器横向滚动。
- 并发 401 使用 single-flight，保存安全 `returnUrl` 后 replace 到登录。

### 开发边界

- 不实现采购下单、物流、财务、供应商管理。
- 静态图中的跨页数量必须由同一数据源派生，不写死多份状态。
- 选品决策、告警已读、Listing 版本和采集任务均以后端持久化结果为准。

---

## 6. 原型图 → Vue 页面文件映射

| 原型 | Vue 文件 | 路由 / 说明 |
|------|----------|-------------|
| `00-global-shell` | `layouts/AppShell.vue` | 已登录全局壳 |
| `01-login` | `views/Login.vue` | `/login`、`/register` 可复用同页 Tab |
| `02-products` | `views/Products.vue` | `/products`；采集配置为子抽屉 |
| `03-trends` | `views/Trends.vue` | `/trends` |
| `04-selections` | `views/Selections.vue` | `/recommendations` |
| `05-competitors` | `views/Competitors.vue` | `/competitors` |
| `06-listing` | `views/Listing.vue` | `/listing` |
| `07-dashboard` | `views/Dashboard.vue` | `/`；`/dashboard` 重定向 |
| `08-inventory` | `views/Inventory.vue` | `/inventory-alerts`；库存风险 / 告警记录 Tab |

建议复用组件：`ScoreRing.vue`、`AlertBanner.vue`、`DataTable.vue`、`StatePanel.vue`、`CollectionConfigDrawer.vue`、`VersionTimeline.vue`、`ListingCompare.vue`。

---

## 7. 签收结论

- PRD P1–P8 共 16 条 Must：11 条 ✅、4 条 ⚠️、1 条 ❌。
- 唯一 ❌ 为商品管理默认图缺「所属品类」列，需在补丁对话最小修复，不要求全面重做。
- 设计阶段按“有条件签收”完成；SDD 可继续，但前端页面视觉验收前必须关闭该 ❌。
- 其余 ⚠️ 分为原型一致性补丁和运行态验证项，按 §4 跟踪。
