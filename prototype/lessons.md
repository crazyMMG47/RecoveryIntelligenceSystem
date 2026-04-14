# Lessons

## 2026-04-13

- Agent 的主输出必须是给下游 agent / LLM / UI 消费的结构化中间层，不能提前写成面向用户的自然语言结论。
- Clinical Agent 应该使用 `LLM + schema`，Insurance Agent 应该使用 `retrieval + LLM + schema`，Orchestrator 保持 `code-first`。
- 规则和关键词匹配只能用于临时 stub，不能当作最终可泛化实现。
