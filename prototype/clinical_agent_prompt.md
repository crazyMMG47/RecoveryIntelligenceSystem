# Clinical Agent Prompt Spec

## Goal

Clinical Agent 负责读取：

- `patient_summary`
- `pt_notes`
- `imaging`

并输出严格符合 `ClinicalAgentOutput` schema 的结构化结果。

它不负责：

- 保险判断
- 给用户写最终解释
- 编造缺失材料

## Input Contract

输入对象是 `ClinicalAgentInput`：

| 字段 | 说明 |
|---|---|
| `question` | 当前用户问题中和临床相关的部分 |
| `patient_summary` | 病例摘要 |
| `pt_notes` | PT 文本列表 |
| `imaging` | 影像描述列表 |

## Output Contract

输出对象必须是 `ClinicalAgentOutput`：

| 字段 | 说明 |
|---|---|
| `decision` | 推荐什么服务、推荐态度、推荐路径 |
| `evidence[]` | 原子化、可追溯的临床证据 |
| `requirements[]` | 临床前提或临床缺口 |
| `risk_items[]` | 风险点 |
| `stop_conditions[]` | 什么时候当前路径不该继续 |
| `next_steps[]` | 给 downstream workflow 的下一步动作 |
| `confidence` | `high` / `medium` / `low` |

## Prompt Rules

| 规则 | 说明 |
|---|---|
| 只返回 schema | 不输出额外 prose |
| 不碰保险 | 不得提 policy、approval、coverage |
| 不编造 | 缺信息时写进 `requirements` 或降置信度 |
| 证据原子化 | 每条 evidence 只表达一个可追溯临床点 |
| 只用输入材料 | 不引入外部医学知识当事实 |

## Current Code Boundary

| 文件 | 作用 |
|---|---|
| [src/hackathon_agent/clinical_prompt.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/clinical_prompt.py) | 生成 system/user prompt |
| [src/hackathon_agent/llm.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/llm.py) | 定义结构化 LLM 接口 |
| [src/hackathon_agent/clinical_llm_agent.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/clinical_llm_agent.py) | 调用 LLM 并要求输出 `ClinicalAgentOutput` |

## Next Step

下一步不是继续改 prompt 文案，而是把真实的 Gemini/OpenAI 结构化输出客户端接进 `StructuredLLM`。
