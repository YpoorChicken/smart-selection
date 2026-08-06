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
| ai_blue_ocean_text | TEXT | | AI 蓝海说明 |
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
| type | ENUM | NOT NULL | `competitor_price_drop` / `inventory_low` / `collection_failed` 等 |
| severity | ENUM | DEFAULT 'warning' | `info` / `warning` / `critical` |
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
| is_current | BOOLEAN | DEFAULT false | 当前生效版本 |
| created_by | UUID | FK → users.id NULL | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| parent_version_id | UUID | FK → listing_versions.id NULL | 基于哪版生成 |

**唯一约束：** `(product_id, version_no)`  
**规则：** 采纳时事务内：旧 `is_current=false`，新版 `is_current=true`；生成失败不写残缺稿（L-04）。

---

#### 1.2.13 `inventory_snapshots` — 库存快照（模块六 Should）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| product_id | UUID | FK → products.id | |
| sku | VARCHAR(64) | | |
| quantity | INT | NOT NULL | |
| reorder_point | INT | | 预警阈值 |
| predicted_daily_sales | Numeric(10,2) | | 销量预测 |
| days_of_cover | Numeric(8,2) | | 可售天数 |
| risk_level | ENUM | | `normal` / `watch` / `critical` |
| recorded_at | TIMESTAMPTZ | NOT NULL | |

**用途：** `/inventory-alerts`「库存风险」Tab；P1 Should 库存摘要。

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
| PATCH | `/products/{id}/watch` | 标记/取消自营关注 | 运营 |
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
| GET | `/recommendations` | 列表；筛 status / category / score | 登录；决策按钮按角色 |
| GET | `/recommendations/{id}` | 四维得分 + AI 蓝海说明 | 登录 |
| POST | `/recommendations/{id}/accept` | 接受；写 decided_by/at | selection_manager / ops_lead |
| POST | `/recommendations/{id}/reject` | 拒绝；可选 reason | 同上 |
| POST | `/recommendations/generate` | 触发批量打分任务（内部/主管） | ops_lead |
| GET | `/recommendations/stats` | 待处理/已接受/已拒绝计数（供 P1） | 登录 |

### 3.4 模块四 — 竞品监控与预警

| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| GET | `/competitors` | 某自营商品下已绑定竞品列表 | 运营 |
| POST | `/competitors` | 添加绑定 `{ own_product_id, competitor_product_id }` | 运营 |
| DELETE | `/competitors/{binding_id}` | 移除监控（soft） | 运营 |
| GET | `/competitors/{binding_id}/snapshots` | 价格/评分历史 | 运营 |
| GET | `/competitors/discover` | 自动发现候选（Could） | 运营 |
| GET | `/alerts` | 告警列表；筛 unread / type / time | 运营+ |
| POST | `/alerts/{id}/read` | 标记已读 | 运营 / ops_lead |
| GET | `/alerts/unread-count` | 未读总数（看板 + 角标） | 登录 |
| GET/PATCH | `/settings/alert-threshold` | 降价阈值读写 | GET 登录；PATCH ops_lead |

### 3.5 模块五 — AI Listing 优化

| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| GET | `/listings/{product_id}/current` | 当前生效原文/版本 | 运营 |
| GET | `/listings/{product_id}/versions` | 版本时间线 | 运营 |
| POST | `/listings/{product_id}/generate` | 触发 AI 生成（异步或同步+超时） | 运营 |
| GET | `/listings/jobs/{job_id}` | 生成任务状态（若异步） | 运营 |
| POST | `/listings/{product_id}/versions/{version_id}/adopt` | 采纳为新版本 | 运营 |
| GET | `/listings/{product_id}/compare` | 原文 vs 指定优化稿双栏数据 | 运营 |

### 3.6 模块六 — 运营看板与库存 / 部署

| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| GET | `/dashboard/summary` | KPI：趋势摘要、选品进度、竞品动态数、未读告警；默认近 7 天 | 全角色读 |
| GET | `/dashboard/category-growth` | 品类增长率 Top N | 全角色读 |
| GET | `/inventory/risks` | 库存风险列表 | 运营+ |
| GET | `/inventory/summary` | 库存预警摘要（P1 Should） | 全角色读 |
| GET | `/health` | 存活探测（Docker） | 公开 |
| GET | `/ready` | 依赖就绪（DB/Redis） | 公开 |

### 3.7 前端路由 ↔ API 映射（速查）

| 页面 | 主要 API |
|------|----------|
| `/` Dashboard | `GET /dashboard/*` · `GET /alerts/unread-count` · `GET /recommendations/stats` |
| `/products` | `GET /products` · `GET/POST /collection-tasks*` |
| `/trends` | `GET /trends` · `GET /trends/{id}/insight` |
| `/recommendations` | `GET/POST /recommendations*` |
| `/competitors` | `GET/POST/DELETE /competitors*` |
| `/listing` | `POST .../generate` · `POST .../adopt` · `GET .../compare` |
| `/inventory-alerts` | `GET /alerts` · `POST /alerts/{id}/read` · `GET /inventory/risks` |

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

### 4.3 竞品降价告警（A-01 / A-02，延迟 < 30min）

```
[Cron / Worker · 每小时]
    │  遍历 active competitor_bindings
    │  拉取竞品最新价 → INSERT competitor_snapshots
    │  Δ% = (new - prev) / prev
    ▼
[AlertService.evaluate()]
    │  IF Δ% <= -threshold (default 5%)
    │    INSERT alerts (type=competitor_price_drop, is_read=false)
    │  失效 unread-count 缓存
    ▼
[Browser]
    │  GET /alerts/unread-count  → 侧栏 ●N + P1 KPI
    │  GET /alerts?is_read=false → P6/库存页「告警记录」
    │  POST /alerts/{id}/read    → is_read=true；计数 -1
```

### 4.4 Listing 生成与采纳（L-01～L-04）

```
[Browser P7]
    │  POST /listings/{product_id}/generate
    ▼
[ListingService.generate()]
    │  读 products 当前文案 + 品类关键词上下文（trends/competitors 摘要）
    │  OpenAI Chat Completion（结构化 JSON：title/bullets/description/keywords）
    │  成功 → INSERT listing_versions (source=ai_generated, is_current=false)
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
    │  并行：
    │    GET /dashboard/summary?range=7d&platform=amazon
    │    GET /dashboard/category-growth
    │    GET /alerts/unread-count
    ▼
[DashboardService]
    │  recommendations GROUP BY status
    │  alerts COUNT unread
    │  competitor_snapshots 近 24h 变价次数
    │  category_trends 近窗 Top 增长
    │  （Should）inventory 风险摘要
    │  Redis GET/SET dashboard:summary:{user}:{range} TTL 60s
    ▼
  < 2s 可交互目标：缓存命中 + 聚合索引；冷启动采集不计入 SLA
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

综合分默认等权（Could：主管自定义权重后重算）：

```
score_total = 0.25*demand + 0.25*competition + 0.25*margin + 0.25*trend
```

| 维度 | 主要输入 | 方向约定 |
|------|----------|----------|
| demand | 品类搜索热度代理：评论增量、BSR 分布 | 越高越好 |
| competition | 卖家密度、头部评分集中度 | 映射为「机会分」：竞争弱 → 分高 |
| margin | 价格带中位 − 预估成本代理（MVP 可用品类价差） | 越高越好 |
| trend | `category_trends.growth_rate` + 季节性 | 增长为正 |

AI 蓝海文案在分数落库后异步生成，写入 `ai_blue_ocean_text`；列表接口不阻塞等待 OpenAI。

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

### 5.3 异步任务

| 任务 | 触发 | 成功标准 |
|------|------|----------|
| 品类采集 | 定时 / 手动 | 完成率 > 95%（PRD） |
| 竞品快照 | 每小时 | 告警延迟 < 30min |
| 趋势月算 | 每日 | 写入 category_trends |
| 选品打分 | 主管触发 / 日批 | 产出 pending 推荐 |
| Listing 生成 | 用户点击 | 超时不落残缺稿 |

### 5.4 Docker 部署（模块六）

```
services:
  api          # FastAPI uvicorn
  worker       # Celery/RQ
  beat         # 定时
  db           # PostgreSQL
  redis        # Redis
  web          # Nginx + Vue 静态（可选同栈）
```

`/health`、`/ready` 供编排探针；一键 `docker compose up`。

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
AlertType:           competitor_price_drop | inventory_low | collection_failed
AlertSeverity:       info | warning | critical
ListingSource:       original | ai_generated | adopted
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
