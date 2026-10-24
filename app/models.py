"""Domain models for StartupOps.

Pydantic models give us free validation and clean serialization. They are
storage-agnostic: the in-memory repository stores them today; the Firestore
repository stores the same ``model_dump(mode="json")`` dicts.

Catalog vs. submission — the core distinction:

  * ``Program``     — a startup/cloud/vendor program you have *identified*
                      and may apply to. A program may exist with no application.
  * ``Application`` — an *actual submission* you have made to a program.
                      It references its program via ``program_id``.

Security rule: these models never carry passwords, API keys, cloud
credentials, tokens, or card data. Only links to supporting documents.

Money rule: an advertised maximum lives on the ``Program`` (marketing); an
``actual_award`` lives on the ``Application`` and may only be set once the
submission reaches an approval status. Advertised maximum != actual award.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator

from .enums import (
    APPROVAL_STATUSES,
    NUMERIC_VALUE_DISCLOSURES,
    BenefitType,
    Priority,
    Status,
    Tier,
    ValueDisclosure,
)

# Field names that must never appear in free-text/notes payloads. Cheap guard
# against someone pasting a secret into a notes box.
_FORBIDDEN_SECRET_HINTS = (
    "password",
    "api_key",
    "apikey",
    "secret_key",
    "access_token",
    "private_key",
    "card number",
)


def _looks_like_secret(value: Optional[str]) -> bool:
    if not value:
        return False
    low = value.lower()
    return any(hint in low for hint in _FORBIDDEN_SECRET_HINTS)


class Program(BaseModel):
    """CATALOG entry: a program we have identified. Not a submission."""

    id: Optional[str] = None
    provider: str
    name: str  # program name, e.g. "Auth0 for Startups"
    tier: Tier = Tier.TIER_3_WATCH
    priority: Priority = Priority.MEDIUM
    benefit_type: BenefitType = BenefitType.CLOUD_CREDITS

    # Catalog pipeline status (pre-submission): RESEARCHED, READY_TO_APPLY,
    # SKIPPED, NOT_ELIGIBLE, etc. Once we submit, the Application carries the
    # submission status.
    status: Status = Status.RESEARCHED

    official_url: Optional[str] = None
    application_url: Optional[str] = None

    # Advertised (marketing) maximum, per the research classification.
    #  * value_disclosure == VERIFIED  -> advertised_maximum holds the number.
    #  * anything else                 -> advertised_maximum is None and the
    #                                     text preserves why (undisclosed /
    #                                     variable / historical / conditional).
    value_disclosure: ValueDisclosure = ValueDisclosure.NOT_CURRENTLY_VERIFIED
    advertised_maximum: Optional[float] = None
    advertised_maximum_text: Optional[str] = None
    currency: Optional[str] = "USD"

    eligibility_summary: Optional[str] = None
    referral_requirement: bool = False
    funding_requirement: bool = False
    bootstrapped_eligibility: bool = True
    existing_customer_eligibility: bool = True

    primary_intended_use: Optional[str] = None
    architecture_impact: Optional[str] = None

    application_deadline: Optional[date] = None
    date_identified: Optional[date] = None
    contact: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("provider", "name")
    @classmethod
    def _required_nonblank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be blank")
        return v.strip()

    @field_validator("advertised_maximum")
    @classmethod
    def _non_negative(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("amount must not be negative")
        return v

    @field_validator("notes", "eligibility_summary", "primary_intended_use")
    @classmethod
    def _no_secrets(cls, v: Optional[str]) -> Optional[str]:
        if _looks_like_secret(v):
            raise ValueError(
                "value looks like a credential/secret; this app must not store secrets"
            )
        return v

    @model_validator(mode="after")
    def _number_only_when_verified_or_conditional(self) -> "Program":
        # A numeric advertised maximum may only exist when the research
        # classifies the value as VERIFIED (a firm figure) or CONDITIONAL (a
        # verified advertised ceiling). Undisclosed/variable/historical/
        # not-verified classes must keep the number None — this structurally
        # prevents an invented figure. A number is never required (a VERIFIED
        # non-cash benefit legitimately has no dollar figure).
        if (
            self.advertised_maximum is not None
            and self.value_disclosure not in NUMERIC_VALUE_DISCLOSURES
        ):
            raise ValueError(
                "advertised_maximum may only be set when value_disclosure is "
                "VERIFIED or CONDITIONAL (do not store an unverified figure)"
            )
        return self


class Application(BaseModel):
    """A concrete SUBMISSION to a program. References its program."""

    id: Optional[str] = None
    program_id: str  # reference to the Program catalog entry
    # Denormalized for display so lists/detail don't need a program lookup.
    provider: str
    program: str

    status: Status = Status.SUBMITTED

    reference: Optional[str] = None       # provider's application reference no.
    confirmation: Optional[str] = None    # e.g. "application received"

    date_started: Optional[date] = None
    date_submitted: Optional[date] = None
    decision_date: Optional[date] = None

    # Actual award — populated ONLY once the submission is approved.
    actual_award: Optional[float] = None
    currency: str = "USD"

    next_action: Optional[str] = None
    next_action_date: Optional[date] = None
    contact: Optional[str] = None
    notes: Optional[str] = None
    confirmation_link: Optional[str] = None

    @field_validator("program_id", "provider", "program")
    @classmethod
    def _required_nonblank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be blank")
        return v.strip()

    @field_validator("actual_award")
    @classmethod
    def _non_negative(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("amount must not be negative")
        return v

    @field_validator("notes")
    @classmethod
    def _no_secrets(cls, v: Optional[str]) -> Optional[str]:
        if _looks_like_secret(v):
            raise ValueError(
                "value looks like a credential/secret; this app must not store secrets"
            )
        return v

    @model_validator(mode="after")
    def _award_requires_approval(self) -> "Application":
        # An advertised maximum is NOT an actual award. An actual award may
        # only be recorded once the submission has reached an approval status.
        if self.actual_award is not None and self.status not in APPROVAL_STATUSES:
            raise ValueError(
                "actual_award may only be set when status is APPROVED or "
                "PARTIALLY_APPROVED (advertised maximum is not an award)"
            )
        return self


class CreditAward(BaseModel):
    """A concrete credit/benefit tied to an approved application."""

    id: Optional[str] = None
    application_id: Optional[str] = None
    program_id: Optional[str] = None
    provider_program: str
    benefit_type: BenefitType = BenefitType.CLOUD_CREDITS

    advertised_maximum: Optional[float] = None
    advertised_maximum_text: Optional[str] = None
    actual_award: Optional[float] = None
    currency: str = "USD"

    activation_date: Optional[date] = None
    expiration_date: Optional[date] = None
    amount_used: float = 0.0

    workload_assignment: Optional[str] = None
    restrictions: Optional[str] = None
    notes: Optional[str] = None
    evidence_link: Optional[str] = None

    @field_validator("provider_program")
    @classmethod
    def _required_nonblank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be blank")
        return v.strip()

    @field_validator("advertised_maximum", "actual_award", "amount_used")
    @classmethod
    def _non_negative(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("amount must not be negative")
        return v

    @model_validator(mode="after")
    def _used_not_exceed_award(self) -> "CreditAward":
        if self.actual_award is not None and self.amount_used > self.actual_award:
            raise ValueError("amount_used cannot exceed actual_award")
        return self


class Followup(BaseModel):
    """A scheduled follow-up / next-contact for a program or application."""

    id: Optional[str] = None
    application_id: Optional[str] = None
    program_id: Optional[str] = None
    provider_program: str
    status: Status = Status.RESEARCHED
    last_contact: Optional[date] = None
    next_followup: Optional[date] = None
    action: Optional[str] = None
    priority: Priority = Priority.MEDIUM
    completed: bool = False
    notes: Optional[str] = None

    @field_validator("provider_program")
    @classmethod
    def _required_nonblank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be blank")
        return v.strip()
