"""
policy_map.py — maps domain + intent → seed URLs for the PolicyRouter.

Principle: be specific. A narrow URL list means the fetcher visits fewer
pages, which means less noise, faster runs, and lower risk of pulling in
irrelevant specialties.

URL selection strategy per entry:
  core_urls   — always fetched for this domain regardless of intent
  intent_urls — fetched only when the router detects that intent

If you add a new insurance provider, add a new top-level domain key and
mirror the structure below.
"""

from __future__ import annotations

_KP_WA = "https://wa-provider.kaiserpermanente.org/provider-manual"

POLICY_MAP: dict = {
    "domains": {

        # ── Physical therapy / rehabilitation ──────────────────────────────
        "pt_rehab": {
            "core_urls": [
                # Prior authorization hub — covers most auth questions
                f"{_KP_WA}/clinical-review/priorauth",
                # Documentation standards — always relevant for PT
                f"{_KP_WA}/working-with-kp/records-standards",
            ],
            "intent_urls": {
                "medical_necessity": [
                    # Clinical review criteria is the primary source for
                    # "is this medically necessary?" determinations
                    f"{_KP_WA}/clinical-review/clinical-review-criteria",
                    # PT-specific guideline if available
                    f"{_KP_WA}/clinical-review/physical-therapy",
                ],
                "authorization": [
                    f"{_KP_WA}/clinical-review/priorauth",
                    # Outpatient rehab sub-page if it exists
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

        # ── Claims / billing ───────────────────────────────────────────────
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

        # ── Pharmacy ───────────────────────────────────────────────────────
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

        # ── Mental health ──────────────────────────────────────────────────
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

        # ── General fallback ───────────────────────────────────────────────
        # Used when domain classifier returns "general".
        # Kept deliberately narrow — a broad crawl of /provider-manual
        # pulls in too many unrelated specialties.
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