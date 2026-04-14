# Demo Case

## 1. Why this case

这个 case 专门用来展示 3-agent workflow 的价值，不演“万能医疗判断”，只演一个现实里常见且有明确行动意义的问题：

`这个患者是否值得申请额外的 2x/week PT？如果值得，Kaiser 需要什么材料，下一步怎么做？`

这个问题有现实意义，因为它同时涉及：

- 临床上是否还有继续 structured rehab 的必要
- 保险上是否满足额外审批条件
- 最终应该先补文档、先继续 PT，还是升级到其他处理路径

## 2. Primary Demo Question

`Given Daniel Lee's history of two ACL reconstructions, incomplete rehabilitation, current functional deficits, and Kaiser policy constraints, is he likely eligible for additional 2x/week physical therapy, what documentation is needed to support approval, and what should the next care plan be?`

## 3. Expected Workflow

| Agent | 读什么 | 回答什么 |
|---|---|---|
| Clinical Agent | patient summary + clinical notes + PT notes + imaging | 继续 structured PT 是否有临床必要，主要依据是什么，缺什么信息 |
| Insurance Agent | policy + Clinical Agent 的结构化结论 | 额外 PT 大概率能否获批，需要补哪些材料，拒赔风险是什么 |
| Orchestrator | 两个 agent 的结构化输出 | 给出最终结论、行动计划、需要补的信息、是否需要人工升级 |

## 4. Patient / FHIR-style Summary

```json
{
  "id": "CASE_003",
  "name": "Daniel Lee",
  "age": 30,
  "sex": "male",
  "insurance": "Kaiser Permanente",
  "chief_complaint": "Persistent right knee instability and pain 8 months after revision ACL reconstruction",
  "history": [
    "Primary ACL reconstruction at Kaiser San Diego 2.5 years ago after sports injury",
    "Revision ACL reconstruction at Kaiser San Jose 8 months ago after recurrent instability",
    "Rehabilitation was inconsistent across locations and interrupted by relocation and work schedule"
  ],
  "current_goal": "Return to recreational basketball and normal daily function without instability",
  "current_barriers": [
    "Pain with activity",
    "Instability during pivoting",
    "Quadriceps weakness",
    "Fear of re-injury"
  ]
}
```

## 5. Clinical Notes

Patient is a 30-year-old male presenting with persistent right knee instability and activity-related pain 8 months after revision ACL reconstruction.

### History

- First ACL reconstruction at Kaiser San Diego 2.5 years ago
- Revision ACL reconstruction at Kaiser San Jose 8 months ago
- Patient reports rehabilitation was not continuous across locations
- Patient changed jobs and relocated during recovery, which interrupted follow-up care

### Current symptoms

- Pain rated 5/10 during cutting, pivoting, and stairs
- Sense of instability during pivoting and quick direction changes
- Reduced confidence in knee function
- Avoiding sports and limiting some daily activities

### Exam

- Mild laxity on exam without clear evidence of acute graft rupture
- Quadriceps weakness on the operative side
- Reduced single-leg control
- Poor neuromuscular control during functional movements
- No acute red-flag neurologic or vascular findings documented

### Clinical assessment

- Persistent functional instability after revision ACL reconstruction
- Current presentation is more consistent with incomplete rehabilitation and neuromuscular deficits than acute structural failure
- Additional structured rehabilitation appears clinically reasonable before considering further invasive intervention

## 6. Imaging

### MRI RIGHT KNEE

#### Findings

- Intact ACL graft with mild stretching
- Mild joint effusion
- Early cartilage degeneration
- No acute tear
- No displaced hardware complication reported

#### Impression

- Suboptimal graft integrity with functional instability
- Imaging does not show an acute catastrophic structural failure
- Findings support chronic overload and incomplete functional recovery rather than an emergent surgical problem

## 7. PT Notes

### Rehabilitation history

#### First surgery course

- Completed about 10 weeks of PT
- Program emphasized strength and progressive loading
- Did not complete the final return-to-sport phase

#### Second surgery course

- Attended PT for only 4 to 5 weeks
- Focus was mostly pain control and basic mobility
- No documented structured quadriceps strengthening progression
- No documented neuromuscular or return-to-sport progression
- Stopped attending after relocation and work schedule changes

### Current functional findings

- Significant quadriceps weakness
- Poor neuromuscular control
- Dynamic valgus tendency during single-leg tasks
- Fear of re-injury
- Not yet returned to prior activity level

### PT assessment

- Patient has not completed a full structured post-revision rehabilitation program
- Deficits remain potentially modifiable with supervised therapy
- Clinical picture supports a trial of additional structured PT before surgical re-evaluation, unless new instability or new structural injury emerges

## 8. Insurance Policy Summary

### Kaiser Permanente Rehabilitation Policy

- Standard PT coverage: 1 session per week without additional approval
- Higher-frequency PT such as 2 sessions per week requires physician justification and utilization review
- Requests for extended PT should document measurable functional deficits and a clear therapy plan
- Approval is stronger when there is evidence that the patient has not yet completed an appropriate structured rehabilitation course
- Patient adherence history may be reviewed during approval decisions
- Revision surgery cases require documentation showing why continued conservative management is still clinically appropriate or, if not, why escalation is needed

## 9. Structured Facts the Agents Should Be Able to Use

| Fact | Why it matters |
|---|---|
| Graft is intact and there is no acute tear | Makes immediate re-operation less automatic |
| Functional instability is still present | Supports need for active management |
| Rehab after revision surgery was incomplete | Important for both clinical reasoning and insurance approval |
| Quadriceps weakness and neuromuscular deficits are documented | Supports additional PT request |
| Patient adherence was interrupted by relocation and work | Can be framed as a risk for approval and also a contextual explanation |
| Patient wants return to sport and normal function | Helps define rehabilitation goal |

## 10. Expected Good Final Answer Shape

一个好的最终回答应该至少包含：

- 是否值得申请额外 2x/week PT
- 为什么当前更像应该先补 structured rehab，而不是直接再次手术
- 保险审批最需要的 supporting documentation
- 如果被拒，下一步怎么办

## 11. Sample Questions for Testing

### Main demo question

- Is Daniel likely eligible for additional 2x/week PT under his Kaiser plan, what documentation would strengthen approval, and what should the next care plan be?

### Secondary test questions

- What clinical findings support continued structured rehabilitation instead of immediate surgical re-intervention?
- What specific documentation gaps could cause Kaiser to deny additional PT sessions?
- How should the system explain the impact of interrupted adherence without treating it as a simple patient-fault story?
