from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, Request

from .demo_data import DEMO_CASE
from .orchestrator import Orchestrator
from .schemas import CaseData, ExternalAgentResponse


logger = logging.getLogger(__name__)


@dataclass
class StoredTask:
    response: ExternalAgentResponse
    task: dict[str, Any]


class A2AAdapter:
    def __init__(self, orchestrator: Orchestrator, public_base_url: str | None = None) -> None:
        self.orchestrator = orchestrator
        self._tasks: dict[str, StoredTask] = {}
        self.public_base_url = public_base_url

    def build_agent_card(self, request: Request) -> dict[str, Any]:
        # Use public base URL if provided (for Hugging Face Spaces and production)
        # Otherwise fall back to request-inferred URL (for localhost/ngrok testing)
        if self.public_base_url:
            base_url = self.public_base_url
        else:
            base_url = str(request.base_url).rstrip("/")

        a2a_url = f"{base_url}/a2a"
        return {
            "protocolVersion": "0.3.0",
            "name": "hackathon_recovery_intelligence_agent",
            "description": (
                "External orchestrator agent for recovery planning. It analyzes the current "
                "clinical situation, insurance authorization constraints, and fixed-plan "
                "benefit rules, then returns a structured packet for Prompt Opinion to summarize."
            ),
            "url": a2a_url,
            "preferredTransport": "JSONRPC",
            "additionalInterfaces": [
                {
                    "url": a2a_url,
                    "transport": "JSONRPC",
                }
            ],
            # Legacy clients may still inspect this pre-0.3 field.
            "supportedInterfaces": [
                {
                    "url": a2a_url,
                    "protocolBinding": "JSONRPC",
                    "protocolVersion": "0.3.0",
                }
            ],
            "version": "0.1.0",
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
                "stateTransitionHistory": False,
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
        card["metadata"] = {
            "debugEndpoint": f"{str(request.base_url).rstrip('/')}/run-case-debug",
        }
        return card

    def handle_json_rpc(self, payload: dict[str, Any], request: Request | None = None) -> dict[str, Any]:
        jsonrpc = payload.get("jsonrpc")
        request_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params", {})

        if jsonrpc != "2.0":
            return self._error_response(request_id, code=-32600, message="Invalid JSON-RPC version.")

        try:
            logger.info("A2A request method=%s params_keys=%s", method, sorted(params.keys()))
            if method in {"message/send", "tasks/send", "SendMessage", "SendA2AMessage"}:
                response = self._message_send(
                    request_id,
                    params,
                    proto_style=method in {"SendMessage", "SendA2AMessage"},
                )
                logger.info("A2A response method=%s summary=%s", method, self._response_summary(response))
                return response
            if method == "agent/getAuthenticatedExtendedCard":
                if request is None:
                    return self._error_response(
                        request_id,
                        code=-32603,
                        message="Request context is required for agent card generation.",
                    )
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": self.build_authenticated_extended_card(request),
                }
                logger.info("A2A response method=%s summary=%s", method, self._response_summary(response))
                return response
            if method in {"tasks/get", "GetTask"}:
                response = self._tasks_get(request_id, params)
                logger.info("A2A response method=%s summary=%s", method, self._response_summary(response))
                return response
            if method == "tasks/cancel":
                return self._error_response(
                    request_id,
                    code=-32601,
                    message="tasks/cancel is not supported by this agent.",
                )
            return self._error_response(request_id, code=-32601, message=f"Method not found: {method}")
        except HTTPException as exc:
            response = self._error_response(request_id, code=-32000, message=exc.detail)
            logger.exception("A2A HTTPException method=%s", method)
            return response
        except Exception as exc:
            response = self._error_response(request_id, code=-32000, message=str(exc))
            logger.exception("A2A exception method=%s", method)
            return response

    def _message_send(
        self,
        request_id: Any,
        params: dict[str, Any],
        *,
        proto_style: bool = False,
    ) -> dict[str, Any]:
        message = self._extract_message(params)
        text = self._extract_text(message)
        if not text:
            raise HTTPException(
                status_code=400,
                detail=(
                    "A2A send requires a text message. "
                    f"params_keys={sorted(params.keys())}"
                ),
            )

        case = self._extract_case(params) or DEMO_CASE
        response = self.orchestrator.run(user_question=text, case=case)
        opinion = self.orchestrator.generate_opinion(response)
        task = self._build_task(message=message, response=response, opinion=opinion, proto_style=proto_style)
        self._tasks[task["id"]] = StoredTask(response=response, task=task)
        result = {"task": task} if proto_style else task

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    def _tasks_get(self, request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        task_id = params.get("id") or params.get("taskId")
        if not task_id or task_id not in self._tasks:
            return self._error_response(request_id, code=-32001, message="Task not found.")

        task = self._tasks[task_id].task
        is_proto_style = task.get("status", {}).get("state") == "TASK_STATE_COMPLETED"
        result = {"task": task} if is_proto_style else task

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    def _extract_text(self, message: dict[str, Any]) -> str:
        for part in message.get("parts", []):
            if part.get("text"):
                return str(part["text"]).strip()
            if part.get("kind") == "text" and part.get("text"):
                return str(part["text"]).strip()
            if part.get("type") == "text" and part.get("text"):
                return str(part["text"]).strip()
            if part.get("kind") == "text" and part.get("content"):
                return str(part["content"]).strip()
        return ""

    def _extract_message(self, params: dict[str, Any]) -> dict[str, Any]:
        message = params.get("message")
        if isinstance(message, dict):
            return message

        content = params.get("content")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                    parts.append({"kind": "text", "text": item["text"]})
                elif isinstance(item, dict) and item.get("kind") == "text" and item.get("text"):
                    parts.append({"kind": "text", "text": item["text"]})
            return {
                "role": "user",
                "parts": parts,
                "messageId": str(params.get("messageId") or uuid4()),
            }

        text = params.get("text") or params.get("input")
        if text:
            return {
                "role": "user",
                "parts": [{"kind": "text", "text": str(text)}],
                "messageId": str(params.get("messageId") or uuid4()),
            }

        return {}

    def _extract_case(self, params: dict[str, Any]) -> CaseData | None:
        metadata = params.get("metadata", {})
        raw_case = metadata.get("case")
        if not raw_case:
            return None
        return CaseData.model_validate(raw_case)

    def _build_task(
        self,
        *,
        message: dict[str, Any],
        response: ExternalAgentResponse,
        opinion: str | None = None,
        proto_style: bool = False,
    ) -> dict[str, Any]:
        task_id = str(message.get("taskId") or uuid4())
        context_id = str(message.get("contextId") or uuid4())
        user_message_id = str(message.get("messageId") or uuid4())
        agent_message_id = str(uuid4())
        timestamp = datetime.now(UTC).isoformat()
        user_parts = self._normalize_parts(message.get("parts", []), proto_style=proto_style)
        status_parts = self._text_parts(opinion or response.short_answer, proto_style=proto_style)
        user_role = "ROLE_USER" if proto_style else "user"
        agent_role = "ROLE_AGENT" if proto_style else "agent"
        user_message = {
            "role": user_role,
            "parts": user_parts,
            "messageId": user_message_id,
            "taskId": task_id,
            "contextId": context_id,
            "kind": "message",
            "metadata": {},
        }
        agent_message = {
            "role": agent_role,
            "parts": status_parts,
            "messageId": agent_message_id,
            "taskId": task_id,
            "contextId": context_id,
            "kind": "message",
            "metadata": {},
        }
        return {
            "id": task_id,
            "contextId": context_id,
            "status": {
                "state": "TASK_STATE_COMPLETED" if proto_style else "completed",
                "message": agent_message,
                "timestamp": timestamp,
            },
            "history": [user_message, agent_message],
            "metadata": {
                "case_id": response.case_id,
                "readiness": response.readiness.value,
                "requires_human_review": response.requires_human_review,
            },
            **({} if proto_style else {"kind": "task"}),
        }

    def _normalize_parts(self, parts: list[dict[str, Any]], *, proto_style: bool) -> list[dict[str, Any]]:
        normalized = []
        for part in parts:
            text = part.get("text") or part.get("content")
            if not text:
                continue
            normalized.extend(self._text_parts(str(text), proto_style=proto_style))
        return normalized

    def _text_parts(self, text: str, *, proto_style: bool) -> list[dict[str, str]]:
        if proto_style:
            return [{"text": text}]
        return [{"kind": "text", "text": text}]

    def _error_response(self, request_id: Any, *, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    def _compact_log(self, value: Any) -> str:
        text = json.dumps(value, ensure_ascii=True, default=str)
        if len(text) <= 1200:
            return text
        return text[:1200] + "...<truncated>"

    def _response_summary(self, response: dict[str, Any]) -> str:
        if "error" in response:
            return self._compact_log(response["error"])
        result = response.get("result", {})
        if not isinstance(result, dict):
            return self._compact_log(result)
        task = result.get("task") if isinstance(result.get("task"), dict) else result
        if task.get("kind") == "task" or "status" in task:
            return self._compact_log(
                {
                    "has_task_wrapper": "task" in result,
                    "kind": task.get("kind"),
                    "status": task.get("status", {}).get("state"),
                    "artifact_count": len(task.get("artifacts", [])),
                    "metadata_keys": sorted(task.get("metadata", {}).keys()),
                }
            )
        return self._compact_log(
            {
                "kind": result.get("kind"),
                "keys": sorted(result.keys()),
            }
        )
