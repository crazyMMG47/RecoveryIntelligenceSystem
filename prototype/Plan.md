# Plan

## 1. MVP目标

我们只做一个能在 Prompt Opinion 里跑通的最小可演示流程：

- 输入：用户问题 + 临床材料 + 保险 policy
- 输出：给 Prompt Opinion 消费的 external agent 数据包，以及内部 clinical / insurance / orchestrator 中间结果
- 最终展示：平台入口 chatbot 读取 external agent 数据包，再转成用户可读回答

这个 MVP 的目标不是证明某个模型强，而是证明：

- 多 agent 分工清晰
- 每个 agent 都有明确职责
- 非结构化材料可以被转成稳定的结构化中间层
- 系统能产出可执行 workflow，而不是只会聊天

## 2. 新架构

| 层 | 形式 | 职责 |
|---|---|---|
| Prompt Opinion chatbot | 平台内置 LLM | 接用户自然语言、触发 external agent、把 external packet 转成人话 |
| Orchestrator | 代码逻辑为主 | 调度 Clinical / Insurance，做冲突检测、优先级合并，并生成 external packet |
| Clinical Agent | `LLM + structured output` | 读取病历/PT/影像，输出临床结构化判断 |
| Insurance Agent | `RAG + LLM + structured output` | 先从长 policy 中检索相关条款，再输出保险结构化判断 |

系统流程：

`用户问题 -> Prompt Opinion chatbot -> external orchestrator -> Clinical Agent + Insurance Agent -> Orchestrator -> external packet -> Prompt Opinion chatbot -> 用户可读回答`

## 2.1 Prompt Opinion最终接法

对 Prompt Opinion 来说，我们最终只暴露一个 external agent。

| 层 | 放在哪里 | 作用 |
|---|---|---|
| Prompt Opinion general chat | 平台内 | 接用户问题，consult external agent |
| External Orchestrator Agent | 我们自己的服务 | 对外统一入口 |
| Clinical Agent | external orchestrator 内部 | 读取临床材料，输出结构化 clinical result |
| Insurance Agent | external orchestrator 内部 | retrieval + LLM 处理 policy，输出结构化 insurance result |

关键原则：

- 不把 Clinical Agent 单独接到 Prompt Opinion
- 不把 Insurance Agent 单独接到 Prompt Opinion
- 对外只暴露一个 orchestrator agent
- multi-agent 价值体现在 external agent 内部，而不是平台侧堆多个独立连接

## 3. 为什么这些 Agent 要加入 LLM

| Agent | 要不要 LLM | 原因 |
|---|---|---|
| Clinical Agent | 要 | 病历、PT notes、影像描述是非结构化文本，不能靠关键词和硬编码规则稳定处理 |
| Insurance Agent | 要，但前面先做 retrieval | policy 很长，先检索相关条款，再让 LLM 基于命中的条款做结构化判断 |
| Orchestrator | v1 先不要重度依赖 LLM | 它的核心是编排、冲突检测、优先级合并，这些更适合用可控的代码逻辑实现 |

| 为什么不能只靠平台入口 LLM | 结果 |
|---|---|
| 入口 LLM 自己读所有原始材料 | agent 分工价值会消失 |
| 没有内部结构化中间层 | 下游难以稳定消费，也难以做冲突检测 |
| 全靠一层聊天式推理 | 系统会退化成单 chatbot，而不是 multi-agent workflow |

| 为什么不能只靠规则，不接内部 LLM | 结果 |
|---|---|
| case 稍微变化 | 关键词规则就会失效 |
| 文本表述不同 | 抽取结果不稳定 |
| 复杂医疗/保险语言 | 无法可靠理解语义 |

结论：

- Clinical Agent 应该是 `LLM + schema`
- Insurance Agent 应该是 `retrieval + LLM + schema`
- Orchestrator 应该是 `code-first`

## 4. 3-Agent职责边界

| Agent | 输入 | 输出 | 不负责什么 |
|---|---|---|---|
| Clinical Agent | 用户问题中的临床部分 + patient summary + PT + imaging | 临床结构化中间结果 | 不直接输出给用户看的最终答案；不读 policy |
| Insurance Agent | 用户问题中的保险部分 + relevant policy clauses + clinical structured output | 保险结构化中间结果 | 不直接做完整临床判断；不读全部原始病历 |
| Orchestrator | 用户问题 + clinical output + insurance output | external packet + 内部 workflow / case resolution | 不承担重文本阅读；不直接承担最终 UI 聊天层 |

## 5. Contract原则

三个 agent 都不应该把主要输出写成自然语言段落。  
主要输出必须是给下游 agent / LLM / UI 消费的结构化中间层。

统一原则：

| 公共块 | 用途 |
|---|---|
| `decision` | 当前层的判断结果 |
| `evidence[]` | 支撑判断的证据 |
| `requirements[]` | 缺失前提、阻断项、必须补齐的材料 |
| `next_steps[]` | 下一步动作 |

## 6. Contract

### 6.1 Clinical Agent 输入

| 字段 | 类型 | 说明 |
|---|---|---|
| `question` | string | 当前用户问题中与临床相关的部分 |
| `patient_summary` | string | 病例摘要 |
| `pt_notes` | string[] | PT notes 列表 |
| `imaging` | string[] | 影像描述列表 |

### 6.2 Clinical Agent 输出

| 字段 | 类型 | 说明 |
|---|---|---|
| `decision` | object | 例如推荐什么 service、推荐态度、推荐路径 |
| `evidence[]` | object[] | 每条证据包含 `code / statement / source_type / source_ref / supports / strength` |
| `requirements[]` | object[] | 临床前提或缺失项 |
| `risk_items[]` | object[] | 风险点 |
| `stop_conditions[]` | string[] | 何时应停止当前路径 |
| `next_steps[]` | string[] | 临床下一步 |
| `confidence` | string | `high` / `medium` / `low` |

### 6.3 Insurance Agent 输入

| 字段 | 类型 | 说明 |
|---|---|---|
| `question` | string | 当前用户问题中与保险相关的部分 |
| `clinical_decision` | object | Clinical Agent 的决策对象 |
| `clinical_evidence[]` | object[] | Clinical Agent 的证据对象 |
| `clinical_requirements[]` | object[] | Clinical Agent 的缺失项/前提 |

### 6.4 Insurance Agent 输出

| 字段 | 类型 | 说明 |
|---|---|---|
| `decision` | object | coverage position、是否需要 review、decision drivers |
| `coverage_rules[]` | object[] | 每条命中的 policy rule 及满足情况 |
| `requirements[]` | object[] | 审批前必须补的材料或条件 |
| `appeal_risk_factors[]` | object[] | 可能降低 approval 强度的因素 |
| `next_steps[]` | string[] | 审批下一步 |
| `confidence` | string | `high` / `medium` / `low` |

### 6.5 Orchestrator 输入

| 字段 | 类型 | 说明 |
|---|---|---|
| `user_question` | string | 用户原始问题 |
| `clinical_output` | object | Clinical Agent 输出 |
| `insurance_output` | object | Insurance Agent 输出 |

### 6.6 Orchestrator 内部输出

| 字段 | 类型 | 说明 |
|---|---|---|
| `case_resolution` | object | 推荐路径、当前 readiness、是否需要人工 review |
| `key_evidence[]` | object[] | 跨 agent 归并后的关键证据 |
| `blocking_requirements[]` | object[] | 当前阻断项 |
| `conflict_items[]` | object[] | 冲突对象，不是普通字符串 |
| `recommended_workflow[]` | object[] | 下一步 workflow，每步有 owner / action / depends_on / done_definition |
| `handoff_packet` | object | 给 downstream LLM 或 UI 的最小结构化上下文 |
| `open_questions[]` | object[] | 还需要回答的问题 |
| `escalation_reason` | string | 是否需要人工介入及原因 |

### 6.7 External Agent 对外输出

| 字段 | 类型 | 说明 |
|---|---|---|
| `short_answer` | string | 给 Prompt Opinion 的简短结论 |
| `sections[]` | object[] | 按 eligibility / documentation / next care plan 分块的数据 |
| `recommended_next_steps[]` | string[] | 可直接转成用户建议的下一步 |
| `blocking_items[]` | string[] | 当前阻断项 |
| `benefits_at_a_glance[]` | string[] | benefit 与 cost-share 关键点 |
| `open_questions[]` | string[] | 仍待补齐的问题 |

## 7. Orchestrator实际做的4件事

| Step | 名称 | 作用 |
|---|---|---|
| 1 | Question decomposition | 把用户问题拆成临床问题和保险问题 |
| 2 | Dispatch with context scoping | Clinical 只看 clinical context；Insurance 只看 retrieved policy + clinical structured output |
| 3 | Conflict detection | 检查路径冲突、证据缺口、低置信度、阻断项 |
| 4 | Workflow synthesis | 合并出最终可执行 workflow，而不是直接写最终 prose |

## 8. Conflict detection规则

| 冲突类型 | 示例 |
|---|---|
| 路径冲突 | Clinical 推荐继续 PT，但 Insurance 认为当前材料不足以支持审批 |
| 低置信度 | 任一 agent 输出 `low` |
| 阻断项未满足 | objective deficits、physician justification、therapy plan 仍未补齐 |
| 证据不足 | Clinical 或 Insurance 关键 evidence 太弱或缺失 |

## 9. Resolution优先级

| 优先级 | 原则 |
|---|---|
| 1 | Safety |
| 2 | Functional status |
| 3 | Structural status |
| 4 | Patient preference |
| 5 | Administrative convenience |

如果高优先级信息不足，就直接暴露缺口，不做猜测。

## 10. 接下来的执行顺序

| 顺序 | 任务 | 产出 |
|---|---|---|
| 1 | 把 external agent 的对外入口定成一个 orchestrator agent | 平台只需要接一个 agent，最稳 |
| 2 | 让这个 orchestrator 内部调用 Clinical 和 Insurance | multi-agent 价值体现在系统内部 |
| 3 | Clinical 直接接 Gemini，输出结构化 clinical result | 临床层从规则版升级为可泛化实现 |
| 4 | Insurance 做 retrieval + Gemini，输出结构化 insurance result | 处理长 policy，不把整段 policy 直接喂给单层逻辑 |
| 5 | Orchestrator 输出 external packet，并保留内部 debug packet | Prompt Opinion 有稳定输入，内部链路仍可调试 |
| 6 | 再加一层对外 A2A adapter | 把平台传来的请求转成内部 orchestrator 输入 |
| 7 | 用 ngrok 暴露这个 external agent | 让 Prompt Opinion 能连上 |
| 8 | 在 Prompt Opinion 的 workspace hub 里 add external agent | 平台拉 card、skills、auth、FHIR context |
| 9 | 用 general chat 测试 consult external agent | 验证最终 judges 路径 |
| 10 | 录 demo + 提交 | 满足 hackathon 提交要求 |

## 11. 当前最应该做的事

| 优先级 | 任务 |
|---|---|
| 1 | 先把 external orchestrator 作为唯一对外 agent 定死 |
| 2 | 把 Clinical Agent 变成真正的 Gemini LLM agent |
| 3 | 然后给 Insurance Agent 加 retrieval 层和 Gemini |
| 4 | 最后补 A2A adapter，再接 Prompt Opinion |
