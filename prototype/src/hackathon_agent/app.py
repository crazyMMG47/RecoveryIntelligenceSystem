from pathlib import Path
import json
import logging
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
a2a_adapter = A2AAdapter(orchestrator)

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
def a2a_metadata(request: Request) -> dict:
    """A2A endpoint metadata discovery (called by Prompt Opinion for validation)."""
    return a2a_adapter.build_agent_card(request)


@app.post("/a2a")
async def a2a_rpc(request: Request) -> dict:
    """A2A JSON-RPC 2.0 endpoint for Prompt Opinion.

    Accepts a JSON-RPC 2.0 request body and returns a JSON-RPC 2.0 response.
    """
    try:
        # Read the raw request body
        body = await request.body()
        if not body:
            logger.warning("A2A POST received empty body")
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error: empty body",
                },
            }

        # Parse JSON
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error("A2A POST received invalid JSON: %s", str(e))
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: invalid JSON: {str(e)}",
                },
            }

        # Log the incoming request
        request_id = payload.get("id")
        method = payload.get("method")
        logger.info(
            "A2A POST /a2a - request_id=%s method=%s jsonrpc=%s body_len=%d",
            request_id,
            method,
            payload.get("jsonrpc"),
            len(body),
        )
        logger.debug("A2A POST /a2a - full request: %s", json.dumps(payload, default=str)[:1500])

        # TEMPORARY: Use minimal response for Prompt Opinion compatibility testing
        if USE_MINIMAL_A2A_RESPONSE:
            response = _build_minimal_a2a_response(request_id)
            logger.info(
                "A2A POST /a2a (MINIMAL MODE) - response_id=%s",
                response.get("id"),
            )
            logger.debug("A2A POST /a2a - minimal response: %s", json.dumps(response, default=str)[:1500])
            return response

        # PRODUCTION: Call the full adapter
        response = a2a_adapter.handle_json_rpc(payload, request)

        # Log the response
        logger.info(
            "A2A POST /a2a - response_id=%s has_error=%s",
            response.get("id"),
            "error" in response,
        )
        logger.debug("A2A POST /a2a - full response: %s", json.dumps(response, default=str)[:1500])

        return response
    except Exception as e:
        logger.exception("A2A POST /a2a - unhandled exception")
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}",
            },
        }


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
                            "text": "Hello from Recovery Intelligence System. This is a minimal response for compatibility testing.",
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
