# 华普智选 — 组件规格（COMPONENT-SPEC.md）

> 产品：华普智选（智能选品与跨境运营中台）  
> 版本：v1.1 | 状态：完整规范  
> 配套：`docs/DESIGN.md`（视觉 Token）· `docs/FLOWS.md`（信息架构与路由）· `docs/PRD.md`（能力）  
> 范围：A0、P1–P7 的 AppShell、基础组件、数据展示、反馈浮层与页面专用组件。

---

## AppShell 规格

> Design Read：像 Shopify Admin 一样熟悉的工作台骨架，像 Jungle Scout 一样密集的数据面——Indigo 主色、表格与图表优先，专为跨境运营团队长时间盯盘与快速决策而设计。

AppShell 是已登录态的全局布局壳。除 A0 登录/注册外，P1–P7 均在此壳内渲染。本规格以 `DESIGN.md` 色板与间距为准；侧栏展开宽度按原型阶段定为 **240px**（`DESIGN.md` §4.1 写 220px，实现与稿面统一采用 240px）。

### 1. 整体结构

```
┌────────────────┬────────────────────────────────────────────┐
│                │ TopBar  56px                               │
│   Sidebar      ├────────────────────────────────────────────┤
│   240px        │ Canvas (#F3F4F6)                            │
│   深色固定     │   └─ Content surface / 页面内容             │
│                │       内边距 24px                           │
└────────────────┴────────────────────────────────────────────┘
```

| 区域 | 尺寸 | 背景 Token | 说明 |
|------|------|------------|------|
| Sidebar | 宽 **240px**；折叠 **64px**（仅图标） | `sidebar` `#111827` | 左固定，全视口高，纵向滚动导航 |
| TopBar | 高 **56px**；左起自侧栏右缘拉满 | `surface` `#FFFFFF` | 底部分割线 `hairline` `#E5E7EB` |
| Canvas | 侧栏右侧剩余宽 | `canvas` `#F3F4F6` | 应用级灰底 |
| Content | Canvas 内，默认拉满可用宽 | 页面自管：卡片/表为 `surface` `#FFFFFF` | 内边距 `spacing.6` **24px**；窄屏 16px |

桌面基准画布：**1440×900**（原型图）。断点行为见 `DESIGN.md` §10。

### 2. Sidebar（左侧导航）

#### 2.1 结构自上而下

1. **品牌区**（高约 56px，与顶栏对齐）  
   - 产品名「华普智选」  
   - 字色 `sidebar-text-active` `#FFFFFF`，字重 600，约 16px  
   - 左侧留白 `spacing.4` 16px；底部分割可用 `rgba(255,255,255,0.08)`
2. **导航分组 + 导航项**（主区域）  
   - 分组标签：`caption` 12px / `ink-disabled` 系浅灰（侧栏内用 `#9CA3AF`）  
   - 分组顺序对齐 `FLOWS.md` §3.1：
     - **看板** → 运营看板
     - **选品分析** → 市场趋势、选品推荐
     - **运营执行** → 商品管理、竞品监控、Listing 优化、库存预警
3. **底栏账号快捷区**（可选，贴底）  
   - 「退出登录」幽灵样式；字色 `sidebar-text`  
   - 与顶栏用户菜单二选一为主出口亦可，原型阶段两者都可出现，以顶栏用户区为完整账号入口

#### 2.2 七个导航项（一级可达）

| # | 文案 | 路由 | 分组 | 角标 |
|---|------|------|------|------|
| 1 | 运营看板 | `/`（`/dashboard` 重定向到 `/`） | 看板 | — |
| 2 | 市场趋势 | `/trends` | 选品分析 | — |
| 3 | 选品推荐 | `/recommendations` | 选品分析 | — |
| 4 | 商品管理 | `/products` | 运营执行 | — |
| 5 | 竞品监控 | `/competitors` | 运营执行 | — |
| 6 | Listing 优化 | `/listing` | 运营执行 | — |
| 7 | 库存预警 | `/inventory-alerts` | 运营执行 | 未读数 `●N`（`danger` 底白字 pill） |

每项：左线性图标（16–18px）+ 文案；行高 **40px**；水平 padding **12px**；圆角 `rounded.md` **6px**；项间距 **4px**。

#### 2.3 导航项状态

| 状态 | 背景 | 文字 / 图标 | 附加 |
|------|------|-------------|------|
| 默认 | 透明 | `sidebar-text` `#D1D5DB` | — |
| Hover | `sidebar-hover` `#1F2937` | `sidebar-text-active` `#FFFFFF`（可略提亮） | 过渡 ≈120ms |
| 选中（当前页） | `sidebar-active` `#312E81` | `sidebar-text-active` `#FFFFFF` | 左侧可加 3px `primary` `#4F46E5` 指示条（可选） |
| 禁用 / 角色不可见 | 不渲染该项 | — | 见 `FLOWS.md` §3.2 |

**规则：** 同一时刻仅一项为选中态。折叠为 64px 时只显示图标；Tooltip 出示文案。

### 3. TopBar（顶栏用户区）

高度 **56px**，白底，水平布局：

| 区段 | 对齐 | 内容 |
|------|------|------|
| 左 | 左 | 页面标题（`page-title` 22px / 600 / `ink` `#111827`）；可选面包屑在标题下或主内容顶（`caption` / `ink-muted`） |
| 中（可选） | 左接标题后 | 平台筛选：Amazon / 全部（小 Tag 或 Segmented；Amazon 用平台色 Tag，不作主 CTA） |
| 右 · 用户区 | 右 | 角色标识（如「选品经理」`tag-neutral`）· 用户名/头像占位 · 下拉：个人设置占位 / 退出登录 |

顶栏右侧为**账号与角色的主入口**；不放业务一级导航（一级导航只在侧栏）。

### 4. Content（内容区）

- 外层 Canvas：`#F3F4F6`
- 页面模块落在白色 `surface` 卡片 / 表格上：边框 `hairline`、圆角 `rounded.lg` 8px、阴影 `elevation.card`
- 内边距 24px；模块间距 24px；遵循 8px 网格
- 内容区**不**再铺深色背景；禁止反转侧栏/内容色

### 5. A0 例外（无壳）

登录 / 注册页**不使用** AppShell：无侧栏、无顶栏、无面包屑。全屏 `canvas` 或极浅结构底 + 居中认证卡片。规格详见原型 `01-login`。

### 6. 与设计 Token 对照（摘录）

```
sidebar:              #111827
sidebar-hover:        #1F2937
sidebar-active:       #312E81
sidebar-text:         #D1D5DB
sidebar-text-active:  #FFFFFF
primary:              #4F46E5
canvas:               #F3F4F6
surface:              #FFFFFF
ink:                  #111827
ink-muted:            #6B7280
hairline:             #E5E7EB
danger:               #DC2626   （库存预警未读角标）
spacing:              4 / 8 / 12 / 16 / 24 …
radius:               md 6px · lg 8px
font:                 系统栈 + Noto Sans SC / PingFang SC / Microsoft YaHei
```

### 7. 禁止项（壳层）

- AI 紫粉渐变侧栏或顶栏
- 浅色侧栏 + 深色内容区反转
- 导航项大圆胶囊成排、玻璃拟态、霓虹光晕
- 在顶栏堆砌业务一级菜单或营销 Slogan
- 强制加载 Inter / 展示衬线作壳层字体

### 8. 验收清单（AppShell）

- [ ] 侧栏 240px 深色；折叠 64px 行为可说明
- [ ] 7 个导航项文案与分组与 `FLOWS.md` §3.1 一致
- [ ] 默认 / hover / 选中三态可辨；库存预警支持未读角标
- [ ] 顶栏 56px 含标题区 + 右侧用户/角色区
- [ ] 内容区灰画布 + 白模块，内边距 24px
- [ ] A0 不套壳
- [ ] 色值与间距可追溯 `DESIGN.md`

---

## 评分圆环（Score Ring）

用于 P4 选品卡片的「蓝海指数」与详情摘要。圆环负责快速分层，四维明细仍由相邻进度条承载，不能用圆环替代解释。

### 1. 结构与尺寸

| 属性 | 规格 |
|------|------|
| 默认尺寸 | `88×88px`；紧凑型 `72×72px` |
| 圆弧宽度 | 默认 `8px`；紧凑型 `6px` |
| 轨道 | `hairline` `#E5E7EB` |
| 中心数字 | 28px / 600；颜色跟随评分色阶 |
| 中心标签 | 「蓝海指数」，11px / 500 / `ink-muted` |
| 起点与方向 | 12 点钟起，顺时针；圆头端点 |
| 动画 | 首次加载 240ms ease-out；减少动态偏好下直接显示终态 |

### 2. 色阶与文案

- `80–100`：`score-high` `#059669`，高潜力。
- `60–79`：`score-mid` `#D97706`，建议复核。
- `0–59`：`score-low` `#DC2626`，风险较高。
- 分数必须同时显示数字，不能仅靠颜色表达；对外输入先钳制到 `0–100`。
- 数据缺失显示灰色空轨道与中心 `—`，附可访问名称「蓝海指数暂无数据」，不显示 0 分。

### 3. 可访问与使用约束

- 组件语义为图形化指标，`aria-label` 示例：「蓝海指数 86 分，高潜力」。
- 圆环和背景对比不足时，以中心数字和相邻文案保证信息可读；不可使用红绿渐变。
- 卡片中每个推荐仅出现一个主圆环；四维分项使用线性进度条，不叠四个小圆环。
- 禁止 3D、发光、仪表盘刻度、速度表指针和彩虹色阶。

---

## 告警横条（Alert Banner）

用于 P5 竞品监控与 P7 库存预警的可驻留反馈。它不是自动消失的 Toast，也不阻断用户查看表格。

### 1. 结构与布局

```
┌────┬──────┬──────────────────────────────┬──────────────┬───┐
│色条│ 图标 │ 主文案 + 辅助信息             │ 次操作 / 主操作 │关闭│
└────┴──────┴──────────────────────────────┴──────────────┴───┘
```

| 属性 | 规格 |
|------|------|
| 最小高度 | 单行 `48px`；双行 `64px` |
| 内边距 | `12px 16px`；元素间距 8–12px |
| 圆角 / 边框 | 6px；1px 同语义浅边框；左侧 4px 强调色条 |
| 图标 | 16–20px 线性图标，使用对应 severity 前景色 |
| 主文案 | 14px / 600，包含对象、变化值、阈值 |
| 辅助文案 | 12px / 400 / `ink-muted`，包含前后值、时间、关联商品 |
| 操作 | 右对齐；最多两个文字/按钮操作 + 关闭图标 |
| 动画 | 插入/展开 160–200ms ease-out；关闭后保持状态，不重复闪现 |

### 2. Severity 变体

| Severity | 前景 / 色条 | 背景 | 用途 |
|----------|-------------|------|------|
| `high` | `danger` `#DC2626` | `danger-bg` `#FEF2F2` | 降价超过阈值、需立即处理 |
| `medium` | `warning` `#D97706` | `warning-bg` `#FFFBEB` | 接近阈值、需要关注 |
| `low` | `ink-muted` `#6B7280` | `surface-sunken` `#F9FAFB` | 低优先级变化、记录性提醒 |

### 3. 状态与行为

- 未读：保留色条与语义浅底，关联表格行同步使用同 severity 左侧指示条。
- 已读：背景降为白色或 `surface-sunken`，保留文字与时间，不再使用强底色。
- 「查看告警」定位 P7 对应记录；「标记已读」立即更新横条、行和导航未读数。
- 关闭仅隐藏当前横条，不等同标记已读；必须保留从告警中心重新查看的入口。
- 多条同时触发时默认只展示最高 severity 的最新一条，并提供「另有 N 条」入口，禁止堆叠占满首屏。
- 文案不得只写「发生异常」；必须包含竞品、涨跌幅、阈值和触发时间。

### 4. 响应式与可访问

- 桌面横向排列；≤768px 时操作区换到下一行，关闭按钮仍位于右上，主文案不可横向溢出。
- `high` 使用 `role="alert"`；`medium/low` 使用 `role="status"`，避免重复播报。
- 图标不单独承担 severity 含义；文案必须出现「高风险 / 中风险 / 低风险」之一。

---

## 基础控件

### 1. Button

| 变体 | 背景 / 边框 | 文字 | 使用 |
|------|-------------|------|------|
| Primary | `primary #4F46E5` | 白色，14px/600 | 页面或操作区唯一主操作 |
| Secondary | 白底 + `hairline-strong` | `ink` | 取消、导出、次操作 |
| Ghost | 透明 | `ink-secondary` | 行内查看、关闭、弱操作 |
| Danger | `danger` 实底或危险描边 | 白色或 `danger` | 确认删除、不可逆操作 |
| Disabled | `surface-sunken` | `ink-disabled` | 无权限或条件未满足 |

- 默认高度 36px，紧凑表格操作 32px；水平内边距 16px，图标按钮宽高相等。
- 圆角 6px；图标与文字间距 8px；触摸热区不小于 36×36px。
- Hover 使用对应 hover 色；Active 使用 `primary-active`；Focus 为 2px `primary-subtle` 外环。
- Loading 时保留原宽度，显示 14px Spinner 与进行中文案并禁用。
- 同一操作区最多一个 Primary；纯图标按钮必须有 Tooltip 与 `aria-label`。

### 2. Input / Select / Search

- 默认高度 36px，表格紧凑筛选可用 32px；圆角 6px。
- 边框 `hairline-strong #D1D5DB`；Hover 加深边框；Focus 为 `primary` 边框 + 2px `primary-subtle` 环。
- 标签 14px/500，辅助和错误 12px；错误态边框与文字使用 `danger`。
- Placeholder 使用 `ink-disabled`，不能替代字段标签。
- 搜索框左侧 16px 搜索图标，清除按钮仅在有值时出现；建议 300ms debounce。
- Select 菜单最大高 320px，选中项使用 `primary-subtle`；长选项省略并提供 Tooltip。

### 3. Checkbox / Radio / Switch

- 控件本体 16–20px，标签热区整体可点击且至少 32px 高。
- 选中使用 `primary`；错误或危险不改变控件选中色，只在说明文本表达。
- Switch 只用于立即生效的二元设置；需要保存的设置使用 Checkbox / Radio + 保存按钮。

### 4. Tabs

- 高度 40px；标签间距 24px；正文 14px/500。
- 选中态 `primary` 文字 + 底部 2px 指示线，未选中 `ink-muted`。
- 数量使用文本或小型 Neutral Badge，不使用大胶囊。
- 切换 Tab 更新 URL query；内容局部 loading，不重载 AppShell。

---

## 数据容器

### 1. Card

- 白底、1px `hairline`、8px 圆角、`elevation.card`；默认内边距 16px，图表或重要模块可用 20–24px。
- 标题区：16px/600 标题 + 可选 12px 副标题 + 右侧弱操作。
- 卡片之间默认 24px；禁止每层容器重复套卡片造成多重边框。
- 可点击卡整体支持 Hover 和键盘 Focus，不只让右上角箭头可点。

### 2. KPI Card

- 结构为指标名 → 28–32px/600 数字 → 12px 环比 / 状态。
- P1 首页版本左侧使用 4px `primary` 色条；四张卡色条统一，不用四种大色块。
- 语义色只用于环比、风险数字和小标签；数字默认 `ink`。
- Loading 骨架保持数字与辅助行位置；点击跳转时整卡热区可用。

### 3. Statistics Bar

用于 P7 库存预警页顶部的总数 / 告警 / 预警汇总。

- 单张白色横向容器，三项等宽；桌面项间使用 1px `hairline` 竖分割。
- 高度 88–104px，内边距 16–24px；数字 28px/600，标签 12px。
- 总数用 `ink`，告警数字用 `danger`，预警数字用 `warning`；不把整块背景染色。
- ≤767px 改为纵向三行，分割线改为水平；每行最小高 64px。

### 4. Toolbar / Filter Bar

- 白底卡片或卡片内 `surface-sunken` 区，控件横向左对齐，间距 12px。
- 右侧放更新时间、导出或唯一主操作；空间不足时先让筛选换行，不压缩控件文字。
- 字段超过 6 个可将低频项收入「更多筛选」，但当前生效条件必须以可移除标签展示。

---

## Table 与 Pagination

### 1. Table

| 属性 | 规格 |
|------|------|
| 表头 | `surface-sunken`，12px/500，`ink-muted`，高 40px |
| 默认行 | 白底，高 40–52px，底部 1px `hairline` |
| Hover | `#F9FAFB`，120ms |
| 选中行 | `primary-subtle` + 左侧 3px `primary` |
| 数字列 | 右对齐，必要时使用 mono |
| 操作列 | 桌面右固定；1–3 个 Ghost / 文字操作 |

- 表格外层 8px 圆角并裁切表头；横向滚动时固定列使用轻冷灰阴影。
- 主字段可由缩略图 + 标题 + 次字段构成；缩略图默认 40×40px、圆角 4px。
- 排序图标与表头文字间距 4px；当前排序方向必须可见。
- 缺失单值使用 `—`；不允许整行连续破折号。

### 2. Inventory Row

| 状态 | 行背景 | 左侧条 | 标签 |
|------|--------|--------|------|
| 告警 | `danger-bg #FEF2F2` | 3px `danger` | 红底红字「告警」 |
| 预警 | `warning-bg #FFFBEB` | 3px `warning` | 橙底橙字「预警」 |
| 正常 | 白色 | 无 | 绿底绿字「正常」 |

- Hover 只轻微加深原语义浅底，不覆盖状态。
- 预计可售天数跟随状态色并加粗；库存数、日均销量与安全库存仍使用中性色。
- 背景色之外必须保留状态文字与图标 / 色条，满足非颜色识别。

### 3. Pagination

- 默认每页 20 条，可选 20 / 50；显示总数、每页数量、当前页与总页数。
- 桌面位于表格底栏右侧；移动端放到横向滚动容器外并分两行。
- 页码按钮 32×32px；当前页使用 `primary-subtle` + `primary` 文字，不用实心大色块。
- 数据刷新失败时保留当前页，不静默跳回第 1 页。

---

## Tag / Badge / Status

| 类型 | 前景 | 背景 | 示例 |
|------|------|------|------|
| Neutral | `ink-secondary` | `surface-sunken` | 品类、待处理 |
| Success | `success` | `success-bg` | 正常、已接受、新增词 |
| Warning | `warning` | `warning-bg` | 预警、中等分 |
| Danger | `danger` | `danger-bg` | 告警、失败、High |
| Primary | `primary` | `primary-subtle` | 当前版本、选中上下文 |
| Amazon | `amazon` | `amazon-bg` | Amazon |
| Shopee | `shopee` | `shopee-bg` | Shopee |

- 高 20–24px，水平内边距 8px，圆角 4px，11–12px/500。
- Badge 数字可用 pill；业务状态 Tag 保持偏方，不做胶囊墙。
- 标签必须有文字；不能只显示无说明色点。
- Listing 删除关键词使用 `danger` 文字 + 删除线 +「删除」，新增关键词使用 Success +「新增」。

---

## Progress / Chart / Diff

### 1. Linear Progress

- 默认轨道高 6px、圆角 3px、背景 `hairline`；紧凑表格可用 4px。
- 分数进度按 score 色阶；任务进度默认 `primary`；失败不把剩余轨道全部染红。
- 百分比放在轨道右侧并使用数字文本，不能只靠长度表达。

### 2. Chart Container

- 白色 Card，标题 16px/600，图例与筛选在右上；图表区桌面最小高 240px。
- 轴线、网格 `hairline`；轴文字 12px `ink-muted`；Tooltip 白底 + `raised` 阴影。
- 系列按 `chart-1` 至 `chart-6`；涨跌场景用 success / danger。
- 禁止 3D、彩虹渐变、纹理、发光和超过 16% 的厚面积填充。

### 3. Listing Compare

- 桌面双栏严格 1:1，中间 1px 分割；字段顺序固定为标题、5 点卖点、描述、关键词。
- 左栏「原版」使用 Neutral Tag；右栏「AI 优化版」只允许标签使用 `primary → primary-hover` 小面积渐变。
- 同一字段左右块高一致；5 条卖点序号逐项对齐。
- AI loading 保留字段结构骨架；成功前不得覆盖原版。
- ≤767px 上下堆叠，原版在前；字段标题重复显示，避免失去对照语义。

### 4. Version Timeline

- 水平时间线用于桌面，节点 12px；历史灰、当前实心 Primary、草稿空心 Primary。
- 节点下显示版本、时间、操作人；连线 1px `hairline-strong`。
- 移动端改垂直时间线；当前版本同时有文字「当前」，不只靠颜色。

---

## 浮层与反馈组件

### 1. Drawer

- 宽 480px；复杂内容 640px；移动端 `100vw`。
- 白底、`elevation.drawer`；头部和底部操作栏固定，正文独立滚动，内边距 24px。
- 顶部标题 16px/600 + 关闭按钮；底栏右对齐，最多一个 Primary。
- 遮罩 `overlay rgba(17,24,39,.45)`；动效与焦点行为见 `INTERACTION.md` §4。

### 2. Dialog

- 默认宽 420–560px，圆角 8px，`elevation.modal`；视口左右至少 16px。
- 结构为标题、正文、底栏；正文最大高 `calc(100vh - 160px)` 并可滚动。
- 确认弹窗默认焦点在安全操作；危险确认使用 Danger。
- 复杂详情或长表单不使用超宽 Dialog，改用 Drawer。

### 3. ElMessage

- 顶部居中，最宽 420px；图标 + 一行文案 + 可选关闭。
- Success / Info 默认 3s，Warning 4s，Error 至少 5s 或手动关闭。
- 同类消息 grouping，最多同时 3 条；不能替代字段错误或页面错误。

### 4. Skeleton / Empty / Error

- Skeleton 使用 `#E5E7EB`，圆角 4px；按最终结构占位，不使用整页 Spinner。
- Empty 使用单色线性图标（48px 以内）、16px 标题、12px 说明和最多一个 Primary。
- Error Alert 使用语义浅底、图标、错误摘要和「重试」；保留容器尺寸与可用旧数据。

---

## 页面专用组合

### 1. Dashboard Composition

- 顶部 4 列 KPI，中部 1:1 双图表，底部决策摘要三栏；模块间距 24px。
- 蓝海卡只用 `primary-subtle` 内层或 2px 顶边高亮，不使用整卡渐变。
- AI 一句话摘要允许标题前单个 `✨`，不使用闪烁动画或大 AI 徽章。

### 2. Selection Card

- 桌面三列；白底细边、8px 圆角、16px 内边距。
- 左侧 Score Ring，右侧四维 Linear Progress；底部风险 Tag 与决策操作。
- 每卡只有一个 Primary「接受」；「查看 AI 分析」与「拒绝」使用弱操作。

### 3. Competitor Monitor

- 商品选择器位于页顶；表格为主；价格折线位于下方。
- 涨价 `▲ +N%` 使用 success，降价 `▼ -N%` 使用 danger，持平 `— 0.0%` 使用 muted。
- Severity：High 红、Medium 橙、Low 灰；告警横条与关联行状态同步。

### 4. Inventory Alert

- 页顶使用 Statistics Bar；下接筛选工具条与 Inventory Table。
- 阈值文案必须可见：「告警 ≤3 天 · 预警 ≤14 天」。
- 页面仅提供查看、标记处理与阈值设置；不包含采购下单、物流或供应商动作。

---

## 响应式与可访问性

### 1. 断点

- `≥1200px`：侧栏 240px 展开，KPI 4 列，复杂页面双栏。
- `768–1199px`：侧栏可折叠 64px，KPI 2 列，表格横向滚动。
- `≤767px`：侧栏覆盖抽屉，内容边距 16px，卡片单列，浮层全宽或保留 16px 边距。

### 2. 375px 表格

- 表格自身容器 `overflow-x: auto`，业务最小宽 760–960px；body 不横向滚动。
- 第一主字段列 sticky left；必要时操作列 sticky right。
- 状态色条位于 sticky 主字段列；分页置于滚动容器外。

### 3. 可访问性

- 正文与背景对比度至少 4.5:1；大数字与图标至少 3:1。
- 所有交互支持键盘；Focus 可见且不被 `overflow` 裁切。
- Icon-only Button、图表、Score Ring 提供 `aria-label`；装饰图标 `aria-hidden="true"`。
- Dialog / Drawer 使用正确角色、焦点锁定和关闭后焦点恢复。
- 状态、涨跌、分数、库存风险不能只靠颜色表达。
- 动画遵循 `prefers-reduced-motion`。

---

## 组件验收清单

- [ ] AppShell、按钮、表单、Tabs、卡片、统计条、表格与分页规格完整
- [ ] Score Ring、告警横条、Listing Diff、版本时间线与库存行可复用
- [ ] 语义色、平台色和评分色不串用
- [ ] Loading / Empty / Error 均有组件级结构
- [ ] Drawer / Dialog / Message 与 `INTERACTION.md` 行为一致
- [ ] 375px 下无 body 横向溢出，表格可独立横向滚动
- [ ] 键盘、焦点、ARIA、非颜色表达与减少动态均有实现

---

*组件视觉 Token 以 `docs/DESIGN.md` 为准；状态流转和动效以 `docs/INTERACTION.md` 为准。*
