# Demo 1 without RAG

## What this is

This directory contains the current prototype for the Recovery Intelligence System hackathon project.

Current scope:

- Clinical Agent uses Gemini and returns structured output
- Insurance Authorization Agent uses Kaiser snippet retrieval + Gemini + schema validation
- Insurance Benefits Agent uses a fixed official Kaiser demo plan to estimate coverage rules and cost-sharing
- Orchestrator is code-first and returns a Prompt Opinion-facing data packet by default
- Prompt Opinion connection is planned but not implemented yet

## Current architecture

| Layer | Current status |
|---|---|
| External Orchestrator Agent | Planned as the only public-facing external agent |
| Clinical Agent | Gemini-based structured output is the only runtime path |
| Insurance Authorization Agent | Kaiser snippet retrieval + Gemini structured output + contract validation |
| Insurance Benefits Agent | Fixed-plan code-first coverage and cost-sharing estimator |
| Orchestrator | Consumes internal outputs and emits a Prompt Opinion-facing answer packet |

## Files to look at

| File | Purpose |
|---|---|
| `Plan.md` | Current project plan |
| `progress.md` | Current progress summary |
| `case.md` | Demo case |
| `clinical_agent_prompt.md` | Clinical Agent prompt spec |
| `src/hackathon_agent/` | Core code |
| `run_clinical_llm.py` | Clinical Agent test runner |
| `run_policy_retriever.py` | Inspect bucketed Kaiser policy retrieval on top of the real Clinical output |
| `run_insurance_llm.py` | Insurance Agent test runner |
| `run_orchestrator_demo.py` | Full orchestrator demo runner |
| `data/policies/kaiser_urls.txt` | Source URL manifest for the Kaiser policy corpus |
| `data/policy_snippets/snippets.jsonl` | Local chunked Kaiser policy corpus used at runtime |

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
export GEMINI_API_KEY="YOUR_KEY_HERE"
```

## Test commands

### Test Clinical Agent only

```bash
PYTHONPATH=src python run_clinical_llm.py
```

### Test full orchestrator flow

```bash
PYTHONPATH=src python run_orchestrator_demo.py
```

### Inspect full internal debug packet

`POST /run-case-debug` returns the internal agent-to-agent packet for debugging.

### Inspect retrieval only

```bash
PYTHONPATH=src python run_policy_retriever.py
```

### Test Insurance Agent only

```bash
PYTHONPATH=src python run_insurance_llm.py
```

Clinical and Insurance now both run through a single Gemini-based path. `/run-case` returns the external packet for Prompt Opinion, while `/run-case-debug` exposes the internal packet. If `GEMINI_API_KEY` is missing, the app fails immediately.

## What has been proven

- Gemini can return structured `ClinicalAgentOutput`
- Insurance retrieval can route into a real Kaiser snippet corpus and return bucketed evidence
- Insurance benefits can now explain the fixed demo plan's visit limits, deductible, coinsurance, and out-of-pocket maximum
- Insurance output is contract-validated before it reaches the orchestrator
- Clinical output can flow into Orchestrator
- Orchestrator can generate a stable external packet for Prompt Opinion plus an internal debug packet

## What is not done yet

- A2A adapter
- Prompt Opinion connection
- ngrok exposure
