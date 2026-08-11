# 华普智选 — 软件设计文档（SDD）

> 版本：v1.0 | 状态：初稿  
> 产品：华普智选（智能选品与跨境运营中台）  
> 依据：`docs/PRD.md` v1.1 · `docs/DESIGN-SIGNOFF.md` · `docs/FLOWS.md`  
> 技术栈：FastAPI · PostgreSQL · SQLAlchemy 2.0 · Redis · OpenAI  
> 文档目标：作为后端建模、API 契约与模块实现的统一技术依据。

---

## 0. 文档范围与约定

### 0.1 交付边界（MVP）

| 做 | 不做（PRD §4） |
|----|----------------|
| Amazon 数据接入（Shopee 接口预留） | 采购 / 物流 / 财务 / 广告 / 社媒 |
| 品类趋势、选品推荐、竞品告警、Listing 优化 | 多语言翻译（后期） |
| 运营看板 + 库存/告警合并页 + Docker 部署 | ERP 下单 |

### 0.2 信息架构对齐（DESIGN-SIGNOFF）

| PRD 编号 | 实现路由 | 说明 |
|----------|----------|------|
| — | `/login` · `/register` | A0 鉴权 |
| P1 | `/`（`/dashboard` 重定向） | 运营看板 |
| P2 + P8 | `/products`（采集配置抽屉） | 商品管理 + 采集配置 |
| P3 | `/trends` | 市场趋势 |
| P4 | `/recommendations` | 智能选品 |
| P5 | `/competitors` | 竞品监控 |
| P6 + 库存 Should | `/inventory-alerts` | 告警记录 Tab + 库存风险 Tab |
| P7 | `/listing` | Listing 优化 |

### 0.3 分层架构

```
┌─────────────────────────────────────────────────────────┐
│  Vue Web（AppShell + 7 业务页）                           │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTPS / JWT
┌──────────────────────────▼──────────────────────────────┐
│  FastAPI（routers → services → repositories）            │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ Celery/定时  │  │ Redis Cache  │  │ OpenAI Client  │  │
│  │ Worker      │  │ + Queue      │  │                │  │
│  └─────────────┘  └──────────────┘  └────────────────┘  │
└──────────────────────────┬──────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │  PostgreSQL (SQLAlchemy) │
              └─────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │ Amazon / Shopee Adapter │
              └─────────────────────────┘
```

---

## 1. 数据库模型设计

> ORM：SQLAlchemy 2.0 Declarative · 主键一律 `UUID` · 时间一律 `TIMESTAMPTZ` · 金额用 `Numeric(12,2)`。

### 1.1 ER 关系总览

```
users ─────────────┬────────── recommendations (decided_by)
                   ├────────── listing_versions (created_by)
                   ├────────── alerts (read_by)
                   └────────── collection_tasks (created_by)

categories ────────┬────────── products
                   ├────────── category_trends
                   ├────────── recommendations
                   └────────── collection_tasks

products ──────────┬────────── product_histories
                   ├────────── watched_products (自营关注)
                   ├────────── competitor_bindings (own_product)
                   ├────────── competitor_bindings (competitor_product)
                   ├────────── listing_versions
                   ├────────── inventory_snapshots
                   └────────── alerts

competitor_bindings ── competitor_snapshots
competitor_bindings ── alerts

platform_accounts ──── collection_tasks
system_settings（KV 配置，如降价阈值）
```

### 1.2 表定义

#### 1.2.1 `users` — 用户与角色

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| email | VARCHAR(255) | UNIQUE NOT NULL | 登录账号 |
| password_hash | VARCHAR(255) | NOT NULL | bcrypt / argon2 |
| display_name | VARCHAR(100) | NOT NULL | |
| role | ENUM | NOT NULL | `operator` / `selection_manager` / `ops_lead` / `boss` |
| is_active | BOOLEAN | DEFAULT true | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**关系：** 1 → N `recommendations`（决策人）、`listing_versions`、`alerts`（已读人）、`collection_tasks`。

**角色写权限摘要（对齐 PRD §5）：**

| 操作 | operator | selection_manager | ops_lead | boss |
|------|:--------:|:-----------------:|:--------:|:----:|
| 选品接受/拒绝 | — | ✓ | ✓ | — |
| 绑定/移除竞品 | ✓ | — | — | — |
| 告警标记已读 | ✓ | 读 | ✓ | — |
| Listing 生成/采纳 | ✓ | — | 读 | — |
| 采集任务配置 | — | — | ✓ | — |
| 告警阈值调整 | — | — | ✓ | — |

---

#### 1.2.2 `categories` — 品类

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| platform | ENUM | NOT NULL | `amazon` / `shopee` |
| external_id | VARCHAR(64) | NOT NULL | 平台品类 ID |
| name | VARCHAR(200) | NOT NULL | |
| parent_id | UUID | FK → categories.id NULL | 树形 |
| path | VARCHAR(500) | | 物化路径，便于筛选 |
| is_watched | BOOLEAN | DEFAULT false | 用户关注品类 |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**唯一约束：** `(platform, external_id)`  
**关系：** 1 → N `products`、`category_trends`、`recommendations`、`collection_tasks`。

---

#### 1.2.3 `products` — 商品主数据

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| platform | ENUM | NOT NULL | `amazon` / `shopee` |
| external_id | VARCHAR(64) | NOT NULL | ASIN / item_id |
| category_id | UUID | FK → categories.id | **所属品类（P2 Must）** |
| title | VARCHAR(500) | NOT NULL | |
| description | TEXT | | |
| bullet_points | JSONB | | 五点描述数组 |
| keywords | TEXT | | 当前关键词串 |
| price | Numeric(12,2) | | 当前价 |
| currency | CHAR(3) | DEFAULT 'USD' | |
| rating | Numeric(3,2) | | 0–5 |
| review_count | INT | DEFAULT 0 | |
| bsr | INT | | Best Seller Rank |
| image_url | VARCHAR(1000) | | |
| product_url | VARCHAR(1000) | | |
| last_synced_at | TIMESTAMPTZ | | 最近同步 |
| raw_payload | JSONB | | 平台原始快照（可选） |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**唯一约束：** `(platform, external_id)`  
**索引：** `(category_id)`、`(title)` gin_trgm（搜索）、`(last_synced_at)`、`(bsr)`。

---

#### 1.2.4 `product_histories` — 商品历史时序

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGSERIAL | PK | 高频写入用自增 |
| product_id | UUID | FK → products.id ON DELETE CASCADE | |
| price | Numeric(12,2) | | |
| rating | Numeric(3,2) | | |
| review_count | INT | | |
| bsr | INT | | |
| recorded_at | TIMESTAMPTZ | NOT NULL | 采样时间 |

**索引：** `(product_id, recorded_at DESC)`  
**规模：** PRD 预估每日 5000+ 条；建议按月分区或定期归档。

---

#### 1.2.5 `watched_products` — 自营关注

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| user_id | UUID | FK → users.id | 关注人；主管可见团队可扩展 |
| product_id | UUID | FK → products.id | |
| note | VARCHAR(500) | | |
| created_at | TIMESTAMPTZ | NOT NULL | |

**唯一约束：** `(user_id, product_id)`  
**用途：** P2 Should「自营关注」；P5 竞品监控的「目标商品」选择器数据源。

---

#### 1.2.6 `collection_tasks` — 采集任务（PRD P8）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| platform | ENUM | NOT NULL | |
| category_id | UUID | FK → categories.id | 关注品类 |
| frequency | ENUM | NOT NULL | `hourly` / `daily` / `manual` |
| trigger_mode | ENUM | NOT NULL | `schedule` / `manual` |
| is_enabled | BOOLEAN | DEFAULT true | |
| status | ENUM | NOT NULL | `pending` / `running` / `success` / `failed` |
| progress_pct | INT | DEFAULT 0 | 0–100，完成率 |
| error_summary | VARCHAR(1000) | | 失败摘要 |
| started_at | TIMESTAMPTZ | | |
| finished_at | TIMESTAMPTZ | | |
| created_by | UUID | FK → users.id | ops_lead |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**关系：** N → 1 `categories`；执行日志可另表 `collection_runs`（Should，MVP 可把最近一次状态写在本表）。

##### 可选扩展 `collection_runs`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| task_id | UUID | FK |
| status | ENUM | success / failed / running |
| items_fetched | INT | |
| error_summary | TEXT | |
| started_at / finished_at | TIMESTAMPTZ | |

---

#### 1.2.7 `category_trends` — 品类趋势（模块二）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| category_id | UUID | FK → categories.id | |
| period_month | DATE | NOT NULL | 存当月 1 日 |
| price_p25 | Numeric(12,2) | | 价格分位 |
| price_p50 | Numeric(12,2) | | |
| price_p75 | Numeric(12,2) | | |
| avg_price | Numeric(12,2) | | |
| growth_rate | Numeric(8,4) | | 环比增长 |
| seasonality_hint | VARCHAR(200) | | 季节性提示 |
| sample_size | INT | | 样本数 |
| ai_insight | TEXT | | AI 趋势解读缓存 |
| ai_verdict | ENUM | | `growing` / `shrinking` / `stable` |
| computed_at | TIMESTAMPTZ | NOT NULL | |

**唯一约束：** `(category_id, period_month)`。

---

#### 1.2.8 `recommendations` — 选品推荐（模块三）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| category_id | UUID | FK → categories.id | |
| product_id | UUID | FK → products.id NULL | 可挂代表商品 |
| title | VARCHAR(300) | NOT NULL | 推荐展示名 |
| score_total | Numeric(5,2) | NOT NULL | 综合分 0–100 |
| score_demand | Numeric(5,2) | NOT NULL | 市场需求 |
| score_competition | Numeric(5,2) | NOT NULL | 竞争强度（越高竞争越弱或按约定语义） |
| score_margin | Numeric(5,2) | NOT NULL | 利润空间 |
| score_trend | Numeric(5,2) | NOT NULL | 趋势方向 |
| ai_blue_ocean_text | TEXT | | AI 蓝海摘要（可读短文，可由深度分析同步） |
| reason | TEXT | | AI 选品深度分析（结构化 JSON：市场机会 / 竞品格局 / 入局建议 / 风险） |
| status | ENUM | NOT NULL | `pending` / `accepted` / `rejected` |
| decided_by | UUID | FK → users.id NULL | |
| decided_at | TIMESTAMPTZ | | |
| reject_reason | VARCHAR(500) | | 可选 |
| note | VARCHAR(500) | | 选品备注 |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**索引：** `(status, score_total DESC)`、`(category_id)`。  
**状态机：** `pending` → `accepted` | `rejected`（MVP 不可逆，对齐 FLOWS §5.1）。

---

#### 1.2.9 `competitor_bindings` — 竞品绑定（模块四）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| own_product_id | UUID | FK → products.id | 自营关注商品 |
| competitor_product_id | UUID | FK → products.id | 竞品 |
| created_by | UUID | FK → users.id | |
| is_active | BOOLEAN | DEFAULT true | 移除 = soft delete |
| created_at | TIMESTAMPTZ | NOT NULL | |
| removed_at | TIMESTAMPTZ | | |

**唯一约束：** `(own_product_id, competitor_product_id)` WHERE `is_active`。

---

#### 1.2.10 `competitor_snapshots` — 竞品价格快照

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGSERIAL | PK | |
| binding_id | UUID | FK → competitor_bindings.id | |
| price | Numeric(12,2) | NOT NULL | |
| rating | Numeric(3,2) | | |
| price_change_pct | Numeric(8,4) | | 相对上一快照 |
| recorded_at | TIMESTAMPTZ | NOT NULL | |

**索引：** `(binding_id, recorded_at DESC)`  
**调度：** 每小时拉取；告警延迟目标 < 30 分钟（PRD §10）。

---

#### 1.2.11 `alerts` — 告警（模块四 + 模块六）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| type | ENUM | NOT NULL | `competitor_price_drop` / `competitor_rating_drop` / `competitor_discovered` / `inventory_low` / `collection_failed` |
| severity | ENUM | DEFAULT 'warning' | `info` / `warning` / `critical`（业务口语 low/medium/high 分别对应三者） |
| product_id | UUID | FK → products.id NULL | |
| competitor_binding_id | UUID | FK NULL | |
| threshold_value | Numeric(8,4) | | 如 0.05 = 5% |
| trigger_value | Numeric(12,4) | | 实际触发值 |
| title | VARCHAR(300) | NOT NULL | |
| message | TEXT | | |
| is_read | BOOLEAN | DEFAULT false | |
| read_by | UUID | FK → users.id NULL | |
| read_at | TIMESTAMPTZ | | |
| triggered_at | TIMESTAMPTZ | NOT NULL | |
| created_at | TIMESTAMPTZ | NOT NULL | |

**索引：** `(is_read, triggered_at DESC)`、`(product_id)`。  
**未读计数：** 单一数据源 `COUNT(*) WHERE is_read = false`，供看板 KPI 与侧栏角标共用（DESIGN-SIGNOFF §5）。

**竞品监控告警规则（价格监控 / 自动告警）：**

| 条件 | severity | type | 说明 |
|------|----------|------|------|
| 竞品降价超 5%（`Δ% ≤ -0.05`） | `warning`（medium） | `competitor_price_drop` | 阈值可由 `alert.price_drop_threshold` 覆盖，默认 0.05 |
| 竞品降价超 10%（`Δ% ≤ -0.10`） | `critical`（high） | `competitor_price_drop` | 高优先级覆盖 medium |
| 评分下降超 0.5 | `warning`（medium） | `competitor_rating_drop` | 相对上一快照评分 |
| 新发现 Top 10 竞品并自动绑定 | `info`（low） | `competitor_discovered` | 发现流程写入；每条绑定一条 |

---

#### 1.2.12 `listing_versions` — Listing 版本（模块五）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| product_id | UUID | FK → products.id | |
| version_no | INT | NOT NULL | 自增版本号 |
| source | ENUM | NOT NULL | `original` / `ai_generated` / `adopted` |
| title | VARCHAR(500) | NOT NULL | |
| description | TEXT | | |
| bullet_points | JSONB | | |
| keywords | TEXT | | |
| keyword_coverage | Numeric(5,2) | | 覆盖率 %；目标 > 90% |
| reason | TEXT | NULL | AI 优化理由；原文版本可空 |
| is_current | BOOLEAN | DEFAULT false | 当前生效版本 |
| created_by | UUID | FK → users.id NULL | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| parent_version_id | UUID | FK → listing_versions.id NULL | 基于哪版生成 |

**唯一约束：** `(product_id, version_no)`  
**规则：** 采纳时事务内：旧 `is_current=false`，新版 `is_current=true`；生成失败不写残缺稿（L-04）。

---

#### 1.2.16 `listing_ab_tests` — Listing 文案 A/B 测试（模块五）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| listing_id | UUID | FK → products.id | 商品 Listing |
| version_a_id | UUID | FK → listing_versions.id | 基线版本 A |
| version_b_id | UUID | FK → listing_versions.id | 对照版本 B（AI 生成） |
| status | ENUM | NOT NULL | `running` / `completed` / `cancelled` |
| metric | ENUM | NOT NULL | `manual` / `ctr` / `conversion` / `keyword_coverage` |
| started_at | TIMESTAMPTZ | NOT NULL | |
| completed_at | TIMESTAMPTZ | NULL | |
| winner | ENUM | NULL | `a` / `b`；完成后填写 |
| created_by | UUID | FK → users.id NULL | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**约束：** `version_a_id ≠ version_b_id`；同一 `listing_id` 同时最多一条 `status=running`（部分唯一索引）。  
**规则：** 创建时 AI 生成 B；完成时可选择胜出并采纳为 `is_current`。

---

#### 1.2.13 `inventory_snapshots` — 库存快照（模块六 Should）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| product_id | UUID | FK → products.id | 索引 `(product_id, recorded_at DESC)` |
| sku | VARCHAR(64) | | |
| quantity | INT | NOT NULL | 可用库存 |
| safety_stock | INT | NOT NULL | 安全库存（原设计稿 `reorder_point`） |
| predicted_daily_sales | Numeric(10,2) | | 预估日销（业务别名 `estimated_daily_sales`；由销量预测 API 回填） |
| days_of_cover | Numeric(8,2) | | 可售天数 = quantity / predicted_daily_sales |
| risk_level | ENUM | NOT NULL · 索引 | `normal` / `watch` / `critical` |
| recorded_at | TIMESTAMPTZ | NOT NULL | |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL | |

**告警规则（模拟）：**
- `quantity < safety_stock` → `risk_level=critical`，写 `alerts`（`type=inventory_low`，`severity=critical`，业务 high）
- `quantity < safety_stock * 2` → `risk_level=watch`，写 `alerts`（`severity=warning`，业务 medium）
- 否则 `normal`；同商品同 severity 24h 内去重

**用途：** `/inventory-alerts`「库存风险」Tab；P1 Should 库存摘要。MVP 数据源为模拟快照（空库自动 seed）。

---

#### 1.2.14 `system_settings` — 系统配置

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| key | VARCHAR(100) | PK | 如 `alert.price_drop_threshold` |
| value | JSONB | NOT NULL | `{"pct": 0.05}` |
| updated_by | UUID | FK → users.id | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**默认：** 竞品降价阈值 `0.05`（5%），仅 `ops_lead` 可改。

---

#### 1.2.15 `platform_credentials`（可选，第二版）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| platform | ENUM | amazon / shopee |
| label | VARCHAR(100) | |
| encrypted_secret | BYTEA | KMS/本地加密 |
| is_active | BOOLEAN | |
| created_at | TIMESTAMPTZ | |

MVP 可用环境变量注入 API Key，表结构预留。

---

### 1.3 关系图（简图）

```
users ──< recommendations
users ──< listing_versions
users ──< alerts (read)
users ──< collection_tasks
users ──< watched_products
users ──< competitor_bindings

categories ──< products ──< product_histories
     │              ├──< watched_products
     │              ├──< listing_versions
     │              ├──< listing_ab_tests
     │              ├──< inventory_snapshots
     │              ├──< alerts
     │              └──< competitor_bindings (own / competitor)
     ├──< category_trends
     ├──< recommendations
     └──< collection_tasks

competitor_bindings ──< competitor_snapshots
competitor_bindings ──< alerts
```

---

## 2. 模块依赖关系图

### 2.1 业务模块依赖（ASCII）

```
                    ┌──────────────────────┐
                    │  M6 运营看板与部署     │
                    │  dashboard / inventory │
                    │  Docker Compose       │
                    └──────────▲───────────┘
                               │ 只读聚合
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
┌────────┴────────┐  ┌─────────┴────────┐  ┌────────┴────────┐
│ M2 市场趋势分析  │  │ M3 智能选品推荐   │  │ M4 竞品监控预警  │
│ trends + AI     │  │ score + AI       │  │ bind + alert    │
└────────▲────────┘  └────────▲─────────┘  └────────▲────────┘
         │                    │                      │
         │         ┌──────────┴──────────┐           │
         │         │                     │           │
         │         │  M5 AI Listing 优化  │◄──────────┤
         │         │ （消费商品与市场上下文）│           │
         │         └──────────▲──────────┘           │
         │                    │                      │
         └────────────────────┼──────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │ M1 数据接入与商品   │
                    │ products / tasks  │
                    │ Amazon·Shopee     │
                    └─────────▲─────────┘
                              │
                    ┌─────────┴─────────┐
                    │ 基础设施层          │
                    │ Auth · Redis · PG │
                    │ OpenAI · Workers  │
                    └───────────────────┘
```

**依赖规则：**

1. **M1 为数据底座**：M2–M5 只读或引用 `products` / `categories` / `product_histories`。
2. **M2 → M3**：趋势分与 AI 解读输入推荐打分；P3→P4 带 `category_id`。
3. **M4 → M6**：告警写入 `alerts`；看板与侧栏角标同源计数。
4. **M5 独立于 M3**：可对任意关注商品优化 Listing，不强制先接受推荐。
5. **M6 不反向写业务表**：仅聚合查询 + 库存快照/告警展示；部署编排不进入业务依赖环。

### 2.2 后端包依赖（建议目录）

```
app/
├── api/                 # FastAPI routers（按模块）
│   ├── auth.py
│   ├── products.py      # M1 + 采集配置
│   ├── trends.py        # M2
│   ├── recommendations.py  # M3
│   ├── competitors.py   # M4
│   ├── alerts.py        # M4/M6
│   ├── listings.py      # M5
│   ├── dashboard.py     # M6
│   └── inventory.py     # M6
├── services/            # 领域服务（无 HTTP）
├── repositories/        # SQLAlchemy 查询
├── workers/             # 采集 / 竞品快照 / 趋势计算
├── adapters/            # amazon.py · shopee.py（stub）
├── ai/                  # OpenAI prompts & clients
├── core/                # config · security · redis · deps
└── models/              # SQLAlchemy 模型
```

```
api ──► services ──► repositories ──► models
              │
              ├──► adapters (platform)
              ├──► ai (OpenAI)
              └──► redis (cache / lock / queue)
workers ──► services（复用同一领域逻辑）
```

---

## 3. API 端点清单

> 前缀：`/api/v1` · 鉴权：`Authorization: Bearer <JWT>`（除登录/注册）  
> 统一响应：`{ "data": ..., "meta": {...} }`；列表带 `page` / `page_size` / `total`。  
> 错误：`4xx/5xx` + `{ "error": { "code", "message" } }`。

### 3.0 鉴权 `auth`

| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| POST | `/auth/register` | 注册 | 公开 |
| POST | `/auth/login` | 登录，返回 JWT | 公开 |
| POST | `/auth/logout` | 登出（可选黑名单） | 登录用户 |
| GET | `/auth/me` | 当前用户与角色 | 登录用户 |

### 3.1 模块一 — 数据接入与商品管理

| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| GET | `/products` | 列表：搜索、品类、排序、分页；含所属品类 | 运营+ |
| GET | `/products/{id}` | 详情 + 可选历史价/排名 | 运营+ |
| GET | `/products/{id}/history` | 商品历史时序（价格/评分/评论/BSR） | 运营+ |
| GET | `/products/{id}/sales-forecast` | 移动平均销量预测（默认未来 7 天）；回填库存预估日销 | 全角色读 |
| PATCH | `/products/{id}/watch` | 标记/取消自营关注 | 运营 |

#### `GET /products/{id}/sales-forecast` 响应约定

简单移动平均法（`method=moving_average`）。历史日销优先取 `product_histories.review_count` 日增量代理；样本不足时用可复现模拟序列。

| 字段 | 说明 |
|------|------|
| `history` | 历史日销序列（`date` + `units`） |
| `forecast` | 未来 N 天预测（`date` + `units` + 点级 `confidence`） |
| `estimated_daily_sales` | 窗口均值预估日销；同步写入 `inventory_snapshots.predicted_daily_sales` |
| `confidence` | 整体置信度 0–1（样本充足度 + 波动 CV） |
| `suggestion` | 一句话补货建议（结合可售天数） |
| `inventory_updated` | 是否已回填库存快照并重算 `days_of_cover` / `risk_level` |
| 查询参数 | `window`（默认 7）· `horizon_days`（默认 7）· `lookback_days`（默认 28）· `sync_inventory`（默认 true） |
| GET | `/categories` | 品类树（可筛 watched） | 运营+ |
| GET | `/collection-tasks` | 采集任务列表与状态 | 运营读 / 主管写 |
| POST | `/collection-tasks` | 创建采集任务 | ops_lead |
| PATCH | `/collection-tasks/{id}` | 启停、改频率/品类 | ops_lead |
| POST | `/collection-tasks/{id}/run` | 手动触发一次 | ops_lead |
| GET | `/collection-tasks/{id}/runs` | 最近运行记录（Should） | ops_lead |

### 3.2 模块二 — 市场趋势分析

| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| GET | `/trends` | 按品类 + 时间范围返回月度价格分布与增长率 | 选品经理主用 |
| GET | `/trends/{category_id}/insight` | AI 趋势解读（缓存优先） | 同上 |
| POST | `/trends/{category_id}/insight/refresh` | 强制重算 AI 解读 | ops_lead / selection_manager |

### 3.3 模块三 — 智能选品推荐

| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| GET | `/recommendations` | 分页列表；筛 `status` / `platform_id`（可选 `category_id` / `min_score`） | 登录；决策按钮按角色 |
| GET | `/recommendations/export` | 按与列表相同筛选导出 CSV（UTF-8 BOM，上限 5000 行） | 登录 |
| GET | `/recommendations/blue-ocean` | 发现蓝海品类（需求高 × 竞争低）；按蓝海指数降序；含四维评分与推荐理由 | 登录 |
| GET | `/recommendations/{id}` | 四维得分 + AI 蓝海说明 + `reason` 深度分析 | 登录 |
| POST | `/recommendations/{id}/ai-analysis` | 基于品类市场数据调用 LLM 生成深度分析，写入 `reason`（并同步摘要至 `ai_blue_ocean_text`） | selection_manager / ops_lead / boss |
| POST | `/recommendations/{id}/accept` | 接受；写 decided_by/at；可选 note | selection_manager / ops_lead |
| POST | `/recommendations/{id}/reject` | 拒绝；可选 reject_reason / note | 同上 |
| POST | `/recommendations/generate` | 触发 `SelectionScorer` 批量打分并落库 `pending` 推荐；可筛 `platform_id` / `category_id` | ops_lead / selection_manager / boss |
| POST | `/recommendations/scan` | 手动触发全品类选品扫描（同日批逻辑）；默认入队 ARQ，可选同步执行 | ops_lead / selection_manager / boss |
| GET | `/recommendations/stats` | 待处理/已接受/已拒绝计数（供 P1） | 登录 |

#### `GET /recommendations` 查询 / 响应

| 字段 | 位置 | 说明 |
|------|------|------|
| `page` / `page_size` | query | 分页，默认 1 / 20，`page_size` 上限 100 |
| `status` | query 可选 | `pending` / `accepted` / `rejected` |
| `platform_id` | query 可选 | 经 `categories.platform` 关联筛选 |
| `category_id` | query 可选 | 品类 UUID |
| `min_score` | query 可选 | `score_total` 下限，0–100 |
| `items` / `meta` | response | 分页列表（含 `category_name` / `platform_id`） |

**排序：** `score_total DESC`，二级 `created_at DESC`。

#### `GET /recommendations/export` 查询

筛选参数与列表一致（无分页）。响应 `Content-Type: text/csv; charset=utf-8`，文件名 `recommendations.csv`。

#### `POST /recommendations/{id}/accept|reject` 请求 / 响应

| 字段 | 位置 | 说明 |
|------|------|------|
| `note` | body 可选 | 写入 `note`，最长 500 |
| `reason` | body 可选（仅 reject） | 写入 `reject_reason`，最长 500 |
| — | response | 更新后的 `RecommendationRead` |

**状态机：** 仅 `pending` 可决策；已决策返回 **409**。非授权角色 **403**。

#### `POST /recommendations/{id}/ai-analysis` 请求 / 响应

| 字段 | 位置 | 说明 |
|------|------|------|
| `id` | path | 推荐行 UUID |
| `analysis.market_opportunity` | response | 市场机会分析 |
| `analysis.competitive_landscape` | response | Top 5 竞品/卖家差异化策略（`rank` / `name` / `differentiation`） |
| `analysis.entry_advice` | response | 入局建议（定价区间与差异化方向） |
| `analysis.risks` | response | 风险提示（1–5 条） |
| `reason` | response | 落库原文（`SelectionAIAnalysis` 的 JSON） |
| `generated_at` | response | 生成时间（UTC） |

**输入：** 服务层聚合该推荐所属品类的市场数据（四维分、趋势分位/增速、价格分布摘要、按评论量排序的 Top 5 商品作为竞品代表）。  
**落库：** `recommendations.reason` ← 结构化 JSON；`ai_blue_ocean_text` ← 由分析摘要拼接的可读短文。  
**模式：** 复用 `LLMClient`（`LLM_MODE=mock|openai`）；无 Key 时 mock 回落。

#### `GET /recommendations/blue-ocean` 查询 / 响应

| 字段 | 位置 | 说明 |
|------|------|------|
| `platform_id` | query 可选 | 平台筛选 |
| `min_demand` | query 可选 | 市场需求分下限，默认 60 |
| `min_competition` | query 可选 | 竞争机会分下限（分高=竞争弱），默认 60 |
| `limit` | query 可选 | 返回条数，默认 20，上限 100 |
| `items[].blue_ocean_index` | response | 蓝海指数（= `score_total`，0–100） |
| `items[].scores` | response | 四维评分详情：demand / competition / margin / trend |
| `items[].reason` | response | 规则化推荐理由（需求高 + 竞争低的可读说明） |

**筛选语义：** `score_demand >= min_demand` 且 `score_competition >= min_competition`（竞争维度为机会分）。  
**排序：** `blue_ocean_index DESC`。

#### `POST /recommendations/generate` 请求 / 响应

| 字段 | 位置 | 说明 |
|------|------|------|
| `platform_id` | body 可选 | 仅对该平台下品类打分 |
| `category_id` | body 可选 | 仅打分单个品类（含其全部子品类商品样本） |
| `limit` | body 可选 | 本批最多写入条数，默认 50，上限 200 |
| `items` | response | 新生成 / 更新的推荐列表（含四维分与综合分） |
| `generated_count` | response | 成功写入条数 |

#### `POST /recommendations/scan` 请求 / 响应

| 字段 | 位置 | 说明 |
|------|------|------|
| `sync` | body 可选 | `true` 时进程内同步执行（联调/无 Worker）；默认 `false` 入队 ARQ |
| `platform_id` | body 可选 | 仅扫描该平台活跃品类 |
| `mode` | response | `queued` / `sync` |
| `job_id` | response | 入队时的 ARQ job id；同步时为 null |
| `scanned` / `created` / `updated` / `skipped` / `errors` | response | 同步模式统计；入队模式可为 null |

**扫描语义（`scan_all_categories`）：**
1. 活跃品类 = 至少有一件商品的品类（可按 `platform_id` 收窄）。
2. 对每个品类跑 `SelectionScorer`；取该品类**最新一条**推荐（优先 `pending`）作基线。
3. **已有推荐且综合分相对变化 ≤ 20%** → 跳过，不重复生成。
4. 无推荐，或相对变化 **> 20%** → 写入/更新 `pending`（已决策品类在分数跳变时新建一条 `pending`）。
5. **新创建**的推荐触发 webhook 预留通知（`SELECTION_WEBHOOK_URL` 未配置则仅打日志，不失败）。

**日批：** Redis + ARQ Cron，每天 **03:30（Asia/Shanghai）** 执行同一任务；Redis 锁 `lock:selection:scan` 防并发。

### 3.4 模块四 — 竞品监控与预警

| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| GET | `/competitors` | 某自营商品下已绑定竞品列表（`own_product_id` 可选） | 运营 |
| POST | `/competitors` | 添加绑定 `{ own_product_id, competitor_product_id }` | 运营 |
| DELETE | `/competitors/{binding_id}` | 移除监控（soft） | 运营 |
| GET | `/competitors/{binding_id}` | 竞品详情（绑定 + 双方商品 + 最近快照） | 运营 |
| GET | `/competitors/{binding_id}/snapshots` | 价格/评分历史 | 运营 |
| GET | `/competitors/discover` | AI 自动发现竞品并创建绑定（Could；`product_id` 必填） | 运营 |
| GET | `/competitors/{product_id}/report` | 竞品分析报告：价格区间 / 排名位置 / 价格趋势 / 洞察 | 运营+ |
| POST | `/competitors/{binding_id}/refresh` | 更新单个活跃竞品最新价/评分并写快照 | 运营 |
| POST | `/competitors/batch-update` | 更新所有活跃竞品数据（快照 + 降价告警评估） | 运营 |
| GET | `/alerts` | 告警列表；筛 `is_read` / `type` / `severity` / 时间窗 | 运营+ |
| POST | `/alerts/{id}/read` | 标记已读 | 运营 / ops_lead |
| GET | `/alerts/unread-count` | 未读总数（看板 + 角标） | 登录 |
| GET | `/alerts/stats` | 告警统计：未读/已读、按 type/severity 分布 | 登录 |
| POST | `/alerts/check` | 手动触发价格监控检查（刷新活跃竞品 + 评估告警） | 运营 / ops_lead |
| GET/PATCH | `/settings/alert-threshold` | 降价阈值读写 | GET 登录；PATCH ops_lead |

#### `GET /competitors/{product_id}/report` 响应约定

对自营商品 `product_id` 生成竞品分析报告。对比集 = **自身 + 活跃绑定竞品**；若无绑定则回落同品类 Top N（按评论量）。

| 字段 | 说明 |
|------|------|
| `product` | 自营商品摘要 |
| `peer_count` | 对比集规模（含自身） |
| `price_range` | `min` / `max` / `avg` / `median` / `p25` / `p75`（仅含有价格的成员） |
| `position` | 你的位置：`price_rank`（1=最便宜）、`rating_rank`（1=评分最高）、`review_count_rank`（1=评论最多）；附 `total` |
| `price_trend` | 近 `days`（默认 30）日序列：`date` / `own_price` / `competitor_avg_price` |
| `insights` | 分析洞察：`summary` / `highlights` / `recommendations` / `risks`（LLM，失败回落启发式） |
| `peers` | 对比集成员简表（id / title / price / rating / review_count / is_self） |
| `generated_at` | 生成时间（UTC） |

**查询参数：** `days`（7–90，默认 30）、`use_ai`（默认 true）。

### 3.5 模块五 — AI Listing 优化

| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| POST | `/listing/keywords/extract/{product_id}` | 从自营+竞品标题挖掘高频词并分类 | 全角色读 |
| GET | `/listing/keywords/suggest` | 基于品类推荐热门搜索词（`category_id` 必填） | 全角色读 |
| POST | `/listing/optimize/{listing_id}` | LLM 生成优化文案并落库新 `ListingVersion` | 运营 |
| POST | `/listing/ab-test/create` | 创建 A/B：锁定 A，AI 生成 B | 运营 |
| PUT | `/listing/ab-test/{id}/complete` | 选择胜出并结束（默认可采纳为 current） | 运营 |
| GET | `/listing/ab-test/history` | A/B 历史（分页，可筛 listing_id/status） | 全角色读 |
| POST | `/listing/batch-optimize` | 批量 AI 优化：提交 `listing_ids`，返回 `task_id` | 运营 |
| GET | `/listing/batch-optimize/{task_id}` | 查询批量优化进度 | 运营 |
| GET | `/listing/{product_id}/current` | 当前生效原文/版本（无版本则合成商品原文） | 全角色读 |
| GET | `/listing/{product_id}/versions` | 版本时间线 | 全角色读 |
| GET | `/listing/{product_id}/compare` | 原文 vs 指定优化稿双栏数据 | 全角色读 |
| POST | `/listing/{product_id}/versions/{version_id}/adopt` | 采纳/回滚为当前生效并回写商品 | 运营 |
| GET | `/listings/{product_id}/current` | 当前生效原文/版本 | 运营 |
| GET | `/listings/{product_id}/versions` | 版本时间线 | 运营 |
| POST | `/listings/{product_id}/generate` | 触发 AI 生成（异步或同步+超时；可用 optimize 替代） | 运营 |
| GET | `/listings/jobs/{job_id}` | 生成任务状态（若异步） | 运营 |
| POST | `/listings/{product_id}/versions/{version_id}/adopt` | 采纳为新版本 | 运营 |
| GET | `/listings/{product_id}/compare` | 原文 vs 指定优化稿双栏数据 | 运营 |

#### 关键词挖掘约定

| 能力 | 说明 |
|------|------|
| `extract_keywords` | 语料 = 自营 `title` / `keywords` / `bullet_points` + 活跃竞品标题；英文 unigram/bi/trigram + 中文 bi/trigram；热度分 = 频次 × log(1+文档覆盖) |
| `categorize_keywords` | 四类：`core` 核心词 / `long_tail` 长尾词 / `brand` 品牌词 / `scenario` 场景词 |
| `suggest_keywords` | 品类含子类，最多采样 200 个商品标题聚合；查询参数 `category_id`（必填）、`limit`（1–100，默认 30） |
| `extract` 查询参数 | `limit`（1–100，默认 40） |

#### `POST /listing/optimize/{listing_id}` 约定

| 项 | 说明 |
|------|------|
| `listing_id` | 商品 UUID，或已有 `ListingVersion` UUID（以其为 parent） |
| LLM 输入 | 商品信息（标题/描述/卖点）+ 关键词种子 + 竞品标题 |
| LLM 输出 | Pydantic：`title` / `bullet_points`(恰 5 条) / `description` / `search_keywords` / `reason` |
| 落库 | 成功才 INSERT `listing_versions`：`source=ai_generated`、`is_current=false`、`parent_version_id` 指向基线；写 `keyword_coverage` 与 `reason` |
| 基线 | 商品尚无版本时，先写入一条 `original`（`is_current=true`）再生成优化稿 |
| 失败 | LLM/校验失败 → HTTP 502，不写残缺稿（L-04） |

#### Listing A/B 测试约定

| 接口 | 说明 |
|------|------|
| `POST /listing/ab-test/create` | Body：`listing_id`（商品）、可选 `version_a_id`、`metric`（默认 `manual`）。AI 生成 B 后写入 `listing_ab_tests`（`running`）。同 Listing 已有 running → 409 |
| `PUT /listing/ab-test/{id}/complete` | Body：`winner`=`a`\|`b`，`adopt` 默认 true。仅 `running` 可完成；采纳时事务内切换 `is_current`，AI 稿可标 `adopted` |
| `GET /listing/ab-test/history` | Query：`listing_id`、`status`、`page`、`page_size`；按 `started_at` 倒序 |

#### 批量优化约定

| 项 | 说明 |
|------|------|
| `POST /listing/batch-optimize` | Body：`listing_ids`（1–50，保序去重）。立即返回 `task_id` / `status=queued` / `total`；后台逐个调用单条 optimize |
| `GET /listing/batch-optimize/{task_id}` | 返回任务状态与每项 `pending`/`running`/`success`/`failed`；含 `progress_pct`、成功/失败计数 |
| 失败策略 | 单项失败记 `failed` + `error`，继续下一项，不中断整批 |
| 进度存储 | Redis（TTL 7 天）；Redis 不可用时回落进程内存（开发降级） |

### 3.6 模块六 — 运营看板与库存 / 部署

| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| GET | `/dashboard/overview` | 综合运营看板：商品总数、监控品类数、待审推荐数、今日告警数、最快增长品类、蓝海品类、一句话摘要；可筛 `platform_id` / `days` | 全角色读 |
| GET | `/dashboard/summary` | KPI：趋势摘要、选品进度、竞品动态数、未读告警；默认近 7 天（规划中，首页优先用 overview） | 全角色读 |
| GET | `/dashboard/market-overview` | 市场概览聚合：品类总数、商品总数、最快增长品类、最竞争品类、价格趋势、季节性洞察；可筛 `platform_id` / `days` | 全角色读 |
| GET | `/dashboard/competition` | 竞品监控看板：监控总数、今日告警、今日价格变动、Top 变动、一句话摘要 | 全角色读 |
| GET | `/dashboard/category-growth` | 品类增长率 Top N（看板柱状图；可筛 `platform_id` / `days` / `limit`，默认 limit=6） | 全角色读 |
| GET | `/dashboard/price-trend` | 近 N 日自营均价 vs 竞品均价（看板折线图；`days` 默认 7） | 全角色读 |
| GET | `/inventory` | 库存列表（每商品最新快照，分页；可筛 risk_level / keyword；空库自动模拟 seed） | 全角色读 |
| GET | `/inventory/risks` | 库存风险列表（仅 watch / critical） | 运营+ |
| GET | `/inventory/alerts` | 库存告警列表（`alerts.type=inventory_low`） | 全角色读 |
| GET | `/inventory/summary` | 库存预警摘要：总数 / critical / watch / 未读库存告警 | 全角色读 |
| PUT | `/inventory/{product_id}` | 更新库存（写入新快照并按规则触发告警） | 运营 |
| POST | `/inventory/seed-mock` | 手动生成模拟库存（已有则跳过） | 运营 |
| POST | `/inventory/check` | 重算风险并补齐库存告警 | 运营 |
| GET | `/health` | 存活探测（Docker） | 公开 |
| GET | `/ready` | 依赖就绪（DB/Redis） | 公开 |

#### `GET /inventory` / `PUT /inventory/{product_id}` 约定

| 字段 | 说明 |
|------|------|
| `quantity` | 可用库存 |
| `safety_stock` | 安全库存阈值 |
| `risk_level` | `critical`（库存 < 安全库存）/ `watch`（库存 < 2×安全库存）/ `normal` |
| `days_of_cover` | 可售天数；无日销预测时为 `null` |
| `alert_created` | 更新接口：是否新写入 `inventory_low` 告警 |

#### `GET /dashboard/overview` 响应约定

综合运营看板首页主接口（时区按服务端 UTC「今日」起算；`days` 默认 30，用于最快增长品类时间窗）。

| 字段 | 说明 |
|------|------|
| `product_total` | 商品总数（可按平台过滤） |
| `watched_category_count` | 监控品类数：`categories.is_watched = true` |
| `pending_recommendation_count` | 待审推荐数：`recommendations.status = pending` |
| `today_alert_count` | 今日告警数（全类型，`triggered_at` ≥ 当日 00:00 UTC） |
| `fastest_growing_category` | 时间窗内最新月度 `growth_rate` 最高的品类；无趋势数据时为 `null` |
| `blue_ocean_category` | 蓝海品类摘要：优先 pending 且需求/竞争机会分 ≥ 60 的最高 `score_total`；逐级回退；无推荐时为 `null` |
| `summary` | 一句话运营摘要（服务端规则拼接，非 LLM） |
| `generated_at` | 服务端聚合时间（UTC） |

#### `GET /dashboard/market-overview` 响应约定

| 字段 | 说明 |
|------|------|
| `category_total` | 品类总数（可按平台过滤） |
| `product_total` | 商品总数（可按平台过滤） |
| `fastest_growing_category` | 时间窗内最新月度 `growth_rate` 最高的品类；无趋势数据时为 `null` |
| `most_competitive_category` | 竞争强度最高品类：`product_count × (1 + avg_review_count)`；无商品时为 `null` |
| `price_trend` | 近 12 个月全市场月均价曲线（优先 `category_trends`，回退 `product_histories`） |
| `seasonality_insights` | 具备明确季节性提示的品类列表（过滤“数据不足/无明显季节性”） |
| `generated_at` | 服务端聚合时间（UTC） |

#### `GET /dashboard/category-growth` 响应约定

| 字段 | 说明 |
|------|------|
| `items` | 时间窗内各品类最新月度趋势，按 `growth_rate` 降序 Top N |
| `days` / `limit` | 请求时间窗与条数 |
| `generated_at` | 聚合时间（UTC） |

#### `GET /dashboard/price-trend` 响应约定

| 字段 | 说明 |
|------|------|
| `days` | 序列长度（默认 7） |
| `points[]` | 按日：`date` / `own_avg_price`（`product_histories` 日均）/ `competitor_avg_price`（活跃绑定快照日均）；无数据日为 `null` |
| `generated_at` | 聚合时间（UTC） |

#### `GET /dashboard/competition` 响应约定

竞品监控看板 KPI（时区按服务端 UTC「今日」起算；`top_limit` 默认 5，最大 20）。

| 字段 | 说明 |
|------|------|
| `monitored_total` | 活跃 `competitor_bindings` 总数 |
| `today_alert_count` | 今日触发的竞品相关告警数（`competitor_price_drop` / `competitor_rating_drop` / `competitor_discovered`） |
| `today_price_change_count` | 今日写入且 `price_change_pct` 非空且非 0 的快照条数 |
| `top_changes` | 今日 |Δ%| 最大的变动 Top N：竞品名、自营商品、涨跌幅、现价、方向 |
| `summary` | 一句话运营摘要（服务端拼接，非 LLM） |
| `generated_at` | 聚合时间（UTC） |

### 3.7 前端路由 ↔ API 映射（速查）

| 页面 | 主要 API |
|------|----------|
| `/` Dashboard | `GET /dashboard/overview` · `GET /dashboard/category-growth` · `GET /dashboard/price-trend`（辅：`market-overview` / `competition`） |
| `/products` | `GET /products` · `GET/POST /collection-tasks*` |
| `/trends` | `GET /trends` · `GET /trends/{id}/insight` |
| `/recommendations` | `GET /recommendations` · `/export` · `/stats` · `/blue-ocean` · `POST /generate` · `/scan` · `/{id}` · accept/reject · ai-analysis |
| `/competitors` | `GET/POST/DELETE /competitors*` · `GET /competitors/{product_id}/report` · `GET /dashboard/competition` |
| `/listing` | `POST /listing/optimize/{id}` · `GET /listing/{id}/current` · `GET /listing/{id}/versions` · `POST .../adopt` · `GET .../compare` · `POST /listing/batch-optimize` · `POST /listing/ab-test/create` · `PUT .../complete` · `GET .../history` |
| `/inventory-alerts` | `GET /inventory` · `GET /inventory/risks` · `GET /inventory/alerts` · `GET /inventory/summary` · `PUT /inventory/{product_id}` · `GET /alerts` · `POST /alerts/{id}/read` |

---

## 4. 核心数据流

### 4.1 总览：一次「选品接受」闭环（Must S-01～S-04）

```
[Browser P4]
    │  GET /api/v1/recommendations?status=pending
    ▼
[FastAPI recommendations.router]
    │  RecommendationService.list()
    ▼
[PostgreSQL recommendations + categories]
    │  JSON → 四维分 + AI 文案
    ▼
[Browser] 用户点击「接受」→ 确认 Dialog
    │  POST /api/v1/recommendations/{id}/accept
    ▼
[AuthZ] role ∈ {selection_manager, ops_lead} 否则 403
    ▼
[RecommendationService.accept()]
    │  BEGIN
    │    UPDATE status='accepted', decided_by, decided_at
    │  COMMIT
    │  可选：失效 Redis dashboard:stats 缓存
    ▼
[Response 200] { id, status, decided_by, decided_at }
    ▼
[Browser] 列表移除/改 Tab；P1 下次拉取 stats 时「已接受」+1
```

### 4.2 数据采集 → 商品库（X-04）

```
[ops_lead · P2 抽屉]
    │  POST /collection-tasks/{id}/run
    ▼
[CollectionService.enqueue_run()]
    │  写 status=running；Celery/RQ 入队
    ▼
[Worker]
    │  AmazonAdapter.fetch_category_top(category)
    │  UPSERT products + INSERT product_histories
    │  更新 progress_pct / status=success|failed
    ▼
[Redis] 可选发布 channel `collection.done`
    ▼
[Browser P2] 轮询 tasks 或刷新
    │  GET /products?q=...
    ▼
  可见新数据 + last_synced_at 刷新
```

### 4.3 竞品价格监控与自动告警（A-01 / A-02，延迟 < 30min）

```
[Cron / Worker · 每小时] 或 [POST /alerts/check]
    │  遍历 active competitor_bindings
    │  拉取竞品最新价/评分 → INSERT competitor_snapshots
    │  Δprice% = (new - prev) / prev
    │  Δrating = prev_rating - new_rating
    ▼
[AlertService.evaluate_competitor_change()]
    │  Δprice% ≤ -10% → critical + competitor_price_drop
    │  Δprice% ≤ -5%  → warning  + competitor_price_drop
    │  Δrating > 0.5  → warning  + competitor_rating_drop
    │  失效 unread-count 缓存
    ▼
[Discover 路径]
    │  新绑定 Top≤10 → info + competitor_discovered
    ▼
[Browser]
    │  GET /alerts/unread-count  → 侧栏 ●N + P1 KPI
    │  GET /alerts?is_read=false → P6/库存页「告警记录」
    │  GET /alerts/stats         → 统计分布
    │  POST /alerts/{id}/read    → is_read=true；计数 -1
```

### 4.4 Listing 生成与采纳（L-01～L-04）

```
[Browser P7]
    │  POST /listing/optimize/{listing_id}
    ▼
[ListingOptimizeService.optimize()]
    │  解析 listing_id → product + parent version
    │  无版本 → INSERT original（商品原文快照）
    │  KeywordMiningService.extract_keywords + 竞品标题
    │  LLM（结构化 JSON：title / bullet_points×5 / description / search_keywords / reason）
    │  成功 → INSERT listing_versions (source=ai_generated, is_current=false, parent_version_id)
    │  失败 → 不写库；返回可重试错误（原文不变）
    ▼
[Browser] GET compare → 双栏原文 | 优化稿
    │  POST .../versions/{id}/adopt
    ▼
[事务]
    │  旧 is_current=false
    │  新 version source 可标 adopted；is_current=true
    │  可选回写 products.title/description/keywords
    ▼
  版本时间线可回看；刷新后仍生效
```

### 4.5 运营看板汇总（单次页面加载）

```
[Browser GET /]
    │  主请求：
    │    GET /dashboard/overview?platform_id=&days=30
    │  可选并行：
    │    GET /dashboard/category-growth
    │    GET /alerts/unread-count
    ▼
[DashboardService.get_overview]
    │  products COUNT
    │  categories COUNT WHERE is_watched
    │  recommendations COUNT WHERE pending
    │  alerts COUNT WHERE triggered_at ≥ today
    │  category_trends 近窗 Top 增长
    │  recommendations 蓝海 Top1（门槛同 blue-ocean）
    │  规则拼接 summary
    ▼
  < 2s 可交互目标：聚合索引；冷启动采集不计入 SLA
```

### 4.6 AI 趋势解读（P3）

```
GET /trends?category_id=&from=&to=
    → 读 category_trends 月度序列（价格分位 + growth_rate）

GET /trends/{category_id}/insight
    → 若 ai_insight 未过期：直接返回
    → 否则：拼月度统计 → OpenAI → 写回 ai_insight / ai_verdict → 返回
```

### 4.7 评分算法（模块三 · 逻辑契约）

实现类：`SelectionScorer`（`app/services/selection_scorer.py`）。  
各维度满分 100，加权汇总为综合分（Could：主管自定义权重后重算）：

```
score_total = 0.30*demand + 0.20*competition + 0.25*margin + 0.25*trend
```

| 维度 | 权重 | 主要输入 | 方向约定 |
|------|------|----------|----------|
| demand（市场需求） | 30% | 月搜索量代理（评论总量 / `sample_size`）+ `category_trends.growth_rate` | 越高越好 |
| competition（竞争强度） | 20% | 同类商品数量、评分分布（≥4.5 头部占比） | **机会分**：竞争越小 → 分越高 |
| margin（利润空间） | 25% | 平均售价 − 平均成本估算（MVP：成本 = 均价 × 55% 或参考 `price_p25`） | 毛利率越高越好 |
| trend（趋势方向） | 25% | 价格趋势（历史月均价斜率）+ 销量代理（评论增量）+ `growth_rate` | 上升趋势得分高 |

**归一化：** 各维度先算原始信号，再钳制到 `[0, 100]`，`score_total` 保留两位小数。  
**落库：** `POST /recommendations/generate` 调用 Scorer → 幂等更新同品类 `pending` 行（无则 INSERT）→ 返回结果。  
**蓝海发现：** `GET /recommendations/blue-ocean` 实时调用 `SelectionScorer`，筛「需求高 + 竞争机会高」品类，按蓝海指数（`score_total`）降序返回评分详情与推荐理由。  
AI 选品深度分析由 `POST /recommendations/{id}/ai-analysis` 同步触发（MVP），写入 `reason`，并同步摘要到 `ai_blue_ocean_text`。批量打分接口不阻塞等待 LLM。

---

## 5. 横切设计

### 5.1 鉴权与 401

- JWT access token（短 TTL）+ 可选 refresh。
- 并发 401：**single-flight** 刷新；失败则清本地态，`replace` 到 `/login?returnUrl=`（安全校验同域相对路径，对齐 INTERACTION）。

### 5.2 缓存（Redis）

| Key 模式 | TTL | 用途 |
|----------|-----|------|
| `dashboard:summary:{role}:{range}` | 60s | P1 KPI |
| `alerts:unread:global` | 30s | 角标 |
| `trends:insight:{category_id}` | 24h | AI 解读 |
| `lock:collection:{task_id}` | 任务时长 | 防重复跑 |
| `lock:competitor:snap` | 短 | 快照互斥 |
| `lock:selection:scan` | 3600s | 全品类选品扫描互斥 |

### 5.3 异步任务

| 任务 | 触发 | 成功标准 |
|------|------|----------|
| 品类采集 | 定时 / 手动 | 完成率 > 95%（PRD） |
| 竞品快照 | 每小时 | 告警延迟 < 30min |
| 趋势月算 | 每日 | 写入 category_trends |
| 选品全量扫描 | 每日 03:30（ARQ Cron）/ `POST /recommendations/scan` | 活跃品类评分完成；跳过分差≤20% 的已有推荐；新推荐可 webhook |
| 选品打分（小批量） | `POST /recommendations/generate` | 产出 pending 推荐 |
| Listing 生成 | 用户点击 | 超时不落残缺稿 |

**Worker：** `arq app.workers.settings.WorkerSettings`（依赖 Redis）。  
**Webhook（预留）：** `POST {SELECTION_WEBHOOK_URL}`，事件 `recommendation.created`；未配置 URL 时 no-op。

### 5.4 Docker 部署（模块六）

```
services:
  api          # FastAPI uvicorn（Dockerfile 多阶段）
  worker       # ARQ worker（复用 api 镜像，含 Cron 日批选品扫描）
  db           # PostgreSQL 15（volume: hpzx_pgdata）
  redis        # Redis 7（volume: hpzx_redisdata）
  frontend     # Nginx + Vue 静态；/api → api:8000
```

**编排文件：** 根目录 `Dockerfile` · `docker-compose.yml` · `.env`（参考 `.env.example`）· `frontend/Dockerfile` · `frontend/nginx.conf`。

**探针：**
- `GET /api/v1/health` — 进程存活
- `GET /api/v1/ready` — DB + Redis 就绪（503 表示未就绪）

**一键启动：**

```bash
cp .env.example .env   # 修改 SECRET_KEY / POSTGRES_PASSWORD
docker compose up -d --build
# 前端 http://localhost  · API http://localhost:8000/api/v1/health
```

### 5.5 设计签收遗留对实现的约束

| 签收项 | 对 SDD/实现的要求 |
|--------|-------------------|
| P2「所属品类」列 ❌ | API `GET /products` **必须**返回 `category`（id+name）；前端表头必显 |
| 未读角标 ⚠️ | 只调 `GET /alerts/unread-count`，禁止多处 Mock 写死 |
| 选品/告警/Listing/采集持久化 ⚠️ | 以本节状态机与事务为准，刷新后不回退 |

---

## 6. 非功能落点

| PRD 要求 | 设计落点 |
|----------|----------|
| 页面核心区 < 2s | 看板聚合缓存；列表强制分页；避免 N+1 |
| ≥1000 行可分页 | `LIMIT/OFFSET` 或 keyset；不一次渲染 1000 DOM |
| 375px 不破版 | 前端职责；Listing 双栏改上下堆叠 |
| 告警 < 30min | 竞品 Worker ≤ 1h，关键路径可 15–30min 补扫 |
| 工作日可用率 > 99% | 健康检查 + 无单点（DB/Redis 可后续托管） |

---

## 7. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-08-06 | 初稿：库表、模块依赖、API、核心数据流；对齐 PRD v1.1 与 DESIGN-SIGNOFF |

---

## 附录 A：枚举汇总

```text
UserRole:            operator | selection_manager | ops_lead | boss
Platform:            amazon | shopee
CollectionFrequency: hourly | daily | manual
CollectionStatus:    pending | running | success | failed
RecommendationStatus: pending | accepted | rejected
AlertType:           competitor_price_drop | competitor_rating_drop | competitor_discovered | inventory_low | collection_failed
AlertSeverity:       info | warning | critical   # 对应业务 low | medium | high
ListingSource:       original | ai_generated | adopted
KeywordCategory:     core | long_tail | brand | scenario
ABTestStatus:        running | completed | cancelled
ABTestMetric:        manual | ctr | conversion | keyword_coverage
ABTestWinner:        a | b
BatchOptimizeStatus: queued | running | completed
BatchOptimizeItemStatus: pending | running | success | failed
TrendVerdict:        growing | shrinking | stable
InventoryRisk:       normal | watch | critical
```

## 附录 B：文档索引

| 文档 | 职责 |
|------|------|
| `PRD.md` | 做什么、验收 Must |
| `DESIGN-SIGNOFF.md` | 设计签收与 IA 定稿 |
| `FLOWS.md` | 用户旅程与状态机 |
| `SDD.md`（本文） | 怎么建库、怎么拆模块、怎么调 API |
| `DESIGN.md` / `COMPONENT-SPEC.md` | 视觉与组件 |
