# 智能选品与跨境运营中台 — CLAUDE.md

> 产品名：华普智选 | 开发前必读：docs/DESIGN-SIGNOFF.md · docs/SDD.md

## 技术栈
- 后端框架：FastAPI（Python 3.11+）
- 数据库：PostgreSQL 15（开发可用 SQLite）
- ORM：SQLAlchemy 2.0（声明式语法）
- 缓存：Redis
- AI：OpenAI 兼容 API（支持 DeepSeek 等）
- 数据采集：httpx / aiohttp
- 任务队列：Redis + ARQ（轻量）
- 前端：Vue 3 + Vite + Element Plus + ECharts + Pinia
- 部署：Docker + docker-compose

## 项目结构（AI 生成时遵守）
project-root/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口，注册路由
│   │   ├── config.py            # 配置管理（从 .env 读取）
│   │   ├── database.py          # 数据库连接
│   │   ├── models/              # SQLAlchemy 模型
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── routers/             # API 路由
│   │   ├── services/            # 业务逻辑
│   │   └── utils/               # 工具函数
│   ├── tests/
│   └── requirements.txt
├── frontend/                    # Vue 3 + Vite
│   └── src/
│       ├── api/                 # axios 封装
│       ├── router/              # 路由（含守卫）
│       ├── stores/              # Pinia 状态
│       ├── views/               # 页面
│       ├── components/          # 组件
│       └── layouts/AppShell.vue # 全局布局壳
├── docs/                        # 设计阶段全部产出，写前端前必读
│   ├── PRD.md
│   ├── DESIGN.md
│   ├── SDD.md
│   ├── FLOWS.md
│   ├── INTERACTION.md
│   ├── COMPONENT-SPEC.md
│   ├── DESIGN-SIGNOFF.md
│   └── prototypes/
├── .cursor/rules/               # Skill 目录
├── CLAUDE.md
├── .env.example
├── docker-compose.yml
└── Dockerfile

## 代码规范
- 所有模型用 SQLAlchemy 2.0 声明式语法
- Pydantic v2 的 model_validate / model_dump
- FastAPI 路由统一前缀 /api/v1
- 每个功能模块：models + schemas + routers + services 四层
- API 返回统一格式：{"code": 200, "data": ..., "message": "ok"}
- 错误处理：HTTPException + 自定义错误码
- 全局异常处理器统一兜底：未捕获异常返回 {"code": 500, "data": null, "message": "服务器内部错误"}，不泄露堆栈
- CORS 白名单：http://localhost:5173（前端开发地址）
- 全局请求日志中间件：记录方法 / 路径 / 状态码 / 耗时
- 环境变量从 .env 读取，不做硬编码
- 前端组件用 Element Plus，页面布局遵守 docs/DESIGN.md

## LLM 调用
- 使用 app/services/llm_client.py（从 05 项目 Skill 生成）
- LLM_MODE=mock（默认） / openai
- 支持 DEEPSEEK_API_KEY 自动识别

## 设计文档引用（写前端代码前必读）
- docs/DESIGN.md — 视觉规范（颜色/间距/字体/组件）
- docs/INTERACTION.md — 交互规范（三态/反馈/动效）
- docs/COMPONENT-SPEC.md — 组件规格（评分圆环/告警横条/双栏对比）
- docs/prototypes/images/0X-xxx.png — 对应页面原型图，照着实现

## Skill 引用
本项目复用 05 项目沉淀的以下 Skill：
- .cursor/rules/llm-client-skill.md — 所有 LLM 调用代码的模板
- .cursor/rules/crud-routes-skill.md — 所有 CRUD 接口的模板
- .cursor/rules/review-checklist.md — 每轮 AI 生成代码后先审查再 commit
前端视觉规范：
- .cursor/rules/taste-skill/SKILL.md — 前端审美规范（间距/排版/配色）
- .cursor/rules/awesome-design-md/ — 设计系统模板

## 数据库约定
- 所有表有 id (Integer PK)、created_at、updated_at
- 软删除用 is_active 字段
- 复合索引用 __table_args__ 定义
- 表结构变更必须走 Alembic 迁移（alembic revision --autogenerate → upgrade head），禁止手动改表

## 安全约定
- 密码用 bcrypt 哈希存储，禁止明文
- 登录接口防爆破：同一账号或 IP 连续失败 5 次，锁定 15 分钟
- 启动时校验必填环境变量（fail-fast），缺哪个报哪个
- 密钥、密码、完整 Prompt 禁止出现在日志和响应中

## Git 规范
- 分支名：feat/xxx、fix/xxx
- commit message：<type>: <描述>
- 每个模块完成后独立 commit