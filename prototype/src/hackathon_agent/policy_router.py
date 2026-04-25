from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schemas import InsuranceAgentInput


@dataclass(frozen=True)
class RoutedPolicyPlan:
    domain: str
    intents: list[str]
    candidate_urls: list[str]
    notes: list[str] = field(default_factory=list)


_DOMAIN_RULES: list[tuple[str, list[str]]] = [
    (
        "pt_rehab",
        [
            "physical therapy",
            "pt",
            "rehab",
            "rehabilitation",
            "acl",
            "knee",
            "quadriceps",
            "revision",
            "instability",
            "orthopedic",
            "post-op",
            "supervised_pt",
            "musculoskeletal",
            "neuromuscular",
        ],
    ),
    ("pharmacy", ["drug", "medication", "injectable", "pharmacy", "infusion", "formulary"]),
    ("mental_health", ["mental health", "psychiatric", "behavioral"]),
    ("radiology", ["radiology", "mri", "ct scan", "x-ray", "imaging"]),
    ("claims", ["appeal", "claim", "denial", "reconsideration"]),
]

_INTENT_RULES: list[tuple[str, list[str]]] = [
    (
        "medical_necessity",
        [
            "medically necessary",
            "medical necessity",
            "criteria",
            "continued therapy",
            "continuation",
            "objective progress",
            "measurable improvement",
        ],
    ),
    (
        "documentation",
        [
            "documentation",
            "document",
            "plan of care",
            "notes",
            "justification",
            "re-evaluation",
            "frequency",
            "duration",
            "records",
        ],
    ),
    (
        "authorization",
        [
            "approval",
            "authorize",
            "authorization",
            "prior auth",
            "preauth",
            "preauthorization",
            "coverage",
        ],
    ),
    ("appeal", ["appeal", "denial", "reconsideration", "retroactive"]),
]


def _classify_domain(text: str) -> str:
    lowered = text.lower()
    for domain, keywords in _DOMAIN_RULES:
        if any(keyword in lowered for keyword in keywords):
            return domain
    return "general"


def _classify_intents(text: str) -> list[str]:
    lowered = text.lower()
    intents = [
        intent
        for intent, keywords in _INTENT_RULES
        if any(keyword in lowered for keyword in keywords)
    ]
    return intents or ["general"]


class PolicyRouter:
    def __init__(self, policy_map: dict[str, Any]) -> None:
        self.policy_map = policy_map

    def route(self, payload: InsuranceAgentInput) -> RoutedPolicyPlan:
        parts = [
            payload.question,
            payload.clinical_decision.recommended_service,
            payload.clinical_decision.recommended_path.value,
            " ".join(payload.clinical_decision.recommendation_reason_codes),
            " ".join(item.code for item in payload.clinical_evidence),
            " ".join(item.statement for item in payload.clinical_evidence),
            " ".join(req.code for req in payload.clinical_requirements),
            " ".join(req.description for req in payload.clinical_requirements),
        ]
        text = " ".join(part for part in parts if part)

        domain = _classify_domain(text)
        intents = _classify_intents(text)
        candidate_urls = self._select_urls(domain=domain, intents=intents)

        return RoutedPolicyPlan(
            domain=domain,
            intents=intents,
            candidate_urls=candidate_urls,
            notes=[
                f"Domain: {domain}",
                f"Intents: {', '.join(intents)}",
                f"Candidate URLs: {len(candidate_urls)}",
            ],
        )

    def _select_urls(self, *, domain: str, intents: list[str]) -> list[str]:
        urls: list[str] = []

        block = self.policy_map.get("domains", {}).get(domain, {})
        urls.extend(block.get("core_urls", []))
        for intent in intents:
            urls.extend(block.get("intent_urls", {}).get(intent, []))

        if not urls:
            fallback = self.policy_map.get("domains", {}).get("general", {})
            urls.extend(fallback.get("core_urls", []))
            for intent in intents:
                urls.extend(fallback.get("intent_urls", {}).get(intent, []))

        deduped: list[str] = []
        seen: set[str] = set()
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            deduped.append(url)

        return deduped
