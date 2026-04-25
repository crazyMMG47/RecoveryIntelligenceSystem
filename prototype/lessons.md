# Lessons

## 2026-04-13

- Agent 的主输出必须是给下游 agent / LLM / UI 消费的结构化中间层，不能提前写成面向用户的自然语言结论。
- Clinical Agent 应该使用 `LLM + schema`，Insurance Agent 应该使用 `retrieval + LLM + schema`，Orchestrator 保持 `code-first`。
- 规则和关键词匹配只能用于临时 stub，不能当作最终可泛化实现。

## 2026-04-19

- Agent 之间必须继续使用结构化中间层通信，但系统的对外最终产物必须是对用户原始问题的直接回答，不能把结构化 summary 当成 demo 最终结果。
- Prompt Opinion 场景下，对外接口应该返回可直接展示给用户的 answer；中间结构化数据是内部交换层和可选调试层，不是最终交付层。
- 根据 hackathon transcript，Prompt Opinion 的 user/general agent 会调用 external agent；external agent 返回数据，Prompt Opinion 侧再做总结展示给用户。
- 因此当前项目的正确目标不是让内部 agents 直接承担最终聊天 UI，而是让 external orchestrator 返回稳定、可总结、可审计的数据包，供 Prompt Opinion agent 生成最终用户答案。
