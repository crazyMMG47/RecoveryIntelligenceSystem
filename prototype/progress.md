# Progress

## Current Status

项目已经从“只有 multi-agent skeleton”推进到“整条 demo 链路可运行、external packet 已跑通、并且已经通过 ngrok 接入 Prompt Opinion external agent”。

当前架构方向已经落地：

| 层 | 当前状态 |
|---|---|
| Prompt Opinion | 已能通过 `SendA2AMessage` 调 external orchestrator，并收到 task / artifact |
| External Orchestrator Agent | 已补 WorkIQ / Prompt Opinion 兼容 A2A adapter，可通过 ngrok 暴露 |
| Clinical Agent | 已收敛为单一 Gemini 路径，并能输出结构化结果 |
| Insurance Authorization Agent | 已接入 `retrieval + Gemini + schema + contract` |
| Insurance Benefits Agent | 已接入固定官方 Kaiser plan 的 coverage / cost-share 解释层 |
| Orchestrator | 已能串起 Clinical + Insurance Authorization + Insurance Benefits，并输出给 Prompt Opinion 总结的完整 case packet |

## 2026-05-03 Update

今天完成的核心变化：

| 文件 | 今日改动 |
|---|---|
| [src/hackathon_agent/a2a.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/a2a.py) | 对齐 Prompt Opinion / WorkIQ 风格 A2A：兼容 `SendMessage` / `SendA2AMessage` / `GetTask`，支持 `ROLE_USER`、bare `{text: ...}` parts、`result.task` wrapper、`TASK_STATE_COMPLETED`，并把完整 external packet 放进 artifact text |
| [src/hackathon_agent/app.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/app.py) | 将 FastAPI request 传入 A2A adapter，使 JSON-RPC authenticated card 等方法能生成正确外部 URL |
| [src/hackathon_agent/orchestrator.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/orchestrator.py) | 外部输出从固定 PT eligibility 短答案改为完整 Prompt Opinion-facing case packet，包括 case context、injury / rehab history、current clinical status、insurance authorization、documentation gaps、next care plan、benefits、blockers、workflow |
| [src/hackathon_agent/insurance_retriever.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/insurance_retriever.py) | 收窄 RAG retrieval：按 bucket 加 PT / coverage / medical necessity / documentation anchor，降低 confidence，避免无触发条件时返回泛化 appeal chunks |
| [src/hackathon_agent/insurance_prompt.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/insurance_prompt.py) | 增加 `appeal_risk_factors.code` 允许词表，并在 prompt 中明确禁止把 decision driver 当 appeal risk code |
| [src/hackathon_agent/insurance_contract.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/insurance_contract.py) | 让 validator 和 prompt 共用 appeal risk 允许词表，保持严格 contract 校验 |
| [src/hackathon_agent/insurance_llm_agent.py](/Users/3o30m/Documents/Hackathon/src/hackathon_agent/insurance_llm_agent.py) | contract retry 提示中补充允许的 appeal risk code，避免 LLM 反复输出非法 code |
| [lessons.md](/Users/3o30m/Documents/Hackathon/lessons.md) | 记录 Prompt Opinion external packet 的纠偏：`open_questions` 只留在 debug 层；对外 artifact 必须是可按用户问题总结的完整 case packet |
| [progress.md](/Users/3o30m/Documents/Hackathon/progress.md) | 本文件，更新当前进度和今日改动 |

今天验证过的关键点：

| 验证项 | 结果 |
|---|---|
| 本地 `/.well-known/agent-card.json` | 通过 |
| ngrok `/.well-known/agent-card.json` | 通过，card 中 URL 正确指向 ngrok HTTPS `/a2a` |
| 本地 `/a2a` JSON-RPC | 通过 |
| ngrok `/a2a` JSON-RPC | 通过 |
| Prompt Opinion `SendA2AMessage` | 已能连通并读取 task / artifact |
| Retrieval 收窄 smoke test | 通过，`stop_or_escalate` 不再无条件返回泛化 appeal chunks |
| Python compile check | `PYTHONPATH=src .venv/bin/python -m compileall -q src` 通过 |

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
- external agent 默认返回 Prompt Opinion 可消费的完整 case packet
- Prompt Opinion 侧已经能拉到 external agent card，并能通过 `SendA2AMessage` 收到 task / artifact
- 当前问题已经从“能不能连上”推进到“如何让 Prompt Opinion 根据用户原始问题正确总结 packet”

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
| `preferredTransport` / `additionalInterfaces` / `supportedInterfaces` | 已补齐 |
| JSON-RPC `message/send` / `tasks/send` | 已实现 |
| Prompt Opinion `SendMessage` / `SendA2AMessage` | 已实现兼容 |
| JSON-RPC `tasks/get` / `GetTask` | 已实现 |
| ngrok 暴露 | 已完成 |
| Prompt Opinion `Add Connection -> Check` | 已通过 |
| Prompt Opinion `SendA2AMessage` | 已通过，能收到 task / artifact |

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
| Authorization confidence | 已完成一轮收紧，仍需更多 case 测试 |
| Retriever ranking 噪音 | 已完成 PT rehab bucket 收窄，仍需扩大样本验证 |
| snippet corpus 重建脚本 | 还没迁入当前项目 |
| Gemini quota | free tier 可能触发 `429 RESOURCE_EXHAUSTED`，demo 前需要确认 key / quota |

## Current Bottleneck

当前主瓶颈已经不再是“能不能连上 Prompt Opinion”，而是：

| 模块 | 当前问题 |
|---|---|
| Prompt Opinion summarization | external agent 已返回完整 packet，仍需用多种用户问题验证入口 agent 是否按原始问题总结 |
| Insurance Authorization | 已接通真实 RAG，但 LLM 输出稳定性还要继续收紧 |
| Insurance Benefits | 目前只支持固定 demo plan，不支持多 plan 切换 |
| Corpus build pipeline | 运行时已用本地 snippets，但还没有把 snippet 重建脚本迁到当前 repo |
| Gemini quota | 真实联调会消耗 Gemini free tier quota，demo 前需要预留或换 key |

## Next Step

下一步主线：

| 顺序 | 任务 |
|---|---|
| 1 | 用 Prompt Opinion 测 3-5 类自然语言问题，确认 external packet 能被按问题正确总结 |
| 2 | 继续收紧 Insurance Authorization contract 和 ranking |
| 3 | 迁入 `kaiser_urls.txt -> snippets.jsonl` 的 corpus build 脚本 |
| 4 | 准备 demo-safe Gemini key / quota，避免现场 `429 RESOURCE_EXHAUSTED` |
| 5 | 让 Benefits Agent 的摘要更贴近 demo 讲解口径 |

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
