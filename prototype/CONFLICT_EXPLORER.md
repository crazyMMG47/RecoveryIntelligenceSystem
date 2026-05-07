# Interactive Conflict Explorer — Demo Guide

Visual demo showing how the Clinical and Insurance agents reason **independently with evidence**, how they **argue their positions**, and how the Orchestrator **resolves conflicts** between them.

## Quick Start

### 1. Start the FastAPI service
```bash
cd prototype
export GEMINI_API_KEY="your-key"
uvicorn src.hackathon_agent.app:app --reload
```

### 2. Open the explorer in your browser
```
http://localhost:8000/explore
```

### 3. Click "🚀 Run Demo Case"
Wait ~60 seconds for the full pipeline to execute:
- Clinical LLM analyzes case
- Insurance RAG retrieves policy rules
- Orchestrator resolves conflicts
- PromptOpinionAgent generates summary

## What You're Looking At

### Clinical Agent Card (Left — Blue)
Shows the Clinical LLM's reasoning:
- **Decision**: What care path the clinical evidence supports (ADDITIONAL_PT, SURGICAL_REEVALUATION, etc.)
- **Confidence**: How sure the clinical agent is (high/medium/low)
- **Why?**: The specific reason codes that drove the recommendation
- **Evidence (Claims)**: Each piece of clinical evidence with:
  - The claim statement (objective weakness, imaging findings, etc.)
  - Strength badge: **STRONG** / MODERATE / weak
  - Clickable source reference (📄 clinical_notes[0]) — click to see the actual note
  - What it supports: "supports: supervised_pt"
- **Requirements**: What clinical prerequisites are satisfied/unsatisfied
- **Risk Factors**: Clinical risks (fear of re-injury, cartilage degeneration, etc.)

### Insurance Agent Card (Right — Purple)
Shows the Insurance LLM's reasoning:
- **Coverage Position**: What the plan likely covers (LIKELY_COVERED / CONDITIONALLY / LIKELY_DENIED)
- **Decision Drivers**: Why insurance made this decision (physician_justification, objective_deficit, etc.)
- **Coverage Rules**: Each plan rule matching the query:
  - ✅ satisfied (green dot) — clinical evidence supports it
  - ❌ unsatisfied (red dot) — need the listed requirement
  - ❓ pending (gray dot) — unclear if satisfied
- **Insurance Requirements**: What documentation is needed (physician justification, objective measurements, etc.)
- **Appeal Risk Factors**: What could weaken the approval on appeal

### Conflict Resolution Panel (Red border)
Shows what the Orchestrator detected:
- **BLOCKING Conflicts**: Red pill — issues that block approval without resolution
  - Example: "Clinical recommends 2x/week, insurance limits 25 visits/year" (conflict_type: CLINICAL_INSURANCE_MISMATCH)
- **Case Readiness**: 🟢 READY / 🟡 PENDING_DOCUMENTATION / 🟠 NEED_MORE_INFO / 🔴 BLOCKED
- **Escalation Reason**: If escalation was triggered, why

### Orchestrator Reasoning Panel (Green border)
Shows the Orchestrator's response:
- **Recommended Workflow**: Numbered steps in order:
  1. What action (e.g., "Collect physician justification for continued supervised PT")
  2. Who's responsible (Clinical / Insurance / Human)
  3. How to know it's done ("Attachment of letter explaining clinical rationale")
- **Blocking Requirements**: Unsatisfied requirements from both agents that block the case
- **Open Questions**: What still needs to be answered (e.g., "Objective strength measurements", "Prior rehab documentation")

## How to Read the Evidence

### Evidence Chain Example

**Clinical Agent shows:**
```
Evidence:
  "Quadriceps weakness documented on exam"
  [STRONG] 📄 clinical_notes[3] → supports: supervised_pt
```

**Click the source ref** to see what the note actually says:
```
Drawer opens:
  Source: clinical_notes[3]
  Text: "Exam shows mild laxity, quadriceps weakness, and poor neuromuscular control."
```

This shows:
- The clinical evidence is **sourced directly from the case data**
- The claim is **traceable and verifiable**
- The evidence **supports the supervised PT recommendation**

### Coverage Rule Example

**Insurance Agent shows:**
```
Coverage Rules:
  "Objective deficit required" [❌ UNSATISFIED]
  Effect: supporting_if_satisfied
  Reason: Missing objective strength measurements
```

This means:
- The plan **requires objective measurements** to approve
- This requirement is **NOT YET satisfied**
- The Insurance agent needs this documentation before approval

### Conflict Example

**Orchestrator detects:**
```
CLINICAL ↔ INSURANCE [BLOCKING]
Conflict: clinical_insurance_mismatch
Reason: Clinical recommends additional PT, insurance denies without documentation
```

This shows:
- Clinical and Insurance agents **disagree** on coverage
- The conflict is **BLOCKING** — it prevents approval
- The Orchestrator **resolved it** with a PENDING_DOCUMENTATION readiness state
- The solution is in the Recommended Workflow steps

## Why This Matters

This explorer demonstrates that **the system works as designed**:

1. ✅ **Agents think independently**: Each has separate inputs, runs separately, produces independent outputs
2. ✅ **Evidence-driven reasoning**: Every claim is sourced and traceable
3. ✅ **Conflict detection**: Orchestrator catches where agents disagree
4. ✅ **Structured resolution**: Not guessing — rule-based resolution with clear next steps
5. ✅ **Transparency**: Care coordinators see **why** every decision was made

## What's Actually Happening Under the Hood

```
1. You click [Run Demo Case]

2. Browser calls GET /demo-case → gets the Daniel Lee case

3. Browser calls POST /run-case-debug with:
   {
     "user_question": "Is Daniel eligible for additional 2x/week PT...",
     "case": { case_id, patient_summary, clinical_notes, pt_notes, imaging }
   }

4. Server executes pipeline:
   ┌─ ClinicalLLMAgent ────────────────┐
   │ Reads: patient_summary, clinical   │
   │ Outputs: decision, evidence[], req  │
   └────────────────────────────────────┘
                    ↓
   ┌─ InsuranceLLMAgent ──────────────────┐
   │ Reads: clinical output + RAG chunks   │
   │ Outputs: coverage_position, rules[]   │
   └───────────────────────────────────────┘
                    ↓
   ┌─ Orchestrator ─────────────────────────┐
   │ Reads: both agent outputs              │
   │ Detects: conflicts                     │
   │ Derives: readiness, workflow steps     │
   │ Outputs: structured resolution         │
   └────────────────────────────────────────┘

5. Browser receives RunCaseDebugResponse with all agent I/O

6. Explorer renders everything in 4 panels for visual inspection
```

## Interpretation Guide

### ✅ Good Signs
- Clinical confidence is HIGH and evidence statements are STRONG
- Insurance coverage position is LIKELY_COVERED or CONDITIONALLY_COVERED
- No BLOCKING conflicts in the Conflict Resolution panel
- Readiness is READY (green)
- Only a few workflow steps, not many

### ⚠️ Watch For
- Clinical confidence is LOW → agent is uncertain about the case
- Insurance has validation_errors → fallback mode (LLM retries exhausted)
- BLOCKING conflicts → agreement needed between agents
- Readiness is BLOCKED (red) → escalate to human
- Long workflow with many dependencies → complex case

### 🔴 Known Limitations
- First run loads embedding model (~5-10 sec), subsequent runs are faster
- Gemini API may rate-limit; wait a minute and retry
- Insurance RAG relies on hybrid keyword/embedding scoring; semantic mismatches can occur
- Clinical and Insurance agents are independent by design (not collaborative)

## Tips for Demos

1. **Show the Evidence Chain**: Click a source ref to prove the evidence is real, not hallucinated
2. **Highlight the Conflict**: Point out how agents reached different conclusions
3. **Follow the Workflow**: Walk through the numbered steps — this is the orchestrator's resolution plan
4. **Emphasize Transparency**: Every claim is traceable; care coordinators see the reasoning
5. **Mention Readiness**: Explain why the case is PENDING_DOCUMENTATION, not BLOCKED

## Troubleshooting

### Page loads but no data appears
1. Check browser console for errors (F12 → Console tab)
2. Verify `/demo-case` works: `curl http://localhost:8000/demo-case`
3. Verify `/run-case-debug` works: 
   ```bash
   curl -X POST http://localhost:8000/run-case-debug \
     -H "Content-Type: application/json" \
     -d '{"user_question": "test?", "case": {...}}'
   ```

### "Running agents..." takes forever
- Normal: first run is ~60 seconds (LLM calls are slow)
- Check server logs for errors
- If Gemini API returns 503, wait and retry

### Evidence drawer shows "(not found)"
- The source_ref format might be wrong
- Should be: `clinical_notes[0]`, `pt_notes[1]`, `imaging[2]`, or `patient_summary`

### Insurance card shows "⚠️ Degraded Mode"
- Insurance agent failed all retries and returned fallback output
- This is rare but indicates the case was hard to analyze
- Check server logs for the actual error

## Customizing for Your Demo

To use a different case, edit `demo_data.py` and change `DEMO_CASE`. The explorer will automatically use the new case data.

To change the user question, edit `explorer.html` and update the `userQuestion` variable in the `explorer()` function (around line 416).

## Next Steps

- **Phase 4**: Add async task management (don't wait 60 seconds)
- **Phase 5**: Add persistent storage (save and retrieve past cases)
- **Phase 6**: Add collaborative mode (agents can ask each other questions)
