# Skill: LLM 调用客户端生成

## 元信息
- 版本：v1.0
- 来源：05-简历解析平台-模块一-对话 3
- 描述：创建通用 LLM 调用客户端，支持 OpenAI 兼容 API / Ollama，带 Mock/Real 切换

## Prompt 模板
请创建一个 LLM 调用客户端，用于调用 {{API兼容服务}} 进行 {{任务描述}}。

文件：app/services/{{文件名}}

要求：
1. 支持 {{支持的API列表}}（通过配置切换，base_url 和 api_key 从环境变量读取）
2. 支持 LLM_MODE 切换：
   - LLM_MODE=mock：返回写死的示例 JSON（字段与真实响应一致）
   - LLM_MODE=openai：真实调用
   - 不配 Key 时自动回落 mock，不抛异常
3. 传入 {{输入数据}}，LLM 返回 {{输出格式说明}}
4. 用 Pydantic v2 模型约束 LLM 输出格式：

class {{输出模型名}}(BaseModel):
    {{字段1}}: {{类型}} = {{默认值}}
    {{字段2}}: {{类型}} = {{默认值}}

5. 超时时间 {{超时秒数}} 秒，失败重试 {{重试次数}} 次
6. 记录 token 消耗（如有）
7. JSON 解析失败时返回明确错误或降级，不要 silent fail
8. 输出完整代码，不要省略

约束：Python 3.11+，Pydantic v2 语法

## 审查清单
- [ ] API Key 是否从环境变量读取？无硬编码
- [ ] 超时时间是否合理？（LLM 通常 30–60 秒）
- [ ] LLM 返回非 JSON 时是否有 try/except + 降级
- [ ] 重试是否有上限？避免无限循环
- [ ] 输出 Pydantic 模型是否与业务字段一致
- [ ] Mock 模式的返回结构与真实 LLM 的 Pydantic 模型是否一致（换 Real 后不用改代码）

## 验证方式
pytest tests/test_{{模块名}}.py -v
# 或手动调用服务层函数，mock LLM 响应