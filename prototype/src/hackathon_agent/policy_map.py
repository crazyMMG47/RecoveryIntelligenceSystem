from __future__ import annotations

_KP_WA = "https://wa-provider.kaiserpermanente.org/provider-manual"

POLICY_MAP: dict = {
    "domains": {
        "pt_rehab": {
            "core_urls": [
                f"{_KP_WA}/clinical-review/priorauth",
                f"{_KP_WA}/working-with-kp/records-standards",
            ],
            "intent_urls": {
                "medical_necessity": [
                    f"{_KP_WA}/clinical-review/clinical-review-criteria",
                    f"{_KP_WA}/clinical-review/physical-therapy",
                ],
                "authorization": [
                    f"{_KP_WA}/clinical-review/priorauth",
                    f"{_KP_WA}/clinical-review/outpatient-rehab",
                ],
                "documentation": [
                    f"{_KP_WA}/working-with-kp/records-standards",
                    f"{_KP_WA}/working-with-kp/documentation-guidelines",
                ],
                "appeal": [
                    f"{_KP_WA}/clinical-review/provider-reconsideration-process",
                    f"{_KP_WA}/billing-claims/claims/processing-claims",
                ],
            },
        },
        "claims": {
            "core_urls": [
                f"{_KP_WA}/billing-claims/claims/processing-claims",
                f"{_KP_WA}/clinical-review/provider-reconsideration-process",
            ],
            "intent_urls": {
                "appeal": [
                    f"{_KP_WA}/clinical-review/provider-reconsideration-process",
                    f"{_KP_WA}/billing-claims/claims/processing-claims",
                ],
                "documentation": [
                    f"{_KP_WA}/billing-claims/claims/claim-submission",
                ],
            },
        },
        "pharmacy": {
            "core_urls": [
                f"{_KP_WA}/clinical-review/drug-criteria",
            ],
            "intent_urls": {
                "authorization": [
                    f"{_KP_WA}/clinical-review/priorauth",
                ],
            },
        },
        "mental_health": {
            "core_urls": [
                f"{_KP_WA}/clinical-review/behavioral-health",
            ],
            "intent_urls": {
                "authorization": [
                    f"{_KP_WA}/clinical-review/priorauth",
                ],
            },
        },
        "general": {
            "core_urls": [
                f"{_KP_WA}/working-with-kp/records-standards",
            ],
            "intent_urls": {
                "authorization": [
                    f"{_KP_WA}/clinical-review/priorauth",
                ],
                "documentation": [
                    f"{_KP_WA}/working-with-kp/records-standards",
                ],
                "appeal": [
                    f"{_KP_WA}/clinical-review/provider-reconsideration-process",
                ],
            },
        },
    }
}
