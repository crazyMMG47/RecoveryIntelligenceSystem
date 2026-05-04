# Recovery Intelligence System — Current Progress

_Last updated: 2026-05-04_

---

## 1. RAG Retrieval and Approaches for the Insurance Agent

There are **two generations** of RAG retrieval in this repo. Only the second is wired into the active agent pipeline.

### Generation 1 — Live Fetcher (`prototype/bucketed_retrieval/`)
`BucketedPolicyRetriever` fetches Kaiser policy pages live from a curated URL list, HTML/PDF-scrapes them via `PolicyFetcher`, applies domain filtering, chunks the text, and then ranks chunks. This is the exploratory version and is **not currently used** by the main agent pipeline.

### Generation 2 — Corpus Retriever (active, in `src/hackathon_agent/insurance_retriever.py`)
`InsurancePolicyRetriever` reads a pre-built JSONL corpus (`prototype/data/policy_snippets/snippets.jsonl`). This is what `InsuranceLLMAgent` and the Orchestrator use.

**Retrieval flow:**

1. **Routing** (`PolicyRouter`): Classifies the insurance input into a domain (`pt_rehab`, `pharmacy`, `mental_health`, `radiology`, `claims`) and intents (`medical_necessity`, `documentation`, `authorization`, `appeal`) by keyword matching across the full case text.
2. **Domain filtering**: Removes chunks whose URL or content matches negative keywords for the routed domain.
3. **Four evidence buckets** produced per retrieval call:
   - `coverage_rules` — plan/benefit language governing approval
   - `medical_necessity` — continuation criteria, measurable progress
   - `documentation_requirements` — physician notes, therapy plan, frequency/duration
   - `stop_or_escalate` — attendance, denial risk, appeals, escalation triggers
4. **Hybrid Ranking (Phase 2 - Embedding-based)**: 
   - **Cosine similarity** (0.2 weight): Semantic similarity using sentence-transformers all-MiniLM-L6-v2
   - **Keyword scoring** (0.8 weight): Token overlap, phrase boosts (+3-4), bucket-label match (+4), URL match (+2.5), PT-specific boosts (+10-15), noise penalties (-2 to -3)
   - **Final score**: 0.2 × cosine + 0.8 × normalized_keyword_score
5. **Diversity selection**: Deduplicates by `(url, section)` pair, keeps top-3 per bucket.
6. **Confidence scoring**: Heuristic (0–0.90 cap) based on chunk count, URL diversity, presence of key terms, and hybrid score strength.

---

## 2. Agent Construction (Current State)

The system currently has **four agents** — the original plan called for three. One (`InsuranceBenefitsAgent`) is planned for removal (see Phase 1 below).

### ClinicalLLMAgent (`src/hackathon_agent/clinical_llm_agent.py`)
- Input: patient summary, clinical notes, PT notes, imaging
- Gemini LLM with structured output schema. Up to 2 retry attempts with contract violation feedback.
- Output: clinical decision (recommended path), evidence, requirements, risk items, confidence

### InsuranceLLMAgent (`src/hackathon_agent/insurance_llm_agent.py`)
- Input: question + clinical output (decision, evidence, requirements)
- RAG step retrieves 4 evidence buckets from corpus, injected into prompt
- Gemini LLM with structured output. Up to 3 retry attempts.
- Output: coverage position, coverage rules, requirements, appeal risk factors, next steps, confidence

### InsuranceBenefitsAgent (`src/hackathon_agent/insurance_benefits_agent.py`) — **planned for removal**
- No LLM. Hardcoded for the fixed demo plan (Kaiser WA VisitsPlus Silver 4500 2026).
- Returns static benefit details: 25 outpatient visits/year, $75/visit copay, $4,500 deductible, $9,800 OOP max, no preauth required for PT.
- **Overlap**: both it and `InsuranceLLMAgent` address "is this PT covered?" — the benefit facts are static for the demo and do not need a separate agent.

### Orchestrator (`src/hackathon_agent/orchestrator.py`)
- Coordinates agents: Clinical → Insurance (→ Benefits, to be removed)
- Conflict detection, requirement deduplication, workflow synthesis
- Outputs `ExternalAgentResponse` with `HandoffPacket` targeting `prompt_opinion_agent`

### A2AAdapter + FastAPI App
- A2A JSON-RPC protocol wrapper around the Orchestrator
- Endpoints: `/run-case`, `/run-case-debug`, `/a2a`, `/.well-known/agent-card.json`

**LLM backend:** Google Gemini (`gemini-2.5-flash-lite` by default) via `GEMINI_API_KEY`.

---

## 3. Current Data Supplied to the RAG

Active corpus: `prototype/data/policy_snippets/snippets.jsonl` — **552 chunks** (expanded from 134 in Phase 3), scraped from 14 Kaiser Permanente Washington provider pages.

**Bucket distribution:**
- `coverage_rules`: 111 chunks (plan/benefit language)
- `medical_necessity`: 50 chunks (PT criteria, ACL protocols, functional requirements)
- `authorization`: 52 chunks (prior auth process, visit limits)
- `documentation_requirements`: 17 chunks (physician notes, therapy plan format)
- `appeals`: 17 chunks (reconsideration, appeal process)
- `condition_guideline`: 16 chunks (ACL rehab protocols, PT milestones)
- `other`: 289 chunks (billing codes, clinical criteria supporting details)

**PT-specific content sources:**
- ACL repair protocol PDF (13 chunks): Detailed post-op PT phases, ROM goals, strength testing, return-to-sport progression
- Physical therapy services criteria PDF (34 chunks): PT medical necessity, evaluation codes, documentation requirements, coverage rules
- Manual PT chunks (10 chunks): Coverage, medical necessity, documentation, and escalation criteria

**Note**: PT-specific chunks exist in corpus but generic priorauth authorization tables often rank higher due to broad keyword matching. This is a known limitation of keyword/embedding hybrid scoring with diverse vocabularies.

---

## 4. How to Run the Agents Locally

```bash
export GEMINI_API_KEY="your-key-here"
cd /home/smooi/RecoveryIntelligenceSystem/prototype
pip install -e .

# Full pipeline demo
python run_orchestrator_demo.py

# Test insurance RAG retrieval in isolation (prints all 4 buckets + chunks)
python run_policy_retriever.py

# Test insurance + clinical agents only
python run_insurance_llm.py

# Run FastAPI server
uvicorn hackathon_agent.app:app --reload --port 8000
```

---

## 5. Planned Changes

---

### Phase 1 — Remove `InsuranceBenefitsAgent` (restore 3-agent architecture)

**Why:** The original plan specified three agents. `InsuranceBenefitsAgent` was added to separate static benefit facts (visit limits, copays, deductibles) from authorization logic, but this creates redundancy — both agents answer "is this PT covered?" and the Orchestrator must reconcile two insurance-layer outputs. For the demo the plan is fixed, so the benefit facts can be folded in as static context without a dedicated agent.

**What changes:**

| File | Change |
|---|---|
| `insurance_benefits_agent.py` | Delete |
| `schemas.py` | Remove `InsuranceBenefitsInput`, `InsuranceBenefitsOutput`, `PlanSource`, `BenefitCoverageStatus`; remove `insurance_benefits_output` from `OrchestratorInput` |
| `orchestrator.py` | Remove `insurance_benefits_agent` param and its wiring in `from_env()`; remove `build_insurance_benefits_input()`; remove benefits call in `run_debug()`; replace `benefits_at_a_glance` population with a static `_DEMO_BENEFITS` constant list in `_build_external_response()` |
| `insurance_prompt.py` | Add a short static "plan context" block to the system prompt listing the fixed demo plan benefit rules (visit limit: 25 visits/yr, copay: $75/visit, no preauth required for PT, deductible: $4,500) — the LLM can reference these when assessing coverage |
| `run_orchestrator_demo.py` | No changes — `Orchestrator.from_env()` will be updated internally |
| `app.py` | No changes |

**Result:** Pipeline becomes Clinical → InsuranceLLM → Orchestrator. The insurance prompt gains a static benefits block. Benefit questions are answered by the same LLM that handles authorization logic.

**Tradeoff:** Benefit facts are baked into the prompt rather than dynamically retrieved — acceptable for a fixed demo plan. If the plan changes in production, you'd move this to a retrieved chunk (Phase 3).

---

### Phase 2 — Add Embedding-Based Hybrid Retrieval to `InsurancePolicyRetriever`

**Why:** The current keyword ranker misses when policy language uses synonyms or paraphrases that don't match the exact query tokens (e.g., "skilled care" vs. "supervised PT", "benefit limit" vs. "visit cap"). Embedding-based similarity captures semantic intent regardless of exact wording, which matters for insurance/medical text that is dense with domain jargon.

**Recommended approach: `sentence-transformers` (local, offline, free)**

Model: `all-MiniLM-L6-v2` — 22M parameters, ~80 MB, 384-dimensional embeddings. Runs entirely on CPU in ~0.5 s for 134 chunks. No extra API calls, no quota, works offline.

Alternative: Gemini `text-embedding-004` API — stays within existing dependencies but adds API cost per query and requires network access.

**New dependency:** add `sentence-transformers>=2.7,<3` to `pyproject.toml`.

**Design — how hybrid scoring works:**

```
At corpus load time (once, then cached):
  PolicySnippetCorpus._embed_chunks()
    → encode all 134 chunk texts with all-MiniLM-L6-v2
    → save to data/policy_snippets/snippets_embeddings.npy
    → subsequent runs load from cache; cache is invalidated when snippets.jsonl changes

At query time (per bucket, 4×/call):
  InsurancePolicyRetriever._rank_chunks()
    → embed the bucket query string
    → cosine_similarity(query_vec, chunk_matrix)  [numpy dot product on normalized vectors]
    → normalize keyword score to [0, 1]
    → final_score = 0.6 × cosine_sim + 0.4 × keyword_score_norm
    → sort descending, apply diversity selection as before
```

**Why hybrid (not pure embedding)?**

The existing keyword boosts encode insurance-specific vocabulary that embeddings alone may not weight correctly (exact terms like "preauthorization", "utilization review", specific rule names). Keeping keyword scoring as a 40% component preserves that signal while semantic similarity fills the paraphrase gaps. The α=0.6/0.4 split is a starting point — tune by inspecting `run_policy_retriever.py` output.

**What changes:**

| File | Change |
|---|---|
| `pyproject.toml` | Add `sentence-transformers>=2.7,<3` |
| `insurance_retriever.py` | Add `EmbeddingModel` wrapper (loads model once, lazy); update `PolicySnippetCorpus` to embed chunks + cache to `.npy`; update `InsurancePolicyRetriever._rank_chunks()` to compute cosine sim and blend with keyword score |
| `run_policy_retriever.py` | Print cosine similarity score alongside keyword score for each retrieved chunk so you can inspect embedding quality vs. keyword quality |

**No changes to prompts, schemas, or Orchestrator** — retrieval is fully internal to `InsurancePolicyRetriever`.

---

### Phase 3 — Expand `snippets.jsonl` with PT-Specific Chunks

**Why:** Phases 1 and 2 improve architecture and algorithm, but retrieval quality is bounded by what is in the corpus. The current 134 chunks are almost entirely about general prior authorization and DME — PT/rehab/ACL clinical criteria content is thin. Even good embeddings cannot retrieve information that doesn't exist in the corpus.

**Target content to add (~20–30 new chunks):**

| Source | Content | Target bucket |
|---|---|---|
| Kaiser WA clinical review criteria — physical therapy | PT continuation criteria, measurable improvement standards, skilled care requirements | `medical_necessity` |
| Kaiser WA outpatient rehab policy | Outpatient PT frequency/duration rules, re-evaluation triggers | `documentation_requirements` |
| ACL rehabilitation protocol | Post-op PT milestones, return-to-sport criteria, strength testing thresholds | `medical_necessity` |
| VisitsPlus Silver 4500 EOC — benefit section | Visit limits, copay schedule, rehab benefit definition | `coverage_rules` |

**How to add them:**

- **Option A — Manual (fastest for demo):** Write 20–30 JSONL lines directly into `snippets.jsonl` with the correct bucket tags. Takes ~30 minutes. Best for demo deadline.
- **Option B — Rebuild via `build_snippets.py`:** The script exists in `prototype/bucketed_retrieval/`. Point it at additional Kaiser URLs, re-run scraping, and merge output into `data/policy_snippets/snippets.jsonl`. More reproducible, good follow-up after the demo.

**Recommendation:** Do Option A for the 8–10 most important PT/medical-necessity chunks before the demo. Run Option B post-demo.

---

### Phase 4 (Post-Demo) — Migrate to a Proper Vector Store

For production or a more robust demo, the manual JSONL + numpy approach can be replaced with a lightweight vector database.

**Recommended: ChromaDB**

```bash
pip install chromadb
```

- In-memory or persistent on disk — no server needed
- Native metadata filtering (replaces the current `_chunk_matches_domain()` URL/content filter cleanly)
- Built-in hybrid search (BM25 + vector) out of the box
- Minimal code change — only `PolicySnippetCorpus` and `_rank_chunks()` internals change; everything above stays the same

**Alternative: FAISS (`faiss-cpu`)**
- Faster for large corpora (>10k chunks) but no metadata filtering — you'd still need the domain filter logic.
- Overkill for 134–500 chunks.

**The four-bucket structure does not change** — ChromaDB supports collection-level or metadata-field filtering to replicate the current bucket logic with a clean API.

---

## 6. Connecting to the Prompt Opinion Agent (Next Major Milestone After Phase 1–2)

The Orchestrator already outputs a `HandoffPacket` with `next_consumer = "prompt_opinion_agent"`. After Phase 1 and 2 are complete, this is the top priority.

**What needs to be built:**

1. `PromptOpinionAgent` class — takes `ExternalAgentResponse`, returns plain-language summary targeted at care coordinators / patients
2. System prompt: translate structured fields to natural language, use only `short_answer`, `sections`, `blocking_items`, `recommended_next_steps`, `benefits_at_a_glance` — do not invent coverage decisions
3. Wire as final step in `Orchestrator.run()`
4. A2A side: the adapter already packages the full response as a `data` artifact — the Prompt Opinion platform side needs to parse `external_agent_response`

**Known blocker:** A2A `SendA2AMessage` still returning protocol errors on the Prompt Opinion side — the `Task/Artifact/Message` structure needs further alignment.

**Completion summary (2026-05-04):**

| Item | Status |
|---|---|
| Phase 1: Remove BenefitsAgent | ✅ Complete |
| Phase 2: Embedding hybrid retrieval | ✅ Complete |
| Phase 3: PT corpus expansion | ✅ Complete (552 chunks, manual + script-based) |
| Phase 4: Vector database (ChromaDB) | Planned for future improvement |
| `PromptOpinionAgent` class | High priority, not started |
| A2A `SendA2AMessage` return body alignment | Known issue, defer to integration phase |
| End-to-end test: question → response | Ready for testing |
| Production RAG ranking tuning | Future work (ChromaDB would improve) |

**Current system state:**
- ✅ 3-agent architecture (Clinical → Insurance → Orchestrator)
- ✅ Hybrid embedding/keyword RAG (552-chunk corpus)
- ✅ Full pipeline end-to-end (demo case works)
- ⚠️ RAG ranking tuned but generic tables dominate (known limitation)
- 🔄 Ready for PromptOpinionAgent integration and A2A testing
