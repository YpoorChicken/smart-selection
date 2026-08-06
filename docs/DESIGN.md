---
version: v1.0
name: Huapu-Zhixuan-Admin
design-read: "像 Shopify Admin 一样熟悉的工作台骨架，像 Jungle Scout 一样密集的数据面——Indigo 主色、表格与图表优先，专为跨境运营团队长时间盯盘与快速决策而设计。"
description: "B2B 跨境运营 SaaS 后台设计系统。参考 Jungle Scout 的数据密度与 Shopify Admin 的侧栏工作台结构——浅色画布、Indigo 主色、表格与图表优先、低装饰高信息量。拨盘：VARIANCE 6 / MOTION 4 / DENSITY 7。"

colors:
  primary: "#4F46E5"
  primary-hover: "#4338CA"
  primary-active: "#3730A3"
  primary-subtle: "#EEF2FF"
  on-primary: "#FFFFFF"
  ink: "#111827"
  ink-secondary: "#374151"
  ink-muted: "#6B7280"
  ink-disabled: "#9CA3AF"
  canvas: "#F3F4F6"
  surface: "#FFFFFF"
  surface-sunken: "#F9FAFB"
  hairline: "#E5E7EB"
  hairline-strong: "#D1D5DB"
  success: "#059669"
  success-bg: "#ECFDF5"
  warning: "#D97706"
  warning-bg: "#FFFBEB"
  danger: "#DC2626"
  danger-bg: "#FEF2F2"
  info: "#2563EB"
  info-bg: "#EFF6FF"
  score-high: "#059669"
  score-mid: "#D97706"
  score-low: "#DC2626"
  amazon: "#FF9900"
  amazon-bg: "#FFF7ED"
  shopee: "#EE4D2D"
  shopee-bg: "#FEF2F2"
  chart-1: "#4F46E5"
  chart-2: "#0EA5E9"
  chart-3: "#059669"
  chart-4: "#F59E0B"
  chart-5: "#EC4899"
  chart-6: "#8B5CF6"
  chart-neutral: "#9CA3AF"
  skeleton: "#E5E7EB"
  skeleton-shine: "#F3F4F6"
  sidebar: "#111827"
  sidebar-hover: "#1F2937"
  sidebar-active: "#312E81"
  sidebar-text: "#D1D5DB"
  sidebar-text-active: "#FFFFFF"
  overlay: "rgba(17, 24, 39, 0.45)"

typography:
  page-title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: 22px
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: -0.2px
  section-title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: 16px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0
  body-strong:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: 14px
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: 0
  caption:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0
  micro:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: 11px
    fontWeight: 500
    lineHeight: 1.3
    letterSpacing: 0.2px
  metric:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: 28px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: -0.4px
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace"
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0

rounded:
  none: 0px
  xs: 2px
  sm: 4px
  md: 6px
  lg: 8px
  xl: 12px
  pill: 9999px

spacing:
  0: 0px
  1: 4px
  2: 8px
  3: 12px
  4: 16px
  5: 20px
  6: 24px
  8: 32px
  10: 40px
  12: 48px
  16: 64px

elevation:
  none: "none"
  card: "0 1px 2px rgba(17, 24, 39, 0.06)"
  raised: "0 4px 12px rgba(17, 24, 39, 0.08)"
  drawer: "0 8px 24px rgba(17, 24, 39, 0.12)"
  modal: "0 16px 40px rgba(17, 24, 39, 0.16)"

components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.md}"
    padding: 8px 16px
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: 8px 16px
  button-danger:
    backgroundColor: "{colors.danger}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.md}"
    padding: 8px 16px
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-secondary}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: 8px 12px
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.lg}"
    padding: 16px
  table-header:
    backgroundColor: "{colors.surface-sunken}"
    textColor: "{colors.ink-muted}"
    typography: "{typography.caption}"
    rounded: "{rounded.none}"
    padding: 10px 12px
  tag-neutral:
    backgroundColor: "{colors.surface-sunken}"
    textColor: "{colors.ink-secondary}"
    typography: "{typography.micro}"
    rounded: "{rounded.sm}"
    padding: 2px 8px
  tag-amazon:
    backgroundColor: "{colors.amazon-bg}"
    textColor: "{colors.amazon}"
    typography: "{typography.micro}"
    rounded: "{rounded.sm}"
    padding: 2px 8px
  tag-shopee:
    backgroundColor: "{colors.shopee-bg}"
    textColor: "{colors.shopee}"
    typography: "{typography.micro}"
    rounded: "{rounded.sm}"
    padding: 2px 8px
  alert-banner-danger:
    backgroundColor: "{colors.danger-bg}"
    textColor: "{colors.danger}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: 12px 16px
  drawer:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: 24px
  sidebar:
    backgroundColor: "{colors.sidebar}"
    textColor: "{colors.sidebar-text}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: 12px
---

# 华普智选 — DESIGN.md

> **Design Read：** 像 Shopify Admin 一样熟悉的工作台骨架，像 Jungle Scout 一样密集的数据面——Indigo 主色、表格与图表优先，专为跨境运营团队长时间盯盘与快速决策而设计。

> 产品：华普智选（智能选品与跨境运营中台）  
> 版本：v1.0 | 状态：定稿  
> 形态：Web 运营后台（P1–P8）  
> 对标：Jungle Scout（数据密度 / 选品分析）+ Shopify Admin（侧栏工作台 / 浅色运营面）  
> 拨盘：**VARIANCE 6** · **MOTION 4** · **DENSITY 7**

本文档供 AI Agent / 前端实现读取，保证 8 个业务页面视觉与交互语言一致。与 `docs/PRD.md` 配套使用；关键取舍见 `docs/decisions.md`。

---

## 1. Visual Theme & Atmosphere

### 设计哲学

运营后台不是营销落地页。默认假设用户每天在表格、趋势图、告警列表里工作数小时——**信息优先、装饰克制、决策路径短**。

| 拨盘 | 分值 | 含义 |
|------|------|------|
| VARIANCE | 6 | 允许平台色、评分色、告警色形成中等视觉变化；结构骨架保持统一，避免每页换一套皮肤 |
| MOTION | 4 | 轻量过渡（抽屉滑入、行 hover、骨架 shimmer）；禁止大面积视差、弹跳、装饰性 Lottie |
| DENSITY | 7 | 偏高密度：表格行高紧凑、KPI 卡信息多、筛选条常驻；仍保留 8px 网格呼吸，不做「无边距堆砌」 |

### 关键特征

- **浅色工作区**：页面背景 `{colors.canvas}`，内容落在白色 `{colors.surface}` 卡片/表格上
- **深色侧栏**：固定左侧导航 `{colors.sidebar}`，对标 Shopify Admin，与内容区形成清晰分区
- **Indigo 主色**：`#4F46E5` 只用于主 CTA、选中态、关键链接与图表主系列——不作全页渐变底
- **数据可视化突出**：趋势、四维得分、价格涨跌是一等公民；图表与数字字重高于插画
- **中英文混排友好**：系统字体栈 + 中文黑体回退，表格数字可 mono

### 情绪关键词

专业 · 冷静 · 可扫描 · 可行动（不是「炫酷」「赛博」「温暖生活方式」）

---

## 2. Color Palette & Roles

### 2.1 品牌主色

| Token | Hex | 用途 |
|-------|-----|------|
| `primary` | `#4F46E5` | 主按钮、侧栏选中指示、关键文字链、图表主系列、焦点环 |
| `primary-hover` | `#4338CA` | 主按钮 / 链接 hover |
| `primary-active` | `#3730A3` | 按下态、强选中 |
| `primary-subtle` | `#EEF2FF` | 选中行底、轻量高亮、Tag 的 Indigo 变体底 |
| `on-primary` | `#FFFFFF` | 主色底上的文字与图标 |

**规则：** 主色面积占比宜低。一屏内通常 1 个实心主按钮即可；其余用次要/幽灵按钮。禁止把整块页面背景刷成主色或紫粉渐变。

### 2.2 中性色（结构）

| Token | Hex | 用途 |
|-------|-----|------|
| `ink` | `#111827` | 标题、表格主字段、KPI 数字 |
| `ink-secondary` | `#374151` | 正文、次要标签 |
| `ink-muted` | `#6B7280` | 辅助说明、表头、时间戳、空状态文案 |
| `ink-disabled` | `#9CA3AF` | 禁用文字与图标 |
| `canvas` | `#F3F4F6` | 应用级背景（侧栏右侧主区域） |
| `surface` | `#FFFFFF` | 卡片、表格、抽屉、弹层内容面 |
| `surface-sunken` | `#F9FAFB` | 表头、筛选条、只读区块底 |
| `hairline` | `#E5E7EB` | 默认分割线、卡片描边、表格行线 |
| `hairline-strong` | `#D1D5DB` | 强调分隔、输入框边框 |

### 2.3 语义色

| Token | Hex | 背景 Token | 用途 |
|-------|-----|------------|------|
| `success` | `#059669` | `success-bg` `#ECFDF5` | 采集成功、已接受选品、涨价正向（视业务语境）、成功 Toast |
| `warning` | `#D97706` | `warning-bg` `#FFFBEB` | 库存预警、任务进行中、中等风险、季节性提示 |
| `danger` | `#DC2626` | `danger-bg` `#FEF2F2` | 竞品降价告警、失败任务、拒绝态强调、破坏性操作 |
| `info` | `#2563EB` | `info-bg` `#EFF6FF` | 中性提示、系统说明、非紧急通知 |

语义色用于**状态与反馈**，不替代品牌主色做营销装饰。

### 2.4 评分色阶（选品综合分 / 分项分）

| 区间 | Token | Hex | 用途 |
|------|-------|-----|------|
| ≥ 80 | `score-high` | `#059669` | 高潜力：数字、进度条、得分徽标 |
| 60–79 | `score-mid` | `#D97706` | 中等：观望 / 需人工复核 |
| < 60 | `score-low` | `#DC2626` | 低分：弱推荐或高风险 |

同一色阶可配 12%–16% 透明度浅底，用于表格单元格或徽章，保证文字对比度 ≥ 4.5:1。

### 2.5 平台标签色

| 平台 | 前景 | 背景 | 用途 |
|------|------|------|------|
| Amazon | `amazon` `#FF9900` | `amazon-bg` `#FFF7ED` | 平台 Tag、筛选芯片、看板平台筛选 |
| Shopee | `shopee` `#EE4D2D` | `shopee-bg` `#FEF2F2` | 同上（第二版入口可先占位） |

平台色**仅用于平台识别**，不要拿来当主 CTA 或整卡染色。多平台并列时用小 Tag，不用大色块。

### 2.6 侧栏专用

| Token | Hex | 用途 |
|-------|-----|------|
| `sidebar` | `#111827` | 侧栏背景 |
| `sidebar-hover` | `#1F2937` | 导航项 hover |
| `sidebar-active` | `#312E81` | 当前页背景（Indigo 深调，与主色同源） |
| `sidebar-text` | `#D1D5DB` | 未选中导航文字 |
| `sidebar-text-active` | `#FFFFFF` | 选中导航文字 |
| `overlay` | `rgba(17,24,39,0.45)` | 抽屉 / 模态遮罩 |

---

## 3. Typography Rules

### 3.1 字体栈（系统优先）

```text
-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial,
"Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif
```

等宽（ASIN、任务 ID、原始 JSON 摘要）：

```text
ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace
```

**不引入**展示用衬线、手写体或营销向可变字体。不强制 Inter / Roboto Webfont 加载；系统栈即可。

### 3.2 字号层级

| 角色 | Token | Size | Weight | 使用场景 |
|------|-------|------|--------|----------|
| 页面标题 | `page-title` | 22px | 600 | P1–P8 顶栏标题，如「运营看板」 |
| 区块标题 | `section-title` | 16px | 600 | 卡片标题、抽屉标题、图表模块名 |
| 正文 | `body` | 14px | 400 | 表格单元格、表单、列表主文案 |
| 正文强调 | `body-strong` | 14px | 600 | 按钮、重要字段、商品标题截断行 |
| 辅助 | `caption` | 12px | 400 | 表头、时间、帮助文案、面包屑 |
| 微标 | `micro` | 11px | 500 | Tag、角标、平台徽章 |
| 指标数字 | `metric` | 28px | 600 | KPI 卡主数字（未读告警、选品进度） |
| 等宽 | `mono` | 12px | 400 | ASIN、任务 ID、日志片段 |

### 3.3 排版原则

- 一页一个 `page-title`；不要叠两层巨型标题
- 表格与列表默认 14px；不要为了「好看」放大到 16–18 导致密度塌陷
- 数字右对齐；货币与百分比保持同一列对齐
- 中文避免全大写英文装饰；英文标签可用 Sentence case

---

## 4. Layout Principles

### 4.1 应用壳层

```
┌──────────┬────────────────────────────────────────┐
│ Sidebar  │ Top bar (标题 / 平台筛选 / 全局操作)     │
│ 220px    ├────────────────────────────────────────┤
│ 可折叠   │ Main canvas (#F3F4F6)                   │
│ → 64px   │   └─ Content cards / tables / charts   │
└──────────┴────────────────────────────────────────┘
```

- 侧栏宽：**220px**（折叠 **64px** 仅图标）
- 顶栏高：**56px**
- 主内容区内边距：**24px**（`spacing.6`）；窄屏 **16px**
- 内容最大宽度：不强制居中窄栏；后台默认**拉满可用宽**，表格优先

### 4.2 间距体系（8px 网格）

基准：**8px**。半档 **4px** 仅用于图标与文字间隙、Tag 内边距。

| Token | px | 常用场景 |
|-------|-----|----------|
| `1` | 4 | 图标-文字间隙、Tag padding-y |
| `2` | 8 | 紧凑组件内间距、表格单元格最小间隙 |
| `3` | 12 | 表单控件组、筛选芯片间距 |
| `4` | 16 | 卡片内边距、列表项间距 |
| `5` | 20 | 中等模块间距 |
| `6` | 24 | 页面边距、卡片间距、抽屉 padding |
| `8` | 32 | 大区块分隔 |
| `10` | 40 | 空状态上下留白 |
| `12` | 48 | 罕见大分隔 |
| `16` | 64 | 登录等非主工作台页面 |

**禁止**随意使用 5 / 7 / 13px 等非网格值。

### 4.3 栅格与密度

- KPI 区：桌面 **4 列**，平板 **2 列**，手机 **1 列**（可点击跳转对应页）
- 列表页：上筛选条 + 下表格，筛选条不收入「高级面板」除非字段 > 6
- 详情 / Listing 双栏：桌面左右 1:1；≤768px **上下堆叠**（PRD L-05）
- 行高：表格默认 **40–44px**；紧凑模式可 **36px**

---

## 5. Component Stylings

### 5.1 按钮

| 类型 | 样式 | 使用 |
|------|------|------|
| Primary | 实心 `primary`，白字，圆角 6px，高 32–36px | 接受选品、生成 Listing、保存配置、手动采集 |
| Secondary | 白底 + `hairline-strong` 边框 | 取消、导出、次要操作 |
| Danger | 实心 `danger` 或危险描边 | 删除监控、拒绝（若需强调） |
| Ghost | 透明底，文字 `ink-secondary` | 表格行内操作、「标记已读」 |
| Disabled | 灰底 / 灰字，无 pointer | 老板角色无决策权时的接受/拒绝 |

同一操作区最多 **一个** Primary。拒绝可用 Secondary + 确认；破坏性操作需二次确认。

### 5.2 卡片

- 白底、`hairline` 1px 边框、圆角 **8px**、阴影用 `elevation.card`（轻）
- 结构：标题行（section-title + 可选操作）→ 内容 → 可选页脚链接（「查看全部」）
- KPI 卡：上 caption 指标名 → 中 `metric` 数字 → 下 caption 环比/跳转暗示
- **卡片用于承载可交互或可扫描模块**；不要把每一句话包进卡片

### 5.3 表格

- 表头：`surface-sunken` 底、`caption`、字色 `ink-muted`、字重 500
- 行：白底，底部分割线 `hairline`；hover：`#F9FAFB`
- 选中行 / 未读告警行：左侧 3px `primary` 或 `danger` 指示条 + 浅底
- 固定列：商品标题列可左固定；操作列右固定
- 分页：底栏右对齐，展示总数；单页默认 20/50 行
- 空列不留「——」堆砌；无数据走空状态组件

### 5.4 标签（Tag / Badge）

| 变体 | 样式 | 场景 |
|------|------|------|
| Neutral | 灰底灰字 | 品类、状态「待处理」 |
| Success | 绿系 | 已接受、采集成功 |
| Warning | 琥珀系 | 进行中、中等分 |
| Danger | 红系 | 未读告警、失败、已拒绝（可选） |
| Amazon / Shopee | 平台色 | 平台标识 |
| Score | 按评分色阶 | 综合得分徽章 |

圆角 **4px**（偏方，不走大圆胶囊）。角标数字（导航未读）用 `pill` + `danger`。

### 5.5 抽屉（Drawer）

- 从右侧滑入，宽 **480px**（商品详情 / 推荐详情）；复杂表单可达 **640px**
- 遮罩 `overlay`；内容白底；顶栏标题 + 关闭；底栏主操作固定
- 动画：220–280ms ease-out（MOTION 4，短而克制）
- 用于：商品详情、选品四维拆解、告警详情、采集任务详情——避免再开独立巨型页时优先抽屉

### 5.6 告警横条（Alert Banner）

- 通栏或卡片顶插入，左图标 + 文案 + 右操作（去处理 / 关闭）
- 竞品降价类默认用 **danger** 变体，文案含阈值与商品名
- 页面级告警（如采集大面积失败）置主内容区顶部，不挡侧栏
- 与 Toast 区分：横条可驻留；Toast 自动消失（成功 3s / 错误可手动关）

### 5.7 表单控件

- 高 32–36px，边框 `hairline-strong`，focus 环 `0 0 0 2px primary-subtle` + 边框 `primary`
- 筛选条：横向排列，换行时左对齐，不居中
- 开关 / 阈值输入与文案同一基线

### 5.8 导航

- 侧栏分组：看板 · 选品分析 · 运营执行 · 系统配置（映射 P1–P8）
- 当前项：`sidebar-active` 底 + 白字；未读角标贴在「告警中心」
- 顶栏可放：平台筛选（Amazon / 全部）、全局搜索（Should）、用户角色标识

---

## 6. Data Visualization

### 6.1 ECharts 配色

**系列色（按顺序取用）：**

```
#4F46E5  #0EA5E9  #059669  #F59E0B  #EC4899  #8B5CF6
```

- 坐标轴 / 分割线：`#E5E7EB`
- 轴文字：`#6B7280`，12px
- 提示框：白底、轻阴影、14px 正文
- 面积图：主色 8%–16% 透明填充，避免厚重渐变
- 涨跌：涨 `#059669`，跌 `#DC2626`（竞品价格场景按业务释义）
- 禁用彩虹渐变、3D、花哨纹理；默认 Cartesian + 必要时 Radar（四维得分）

### 6.2 图表场景映射

| 页面 | 图表 | 说明 |
|------|------|------|
| P1 运营看板 | 小型趋势 sparkline / 条形摘要 | 可点击跳转 |
| P3 市场趋势 | 月度价格分布 + 增长率折线/柱 | 配 AI 解读文本块 |
| P4 智能选品 | 雷达图或分组条：四维分项 | 与综合分色阶一致 |
| P5 竞品监控 | 价格变化 % 与箭头 | 阈值告警联动 |
| P2 详情 | 历史价格 / 排名小图 | 存在 ProductHistory 时 |

### 6.3 评分色阶（再次强调）

- **≥ 80** → 绿 `#059669`
- **60–79** → 黄/琥珀 `#D97706`
- **< 60** → 红 `#DC2626`

综合分与分项分使用同一套阈值，避免「综合分绿色但竞争维度红色」时无法解释——分项可独立着色，综合分按总分阈值。

---

## 7. 三态规范

所有列表、图表、详情内容区必须实现三态，禁止空白闪烁或永久 Loading。

### 7.1 Loading — 骨架屏

- 用灰色块 `{colors.skeleton}` + 轻微 shimmer（`skeleton-shine`），**不要**大号居中 Spinner 占满整页
- 结构对齐最终布局：KPI 四卡骨架、表头+行骨架、图表矩形骨架
- 局部刷新（筛选、翻页）可在表格区叠加半透明遮罩 + 小型 spinner，保留表头
- AI 生成（Listing / 趋势解读）：内容区骨架 + 文案「正在生成…」，失败不留残稿（PRD L-04）

### 7.2 空状态

- 居中：简洁线性图标（单色 `ink-disabled`）+ 标题（section-title）+ 一句说明（caption）+ 可选主操作
- 文案示例：
  - 商品：「还没有同步商品。去配置采集任务。」→ 链到 P8
  - 选品：「暂无待处理推荐」
  - 告警：「暂无告警」
- 禁止插画英雄图、禁止表情包、禁止三列营销空状态

### 7.3 错误提示

- 区块级：Alert Banner（danger / warning）+「重试」
- 页面级加载失败：替换主内容区，保留侧栏
- 表单校验：字段下红字 caption，边框 `danger`
- Toast：成功短、错误可驻留；不打断未保存表单
- 采集失败：列表状态列显示「失败」+ 可展开错误摘要（P8）

---

## 8. Depth & Elevation

| Level | Token | 使用 |
|-------|-------|------|
| 0 | 无阴影 + hairline | 表格、默认卡片 |
| 1 | `card` | 悬浮感 KPI / 模块卡 |
| 2 | `raised` | 下拉菜单、日期选择 |
| 3 | `drawer` | 右侧抽屉 |
| 4 | `modal` | 确认框、采纳版本确认 |

阴影低对比、偏冷灰；**禁止**彩色光晕、多层霓虹投影。

---

## 9. Motion

MOTION = 4（克制）：

| 交互 | 时长 | 缓动 |
|------|------|------|
| 按钮 / 行 hover | 120ms | ease |
| 抽屉 / 模态进出 | 240ms | ease-out |
| 折叠侧栏 | 200ms | ease-in-out |
| 骨架 shimmer | 1.2s | linear loop |
| 页面切换 | 可选 150ms fade；可关 | — |

禁止：弹跳 spring 乱入、数字无意义滚动动画（KPI 可静态直出）、图表反复重播动画。

---

## 10. Responsive Behavior

| 断点 | 宽度 | 行为 |
|------|------|------|
| Desktop | ≥ 1200px | 侧栏展开；KPI 4 列；Listing 双栏 |
| Tablet | 768–1199px | 侧栏可折叠；KPI 2 列；表格横向滚动 |
| Mobile | ≤ 767px | 侧栏抽屉化；KPI 1 列；双栏改上下堆叠 |

**375px 必测（PRD）：** P1、P2、P4、P6、P7。要求：无横向撑破、主操作可点、Listing 双栏堆叠完整可读。

触摸目标：可点击热区 ≥ 32px；重要按钮 ≥ 36px。

---

## 11. Do's and Don'ts（反模式清单）

### 必须做

- 保持浅色画布 + 深色侧栏的工作台结构
- 用表格与图表承载密度；文案服务于决策
- 评分、告警、平台用约定色，不另造体系
- 每个数据区块实现 loading / empty / error
- 主按钮克制；角色无权限时禁用并可见

### 禁止（AI 易犯反模式）

| 反模式 | 为什么禁止 |
|--------|------------|
| **AI 紫粉渐变英雄背景**（purple → pink/indigo 大面积渐变） | 营销站套路；破坏 B2B 可信度，且与「主色克制」冲突 |
| **三均等大卡片 Hero**（首屏三列图标+口号） | 运营后台首屏应是 KPI / 待办 / 告警，不是特性卖点 |
| **大圆角玻璃拟态 / 霓虹光晕** | 与 Shopify Admin / Jungle Scout 气质相悖 |
| **装饰性插画占首屏** | 挤占趋势与表格空间 |
| **把平台色当品牌主色** | Amazon 橙 / Shopee 红仅作 Tag |
| **深色内容区 + 浅色侧栏反转**（除非独立主题工程） | MVP 只做一套浅色工作区 |
| **每张卡片一层厚阴影** | 噪音；用 hairline 分区 |
| **全宽营销口号压过数据** | 老板看板也是数据页 |
| **无骨架的空白 Loading** | 造成布局跳动，破坏 <2s 感知 |
| **圆角 999 的大胶囊按钮成排** | 筛选芯片可小圆角；主按钮保持 6px 方圆 |
| **仪表盘贴纸徽章乱飞**（NEW / HOT / AI 闪烁） | 告警用横条与角标即可 |
| **彩虹图例超过 6 系列还继续加色** | 系列过多应聚合或小倍数 |

---

## 12. Page-Level Notes（对接 PRD 八页）

| 页面 | 布局要点 |
|------|----------|
| P1 运营看板 | 顶：平台筛选；上排 KPI 卡（可点）；下：趋势摘要 + 选品进度 + 竞品动态 |
| P2 商品管理 | 筛选条 + 高密度表；详情抽屉或侧页；平台 Tag + 评分 |
| P3 市场趋势 | 左/上：品类与时间；主区图表；侧或下：AI 解读文本卡 |
| P4 智能选品 | 表 + 综合分色阶；行展开/抽屉看四维与雷达；接受/拒绝 Primary+Secondary |
| P5 竞品监控 | 表为主；涨跌色；跳转 P6 |
| P6 告警中心 | 未读强调；danger 横条可作页顶摘要；筛选未读/类型/时间 |
| P7 Listing 优化 | 双栏对比；生成中骨架；采纳确认模态 |
| P8 采集配置 | 表单 + 任务状态表；成功/失败语义色；Shopee 入口可 Disabled +「第二版」Tag |

---

## 13. Agent Prompt Guide

### 快速色板

```
Primary:  #4F46E5
Canvas:   #F3F4F6
Surface:  #FFFFFF
Ink:      #111827
Muted:    #6B7280
Line:     #E5E7EB
Success:  #059669
Warning:  #D97706
Danger:   #DC2626
Amazon:   #FF9900
Shopee:   #EE4D2D
Sidebar:  #111827
```

### 推荐提示词片段

```text
Build a light-theme B2B admin page for 华普智选.
Use a dark sidebar (#111827) + gray canvas (#F3F4F6) + white content cards.
Primary action color #4F46E5. Density high (tables, KPIs, charts).
No purple gradients, no three equal marketing cards, no glassmorphism.
Score colors: ≥80 green #059669, 60–79 amber #D97706, <60 red #DC2626.
Amazon/Shopee as small tags only. Include skeleton/empty/error states.
Motion subtle (≈200ms). 8px spacing grid.
```

### CSS 变量建议

```css
:root {
  --color-primary: #4F46E5;
  --color-canvas: #F3F4F6;
  --color-surface: #FFFFFF;
  --color-ink: #111827;
  --color-muted: #6B7280;
  --color-line: #E5E7EB;
  --color-success: #059669;
  --color-warning: #D97706;
  --color-danger: #DC2626;
  --color-amazon: #FF9900;
  --color-shopee: #EE4D2D;
  --color-sidebar: #111827;
  --radius-md: 6px;
  --radius-lg: 8px;
  --space-2: 8px;
  --space-4: 16px;
  --space-6: 24px;
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial,
    "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
}
```

---

## 14. 验收对照（设计侧）

- [ ] 主色仅为 `#4F46E5` 系列，无大面积紫渐变背景  
- [ ] 语义色与平台 Tag 色用途不串用  
- [ ] 间距可追溯到 8px 网格  
- [ ] 系统字体栈，标题/正文/辅助层级齐全  
- [ ] 卡片 / 表格 / 按钮 / 标签 / 抽屉 / 告警横条样式可复用  
- [ ] ECharts 使用约定系列色；评分三段色阶正确  
- [ ] 列表与 AI 生成区具备骨架 / 空 / 错三态  
- [ ] 反模式清单中的项在实现中未出现  
- [ ] 375px 下 P1/P2/P4/P6/P7 不破版  

---

*与 `docs/PRD.md` 配套：PRD 定义做什么，DESIGN.md 定义长什么样。关键决策见 `docs/decisions.md`。实现时三者同时满足。*
