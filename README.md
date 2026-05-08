---
title: RecoveryIQ - PT Authorization Agent
emoji: 🏥
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
app_port: 7860
---

# RecoveryIntelligenceSystem
## Medical A2A Workflow

This project builds a multi-agent clinical + insurance reasoning workflow for physical therapy (PT) authorization decisions.

## How It Works

The system uses four specialized agents working in sequence:

### Components
- **Clinical Agent**: Reads patient summary, clinical notes, PT assessments, and imaging studies to determine clinical necessity for PT
- **Insurance Agent**: Retrieves relevant policy clauses and matches clinical evidence against coverage requirements using RAG
- **Orchestrator**: Compares clinical and insurance positions, detects conflicts, and generates a recommended workflow with blocking requirements
- **PromptOpinionAgent**: Converts structured agent outputs into plain-language markdown summaries for care coordinators

## Deployment

This Space implements the **A2A (Agent-to-Agent) Protocol** to integrate with the Prompt Opinion Marketplace.

### Agent Card
The agent is discoverable at:
```
https://<space-url>/.well-known/agent-card.json
```

### A2A Endpoint
The agent accepts JSON-RPC 2.0 requests at:
```
POST https://<space-url>/a2a
```

### Example Query
```bash
curl -X POST https://<space-url>/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-1",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "Is Daniel eligible for 2x/week PT?"}]
      }
    }
  }'
```

## Running Locally

### Prerequisites
```bash
cd prototype
export GEMINI_API_KEY="your-gemini-api-key"
pip install -r requirements.txt
```

### Start the Service
```bash
uvicorn src.hackathon_agent.app:app --reload --host 0.0.0.0 --port 8000
```

### Available Endpoints
- Health check: `GET /health`
- Demo case: `GET /demo-case`
- Agent card: `GET /.well-known/agent-card.json`
- A2A endpoint: `POST /a2a`
- Direct invocation: `POST /run-case`
- Web UI: `GET /explore`

### Run Tests
```bash
python test_public_url.py http://localhost:8000 --with-case
python run_orchestrator_with_opinion.py
```

## Architecture

See `SYSTEM_ARCHITECTURE_CHART.md` and `SYSTEM_WORKFLOW.md` for detailed diagrams and data flow documentation.

## Integration with Prompt Opinion Marketplace

Once deployed to Hugging Face Spaces:
1. Get your Space URL: `https://<username>-recovery-iq.hf.space`
2. Share the agent card URL with Prompt Opinion: `https://<username>-recovery-iq.hf.space/.well-known/agent-card.json`
3. Prompt Opinion will auto-discover your agent and route PT authorization queries to your A2A endpoint

See `prototype/PROMPT_OPINION_CHECKLIST.md` for full integration steps.

## Current Goal

Build a minimal end-to-end demo where:
1. User asks a care question
2. Backend agent system returns structured JSON
3. Prompt Opinion Marketplace renders the result into a user-friendly answer for care coordinators

## References

- **Architecture**: `SYSTEM_ARCHITECTURE_CHART.md`
- **Workflow**: `SYSTEM_WORKFLOW.md`
- **Deployment**: `prototype/START_SERVICE.md`
- **A2A Protocol**: `prototype/A2A_DEPLOYMENT.md`
- **Integration Checklist**: `prototype/PROMPT_OPINION_CHECKLIST.md`
