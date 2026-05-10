"""Test A2A integration with public URLs and PromptOpinionAgent."""
from __future__ import annotations

import json
from src.hackathon_agent.a2a import A2AAdapter
from src.hackathon_agent.orchestrator import Orchestrator
from src.hackathon_agent.demo_data import DEMO_CASE
from fastapi import Request
from unittest.mock import MagicMock


def test_agent_card_with_public_url() -> None:
    """Test agent card discovery endpoint with public base URL."""
    orchestrator = Orchestrator.from_env()
    adapter = A2AAdapter(orchestrator)

    # Mock a request with a public base URL
    request = MagicMock(spec=Request)
    request.base_url = "https://recovery-iq.example.com/"

    card = adapter.build_agent_card(request)

    print("=" * 80)
    print("Agent Card (Discovery Endpoint)")
    print("=" * 80)
    print(json.dumps(card, indent=2))

    # Verify key fields
    assert card["protocolVersion"] == "0.3.0"
    assert card["url"] == "https://recovery-iq.example.com/a2a"
    assert card["name"] == "hackathon_recovery_intelligence_agent"
    assert card["preferredTransport"] == "JSONRPC"
    print("\n✓ Agent card structure is correct")


def test_a2a_json_rpc_with_opinion() -> None:
    """Test A2A JSON-RPC endpoint with PromptOpinionAgent integration."""
    orchestrator = Orchestrator.from_env()
    adapter = A2AAdapter(orchestrator)

    # Create a JSON-RPC request to send a message
    payload = {
        "jsonrpc": "2.0",
        "id": "test-123",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "text": "Is Daniel eligible for 2x/week PT under his Kaiser plan?"
                    }
                ],
                "messageId": "msg-1",
                "taskId": "task-1",
                "contextId": "context-1",
            },
            "metadata": {
                "case": DEMO_CASE.model_dump(),
            }
        }
    }

    print("\n" + "=" * 80)
    print("A2A JSON-RPC Request (message/send)")
    print("=" * 80)
    print(f"Method: {payload['method']}")
    print(f"Request ID: {payload['id']}")

    # Call the A2A handler
    response = adapter.handle_json_rpc(payload)

    print("\n" + "=" * 80)
    print("A2A JSON-RPC Response")
    print("=" * 80)
    print(json.dumps(response, indent=2, default=str)[:2000] + "...")

    # Verify response structure
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == "test-123"
    assert "result" in response
    assert "error" not in response

    task = response["result"].get("task") or response["result"]
    assert task["id"]
    assert task["status"]["state"] == "completed"
    assert len(task["artifacts"]) == 1

    artifact_names = [a["name"] for a in task["artifacts"]]
    assert "external_agent_response" in artifact_names
    assert "plain_language_opinion" not in artifact_names
    assert "external_agent_response" not in task["metadata"]

    artifact = task["artifacts"][0]
    artifact_text = artifact["parts"][0]["text"]
    artifact_packet = json.loads(artifact_text)
    assert artifact_packet["packet_type"] == "prompt_opinion_external_agent_response"
    assert "open_questions" not in artifact_packet

    print("\n✓ A2A response contains one structured artifact")
    print("✓ Plain-language opinion is returned only in status.message")


def test_authenticated_extended_card() -> None:
    """Test authenticated extended card endpoint."""
    orchestrator = Orchestrator.from_env()
    adapter = A2AAdapter(orchestrator)

    request = MagicMock(spec=Request)
    request.base_url = "https://recovery-iq.example.com/"

    card = adapter.build_authenticated_extended_card(request)

    print("\n" + "=" * 80)
    print("Authenticated Extended Card")
    print("=" * 80)
    print(json.dumps(card, indent=2))

    assert "metadata" in card
    assert "debugEndpoint" in card["metadata"]
    print("\n✓ Extended card contains debug endpoint")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("A2A Integration Tests with PromptOpinionAgent")
    print("=" * 80)

    test_agent_card_with_public_url()
    test_a2a_json_rpc_with_opinion()
    test_authenticated_extended_card()

    print("\n" + "=" * 80)
    print("All tests passed!")
    print("=" * 80)
