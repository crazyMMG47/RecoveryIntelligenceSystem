from fastapi import FastAPI

from .demo_data import DEMO_CASE
from .orchestrator import Orchestrator
from .schemas import RunCaseRequest, RunCaseResponse


app = FastAPI(title="Hackathon Agent API", version="0.1.0")
orchestrator = Orchestrator.from_env()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/demo-case")
def demo_case() -> dict:
    return DEMO_CASE.model_dump()


@app.post("/run-case", response_model=RunCaseResponse)
def run_case(request: RunCaseRequest) -> RunCaseResponse:
    return orchestrator.run(user_question=request.user_question, case=request.case)
