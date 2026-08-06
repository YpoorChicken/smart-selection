# Skill: 数据模型生成

## 元信息
- 版本：v1.0
- 来源：05-简历解析平台-模块一/二/三-模型对话
- 描述：根据 SDD 的数据模型章节，生成 SQLAlchemy 2.0 模型

## Prompt 模板
请为 {{业务模块}} 创建数据模型。

新建模型 {{模型名}}：
- {{字段1}}: {{类型}}（{{约束}}）
- {{字段2}}: {{类型}}（{{约束}}）
- 外键关系：{{关系描述}}（{{级联规则}}）

约束：
- 使用 SQLAlchemy 2.0 声明式语法
- 所有表有 id (Integer PK)、created_at、updated_at
- JSON 字段在 SQLite 下用 Text 存储（SQLite 不支持 JSON 列）
- 新增字段为空时已有数据不报错（nullable=True）
- 级联删除用 cascade="all, delete-orphan"
- 与 docs/SDD.md 的数据模型一致

## 审查清单
- [ ] JSON 字段存 Text 而不是 JSON 类型？（SQLite 不支持 JSON 列）
- [ ] 已有数据迁移会不会失败？（nullable=True + 默认值）
- [ ] 日志/子表有没有做级联删除？（cascade="all, delete-orphan"）
- [ ] 外键指向的表和字段是否存在？
- [ ] 字段类型是否与 SDD 一致？（JSON vs Text、Float vs Integer）

## 验证方式
启动服务，确认表结构已创建
pytest tests/test_models.py -v