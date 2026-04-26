"""Smart mock content generator for Boardroom War Game.

Replaces empty mock placeholders with realistic fake agent content
based on templates, so the dashboard shows actual speeches.
"""
from __future__ import annotations

import random
from datetime import datetime
from typing import Dict


class MockLibrary:
    """Content library for mock mode."""

    def __init__(self):
        random.seed(datetime.now().timestamp())

    # ------------------------------------------------------------------
    # CEO — Opening Pitch
    # ------------------------------------------------------------------
    @staticmethod
    def ceo_opening_pitch(idea: str) -> str:
        return (
            f"Our board members know the pain of {idea.lower().replace('ai-powered ', '')} — "
            f"it's inconsistent, expensive, and deeply frustrating.\n\n"
            f"We're building **{idea}** to solve this at scale.\n"
            f"Our approach? A 3-pronged AI layer that learns user behaviour, automates the boring parts, "
            f"and delivers results without human intervention.\n\n"
            f"The ask: a **$4M seed round** for 18 months' runway. "
            f"Confidence: 4 out of 5 — we have the team, the market is real, and the tech is proven in beta."
        )

    # ------------------------------------------------------------------
    # CTO — Technical Cross-Exam
    # ------------------------------------------------------------------
    @staticmethod
    def cto_rebuttal(idea: str) -> str:
        responses = [
            f"Technically, the claim that building {idea} is trivial is incorrect. "
            f"We need real-time inference on-device, which demands a custom ONNX runtime. "
            f"The MVP is 8–10 weeks, not 6. Core risk: latency budget for edge deployment is unrealistic.",
            f"I reviewed the architecture. The data-pipeline risk is larger than the model risk. "
            f"We need 6 months of production telemetry before trusting the inference pipeline in production.",
            f"The tech stack is solid — transformer-based models on cloud GPU — but edge inference is unproven. "
            f"Recommended MVP scope: 10 weeks, focusing on API-first delivery before any on-device work.",
        ]
        return random.choice(responses)

    # ------------------------------------------------------------------
    # CFO — Financial Stress-Test
    # ------------------------------------------------------------------
    @staticmethod
    def cfo_rebuttal(idea: str) -> str:
        responses = [
            f"The unit economics here are questionable. Our model suggests a burn rate of $280K/month with only 14 months of runway.",
            f"We ran the numbers. At a $45 CAC and $12 monthly price point, payback is 47 months. "
            f"This is a Series-A pitch asking for Seed money.",
            f"TAM looks large on paper, but SOM is under-validated. "
            f"Conservative 3-year revenue projection: $2.1M ARR — below the threshold most Series-A investors want.",
        ]
        return random.choice(responses)

    # ------------------------------------------------------------------
    # CRO — GTM Analysis
    # ------------------------------------------------------------------
    @staticmethod
    def cro_rebuttal(idea: str) -> str:
        responses = [
            f"The GTM plan is heavy on content marketing but light on distribution partnerships. "
            f"Top acquisition channel should be outbound sales, not TikTok ads.",
            f"Viral coefficient estimate of 1.4 is optimistic. In B2B SaaS, 1.1 is the realistic ceiling.",
            f"I like the PLG angle, but the onboarding friction is too high for self-serve. "
            f"We need a concierge onboarding motion to get the first 100 paying customers.",
        ]
        return random.choice(responses)

    # ------------------------------------------------------------------
    # Customer — Customer Reality Check
    # ------------------------------------------------------------------
    @staticmethod
    def customer_rebuttal(idea: str) -> str:
        responses = [
            f"As a buyer, I don't care about the AI — I care about ROI. Show me a case study, not a pitch.",
            f"Switching cost is too high. We'd need 18 months to integrate this, and our current vendor is fine.",
            f"I'd need to see SOC2 Type II and ISO 27001 before procurement even looks at this. "
            f"Willingness to pay: MEDIUM, but only after a pilot.",
        ]
        return random.choice(responses)

    # ------------------------------------------------------------------
    # Counsel — Risk Audit
    # ------------------------------------------------------------------
    @staticmethod
    def counsel_rebuttal(idea: str) -> str:
        responses = [
            f"Patent landscape is littered with prior art in {idea.lower()}. One search found 14 overlapping claims.",
            f"GDPR Article 22 implications are real here — automated decision-making without human review is a liability.",
            f"The open-source compliance claim is unverified. We need a full SBOM before any wire transfer. "
            f"Litigation risk: MODERATE. IP risk: HIGH.",
        ]
        return random.choice(responses)

    # ------------------------------------------------------------------
    # CEO — Closing Rebuttal
    # ------------------------------------------------------------------
    @staticmethod
    def ceo_closing_rebuttal(idea: str) -> str:
        return (
            f"Let me address the top 3 objections directly.\n\n"
            f"**Technical**: Yes, edge inference is hard — but our beta already runs on-device with 89% accuracy. "
            f"We're NOT proposing unproven science.\n\n"
            f"**Financial**: The $45 CAC assumes zero virality. Our referral loop has already reduced blended CAC to $28 in beta.\n\n"
            f"**Compliance**: We're engaging Fenwick & West for IP review and have a SOC2 roadmap in place. "
            f"90 days to Type I audit.\n\n"
            f"Confidence delta: +1. I'm more bullish now than in the opening pitch."
        )

    # ------------------------------------------------------------------
    # Board Chair — Final Resolution
    # ------------------------------------------------------------------
    @staticmethod
    def board_resolution(idea: str) -> str:
        return (
            f"After careful deliberation, the board has reached a decision on **{idea}**.\n\n"
            f"**Resolution: CONDITIONAL APPROVAL**\n\n"
            f"**Funding recommendation**: $4M seed, with tranched release tied to milestones.\n"
            f"**Risk level**: MEDIUM — technical and GTM risks are real but manageable.\n\n"
            f"**Majority opinion**: The idea has legs. Team is strong, market is non-zero, and the beta shows promise. "
            f"However, we need validated unit economics before full release.\n\n"
            f"**Dissenting opinion**: CTO and Counsel abstain. CTO wants edge-inference validation. Counsel wants IP clearance.\n\n"
            f"**Non-negotiables**:\n"
            f"1. Complete IP landscape review within 60 days.\n"
            f"2. Demonstrate on-device latency under 200ms for 95th percentile.\n"
            f"3. Close 3 beta customers with signed LOIs.\n\n"
            f"**Vote tally**: APPROVE 4 | REJECT 0 | CONDITIONAL 3\n\n"
            f"We reconvene in 90 days."
        )


def generate_smart_responses(idea: str, tasks: list) -> Dict:
    """Generate realistic mock agent speeches for the given idea.

    Maps each task in *tasks* to a string of fake content.
    """
    lib = MockLibrary()
    out: Dict = {}

    # Identity map by expected_output (stable fingerprint)
    for t in tasks:
        slug = t.expected_output.lower()
        agent = t.agent.role.lower() if hasattr(t.agent, 'role') else ''

        if 'resolution' in slug:
            out[t] = lib.board_resolution(idea)
        elif 'opening pitch' in slug:
            out[t] = lib.ceo_opening_pitch(idea)
        elif 'technical' in slug:
            out[t] = lib.cto_rebuttal(idea)
        elif 'financial' in slug:
            out[t] = lib.cfo_rebuttal(idea)
        elif 'gtm' in slug or 'go-to-market' in slug:
            out[t] = lib.cro_rebuttal(idea)
        elif 'customer' in slug:
            out[t] = lib.customer_rebuttal(idea)
        elif 'risk' in slug:
            out[t] = lib.counsel_rebuttal(idea)
        elif 'closing' in slug:
            out[t] = lib.ceo_closing_rebuttal(idea)
        else:
            out[t] = f"[{agent}] delivered their analysis on '{t.description.split(chr(10))[0]}'."

    return out
