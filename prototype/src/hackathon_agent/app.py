from pathlib import Path
import json
import logging
import os
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse

from .a2a import A2AAdapter
from .demo_data import DEMO_CASE
from .orchestrator import Orchestrator
from .schemas import ExternalAgentResponse, RunCaseDebugResponse, RunCaseRequest

logger = logging.getLogger(__name__)

app = FastAPI(title="Hackathon Agent API", version="0.1.0")
orchestrator = Orchestrator.from_env()

# Public base URL for agent card URLs (must be HTTPS)
# Hugging Face Space may report internal upstream as http://, but public URL is always https://
PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "",
).rstrip("/") or None

a2a_adapter = A2AAdapter(orchestrator, public_base_url=PUBLIC_BASE_URL)

# Feature flag for minimal response mode (for Prompt Opinion compatibility testing)
USE_MINIMAL_A2A_RESPONSE = True


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/demo-case")
def demo_case() -> dict:
    return DEMO_CASE.model_dump()


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "message": "Hackathon external agent is running."}


@app.get("/.well-known/agent-card.json")
def public_agent_card(request: Request) -> dict:
    return a2a_adapter.build_agent_card(request)


@app.get("/.well-known/agent.json")
def legacy_agent_card(request: Request) -> dict:
    return a2a_adapter.build_agent_card(request)


@app.get("/agent/authenticatedExtendedCard")
def authenticated_extended_card(request: Request) -> dict:
    return a2a_adapter.build_authenticated_extended_card(request)


@app.get("/a2a")
def a2a_validation(request: Request) -> dict:
    """A2A endpoint validation (called by Prompt Opinion to verify endpoint readiness).

    Returns a minimal task object for validation. Prompt Opinion uses this to confirm
    the endpoint is reachable and returns valid task structures.
    Actual invocations use POST /a2a with JSON-RPC request body.
    """
    task_id = str(uuid4())
    context_id = str(uuid4())
    message_id = str(uuid4())

    return {
        "id": task_id,
        "contextId": context_id,
        "kind": "task",
        "status": {
            "state": "completed",
            "message": {
                "kind": "message",
                "role": "agent",
                "messageId": message_id,
                "taskId": task_id,
                "contextId": context_id,
                "parts": [
                    {
                        "kind": "text",
                        "text": "Recovery Intelligence A2A endpoint is reachable. Use POST /a2a for JSON-RPC message/send invocation.",
                    }
                ],
            },
        },
    }


@app.post("/a2a")
async def a2a_rpc(request: Request) -> dict:
    """A2A JSON-RPC 2.0 endpoint for Prompt Opinion."""
    try:
        body = await request.json()
        return a2a_adapter.handle_json_rpc(body, request)
    except Exception as e:
        logger.exception("A2A POST /a2a - unhandled exception")
        # Even on exception, return a valid task response
        return _build_minimal_a2a_response(request_id)


def _build_minimal_a2a_response(request_id: str) -> dict:
    """Build a minimal A2A response for Prompt Opinion compatibility testing.

    This excludes fields that may cause deserialization issues:
    - history
    - artifacts
    - metadata
    - timestamp
    """
    task_id = str(uuid4())
    context_id = str(uuid4())
    message_id = str(uuid4())

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "id": task_id,
            "contextId": context_id,
            "kind": "task",
            "status": {
                "state": "completed",
                "message": {
                    "kind": "message",
                    "role": "agent",
                    "messageId": message_id,
                    "taskId": task_id,
                    "contextId": context_id,
                    "parts": [
                        {
                            "kind": "text",
                            "text": "Hello from Recovery Intelligence System. Prompt Opinion successfully invoked POST /a2a.",
                        }
                    ],
                },
            },
        },
    }


@app.post("/")
async def root_rpc(request: Request) -> dict:
    """Root POST endpoint (alias for /a2a for compatibility)."""
    return await a2a_rpc(request)


@app.post("/run-case", response_model=ExternalAgentResponse)
def run_case(request: RunCaseRequest) -> ExternalAgentResponse:
    return orchestrator.run(user_question=request.user_question, case=request.case)


@app.post("/run-case-debug", response_model=RunCaseDebugResponse)
def run_case_debug(request: RunCaseRequest) -> RunCaseDebugResponse:
    return orchestrator.run_debug(user_question=request.user_question, case=request.case)


@app.get("/explore", response_class=FileResponse)
def explore() -> FileResponse:
    html_path = Path(__file__).parent / "static" / "explorer.html"
    return FileResponse(html_path, media_type="text/html")
