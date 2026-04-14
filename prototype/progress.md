# Progress

## Current Status

项目已经从“只有想法和 case 文档”推进到“有真实可运行的 multi-agent skeleton”。

当前架构方向已经确定：

| 层 | 当前状态 |
|---|---|
| Prompt Opinion | 还没有接入，但接法已经明确 |
| External Orchestrator Agent | 架构和本地代码骨架已存在 |
| Clinical Agent | 已接入 Gemini，并能输出结构化结果 |
| Insurance Agent | 仍然是规则版，retrieval + Gemini 还没开始 |
| Orchestrator | 已能串起 Clinical 和 Insurance，并输出结构化 workflow |

## What Is Done

### 1. Planning and architecture

| 项目 | 状态 |
|---|---|
| hackathon 背景整理 | 已完成 |
| demo case 收敛 | 已完成 |
| multi-agent 方案收敛 | 已完成 |
| Prompt Opinion 最终接法明确 | 已完成 |

关键结论：

- 对外只暴露一个 external orchestrator agent
- Clinical Agent 用 `LLM + schema`
- Insurance Agent 用 `retrieval + LLM + schema`
- Orchestrator 用 `code-first`

### 2. Schema and structured contract

| 项目 | 状态 |
|---|---|
| typed schema | 已完成 |
| Clinical / Insurance / Orchestrator contract | 已完成 |
| structured intermediate layer | 已完成 |

当前代码已经不再把 agent 主输出设计成用户可读 prose，而是结构化中间层。

### 3. Clinical Agent

| 项目 | 状态 |
|---|---|
| Clinical prompt spec | 已完成 |
| Gemini client 接入 | 已完成 |
| `ClinicalLLMAgent` | 已完成 |
| schema-level validation | 已完成 |
| semantic validation | 已完成 |
| controlled vocabulary 收紧 | 已完成第一轮 |

已验证：

- Gemini 能真实返回 `ClinicalAgentOutput`
- 输出能通过 Pydantic 校验
- 输出能通过语义级校验
- 输出已开始稳定使用内部 code 和 source_ref

### 4. Orchestrator

| 项目 | 状态 |
|---|---|
| 本地 orchestrator 流程 | 已完成 |
| 能消费 Gemini Clinical output | 已完成 |
| 能生成 `case_resolution` / `blocking_requirements` / `recommended_workflow` | 已完成 |
| `from_env()` 显式切换 Gemini Clinical | 已完成 |

### 5. Demo runners

| 文件 | 作用 |
|---|---|
| [run_clinical_llm.py](/Users/3o30m/Documents/Hackathon/run_clinical_llm.py) | 单独测试 Clinical Gemini |
| [run_orchestrator_demo.py](/Users/3o30m/Documents/Hackathon/run_orchestrator_demo.py) | 测试当前完整 orchestrator 链路 |

## What Has Been Proven

这一步已经证明了几件重要的事：

| 已证明的点 | 说明 |
|---|---|
| Clinical 不再是关键词规则 | 已升级为真实 Gemini LLM |
| 结构化中间层可行 | LLM 输出能被严格 schema 消费 |
| Orchestrator 架构可行 | Clinical output 能继续流到 Insurance 和 Orchestrator |
| 系统能产出 workflow，而不只是聊天回答 | 已能输出 blocking requirements 和 next workflow |

## What Is Not Done Yet

| 项目 | 状态 |
|---|---|
| Insurance retrieval | 未开始 |
| Insurance Gemini | 未开始 |
| A2A adapter | 未开始 |
| external agent card / skills | 未开始 |
| Prompt Opinion 联调 | 未开始 |
| ngrok 暴露 | 未开始 |
| marketplace publish | 未开始 |

## Current Bottleneck

当前唯一的主瓶颈不是 Clinical，也不是 API，而是 Insurance Agent 还停在规则版。

所以系统当前真实状态是：

| 模块 | 状态 |
|---|---|
| Clinical | LLM 版 |
| Insurance | 规则版 |
| Orchestrator | 可运行，但下游一半还没升级 |

## Next Step

下一步主线已经很明确：

| 顺序 | 任务 |
|---|---|
| 1 | 做 Insurance policy chunking |
| 2 | 做 Insurance retrieval |
| 3 | 给 Insurance Agent 加 Gemini structured output |
| 4 | 再跑完整 orchestrator |
| 5 | 最后补 A2A adapter，接 Prompt Opinion |

## Files Added or Evolved

| 文件 | 当前作用 |
|---|---|
| [Plan.md](/Users/3o30m/Documents/Hackathon/Plan.md) | 当前总计划 |
| [case.md](/Users/3o30m/Documents/Hackathon/case.md) | demo case |
| [clinical_agent_prompt.md](/Users/3o30m/Documents/Hackathon/clinical_agent_prompt.md) | Clinical prompt spec |
| [lessons.md](/Users/3o30m/Documents/Hackathon/lessons.md) | 过程中的关键纠偏 |
| [src/hackathon_agent/schemas.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/schemas.py) | typed contracts |
| [src/hackathon_agent/clinical_llm_agent.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/clinical_llm_agent.py) | Gemini-based Clinical Agent |
| [src/hackathon_agent/gemini_llm.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/gemini_llm.py) | Gemini structured client |
| [src/hackathon_agent/orchestrator.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/orchestrator.py) | orchestrator logic |
| [run_clinical_llm.py](/Users/3o30m/Documents/Hackathon/run_clinical_llm.py) | Clinical demo runner |
| [run_orchestrator_demo.py](/Users/3o30m/Documents/Hackathon/run_orchestrator_demo.py) | orchestrator demo runner |
