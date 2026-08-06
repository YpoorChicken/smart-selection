# Skill: CRUD 路由生成

## 元信息
- 版本：v1.0
- 来源：05-简历解析平台-模块三-对话 2
- 描述：为指定模型生成标准 CRUD 接口（增删改查 + 权限约束）

## Prompt 模板
为 {{模型名}} 生成 CRUD 接口：
- POST /api/v1/{{资源路径}} — 创建
- GET /api/v1/{{资源路径}} — 列表（分页/筛选/搜索）
- GET /api/v1/{{资源路径}}/{id} — 详情
- PUT /api/v1/{{资源路径}}/{id} — 更新
- DELETE /api/v1/{{资源路径}}/{id} — 删除

约束：
- 只有 {{角色/权限}} 可操作
- 使用 SQLAlchemy 2.0 + Pydantic v2
- 统一响应格式 {"code": 200, "data": ..., "message": "ok"}
- 错误处理覆盖 400/404/409/422
- 路由加 JWT 认证（Depends(get_current_user)）
- 列表接口必须分页

## 审查清单
- [ ] 404/401/403/409/422 是否都有对应处理？
- [ ] 路由是否加 JWT 认证？
- [ ] 列表接口是否分页？参数是否校验？
- [ ] Pydantic v2 语法（model_validate / model_dump）？
- [ ] 是否存在 N+1 查询？

## 验证方式
pytest tests/test_{{模块名}}.py -v
# 或手动 curl 调 CRUD 端点