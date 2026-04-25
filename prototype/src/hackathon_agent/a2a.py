from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, Request

from .demo_data import DEMO_CASE
from .orchestrator import Orchestrator
from .schemas import CaseData, ExternalAgentResponse


@dataclass
class StoredTask:
    response: ExternalAgentResponse
    task: dict[str, Any]


class A2AAdapter:
    def __init__(self, orchestrator: Orchestrator) -> None:
        self.orchestrator = orchestrator
        self._tasks: dict[str, StoredTask] = {}

    def build_agent_card(self, request: Request) -> dict[str, Any]:
        base_url = str(request.base_url).rstrip("/")
        a2a_url = f"{base_url}/a2a"
        return {
            "name": "hackathon_recovery_intelligence_agent",
            "description": (
                "External orchestrator agent for recovery planning. It analyzes the current "
                "clinical situation, insurance authorization constraints, and fixed-plan "
                "benefit rules, then returns a structured packet for Prompt Opinion to summarize."
            ),
            "url": a2a_url,
            "supportedInterfaces": [
                {
                    "url": a2a_url,
                    "protocolBinding": "JSONRPC",
                    "protocolVersion": "1.0",
                }
            ],
            "version": "0.1.0",
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
            },
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain", "application/json"],
            "skills": [
                {
                    "id": "pt_eligibility_review",
                    "name": "PT Eligibility Review",
                    "description": (
                        "Assess likely eligibility for additional supervised physical therapy, "
                        "required documentation, and the next care-plan steps."
                    ),
                    "tags": [
                        "clinical",
                        "insurance",
                        "physical-therapy",
                        "authorization",
                        "care-plan",
                    ],
                    "inputModes": ["text/plain"],
                    "outputModes": ["text/plain", "application/json"],
                }
            ],
            "supportsAuthenticatedExtendedCard": False,
        }

    def build_authenticated_extended_card(self, request: Request) -> dict[str, Any]:
        card = self.build_agent_card(request)
        card["additionalInterfaces"] = {
            "debugEndpoint": f"{str(request.base_url).rstrip('/')}/run-case-debug",
        }
        return card

    def handle_json_rpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        jsonrpc = payload.get("jsonrpc")
        request_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params", {})

        if jsonrpc != "2.0":
            return self._error_response(request_id, code=-32600, message="Invalid JSON-RPC version.")

        try:
            if method == "message/send":
                return self._message_send(request_id, params)
            if method == "tasks/get":
                return self._tasks_get(request_id, params)
            if method == "tasks/cancel":
                return self._error_response(
                    request_id,
                    code=-32601,
                    message="tasks/cancel is not supported by this agent.",
                )
            return self._error_response(request_id, code=-32601, message=f"Method not found: {method}")
        except HTTPException as exc:
            return self._error_response(request_id, code=-32000, message=exc.detail)
        except Exception as exc:
            return self._error_response(request_id, code=-32000, message=str(exc))

    def _message_send(self, request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        message = params.get("message", {})
        text = self._extract_text(message)
        if not text:
            raise HTTPException(status_code=400, detail="A2A message/send requires a text message.")

        case = self._extract_case(params) or DEMO_CASE
        response = self.orchestrator.run(user_question=text, case=case)
        task = self._build_task(message=message, response=response)
        self._tasks[task["id"]] = StoredTask(response=response, task=task)

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": task,
        }

    def _tasks_get(self, request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        task_id = params.get("id")
        if not task_id or task_id not in self._tasks:
            return self._error_response(request_id, code=-32001, message="Task not found.")

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": self._tasks[task_id].task,
        }

    def _extract_text(self, message: dict[str, Any]) -> str:
        for part in message.get("parts", []):
            if part.get("kind") == "text" and part.get("text"):
                return str(part["text"]).strip()
        return ""

    def _extract_case(self, params: dict[str, Any]) -> CaseData | None:
        metadata = params.get("metadata", {})
        raw_case = metadata.get("case")
        if not raw_case:
            return None
        return CaseData.model_validate(raw_case)

    def _build_task(self, *, message: dict[str, Any], response: ExternalAgentResponse) -> dict[str, Any]:
        task_id = str(uuid4())
        context_id = str(uuid4())
        artifact_id = str(uuid4())
        user_message_id = str(message.get("messageId") or uuid4())
        agent_message_id = str(uuid4())
        user_message = {
            "role": "user",
            "parts": message.get("parts", []),
            "messageId": user_message_id,
            "taskId": task_id,
            "contextId": context_id,
            "kind": "message",
            "metadata": {},
        }
        agent_message = {
            "role": "agent",
            "parts": [
                {
                    "kind": "text",
                    "text": response.short_answer,
                }
            ],
            "messageId": agent_message_id,
            "taskId": task_id,
            "contextId": context_id,
            "kind": "message",
            "metadata": {},
        }
        return {
            "id": task_id,
            "contextId": context_id,
            "kind": "task",
            "status": {
                "state": "completed",
                "message": agent_message,
            },
            "history": [user_message, agent_message],
            "artifacts": [
                {
                    "artifactId": artifact_id,
                    "name": "external_agent_response",
                    "description": "Structured external-agent packet for Prompt Opinion.",
                    "parts": [
                        {
                            "kind": "text",
                            "text": response.short_answer,
                        },
                        {
                            "kind": "data",
                            "data": response.model_dump(mode="json"),
                        },
                    ],
                }
            ],
            "metadata": {
                "case_id": response.case_id,
                "readiness": response.readiness.value,
                "requires_human_review": response.requires_human_review,
            },
        }

    def _error_response(self, request_id: Any, *, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }
