# Progress

## Current Status

项目已经从“只有 multi-agent skeleton”推进到“整条 demo 链路可运行、external packet 已跑通、并且开始真实接 Prompt Opinion external agent”。

当前架构方向已经落地：

| 层 | 当前状态 |
|---|---|
| Prompt Opinion | 已能添加 external connection，agent card 可被识别；当前卡在 `SendA2AMessage` 返回体解析 |
| External Orchestrator Agent | 已补最小 A2A adapter，可通过 ngrok 暴露 |
| Clinical Agent | 已收敛为单一 Gemini 路径，并能输出结构化结果 |
| Insurance Authorization Agent | 已接入 `retrieval + Gemini + schema + contract` |
| Insurance Benefits Agent | 已接入固定官方 Kaiser plan 的 coverage / cost-share 解释层 |
| Orchestrator | 已能串起 Clinical + Insurance Authorization + Insurance Benefits，并默认输出给 Prompt Opinion 消费的数据包 |

## What Is Done

### 1. Planning and architecture

| 项目 | 状态 |
|---|---|
| hackathon 背景整理 | 已完成 |
| demo case 收敛 | 已完成 |
| multi-agent 方案收敛 | 已完成 |
| Prompt Opinion 最终接法明确 | 已完成 |
| Prompt Opinion connection 首轮联调 | 已开始 |

关键结论：

- 对外只暴露一个 external orchestrator agent
- Clinical Agent 用 `LLM + schema`
- Insurance Authorization Agent 用 `retrieval + LLM + schema`
- Insurance Benefits Agent 用 `code-first + official plan docs`
- Orchestrator 用 `code-first`

### 2. Schema and structured contract

| 项目 | 状态 |
|---|---|
| typed schema | 已完成 |
| Clinical / Insurance / Orchestrator contract | 已完成 |
| Insurance Benefits schema | 已完成 |
| structured intermediate layer | 已完成 |

当前代码仍然坚持结构化中间层做 agent 间交换，对外默认输出的是给 Prompt Opinion agent 消费的数据包。

新增结论：

- internal agent 间继续使用结构化中间层
- external agent 默认返回 Prompt Opinion 可消费的数据包
- Prompt Opinion 侧已经能拉到 external agent card
- 当前问题已经从“能不能连上”推进到“`SendA2AMessage` 的 A2A 返回体是否完全符合预期”

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
- 真实 Gemini key 已完成本地联调

### 4. Insurance Authorization Agent

| 项目 | 状态 |
|---|---|
| `InsuranceLLMAgent` | 已完成 |
| Insurance prompt | 已完成 |
| Insurance contract | 已完成 |
| local snippet corpus loader | 已完成 |
| bucketed retrieval | 已完成 |
| routing (`domain + intents + candidate_urls`) | 已完成 |
| Kaiser snippet corpus 接入 | 已完成 |
| contract 收紧（confidence / next_steps / 语义一致性） | 已完成第一轮 |

已接入的本地语料：

| 文件 | 作用 |
|---|---|
| [data/policies/kaiser_urls.txt](/Users/3o30m/Documents/Hackathon/data/policies/kaiser_urls.txt) | Kaiser policy source manifest |
| [data/policy_snippets/snippets.jsonl](/Users/3o30m/Documents/Hackathon/data/policy_snippets/snippets.jsonl) | 本地 chunked Kaiser policy corpus |

当前 Authorization Agent 已经不是“拆 `policy_text` 的假 retrieval”，而是真正基于 Kaiser snippets 做 bucketed retrieval。

### 5. Insurance Benefits Agent

| 项目 | 状态 |
|---|---|
| 固定 demo plan 选型 | 已完成 |
| 官方 EOC 来源确定 | 已完成 |
| `InsuranceBenefitsAgent` | 已完成 |
| deductible / coinsurance / out-of-pocket / visit limit 固化 | 已完成 |
| benefits summary 接入 orchestrator | 已完成 |

当前固定 demo 参考 plan：

| 项目 | 选择 |
|---|---|
| Insurance plan | Kaiser Foundation Health Plan of Washington VisitsPlus Silver 4500 (2026) |
| 官方目录页 | [Washington Individual & Family Plan Documents](https://healthy.kaiserpermanente.org/washington/support/forms/documents/individual-family) |
| 官方 EOC PDF | [2026 VisitsPlus Silver 4500 EOC](https://healthy.kaiserpermanente.org/content/dam/kporg/final/documents/health-plan-documents/eoc/wa/individual-family/2026/off-visitsplus-silver-4500-wa-en.pdf) |

当前 Benefits Agent 能回答：

| 能回答的问题 | 当前状态 |
|---|---|
| 这类 outpatient PT 是否属于固定 demo plan benefit | 已完成 |
| in-network requirement | 已完成 |
| preauthorization / plan rule 说明 | 已完成 |
| rehab visit limit | 已完成 |
| member cost share | 已完成 |
| deductible / out-of-pocket max | 已完成 |

### 6. Orchestrator

| 项目 | 状态 |
|---|---|
| 本地 orchestrator 流程 | 已完成 |
| 能消费 Gemini Clinical output | 已完成 |
| 能消费 Insurance Authorization output | 已完成 |
| 能消费 Insurance Benefits output | 已完成 |
| blocking requirements 去重 | 已完成 |
| `benefits_summary` 注入最终输出 | 已完成 |
| `from_env()` 单一路径装配 Gemini Clinical + Insurance | 已完成 |
| `/run-case` 对外 packet | 已完成 |
| `/run-case-debug` 内部调试 packet | 已完成 |
| `run_orchestrator_demo.py` 真实 Gemini 联调 | 已完成 |

### 7. External Agent / A2A

| 项目 | 状态 |
|---|---|
| 最小 A2A adapter | 已完成 |
| agent card (`/.well-known/agent-card.json`) | 已完成 |
| `supportedInterfaces` | 已补齐 |
| JSON-RPC `message/send` | 已实现，仍在联调 |
| JSON-RPC `tasks/get` | 已实现 |
| ngrok 暴露 | 已完成 |
| Prompt Opinion `Add Connection -> Check` | 已通过 |
| Prompt Opinion `SendA2AMessage` | 仍报错，说明返回体还有协议细节待修 |

### 8. Demo runners

| 文件 | 作用 |
|---|---|
| [run_clinical_llm.py](/Users/3o30m/Documents/Hackathon/run_clinical_llm.py) | 单独测试 Clinical |
| [run_policy_retriever.py](/Users/3o30m/Documents/Hackathon/run_policy_retriever.py) | 在真实 Clinical 输出基础上检查 Kaiser retrieval buckets |
| [run_insurance_llm.py](/Users/3o30m/Documents/Hackathon/run_insurance_llm.py) | 单独测试 Insurance Authorization |
| [run_orchestrator_demo.py](/Users/3o30m/Documents/Hackathon/run_orchestrator_demo.py) | 打印默认 external packet |

## What Has Been Proven

这一步已经证明了几件重要的事：

| 已证明的点 | 说明 |
|---|---|
| Clinical 不再保留关键词主路径 | 已升级为真实 Gemini LLM 单一路径 |
| Insurance Authorization 不再是规则 stub | 已升级为真实 Kaiser snippet retrieval + Gemini |
| Insurance Benefits 不再缺位 | 已能回答固定 demo plan 的 coverage / cost-share 规则 |
| 结构化中间层可行 | LLM 输出能被严格 schema 消费 |
| Orchestrator 架构可行 | Clinical + Authorization + Benefits 都能流入 external packet |
| 对外/对内边界清楚 | 默认对外 packet 给 Prompt Opinion，总调试包单独暴露 |
| external packet 已真实跑通 | `run_orchestrator_demo.py` 已返回稳定 `ExternalAgentResponse` |
| Prompt Opinion external connection 可建立 | card 已能被 Prompt Opinion 解析 |

## Current Known Issues

| 项目 | 状态 |
|---|---|
| Insurance Authorization 的语义稳定性 | 仍需继续收紧 |
| Authorization confidence | 仍可能偏乐观，已开始第一轮收紧 |
| Retriever ranking 噪音 | 仍需继续压低无关 chunk |
| snippet corpus 重建脚本 | 还没迁入当前项目 |
| A2A `message/send` 返回体细节 | 仍需继续对齐 Prompt Opinion 的解析预期 |

## Current Bottleneck

当前主瓶颈已经不再是“Insurance 还没开始”，而是：

| 模块 | 当前问题 |
|---|---|
| A2A adapter | Prompt Opinion 已能 check 通过，但 `SendA2AMessage` 仍返回错误，说明 JSON-RPC `Task/Artifact/Message` 结构还差协议细节 |
| Insurance Authorization | 虽然已接通真实 RAG，但输出稳定性还要继续收紧 |
| Insurance Benefits | 目前只支持固定 demo plan，不支持多 plan 切换 |
| Corpus build pipeline | 运行时已用本地 snippets，但还没有把 snippet 重建脚本迁到当前 repo |

## Next Step

下一步主线：

| 顺序 | 任务 |
|---|---|
| 1 | 继续对齐 A2A `message/send` 返回体，打通 Prompt Opinion `SendA2AMessage` |
| 2 | 继续收紧 Insurance Authorization contract 和 ranking |
| 3 | 迁入 `kaiser_urls.txt -> snippets.jsonl` 的 corpus build 脚本 |
| 4 | 让 Benefits Agent 的摘要更贴近 demo 讲解口径 |

## Files Added or Evolved

| 文件 | 当前作用 |
|---|---|
| [Plan.md](/Users/3o30m/Documents/Hackathon/Plan.md) | 当前总计划 |
| [case.md](/Users/3o30m/Documents/Hackathon/case.md) | demo case |
| [clinical_agent_prompt.md](/Users/3o30m/Documents/Hackathon/clinical_agent_prompt.md) | Clinical prompt spec |
| [lessons.md](/Users/3o30m/Documents/Hackathon/lessons.md) | 过程中的关键纠偏 |
| [progress.md](/Users/3o30m/Documents/Hackathon/progress.md) | 当前进度 |
| [src/hackathon_agent/a2a.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/a2a.py) | 最小 A2A adapter、agent card、JSON-RPC task 封装 |
| [src/hackathon_agent/schemas.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/schemas.py) | typed contracts，包括 benefits schema |
| [src/hackathon_agent/clinical_llm_agent.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/clinical_llm_agent.py) | Gemini-based Clinical Agent |
| [src/hackathon_agent/insurance_retriever.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/insurance_retriever.py) | Kaiser snippet retrieval |
| [src/hackathon_agent/insurance_llm_agent.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/insurance_llm_agent.py) | Authorization agent |
| [src/hackathon_agent/insurance_benefits_agent.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/insurance_benefits_agent.py) | Fixed-plan benefits agent |
| [src/hackathon_agent/insurance_contract.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/insurance_contract.py) | Authorization semantic validator |
| [src/hackathon_agent/policy_router.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/policy_router.py) | Insurance retrieval router |
| [src/hackathon_agent/policy_map.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/policy_map.py) | Seed URL mapping |
| [src/hackathon_agent/orchestrator.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/orchestrator.py) | orchestrator logic，默认输出 Prompt Opinion-facing external packet |
| [src/hackathon_agent/app.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/app.py) | FastAPI + A2A / agent card / debug endpoints |
| [data/policies/kaiser_urls.txt](/Users/3o30m/Documents/Hackathon/data/policies/kaiser_urls.txt) | source URL manifest |
| [data/policy_snippets/snippets.jsonl](/Users/3o30m/Documents/Hackathon/data/policy_snippets/snippets.jsonl) | local snippet corpus |
| [run_clinical_llm.py](/Users/3o30m/Documents/Hackathon/run_clinical_llm.py) | Clinical demo runner |
| [run_policy_retriever.py](/Users/3o30m/Documents/Hackathon/run_policy_retriever.py) | retrieval demo runner |
| [run_insurance_llm.py](/Users/3o30m/Documents/Hackathon/run_insurance_llm.py) | Insurance demo runner |
| [run_orchestrator_demo.py](/Users/3o30m/Documents/Hackathon/run_orchestrator_demo.py) | full orchestrator demo runner |
