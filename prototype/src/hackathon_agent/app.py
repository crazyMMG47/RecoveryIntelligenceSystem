from fastapi import FastAPI, Request

from .a2a import A2AAdapter
from .demo_data import DEMO_CASE
from .orchestrator import Orchestrator
from .schemas import ExternalAgentResponse, RunCaseDebugResponse, RunCaseRequest


app = FastAPI(title="Hackathon Agent API", version="0.1.0")
orchestrator = Orchestrator.from_env()
a2a_adapter = A2AAdapter(orchestrator)


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


@app.post("/a2a")
def a2a_rpc(payload: dict, request: Request) -> dict:
    _ = request
    return a2a_adapter.handle_json_rpc(payload)


@app.post("/")
def root_rpc(payload: dict, request: Request) -> dict:
    _ = request
    return a2a_adapter.handle_json_rpc(payload)


@app.post("/run-case", response_model=ExternalAgentResponse)
def run_case(request: RunCaseRequest) -> ExternalAgentResponse:
    return orchestrator.run(user_question=request.user_question, case=request.case)


@app.post("/run-case-debug", response_model=RunCaseDebugResponse)
def run_case_debug(request: RunCaseRequest) -> RunCaseDebugResponse:
    return orchestrator.run_debug(user_question=request.user_question, case=request.case)
