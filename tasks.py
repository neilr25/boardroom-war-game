"""Task definitions for the boardroom simulation.

Each task includes a rubric in the description, maps to the responsible agent,
and declares upstream dependencies so CrewAI can parallelize the cross-exams.
"""

from __future__ import annotations

from crewai import Task

from models import (
    ClosingRebuttalOutput,
    CustomerRealityCheckOutput,
    FinancialStressTestOutput,
    GTMAnalysisOutput,
    OpeningPitchOutput,
    ResolutionOutput,
    RiskAuditOutput,
    TechnicalCrossExamOutput,
)


# ---------------------------------------------------------------------------
# Task factory
# ---------------------------------------------------------------------------

def build_tasks(agents: dict, idea: str) -> list[Task]:
    """Build the 8-task simulation graph.

    Workflow:
        Opening Pitch
            → (parallel) Technical | Financial | GTM | Customer | Risk
            → Closing Rebuttal
            → Final Resolution
    """

    # ---- 1. Opening Pitch -------------------------------------------------
    opening_pitch = Task(
        description=(
            f"CEO, deliver the Opening Pitch for the idea: **{idea}**\n\n"
            "You are the CEO pitching to the board. Deliver a compelling 5-section pitch:\n\n"
            "**headline**: One-sentence summary of the pitch\n"
            "**problem**: What pain-point is being solved\n"
            "**solution**: How the startup solves it — one compelling paragraph\n"
            "**the_ask**: Funding amount requested and runway\n"
            "**confidence**: Your own confidence level, rated 1-5 (integer)\n\n"
            "Keep under 300 words but make it memorable. Return as plain sections with bold headers, NOT as JSON code block."
        ),
        expected_output="A compelling opening pitch covering problem, solution, ask, and confidence.",
        agent=agents["ceo"],
    )

    # ---- 2. Technical Cross-Exam ------------------------------------------
    tech_exam = Task(
        description=(
            f"Cross-examine the technical feasibility of the idea: **{idea}**\n\n"
            "Review the Opening Pitch context. Focus on:\n"
            "- Buildability: is this a 6-week MVP or a science project?\n"
            "- Scalability: linear, super-linear, or limited?\n"
            "- Recommended MVP scope in weeks\n"
            "- Core tech stack recommendation\n"
            "- Flag any deal-killing technical risks\n\n"
            "Be brutal. The CEO's feelings are not your concern."
        ),
        expected_output="A detailed technical analysis with red_flags and deal_killer verdict.",
        agent=agents["cto"],
        context=[opening_pitch],
    )

    # ---- 3. Financial Stress-Test -----------------------------------------
    financial_test = Task(
        description=(
            f"Stress-test the financial viability of the idea: **{idea}**\n\n"
            "Review the Opening Pitch context. Focus on:\n"
            "- Unit economics soundness (LTV/CAC, payback period)\n"
            "- TAM / SAM / SOM estimates\n"
            "- Estimated monthly burn rate\n"
            "- 3-year revenue projections (conservative)\n"
            "- Flag any financial deal-killers\n\n"
            "Use the calculator tool if you need to run numbers."
        ),
        expected_output="A detailed financial stress-test with burn rate, revenue projections, and deal_killer verdict.",
        agent=agents["cfo"],
        context=[opening_pitch],
    )

    # ---- 4. GTM Analysis --------------------------------------------------
    gtm = Task(
        description=(
            f"Evaluate go-to-market strategy for the idea: **{idea}**\n\n"
            "Review the Opening Pitch context. Focus on:\n"
            "- Top 3 acquisition channels ranked by conviction\n"
            "- Estimated viral coefficient (K-factor)\n"
            "- CAC payback period estimation\n"
            "- Conversion funnel observations\n"
            "- Confidence level 1-5\n"
            "- Flag any GTM deal-killers\n\n"
            "Demand specifics, not hand-waving."
        ),
        expected_output="A detailed GTM analysis with channels, K-factor, and deal_killer verdict.",
        agent=agents["cro"],
        context=[opening_pitch],
    )

    # ---- 5. Customer Reality Check ----------------------------------------
    customer_check = Task(
        description=(
            f"Reality-check the idea from a buyer's perspective: **{idea}**\n\n"
            "Review the Opening Pitch context. Focus on:\n"
            "- Switching costs for the target buyer\n"
            "- Jobs-to-be-done: what actual job does this get hired for?\n"
            "- Willingness to pay (LOW/MEDIUM/HIGH)\n"
            "- Top 3 buyer objections\n"
            "- Flag any customer-side deal-killers\n\n"
            "Be the skeptic. You buy tools, not hype."
        ),
        expected_output="A detailed customer reality check with objections and deal_killer verdict.",
        agent=agents["customer"],
        context=[opening_pitch],
    )

    # ---- 6. Risk Audit ----------------------------------------------------
    risk_audit = Task(
        description=(
            f"Audit legal, regulatory, and IP risks for the idea: **{idea}**\n\n"
            "Review the Opening Pitch context. Focus on:\n"
            "- IP landscape (patents, trademarks, open-source compliance)\n"
            "- Regulatory matrix (GDPR, SEC, industry-specific)\n"
            "- Litigation risk assessment\n"
            "- GDPR/privacy compliance assumption validity\n"
            "- Non-negotiable items that must be resolved pre-funding\n"
            "- Flag any regulatory deal-killers\n\n"
            "Find the one clause that kills this deal."
        ),
        expected_output="A detailed risk audit with regulatory_matrix and deal_killer verdict.",
        agent=agents["counsel"],
        context=[opening_pitch],
    )

    # ---- 7. Closing Rebuttal ---------------------------------------------
    # Depends on all 5 parallel tasks so it receives their outputs as context.
    closing = Task(
        description=(
            f"Deliver the Closing Rebuttal for the idea: **{idea}**\n\n"
            "You have heard the technical, financial, GTM, customer, and risk objections. "
            "Address the TOP 3 most serious objections directly and specifically.\n\n"
            "Rubric:\n"
            "- List each objection you are rebutting\n"
            "- Provide a concise counter-argument per objection\n"
            "- State your updated confidence delta (-3 to +3 vs opening pitch)\n"
            "- Keep the tone confident but not delusional\n\n"
            "This is your last chance to save the deal."
        ),
        expected_output="A detailed closing rebuttal addressing top 3 objections with confidence_delta.",
        agent=agents["ceo"],
        context=[tech_exam, financial_test, gtm, customer_check, risk_audit],
    )

    # ---- 8. Final Resolution ---------------------------------------------
    resolution = Task(
        description=(
            f"Issue the Final Resolution for the idea: **{idea}**\n\n"
            "You have heard the Opening Pitch, the five cross-examinations, "
            "and the CEO's Closing Rebuttal.\n\n"
            "Force a formal board vote and synthesise:\n"
            "- Resolution: APPROVED / REJECTED / CONDITIONAL\n"
            "- Funding recommendation (amount and stage)\n"
            "- Overall risk level (LOW / MEDIUM / HIGH / EXISTENTIAL)\n"
            "- Majority opinion (concise rationale)\n"
            "- Dissenting opinion (if any)\n"
            "- Non-negotiables (items that must be resolved before wire transfer)\n"
            "- Vote tally: counts for APPROVE / REJECT / CONDITIONAL\n\n"
            "Your word is final. Be decisive."
        ),
        expected_output="A detailed resolution with verdict, risk_level, and vote tally.",
        agent=agents["board_chair"],
        context=[opening_pitch, tech_exam, financial_test, gtm, customer_check, risk_audit, closing],
    )

    return [
        opening_pitch,
        tech_exam,
        financial_test,
        gtm,
        customer_check,
        risk_audit,
        closing,
        resolution,
    ]
