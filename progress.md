# 项目进度

## 当前阶段

**设计阶段 10 次对话全部完成** ✅ · **技术准备完成** ✅ · **开发阶段开始**

## 阶段清单

- [x] PRD 与页面信息架构确认
- [x] DESIGN 视觉规范
- [x] 8 个页面高保真原型与提示词
- [x] COMPONENT-SPEC 完整组件规范
- [x] INTERACTION 全站交互规范
- [x] 对照 PRD Must 逐页设计验收
- [x] DESIGN-SIGNOFF 设计签收
- [x] SDD 技术设计（`docs/SDD.md`）
- [ ] 前端开发
- [ ] 接口联调与端到端验收

## 前端实现进度

- [x] Vite + Vue 3 + TypeScript 工程初始化（Element Plus / Pinia / Vue Router / Axios / ECharts）
- [x] AppShell 全局布局（240px 深色侧栏 + 56px 顶栏 + 内容区白卡片）
- [x] 登录/注册页（居中卡片 + Tab）+ axios 拦截器 + 路由守卫
- [x] 七个业务页占位路由：看板 / 商品 / 趋势 / 选品 / 竞品 / Listing / 库存
- [x] **运营看板首页**（`Dashboard.vue`）：四 KPI（商品总数/监控品类/待审推荐/今日告警）+ Top 品类增长率柱状图 + 近 7 天价格折线 + 最快增长/蓝海高亮卡 + AI 摘要；骨架→淡入、hover 上浮；对接 `/dashboard/overview` · `category-growth` · `price-trend`
- [x] **库存预警页**（`Inventory.vue`）：统计条（总数/告警/预警）+ 风险表格（状态色行）+ 行内更新库存；对接 `/inventory` · `/summary` · `PUT /{product_id}`；三态齐全
- [x] 前端收尾：`PageHeader` / `EmptyState` / `NotFoundView`(404) + AppShell 面包屑旁页面名；主表 `table-scroll` 小屏横向滚动
- [x] `ScoreRing.vue` — 蓝海指数圆环（对齐 COMPONENT-SPEC）
- [x] `ProductScoreCard.vue` — 商品评分卡片（商品名 / 价格 / 评分 / 蓝海指数）
- [x] **商品管理页**（`ProductsView.vue`）：按 `02-products-collection.png` 完成层级品类树（父类含子类商品、递归商品数、过滤 / 跨平台近义合并）、商品表（所属品类 / 最近同步 / 搜索 / 平台 / 排序 / 分页）、采集配置抽屉、同步操作与价格历史 ECharts 弹窗；三态齐全
- [x] **市场趋势页**（`TrendsView.vue` / `Trends.vue`）：按 `03-trends.png` 完成左 40% 品类趋势表 + 右 60% 价格分布柱状图 / 价格变化折线图 + AI 解读四块（摘要/亮点/推荐/风险），对接 `/trends/categories`、price-distribution、ai-report；三态与淡入齐全

## 后端实现进度

- [x] FastAPI 应用骨架与 `routers/services/models/schema/utils` 分层
- [x] User、PlatformCredential、Category、Product、ProductHistory ORM 模型
- [x] SQLite / PostgreSQL 动态数据库配置与启动 fail-fast 校验
- [x] JWT 登录、bcrypt 密码哈希、初始管理员幂等初始化
- [x] CORS、统一异常响应、请求/脱敏 SQL 日志、登录防爆破
- [x] Swagger 登录持久化、`/health` 与 `/ready` 探针
- [x] 数据源接入层（`DataSource` 抽象 + Mock / FakeStore + 工厂切换）
- [x] DummyJSON 数据源（免费联调推荐；含 `stock`；`DATA_SOURCE=dummyjson`；旧 `fakestore` 配置映射到 DummyJSON）
- [x] Amazon SP-API 数据源（LWA Token 缓存 + Catalog Items；缺凭据回落 Mock）
- [x] Shopee Open Platform 数据源（HMAC 签名 + Token 4h 缓存 + 商品归一化；缺凭据回落 Mock）
- [x] 登录认证整合 Redis（远程 `192.168.200.180:6379`：防爆破计数/锁定 + 会话用户缓存）
- [x] 商品同步服务 ProductSyncService + `/api/v1/sync/*`
- [x] 商品/品类查询：`GET /products`、`/products/{id}`、`/products/{id}/history`、`/categories`
- [x] 市场趋势数据模型：`CategoryTrend` / `category_trends`（严格对齐 SDD §1.2.7，含品类双向关联、月度唯一约束与 `TrendVerdict`）
- [x] 市场趋势分析服务与 API：`TrendAnalysisService`（月度价格分位 / 环比增长 / 季节性 / 增长品类）+ `POST /api/v1/trends/calculate` + `GET /api/v1/trends/categories`
- [x] 价格分布分析 API：`GET /api/v1/trends/categories/{id}/charts/price-distribution`（四分位区间商品数 / 平均评分 / 月度价格曲线 / 分析建议，父品类含全部子类）
- [x] 品类趋势 AI 报告：`POST /api/v1/trends/categories/{id}/ai-report`（趋势计算 + 价格分布聚合 + 千问/OpenAI 兼容 LLM，Pydantic 约束摘要 / 亮点 / 推荐 / 风险并缓存至 `ai_insight`）
- [x] 市场概览看板：`GET /api/v1/dashboard/market-overview`（品类/商品总数、最快增长、最竞争、价格趋势、季节性洞察；已同步 `docs/SDD.md` §3.6）
- [x] 综合运营看板：`GET /api/v1/dashboard/overview`（商品总数、监控品类数、待审推荐数、今日告警数、最快增长、蓝海品类、一句话摘要；已回写 SDD / DD-027）
- [x] 看板图表接口：`GET /dashboard/category-growth` + `GET /dashboard/price-trend`（首页柱状/折线；已回写 SDD / DD-030）
- [x] 库存预警（模拟）：`InventorySnapshot` + `GET /inventory` · `/risks` · `/alerts` · `/summary` · `PUT /inventory/{product_id}`；规则 quantity<safety→critical、<2×safety→watch；空库自动 seed；已回写 SDD / DD-028
- [x] 销量预测：`GET /products/{id}/sales-forecast`（移动平均未来 7 天；历史/预测/置信度/一句话建议；回填 `InventorySnapshots.predicted_daily_sales`≈estimated_daily_sales）；已回写 SDD / DD-029
- [x] 选品推荐数据模型：`Recommendation` / `recommendations`（严格对齐 SDD §1.2.8；含四维得分、决策字段、`(status, score_total DESC)` / `category_id` 索引、`RecommendationStatus` 状态机；决策字段内嵌不单建 selection_decisions）
- [x] 选品评分算法：`SelectionScorer`（需求 30% / 竞争 20% / 利润 25% / 趋势 25%）+ `POST /api/v1/recommendations/generate`；已回写 `docs/SDD.md` §3.3 / §4.7
- [x] 蓝海品类发现：`GET /api/v1/recommendations/blue-ocean`（需求高×竞争低筛选，蓝海指数降序，含四维评分与推荐理由；已写入 SDD §3.3）
- [x] 选品 AI 深度分析：`POST /api/v1/recommendations/{id}/ai-analysis`（品类市场数据 + Top5 竞品 → 市场机会/竞品格局/入局建议/风险；落库 `reason`，摘要同步 `ai_blue_ocean_text`；已回写 SDD / DD-015）
- [x] 选品推荐管理接口：`GET /recommendations`（分页，筛 status/platform）、详情、accept/reject（409 状态冲突）、`GET /export` CSV、`GET /stats`；已回写 SDD §3.3
- [x] 定时选品扫描：`scan_all_categories` + ARQ Cron 每日 03:30（Asia/Shanghai）+ `POST /recommendations/scan`（入队/同步）+ 分差≤20% 跳过 + webhook 预留；已回写 SDD / DD-016
- [x] 选品推荐页（`Selections.vue`）：蓝海发现卡片网格（圆环色阶/四维条/风险标签）+ 筛选分页 + AI 分析抽屉四块 + 推荐列表/已接受 Tab；对接 blue-ocean / recommendations / ai-analysis / accept·reject
- [x] 竞品监控页（`Competitors.vue`）：自营商品选择器 + 竞品表（涨跌色/告警级别）+ 多竞品价格折线对比 + 未读告警横条/列表（severity 分色、标记已读）+ 刷新确认 / 添加竞品（discover）；对接 competitors / alerts API
- [x] 竞品写权限：刷新/添加/标记已读仅 `operator` / `ops_lead`（后端 403 + 前端禁用与 tooltip）；种子账号 `zhangsan` 角色改为 `ops_lead`
- [x] 登录态 hydrate：路由守卫/`App` 启动时调 `/auth/me` 刷新角色，修复 localStorage 旧 `boss` 导致「添加竞品」按钮禁用
- [x] 竞品监控数据模型：`WatchedProduct` / `CompetitorBinding` / `CompetitorSnapshot` / `Alert` / `SystemSetting`（对齐 SDD §1.2.5 / §1.2.9–§1.2.11 / §1.2.14；`AlertType`/`AlertSeverity`；活跃绑定部分唯一索引；快照 BIGSERIAL）
- [x] 竞品发现服务：`CompetitorDiscoveryService`（`discover_competitors` / `update_competitor_data` / `batch_update_all`）+ API `GET /competitors/discover`、`GET /competitors/{id}`、`POST /competitors/batch-update`、`POST /competitors/{id}/refresh`；AI 挑选 + 启发式回落；快照与降价告警评估
- [x] 价格监控与自动告警：`AlertService`（降价 5%→warning / 10%→critical、评分降 0.5→warning、Top10 发现→info）+ API `GET /alerts`、`POST /alerts/{id}/read`、`GET /alerts/unread-count`、`GET /alerts/stats`、`POST /alerts/check`；已回写 SDD / DD-019
- [x] 竞品分析报告：`GET /competitors/{product_id}/report`（价格区间 / 价格·评分·评论排名 / 价格趋势 / AI 洞察；无绑定回落同品类）；已回写 SDD / DD-020
- [x] 竞品监控看板：`GET /dashboard/competition`（监控总数 / 今日告警 / 今日价格变动 / Top 变动 / 一句话摘要）；已回写 SDD / DD-021
- [x] Listing 管理数据模型：`ListingVersion` / `listing_versions` + `ListingSource`（对齐 SDD §1.2.12 / 附录 A；`(product_id, version_no)` 唯一；`is_current` 部分唯一；自引用 `parent_version_id`）；已记 DD-022
- [x] Listing 关键词挖掘：`KeywordMiningService`（`extract_keywords` / `categorize_keywords` / `suggest_keywords`）+ API `POST /listing/keywords/extract/{product_id}`、`GET /listing/keywords/suggest`；`KeywordCategory` 四类；已回写 SDD / DD-023
- [x] Listing AI 优化：`ListingOptimizeService` + `LLMClient.generate_listing_optimize` + API `POST /listing/optimize/{listing_id}`；Pydantic 约束标题/5卖点/描述/搜索词/理由；落库新 `ListingVersion`（含 `reason`）；已回写 SDD / DD-024
- [x] Listing A/B 测试：`ListingABTest` / `listing_ab_tests` + API `POST /listing/ab-test/create`、`PUT /listing/ab-test/{id}/complete`、`GET /listing/ab-test/history`；创建时 AI 生成 B，完成可选采纳胜出；已回写 SDD / DD-025
- [x] Listing 批量优化：`ListingBatchOptimizeService` + API `POST /listing/batch-optimize`、`GET /listing/batch-optimize/{task_id}`；BackgroundTasks 逐个执行，单项失败不中断；进度 Redis/内存；已回写 SDD / DD-026
- [x] Listing 版本 API：`GET /listing/{id}/current|versions|compare`、`POST .../versions/{id}/adopt`
- [x] Listing 优化页（`Listing.vue`）：商品选择器 + 双栏对比（原版/AI 优化版）+ 关键词增删高亮 + 优化理由 + 版本时间线回滚 + A/B 胜出入口；对接 optimize / versions / adopt / ab-test
- [x] Docker 部署：根目录多阶段 `Dockerfile`（api/worker）+ `frontend/Dockerfile`（nginx）+ `docker-compose.yml`（api/db/redis/worker/frontend）+ `.env.example` + healthcheck；已回写 SDD §5.4
- [x] 项目 README.md（简介/架构图/六模块/五步启动/API 文档/原型截图）+ CLAUDE.md 完整信息补充
- [ ] 为本轮模型生成 Alembic 初始迁移（进入生产部署前）


## 设计评审遗留

- [ ] 补丁：`02-products.png` 默认表格增加「所属品类」列（当前唯一 ❌）
- [ ] 补丁：统一库存预警相关侧栏未读角标
- [ ] 补丁：`04-selections-drawer.png` 复用定稿 AppShell

以上遗留不要求全面重做；详见 `docs/DESIGN-SIGNOFF.md` §4。

## 签收依据

- `docs/DESIGN-SIGNOFF.md`
- `docs/DESIGN.md`
- `docs/COMPONENT-SPEC.md`
- `docs/INTERACTION.md`
- `docs/prototypes/`
