"""Pydantic output schemas for every boardroom task.

These guarantee structured memos and a machine-readable RESOLUTION.md."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Task outputs
# ---------------------------------------------------------------------------

class OpeningPitchOutput(BaseModel):
    headline: str = Field(..., description="One-sentence summary of the pitch")
    problem: str = Field(..., description="What pain-point is being solved")
    solution: str = Field(..., description="How the startup solves it")
    the_ask: str = Field(..., description="Funding amount requested and runway")
    confidence: int = Field(..., ge=1, le=5, description="CEO's own confidence level")


class TechnicalCrossExamOutput(BaseModel):
    buildability: Literal["EASY", "MODERATE", "HARD", "IMPOSSIBLE"] = Field(..., description="Feasibility assessment")
    scalability: Literal["LIMITED", "LINEAR", "SUPERLINEAR", "UNKNOWN"] = Field(..., description="Technical scalability")
    mvp_scope_weeks: int = Field(..., ge=1, le=52, description="Recommended MVP timeline in weeks")
    tech_stack_recommendation: str = Field(..., description="Recommended core technologies")
    red_flags: List[str] = Field(default_factory=list, description="Technical deal-killers")
    deal_killer: bool = Field(default=False, description="Does a technical red flag kill the deal")


class FinancialStressTestOutput(BaseModel):
    unit_economics_sound: bool = Field(..., description="Are LTV/CAC and payback period viable")
    tam_sam_som: Dict[str, str] = Field(..., description="Market size estimates")
    burn_rate_monthly: Optional[str] = Field(default=None, description="Estimated monthly burn")
    revenue_projections: Optional[str] = Field(default=None, description="3-year revenue outlook")
    deal_killer: bool = Field(default=False, description="Financial deal-killer present")
    red_flags: List[str] = Field(default_factory=list, description="Financial red flags")


class GTMAnalysisOutput(BaseModel):
    primary_channels: List[str] = Field(..., description="Top 3 acquisition channels")
    viral_coefficient_estimate: Optional[float] = Field(default=None, description="Estimated K-factor")
    payback_period_est: Optional[str] = Field(default=None, description="CAC payback period")
    conversion_funnel_notes: str = Field(default="", description="Conversion funnel observations")
    confidence: int = Field(..., ge=1, le=5, description="CRO's confidence in GTM")
    deal_killer: bool = Field(default=False, description="GTM deal-killer present")


class CustomerRealityCheckOutput(BaseModel):
    switching_costs: Literal["LOW", "MEDIUM", "HIGH"] = Field(..., description="Barrier to adoption")
    jobs_to_be_done: List[str] = Field(..., description="What jobs the customer hires this for")
    willingness_to_pay: Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"] = Field(..., description="Price sensitivity")
    objections: List[str] = Field(default_factory=list, description="Top buyer objections")
    deal_killer: bool = Field(default=False, description="Customer-side deal-killer")


class RiskAuditOutput(BaseModel):
    ip_status: Literal["CLEAR", "MURKY", "RISKY", "UNKNOWN"] = Field(..., description="IP and patent landscape")
    regulatory_matrix: List[str] = Field(default_factory=list, description="Applicable regulations")
    litigation_risk: Literal["LOW", "MEDIUM", "HIGH", "EXISTENTIAL"] = Field(..., description="Litigation risk")
    gdpr_compliance: bool = Field(default=True, description="GDPR/privacy compliance assumption")
    deal_killer: bool = Field(default=False, description="Regulatory deal-killer")
    non_negotiables: List[str] = Field(default_factory=list, description="Items that must be resolved pre-funding")


class ClosingRebuttalOutput(BaseModel):
    objections_addressed: List[str] = Field(..., description="Which objections from parallel tasks were rebutted")
    counter_arguments: str = Field(..., description="CEO's rebuttal narrative")
    confidence_delta: int = Field(default=0, ge=-3, le=3, description="Change in confidence from opening pitch")


class ResolutionOutput(BaseModel):
    resolution: Literal["APPROVED", "REJECTED", "CONDITIONAL"] = Field(..., description="Board decision")
    funding_recommendation: str = Field(..., description="Recommended funding amount")
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "EXISTENTIAL"] = Field(..., description="Overall risk")
    majority_opinion: str = Field(..., description="Concise majority rationale")
    dissenting_opinion: str = Field(default="", description="Concise dissent rationale")
    non_negotiables: List[str] = Field(default_factory=list, description="Pre-conditions for funding")
    vote_tally: Dict[str, int] = Field(default_factory=dict, description="VOTES: APPROVE/REJECT/CONDITIONAL counts")
