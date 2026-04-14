# Demo 1 without RAG

## What this is

This directory contains the current prototype for the Recovery Intelligence System hackathon project.

Current scope:

- Clinical Agent uses Gemini and returns structured output
- Insurance Agent is still rule-based
- Orchestrator is code-first
- Prompt Opinion connection is planned but not implemented yet

## Current architecture

| Layer | Current status |
|---|---|
| External Orchestrator Agent | Planned as the only public-facing external agent |
| Clinical Agent | Gemini-based structured output is working |
| Insurance Agent | Rule-based placeholder, no retrieval yet |
| Orchestrator | Consumes Clinical + Insurance outputs and produces structured workflow |

## Files to look at

| File | Purpose |
|---|---|
| `Plan.md` | Current project plan |
| `progress.md` | Current progress summary |
| `case.md` | Demo case |
| `clinical_agent_prompt.md` | Clinical Agent prompt spec |
| `src/hackathon_agent/` | Core code |
| `run_clinical_llm.py` | Clinical Agent test runner |
| `run_orchestrator_demo.py` | Full orchestrator demo runner |

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
USE_GEMINI_CLINICAL_AGENT=true PYTHONPATH=src python run_orchestrator_demo.py
```

## What has been proven

- Gemini can return structured `ClinicalAgentOutput`
- Clinical output can flow into Orchestrator
- Orchestrator can generate structured workflow and blocking requirements

## What is not done yet

- Insurance retrieval
- Insurance Gemini integration
- A2A adapter
- Prompt Opinion connection
- ngrok exposure
