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
