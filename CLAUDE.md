# 智能选品与跨境运营中台 — CLAUDE.md

> 产品名：**华普智选** | 开发前必读：`docs/DESIGN-SIGNOFF.md` · `docs/SDD.md` · `README.md`

## 产品一句话

数据驱动选品 + AI 自动化运营的跨境中台：采集 → 趋势 → 蓝海选品 → 竞品告警 → Listing 优化 → 运营看板 / 库存预警，Docker 可一键交付。

## 技术栈

- 后端框架：FastAPI（Python 3.11+）
- 数据库：PostgreSQL 15（开发可用 SQLite）
- ORM：SQLAlchemy 2.0（声明式语法）
- 缓存 / 队列：Redis + ARQ（轻量 Worker / Cron）
- AI：OpenAI 兼容 API（支持千问 / DeepSeek 等；默认 `LLM_MODE=mock`）
- 数据采集：httpx · 数据源工厂（mock / dummyjson / amazon / shopee；`fakestore` 兼容映射到 DummyJSON）
- 前端：Vue 3 + Vite + TypeScript + Element Plus + ECharts + Pinia
- 部署：Docker + docker-compose（api / worker / db / redis / frontend）

## 六大业务模块（与 PRD / SDD 对齐）

| # | 模块 | 前端路由 | 后端前缀（节选） |
|---|------|----------|------------------|
| 1 | 数据接入与商品管理 | `/products` | `/api/v1/products` · `/sync` · `/categories` |
| 2 | 市场趋势分析 | `/trends` | `/api/v1/trends` |
| 3 | 智能选品推荐 | `/recommendations` | `/api/v1/recommendations` |
| 4 | 竞品监控与预警 | `/competitors` · `/inventory-alerts` | `/api/v1/competitors` · `/alerts` |
| 5 | AI Listing 优化 | `/listing` | `/api/v1/listing` |
| 6 | 运营看板与部署 | `/` · 库存 Tab | `/api/v1/dashboard` · `/inventory` · Docker |

完整契约：`docs/SDD.md` §3；进度：`progress.md`；决策：`docs/decisions.md`（DD-xxx）。

## 项目结构（AI 生成时遵守）

```
project-root/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口，注册路由
│   │   ├── config.py            # 配置管理（从 .env 读取）
│   │   ├── database.py          # 数据库连接
│   │   ├── models/              # SQLAlchemy 模型
│   │   ├── schema/              # Pydantic schemas（注意目录名 schema）
│   │   ├── routers/             # API 路由
│   │   ├── services/            # 业务逻辑
│   │   ├── workers/             # ARQ 任务与 WorkerSettings
│   │   └── utils/               # 工具函数
│   ├── scripts/                 # docker_entrypoint 等
│   ├── tests/
│   └── requirements.txt
├── frontend/                    # Vue 3 + Vite
│   ├── src/
│   │   ├── api/                 # axios 封装
│   │   ├── router/              # 路由（含守卫）
│   │   ├── stores/              # Pinia 状态
│   │   ├── views/               # 页面
│   │   ├── components/          # 组件
│   │   └── layouts/AppShell.vue # 全局布局壳
│   ├── nginx.conf               # 生产反代 /api
│   └── Dockerfile
├── docs/                        # 设计阶段全部产出，写前端前必读
│   ├── PRD.md · DESIGN.md · SDD.md · FLOWS.md
│   ├── INTERACTION.md · COMPONENT-SPEC.md · DESIGN-SIGNOFF.md
│   ├── decisions.md · prototypes/images/
├── .cursor/rules/               # Skill 目录
├── CLAUDE.md · README.md · progress.md
├── .env.example
├── docker-compose.yml
└── Dockerfile                   # 后端 / Worker 多阶段镜像
```

## 本地快速启动（开发）

1. `cp .env.example .env`（开发可用 `DB_TYPE=sqlite`，需本机 Redis）
2. 后端：`cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000`
3. 前端：`cd frontend && npm install && npm run dev` → http://localhost:5173
4. 登录种子账号：`zhangsan@126.com` / `Zs123456`
5. API 文档：http://localhost:8000/docs · 探针：`/api/v1/health` · `/api/v1/ready`

Worker（可选）：`cd backend && arq app.workers.settings.WorkerSettings`

Docker：`docker compose up -d --build` → 前端 http://localhost · API :8000（详见 `README.md` / SDD §5.4）

## 默认端口与账号

| 用途 | 值 |
|------|-----|
| 前端 Vite | `5173`（代理 `/api` → `8000`） |
| 后端 uvicorn | `8000` |
| Compose 前端 Nginx | `80` |
| PostgreSQL / Redis（Compose） | `5432` / `6379` |
| 初始管理员 | `zhangsan@126.com` / `Zs123456`（首次创建后请改密） |

## 代码规范

- 所有模型用 SQLAlchemy 2.0 声明式语法
- Pydantic v2 的 `model_validate` / `model_dump`
- FastAPI 路由统一前缀 `/api/v1`
- 每个功能模块：models + schema + routers + services 四层
- API 返回统一格式：`{"code": 200, "data": ..., "message": "ok"}`
- 错误处理：HTTPException + 自定义错误码
- 全局异常处理器统一兜底：未捕获异常返回 `{"code": 500, "data": null, "message": "服务器内部错误"}`，不泄露堆栈
- CORS 白名单：开发默认 `http://localhost:5173`；Docker 需含前端来源（见 `.env.example`）
- 全局请求日志中间件：记录方法 / 路径 / 状态码 / 耗时
- 环境变量从 `.env` 读取，不做硬编码
- 前端组件用 Element Plus，页面布局遵守 `docs/DESIGN.md`

## LLM 调用

- 使用 `app/services/llm_client.py`（从 05 项目 Skill 生成）
- `LLM_MODE=mock`（默认） / `openai`
- 支持 `DASHSCOPE_API_KEY` / `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` 自动识别
- 密钥与完整 Prompt 禁止写入日志或 API 响应

## 设计文档引用（写前端代码前必读）

- `docs/DESIGN.md` — 视觉规范（颜色/间距/字体/组件）
- `docs/INTERACTION.md` — 交互规范（三态/反馈/动效）
- `docs/COMPONENT-SPEC.md` — 组件规格（评分圆环/告警横条/双栏对比）
- `docs/prototypes/images/0X-xxx.png` — 对应页面原型图，照着实现

## Skill 引用

本项目复用 05 项目沉淀的以下 Skill：

- `.cursor/rules/llm-client-skill.md` — LLM 调用代码模板
- `.cursor/rules/crud-routes-skill.md` — CRUD 接口模板
- `.cursor/rules/review-checklist.md` — AI 生成后审查再 commit
- `.cursor/rules/readme-skill.md` — README / API 文档生成
- `.cursor/rules/taste-skill/` — 前端审美规范（间距/排版/配色）
- `.cursor/rules/awesome-design-md/` — 设计系统模板

上下文进度文件（勿重建，只更新）：

- `progress.md` — 已完成 / 未完成
- `docs/decisions.md` — 重要设计决策（DD）
- 若存在 `task_plan.md` — 当前任务步骤

## 数据库约定

- 业务主键多为 **UUID**（部分时序表用 BIGSERIAL，如竞品快照）
- 表普遍含 `created_at` / `updated_at`；软删除按模块用 `is_active` 等字段
- 复合索引用 `__table_args__` 定义
- 表结构变更必须走 Alembic 迁移（`alembic revision --autogenerate` → `upgrade head`），禁止手动改表
- 开发环境非 production 时 `init_db()` 可 `create_all`；Compose 入口也会 bootstrap（Alembic 落地前）

## 安全约定

- 密码用 bcrypt 哈希存储，禁止明文
- 登录接口防爆破：同一账号或 IP 连续失败达阈值锁定一段时间（见 `.env`）
- 启动时校验必填环境变量（fail-fast），缺哪个报哪个
- 生产环境禁止使用默认 `SECRET_KEY` 占位值
- 密钥、密码、完整 Prompt 禁止出现在日志和响应中

## Git 规范

- 分支名：`feat/xxx`、`fix/xxx`
- commit message：`<type>: <描述>`
- 每个模块完成后独立 commit

## AI 协作提示

1. 新对话先读 `progress.md` + `docs/decisions.md` + 相关 SDD 章节
2. 写前端先读 DESIGN / INTERACTION / 对应原型图，再按 taste-skill
3. 新接口写完后回写 `docs/SDD.md`，重要取舍记入 `docs/decisions.md`
4. 生成代码后用 `review-checklist.md` 自检
5. 用户未明确要求时不要主动 commit / push
