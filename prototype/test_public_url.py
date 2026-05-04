#!/usr/bin/env python
"""Test the A2A endpoints with a public/custom base URL."""
from __future__ import annotations

import json
import sys
import requests
from src.hackathon_agent.demo_data import DEMO_CASE


def test_agent_card(base_url: str) -> None:
    """Fetch and display the agent card."""
    url = f"{base_url}/.well-known/agent-card.json"
    print(f"\n{'='*80}")
    print("Testing Agent Card Discovery")
    print(f"{'='*80}")
    print(f"URL: {url}")

    try:
        response = requests.get(url)
        response.raise_for_status()
        card = response.json()

        print(f"\n✓ Agent card fetched successfully")
        print(f"  - Protocol: {card.get('protocolVersion')}")
        print(f"  - Name: {card.get('name')}")
        print(f"  - A2A URL: {card.get('url')}")
        print(f"  - Skills: {len(card.get('skills', []))} available")

        return card
    except Exception as exc:
        print(f"✗ Failed to fetch agent card: {exc}")
        return None


def test_a2a_invoke(base_url: str, case_data: dict | None = None) -> None:
    """Invoke the A2A endpoint and display results."""
    url = f"{base_url}/a2a"
    print(f"\n{'='*80}")
    print("Testing A2A Invocation (message/send)")
    print(f"{'='*80}")
    print(f"URL: {url}")

    payload = {
        "jsonrpc": "2.0",
        "id": "public-test-1",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "text": "Is Daniel eligible for 2x/week PT under his Kaiser plan? What documentation is needed?"
                    }
                ],
            },
        }
    }

    if case_data:
        payload["params"]["metadata"] = {"case": case_data}

    try:
        print(f"\n→ Sending request (this may take 30-60 seconds)...")
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()

        if "error" in result:
            print(f"✗ A2A error: {result['error']}")
            return

        print(f"\n✓ A2A invocation successful")

        task = result.get("result", {}).get("task") or result.get("result", {})
        print(f"  - Task ID: {task.get('id')}")
        print(f"  - Status: {task.get('status', {}).get('state')}")
        print(f"  - Artifacts: {len(task.get('artifacts', []))} available")

        # Display artifact names
        for i, artifact in enumerate(task.get("artifacts", []), 1):
            name = artifact.get("name")
            desc = artifact.get("description")
            print(f"    {i}. {name}: {desc}")

        # Display the plain-language opinion
        print(f"\n{'='*80}")
        print("Plain-Language Opinion (from PromptOpinionAgent)")
        print(f"{'='*80}")
        message = task.get("status", {}).get("message", {})
        parts = message.get("parts", [])
        if parts:
            text = parts[0].get("text", "")
            # Show first 1000 chars
            preview = text[:1000]
            print(preview)
            if len(text) > 1000:
                print(f"\n... ({len(text) - 1000} more characters)")

    except requests.Timeout:
        print(f"✗ Request timed out after 120 seconds")
    except Exception as exc:
        print(f"✗ A2A invocation failed: {exc}")


def main() -> None:
    """Main test runner."""
    if len(sys.argv) < 2:
        print("Usage: python test_public_url.py <base_url> [--with-case]")
        print("\nExamples:")
        print("  python test_public_url.py http://localhost:8000")
        print("  python test_public_url.py https://recovery-iq.example.com --with-case")
        print("  python test_public_url.py https://xxxx-xx-xxx-xxx.ngrok.io")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")
    with_case = "--with-case" in sys.argv

    print(f"\n{'='*80}")
    print("RecoveryIQ A2A Public URL Tests")
    print(f"{'='*80}")
    print(f"Base URL: {base_url}")

    card = test_agent_card(base_url)

    if card:
        case_data = DEMO_CASE.model_dump() if with_case else None
        test_a2a_invoke(base_url, case_data)

    print(f"\n{'='*80}")
    print("Tests Complete")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
