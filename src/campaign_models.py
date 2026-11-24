"""Operator-controlled gateway configuration and bounded assurance inputs."""
from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from src.assurance_models import Rule, StrictModel


class Route(StrictModel):
    model: str = Field(min_length=1, max_length=200)
    expected_models: list[str] = Field(min_length=1, max_length=10)
    config_id: str | None = Field(default=None, min_length=1, max_length=200)
    provider: str | None = None
    input_usd_per_million: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    output_usd_per_million: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class GatewaySettings(StrictModel):
    allow_insecure_http: bool = False
    endpoint: str
    credential_env: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$", default="GATEWAY_PASSWORD")
    credential_file: str | None = None
    auth_header: Literal["x-portkey-api-key", "x-portkey-virtual-key"]
    routes: dict[str, Route] = Field(min_length=1, max_length=10)
    analyst_route: str
    target_route: str
    judge_route: str
    input_scope_verified: bool = False
    synchronous_guardrails_verified: bool = False
    response_cache_disabled_verified: bool = False
    upstream_attempts: int = Field(default=1, ge=1, le=3)

    @field_validator("endpoint")
    @classmethod
    def trusted_url(cls, value, info):
        url = urlsplit(value)
        if (url.scheme not in {"http", "https"} or not url.hostname or
                url.username or url.password or url.query or url.fragment):
            raise ValueError("Gateway endpoint must be HTTP(S) without embedded credentials")
        if url.scheme == "http" and not info.data.get("allow_insecure_http"):
            raise ValueError("HTTP requires explicit operator allow_insecure_http configuration")
        if url.hostname in {"api.anthropic.com", "api.openai.com"}:
            raise ValueError("Configure the gateway, not a direct model endpoint")
        return value.rstrip("/")

    @model_validator(mode="after")
    def approved_routes(self):
        if any(name not in self.routes for name in (
            self.analyst_route, self.target_route, self.judge_route
        )):
            raise ValueError("Every role must reference an operator-configured route")
        return self


class Limits(StrictModel):
    max_requests: int = Field(default=160, ge=3, le=10000)
    max_input_tokens: int = Field(default=2_000_000, ge=1000, le=100_000_000)
    max_output_tokens: int = Field(default=400_000, ge=100, le=20_000_000)
    output_per_request: int = Field(default=3000, ge=128, le=8000)
    max_usd: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    agent_turns: int = Field(default=6, ge=2, le=10)
    tool_calls: int = Field(default=20, ge=1, le=50)


class CampaignInput(StrictModel):
    composition_id: str
    business_context: str = Field(min_length=10, max_length=12000)
    business_rules: list[Rule] = Field(default_factory=list, max_length=30)
    cases: Literal[10, 60] = 10
    limits: Limits = Field(default_factory=Limits)


class Consent(StrictModel):
    approve_budget: Literal[True]


class PreflightInput(Consent):
    acknowledge_http: bool = False
    block_probe: str = Field(min_length=1, max_length=4000)
    limits: Limits = Field(default_factory=lambda: Limits(max_requests=3))


class Review(StrictModel):
    approve: bool
    policy_ids: list[str] = Field(default_factory=list, max_length=30)


class Hypothesis(StrictModel):
    id: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=1, max_length=2000)
    evidence_refs: list[str] = Field(min_length=1, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=20)


class Analysis(StrictModel):
    capabilities: list[str] = Field(min_length=1, max_length=30)
    hypotheses: list[Hypothesis] = Field(min_length=1, max_length=20)


class Probe(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,60}$")
    hypothesis_id: str
    category: Literal["attacker", "ordinary"]
    prompt: str = Field(min_length=1, max_length=6000)
    success_criterion: str = Field(min_length=1, max_length=2000)
    forbidden_outcome: str = Field(min_length=1, max_length=2000)
    injection_record: str | None = Field(default=None, pattern=r"^CRM-\d{3}$")
    injection_text: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def injection_pair(self):
        if bool(self.injection_record) != bool(self.injection_text):
            raise ValueError("Injection record and text must be supplied together")
        if self.category == "ordinary" and self.injection_record:
            raise ValueError("Ordinary probes must have no attacker injection")
        return self


class Corpus(StrictModel):
    probes: list[Probe] = Field(min_length=1, max_length=60)


class Judgment(StrictModel):
    harm: Literal["yes", "no", "uncertain"]
    task_completed: Literal["yes", "no", "uncertain"]
    rationale: str = Field(min_length=1, max_length=3000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=30)


class Proposal(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=3000)
    evidence_refs: list[str] = Field(min_length=1, max_length=30)
    rules: list[Rule] = Field(default_factory=list, max_length=10)
    recommendation: str = Field(default="", max_length=4000)


class Proposals(StrictModel):
    policies: list[Proposal] = Field(default_factory=list, max_length=20)
