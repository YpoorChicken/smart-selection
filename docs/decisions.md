# 设计决策记录（Design Decisions）

> 产品：华普智选（智能选品与跨境运营中台）  
> 关联：`docs/PRD.md` · `docs/DESIGN.md`  
> 用途：记录 DESIGN.md 定稿时的关键取舍，供评审与后续迭代追溯。

---

## DD-001 · Design Read（设计定位）

**决策：**  
像 Shopify Admin 一样熟悉的工作台骨架，像 Jungle Scout 一样密集的数据面——Indigo 主色、表格与图表优先，专为跨境运营团队长时间盯盘与快速决策而设计。

**理由：**  
目标用户每天长时间盯数据（PRD：运营 / 选品经理 / 运营主管 / 老板）。定位必须是「可扫描的运营工作台」，不是营销落地页或消费级仪表盘。

**状态：** 已采纳（DESIGN.md v1.0）

---

## DD-002 · 对标与壳层结构

**决策：**  
- 壳层对标 **Shopify Admin**：深色侧栏 + 浅灰画布 + 白色内容面  
- 数据面密度对标 **Jungle Scout**：表格、评分、趋势图优先于插画与口号

**理由：**  
跨境卖家对这两类产品已有肌肉记忆；降低学习成本，并把首屏面积留给 KPI / 待办 / 告警。

**状态：** 已采纳

---

## DD-003 · 拨盘设定

| 拨盘 | 分值 | 决策含义 |
|------|------|----------|
| VARIANCE | **6** | 允许平台色、评分色、告警色形成中等变化；页面骨架统一，不每页换皮 |
| MOTION | **4** | 仅抽屉/hover/骨架 shimmer 等轻量动效；禁止装饰性大动效 |
| DENSITY | **7** | 偏高密度（表行 40–44px、筛选常驻）；仍遵守 8px 网格呼吸 |

**理由：**  
与「长时间盯盘」匹配：信息多但不过度花哨；动效服务状态反馈而非氛围。

**状态：** 已采纳（任务硬约束）

---

## DD-004 · 主色选用 Indigo `#4F46E5`

**决策：**  
品牌主色固定为 `#4F46E5`（及 hover/active/subtle 系列），仅用于主 CTA、选中态、焦点环、图表主系列。

**明确不做：**  
- 不做全页紫粉 / Indigo 渐变背景  
- 不把主色当大面积画布染色  

**理由：**  
任务指定主色；同时规避 AI 常见「紫渐变 SaaS」反模式——主色作**点缀行动色**，画布保持中性灰白，可信度与可读性更高。

**状态：** 已采纳

---

## DD-005 · 语义色与平台色分离

**决策：**  
- 语义色：成功 `#059669` / 警告 `#D97706` / 危险 `#DC2626`（另附 info）  
- 平台 Tag：Amazon `#FF9900` / Shopee `#EE4D2D`（仅小标签）  
- 评分色阶复用语义绿/琥珀/红：≥80 / 60–79 / <60  

**理由：**  
状态反馈与平台识别职责不同；混用会导致「降价告警」与「Shopee 标签」抢同一红色语义。评分色阶与告警语义对齐，降低认知切换成本。

**状态：** 已采纳

---

## DD-006 · 8px 间距 + 系统字体 + 克制圆角阴影

**决策：**  
- 间距基准 8px（半档 4px 仅用于图标间隙 / Tag）  
- 字体：系统栈 + 中文黑体回退；等宽用于 ASIN / 任务 ID  
- 圆角：控件 6px、卡片 8px；Tag 偏方（4px），角标才用 pill  
- 阴影：4 级冷灰 elevation，默认卡片以 hairline 为主  

**理由：**  
对齐 Shopify Admin 工程感；高密度后台不适合大圆角玻璃拟态与厚投影。系统字体免 webfont 阻塞，利于 PRD「核心区域 <2s」感知。

**状态：** 已采纳

---

## DD-007 · 组件优先级：表 > 卡 > 装饰

**决策：**  
核心组件规范锁定为：卡片、表格、标签、按钮、抽屉、告警横条。列表页默认「筛选条 + 表格」；详情优先右侧抽屉（480/640px），避免无谓新开巨型页。

**理由：**  
PRD 八页以列表、监控、告警、配置为主；抽屉缩短「扫一眼 → 决策」路径（接受/拒绝、标记已读、查看四维分）。

**状态：** 已采纳

---

## DD-008 · 可视化与评分色阶

**决策：**  
- ECharts 系列色：`#4F46E5 #0EA5E9 #059669 #F59E0B #EC4899 #8B5CF6`（最多 6 系列）  
- 评分：≥80 绿 / 60–79 琥珀 / <60 红  
- 默认 Cartesian；四维得分可用 Radar  

**理由：**  
与选品引擎四维打分、趋势分析、竞品涨跌直接对应；限制系列数防止彩虹图例噪音。

**状态：** 已采纳

---

## DD-009 · 三态强制

**决策：**  
所有列表、图表、AI 生成区必须实现：骨架屏 Loading / 空状态 / 错误提示。禁止整页大 Spinner、禁止空白闪烁、禁止 AI 失败残留残稿。

**理由：**  
对齐 PRD 非功能（加载感知、<2s）与 L-04（生成失败不展示残缺优化稿）。

**状态：** 已采纳

---

## DD-010 · 反模式清单作为验收项

**决策：**  
将「AI 紫渐变英雄背景」「三均等营销大卡片」「玻璃拟态/霓虹光晕」「平台色当主 CTA」等写入 DESIGN.md 反模式，并纳入设计侧验收勾选。

**理由：**  
Agent / 低代码生成 UI 最易落入营销站套路；用否定清单比仅给 token 更能守住 B2B 气质。

**状态：** 已采纳

---

## DD-011 · 浅色工作区唯一主题（MVP）

**决策：**  
MVP 只交付浅色内容区 + 深色侧栏；不做深色内容主题、不做营销夜间画布。

**理由：**  
表格与长时阅读在浅底上对比度与打印/导出更稳；双主题会稀释排期且易与侧栏分区逻辑冲突。

**状态：** 已采纳（后续主题另开决策）

---

## DD-012 · 响应式底线

**决策：**  
375px 必测 P1 / P2 / P4 / P6 / P7；Listing 双栏改为上下堆叠；侧栏在窄屏抽屉化。

**理由：**  
直接承接 PRD §8 / L-05；设计系统不另造断点哲学。

**状态：** 已采纳

---

## DD-014 · 选品四维权重调整为 30/20/25/25

**决策：**  
`SelectionScorer` 综合分权重采用：市场需求 30%、竞争强度 20%、利润空间 25%、趋势方向 25%（覆盖原 SDD 等权 0.25）。由 `POST /recommendations/generate` 触发批量打分。

**理由：**  
市场需求对蓝海判断更前置；竞争维度以「机会分」表达，权重略降避免与需求信号重复放大。

**状态：** 已采纳（2026-08-08，已回写 `docs/SDD.md` §4.7）

---

## DD-013 · 选品推荐与决策共用 `recommendations` 单表

**决策：**  
不拆分 `product_recommendations` 与 `selection_decisions` 两张表；严格按 SDD §1.2.8 使用单表 `recommendations`。打分字段（`score_*` / `ai_blue_ocean_text`）与决策字段（`status` / `decided_by` / `decided_at` / `reject_reason` / `note`）同存一行。ORM 类名 `Recommendation`，并以别名 `ProductRecommendation` / `SelectionDecision` 兼容业务用语。

**理由：**  
SDD 状态机与接受/拒绝事务均围绕单行 `UPDATE`；拆表会引入 1:1 同步与多余 JOIN，且无文档依据。

**状态：** 已采纳（2026-08-08）

---

## DD-015 · AI 选品深度分析落库 `recommendations.reason`

**决策：**  
新增 `POST /recommendations/{id}/ai-analysis`；LLM 输出四段结构（市场机会 / Top5 竞品差异化 / 入局建议 / 风险），JSON 写入 `reason`，可读摘要同步 `ai_blue_ocean_text`。无独立卖家字段时以评论量 Top 商品代理竞品代表。

**理由：**  
任务用语 `ProductRecommendation.reason` 与蓝海列表响应里的规则化 `reason` 区分：前者为持久化深度分析；列表接口 `reason` 仍为规则文案。`ai_blue_ocean_text` 保留给抽屉短文展示。

**状态：** 已采纳（2026-08-08，已回写 `docs/SDD.md` §1.2.8 / §3.3 / §4.7）

---

## DD-016 · 日批选品扫描用 Redis + ARQ，跳过阈值 20%

**决策：**  
全品类扫描 `scan_all_categories` 由 ARQ Cron 每天 03:30（Asia/Shanghai）执行；手动 `POST /recommendations/scan` 默认入队同一任务。已有推荐且综合分相对变化 ≤ 20% 跳过；新创建推荐走 `WebhookNotifier` 预留回调（无 URL 则 no-op）。

**理由：**  
与 CLAUDE 技术栈「Redis + ARQ」一致；跳过阈值避免日批噪声；webhook 先预留契约便于后续对接企业微信/飞书。

**状态：** 已采纳（2026-08-08，已回写 `docs/SDD.md` §3.3 / §5.3）

---

## DD-017 · 竞品监控按 SDD 拆五表，快照用 BIGSERIAL

**决策：**  
模块四模型严格按 SDD：`watched_products`（目标商品选择器）、`competitor_bindings`（软删 + 活跃对部分唯一索引）、`competitor_snapshots`（BIGSERIAL 时序）、`alerts`（含 binding/阈值/触发值字段）、`system_settings`（降价阈值 KV）。不合并告警进绑定表；不自建 `payload` JSON 替代 SDD 列。

**理由：**  
与采集调度、未读角标、看板 KPI 共用同一 `alerts` 表；时序快照高写入用自增整型 PK；部分唯一索引支持软删后重新绑定。

**状态：** 已采纳（2026-08-08）

---

## DD-018 · 竞品发现：同品类检索 + AI 挑选，失败回落启发式

**决策：**  
`GET /competitors/discover`（Could）在同品类候选池上用 LLM 按 `candidate_index` 挑选并自动创建 `competitor_bindings` + 首条快照；LLM 失败或关闭时用标题重合/价格接近/评论量启发式。`POST /competitors/batch-update` 与单条 `refresh` 拉取数据源详情（失败回落本地价）写 `competitor_snapshots`，并按 `alert.price_drop_threshold`（默认 5%）评估降价告警。

**理由：**  
候选序号约束避免模型编造 UUID；自动建绑定满足「发现即监控」；快照与告警路径对齐 SDD §4.3，供小时 Worker 复用同一服务方法。

**状态：** 已采纳（2026-08-08，已回写 `docs/SDD.md` §3.4）

---

## DD-019 · 告警 severity 保留 info/warning/critical，业务 low/medium/high 映射

**决策：**  
库内 `AlertSeverity` 仍为 `info|warning|critical`（对齐既有 SDD）；业务规则口语 low/medium/high 分别映射。新增类型 `competitor_rating_drop`、`competitor_discovered`。降价：超 5%→warning、超 10%→critical；评分降超 0.5→warning；Top10 新发现→info。API 增补 `GET /alerts/stats`、`POST /alerts/check`（SDD 原缺省先回写再实现）。

**理由：**  
避免破坏已建表与附录枚举；映射关系写进 SDD 便于前后端统一展示文案。

**状态：** 已采纳（2026-08-08，已回写 `docs/SDD.md` §1.2.11 / §3.4 / §4.3 / 附录 A）

---

## DD-020 · 竞品分析报告对比集优先活跃绑定

**决策：**  
`GET /competitors/{product_id}/report` 对比集 = 自身 + 活跃 `competitor_bindings`；无绑定时回落同品类评论量 Top10。排名约定：`price_rank` 1=最便宜，`rating_rank` / `review_count_rank` 1=最高。趋势：自营走 `product_histories`，竞品走快照日均价。洞察走 LLM，失败回落启发式。

**理由：**  
报告应反映运营已监控的竞品，而非全品类噪声；回落保证冷启动仍可出图。

**状态：** 已采纳（2026-08-08，已回写 `docs/SDD.md` §3.4）

---

## DD-021 · 竞品监控看板只读聚合，摘要服务端拼接

**决策：**  
新增 `GET /dashboard/competition`：监控总数=活跃绑定；今日告警仅计竞品三类；今日变价=当日 `price_change_pct≠0` 快照数；Top 按 |Δ%| 排序。`summary` 用规则模板拼接，不调 LLM，保证看板秒开。

**理由：**  
看板 KPI 需稳定低延迟；一句话摘要字段固定、信息密度有限，启发式足够。

**状态：** 已采纳（2026-08-08，已回写 `docs/SDD.md` §3.6）

---

## DD-022 · Listing 版本单表 + 当前生效部分唯一

**决策：**  
模块五仅建 `listing_versions`（对齐 SDD §1.2.12），不另建 jobs 持久表；异步任务状态走 Redis/ARQ。约束：`(product_id, version_no)` 唯一；`is_current=true` 对 `product_id` 部分唯一，保证采纳后「一商品一当前稿」。`bullet_points` 用 JSON + PostgreSQL JSONB variant。生成失败不落库（L-04）。

**理由：**  
版本时间线与原文/优化稿对比只需一表；部分唯一索引把采纳事务的不变量下沉到 DB，避免并发采纳双 current。

**状态：** 已采纳（2026-08-10，对齐 `docs/SDD.md` §1.2.12 / §4.4）

---

## DD-023 · Listing 关键词挖掘走启发式，不落库

**决策：**  
`KeywordMiningService` 提供 `extract_keywords` / `categorize_keywords` / `suggest_keywords`；API 前缀用 `/listing/keywords/*`（与前端路由 `/listing` 对齐）。分类四档：`core` / `long_tail` / `brand` / `scenario`。无 jieba 依赖：英文 n-gram + 中文 bi/trigram；热度 = 频次 × log(1+DF)。挖掘结果即时返回，不写表。

**理由：**  
关键词挖掘是 Listing 生成前的辅助输入，结果随商品/竞品标题变化；落库会引入过期缓存与同步成本。启发式可离线可测，失败面小于再调一次 LLM。

**状态：** 已采纳（2026-08-10，已回写 `docs/SDD.md` §3.5）

---

## DD-024 · Listing 优化走同步 LLM + 新版本落库

**决策：**  
`POST /listing/optimize/{listing_id}`：`listing_id` 可解析为商品或已有版本；输入 = 商品文案 + 关键词种子 + 竞品标题；输出用 `ListingOptimizeAIResult`（Pydantic）约束五字段。成功才 INSERT `listing_versions`（`ai_generated` / 非 current / `parent_version_id`）；无版本时先落 `original`。`reason` 与 `keyword_coverage` 一并落库。失败 502 不写残缺稿。

**理由：**  
与 SDD L-04 一致；版本链支持对比与回滚，不在生成时直接覆盖 current，避免误采纳。

**状态：** 已采纳（2026-08-10，已回写 `docs/SDD.md` §1.2.12 / §3.5 / §4.4）

---

## DD-025 · Listing A/B 测试单表 + 人工选胜出

**决策：**  
新增 `listing_ab_tests`：`listing_id`（商品）+ `version_a_id` / `version_b_id` + `status` / `metric` / `winner`。创建接口 AI 生成 B；同 Listing 仅允许一条 `running`。MVP `metric` 默认 `manual`，完成接口人工选 `a`/`b`，默认 `adopt=true` 切换 `is_current`。不接平台实时 CTR（预留枚举）。

**理由：**  
跨境 Listing 优化的 A/B 核心是「基线 vs AI 稿」可回溯对比；真实流量指标依赖平台回传，MVP 先闭环版本与采纳。

**状态：** 已采纳（2026-08-10，已回写 `docs/SDD.md` §1.2.16 / §3.5）

---

## DD-026 · 批量 Listing 优化：任务进度 Redis + 失败不中断

**决策：**  
`POST /listing/batch-optimize` 立即返回 `task_id`，用 FastAPI `BackgroundTasks` 后台逐个调用单条 optimize；进度 JSON 存 Redis（TTL 7 天，不可用回落内存）。`GET /listing/batch-optimize/{task_id}` 查进度。单项失败记 `failed` 后继续，整批仍标记 `completed`。

**理由：**  
批量 LLM 耗时长，需可轮询；进程内 BackgroundTasks 免强依赖 ARQ Worker，与「失败不中断」一致。

**状态：** 已采纳（2026-08-10，已回写 `docs/SDD.md` §3.5）

---

## DD-027 · 综合运营看板 overview 聚合接口

**决策：**  
首页综合 KPI 使用 `GET /dashboard/overview`（非未实现的 `summary`）。字段固定为：商品总数、监控品类数（`is_watched`）、待审推荐数、今日告警数（全类型 UTC 今日）、最快增长品类、蓝海品类 Top1、规则拼接一句话摘要。蓝海优先读已落库推荐（门槛同 blue-ocean），避免每次全量打分。

**理由：**  
看板首屏需一次请求拿到决策摘要；与 `market-overview`（市场曲线）/`competition`（竞品盯盘）分工清晰。

**状态：** 已采纳（2026-08-11，已回写 `docs/SDD.md` §3.6 / §4.5）

---

## DD-028 · 库存预警模拟快照与安全库存规则

**决策：**  
`inventory_snapshots` 使用 `safety_stock`（替代设计稿 `reorder_point` 命名）。规则：`quantity < safety_stock` → critical/high；`< 2×safety_stock` → watch/medium；否则 normal。更新库存写入新快照并落 `alerts.type=inventory_low`（24h 同 severity 去重）。MVP 无真实仓储对接，空库自动生成模拟快照。

**理由：**  
与原型「安全库存」用语一致；先闭环列表/风险/告警/更新，便于库存预警页联调。

**状态：** 已采纳（2026-08-11，已回写 `docs/SDD.md` §1.2.13 / §3.6）

---

## DD-029 · 销量预测用移动平均并回填库存日销

**决策：**  
`GET /products/{id}/sales-forecast` 采用简单移动平均（默认窗口 7、预测未来 7 天）。历史日销优先用评论增量代理，不足则模拟。响应含历史序列、预测点（含置信度）、一句话建议；预估日销回填 `inventory_snapshots.predicted_daily_sales`（业务别名 `estimated_daily_sales`）并重算可售天数/风险，形成「预测 → 补货」闭环。

**理由：**  
无平台真实订单时先用可解释统计方法；与库存预警共用日销字段，避免两套口径。

**状态：** 已采纳（2026-08-11，已回写 `docs/SDD.md` §3.1 / §1.2.13）

---

## DD-030 · 运营看板首页对接 overview + 图表专用接口

**决策：**  
首页 `/`（`Dashboard.vue`）KPI / 最快增长 / 蓝海 / AI 摘要统一走 `GET /dashboard/overview`；柱状图走 `GET /dashboard/category-growth`；折线图走 `GET /dashboard/price-trend`（近 7 日自营历史均价 vs 活跃竞品快照均价）。AppShell 不改版。

**理由：**  
overview 已覆盖四卡片与底部洞察；图表需要序列数据，单独接口避免把重量级序列塞进 overview，并与原型「Top 增长率 / 近 7 天价格」对齐。

**状态：** 已采纳（2026-08-11，已回写 `docs/SDD.md` §3.6 / §3.7）

---

## 变更日志

| 日期 | 说明 |
|------|------|
| 2026-08-02 | 初版：随 `docs/DESIGN.md` v1.0 定稿写入 DD-001～DD-012 |
| 2026-08-08 | 新增 DD-013：选品推荐单表建模 |
| 2026-08-08 | 新增 DD-014：选品权重 30/20/25/25 与 generate API |
| 2026-08-08 | 新增 DD-015：选品 AI 深度分析 API 与 `reason` 字段 |
| 2026-08-08 | 新增 DD-016：ARQ 日批选品扫描与 webhook 预留 |
| 2026-08-08 | 新增 DD-017：竞品监控五表建模 |
| 2026-08-08 | 新增 DD-018：竞品发现服务与 API |
| 2026-08-08 | 新增 DD-019：价格监控告警规则与 alerts API |
| 2026-08-08 | 新增 DD-020：竞品分析报告 API |
| 2026-08-08 | 新增 DD-021：竞品监控看板 API |
| 2026-08-10 | 新增 DD-022：Listing 版本模型与当前生效部分唯一索引 |
| 2026-08-10 | 新增 DD-023：Listing 关键词挖掘服务与 API |
| 2026-08-10 | 新增 DD-024：Listing AI 优化 API 与版本落库 |
| 2026-08-10 | 新增 DD-025：Listing A/B 测试模型与 API |
| 2026-08-10 | 新增 DD-026：Listing 批量优化与进度查询 |
| 2026-08-11 | 新增 DD-027：综合运营看板 overview API |
| 2026-08-11 | 新增 DD-028：库存预警模拟快照与安全库存规则 |
| 2026-08-11 | 新增 DD-029：销量预测移动平均与库存日销回填 |
| 2026-08-11 | 新增 DD-030：运营看板首页 overview + category-growth + price-trend |
