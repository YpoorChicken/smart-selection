# Skill: AI 生成代码审查模板

## 元信息
- 版本：v1.0
- 来源：04-AI代码审查与测试.md
- 描述：AI 改完代码后，按「终端冒烟 → pytest → AI 审查」三步走

## 使用流程
### 第 1 步：终端冒烟
python -c "from app.main import app; print('import ok')"
pytest --collect-only -q
uvicorn app.main:app --reload
curl http://localhost:8000/health

### 第 2 步：跑测试
pytest -v

### 第 3 步：AI 审查（模板 3）

## 模板 3：一键审查（每次改代码默认用这个）
你是 {{项目名}} 的代码审查员。请对本次变更做审查，只输出报告，不要直接改代码。

项目约束：
{{技术栈列表}}
参考项目 CLAUDE.md

前提：用户已在终端跑过冒烟和 pytest 且通过。不要重复检查能否 import 或能否启动。

只查以下项：
1. 未被执行到的 import、虚构模块、requirements.txt 漏包
2. Pydantic v1 旧语法（orm_mode、@validator 等）
3. 路由是否还缺 401/403/404/409/422（现有 pytest 未覆盖的）

输出格式：
- 必须修
- 建议修
- 可忽略

本次变更：
（已 @ 引用的文件或 git diff）

## 模板 2：错误处理与写测试（新路由、还没有 pytest 时用）
你是 FastAPI 后端 QA。请审查以下 API 代码的错误路径覆盖。

检查项（每条路由逐项核对）：
- 资源不存在 → 应 404，而非 500 或 None
- 未登录 → 应 401
- 无权限 → 应 403
- 冲突/重复 → 应 409
- 参数校验失败 → 应 422
- 是否缺少 try/except 或 HTTPException

输出两部分：
1. 缺失清单表格：路由 | 缺失场景 | 当前行为 | 期望 status_code
2. 建议 pytest 用例列表：用例名 | 请求 | 断言 status_code

然后按用例列表生成 tests/ 下测试文件，使用 conftest 的 client 和 auth_headers。
每条测试断言具体的 response.status_code。

待审查内容：
（@ 引用的路由文件或 git diff）

## 模板 1：导入与版本检查（备用）
你是 Python 静态审查专家。请审查以下代码，只输出问题列表，不要直接改代码。

项目约束（违反即报问题）：
- Python 3.11+
- FastAPI 0.104+
- Pydantic v2：禁止 orm_mode、@validator；应使用 from_attributes、@field_validator
- SQLAlchemy 2.0+
- JWT 只用 pyjwt；禁止 fastapi.jwt 等虚构模块

检查项：
1. 每个 import 是否可能不存在（列出可疑项及理由）
2. 是否使用了 requirements.txt 中未声明的第三方包
3. 是否使用了上述旧版语法

输出格式（Markdown 表格）：
| 编号 | 位置 | 类型 | 描述 | 修复建议 |

待审查内容：
（@ 引用的文件或 git diff）

## 三个模板怎么选
| 什么时候 | 用哪个 |
|----------|--------|
| 每次改完代码，第三斧审查 | 模板 3 |
| 新路由，还没有 pytest | 模板 2 |
| 专攻 import/旧语法，模板 3 看不清 | 模板 1（少见） |