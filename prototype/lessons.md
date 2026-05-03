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

## 2026-05-03

- `open_questions` 可以保留在 internal/debug output 里用于审计缺口，但不应该暴露在 Prompt Opinion-facing external packet 中，否则入口 agent 会把它误解成继续查询病历的交互功能。
- 当前 demo 的正确外部链路是：用户在 Prompt Opinion 提问，Prompt Opinion 调 external orchestrator，orchestrator 内部分派 Clinical / Insurance / Benefits agents，最后只把可总结的结论、缺失材料和下一步返回给 Prompt Opinion。
- External packet 必须围绕用户原始问题提供足够完整的结构化 case packet，而不是让 `short_answer` 承担完整最终答案。Prompt Opinion 负责根据用户问题从 packet sections 中总结；status line 只能是完成提示，不能是固定 eligibility 模板。
