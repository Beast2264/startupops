"""Enumerations for StartupOps.

Boring, explicit string enums so they serialize cleanly to templates and,
later, to Firestore documents without any translation layer.
"""
from __future__ import annotations

from enum import Enum


class Status(str, Enum):
    """Lifecycle status of a startup-program application."""

    RESEARCHED = "RESEARCHED"
    READY_TO_APPLY = "READY_TO_APPLY"
    APPLICATION_STARTED = "APPLICATION_STARTED"
    WAITING_ON_DOCUMENT = "WAITING_ON_DOCUMENT"
    SUBMITTED = "SUBMITTED"
    CONFIRMATION_RECEIVED = "CONFIRMATION_RECEIVED"
    UNDER_REVIEW = "UNDER_REVIEW"
    MORE_INFO_REQUESTED = "MORE_INFO_REQUESTED"
    APPROVED = "APPROVED"
    PARTIALLY_APPROVED = "PARTIALLY_APPROVED"
    WAITLISTED = "WAITLISTED"
    REJECTED = "REJECTED"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    SKIPPED = "SKIPPED"
    EXPIRED = "EXPIRED"
    CLOSED = "CLOSED"


# Statuses that represent an actual award decision. An actual_award amount may
# ONLY be recorded when the application has reached one of these.
APPROVAL_STATUSES: frozenset[Status] = frozenset(
    {Status.APPROVED, Status.PARTIALLY_APPROVED}
)

# Terminal statuses — no further forward transition expected.
TERMINAL_STATUSES: frozenset[Status] = frozenset(
    {
        Status.REJECTED,
        Status.NOT_ELIGIBLE,
        Status.SKIPPED,
        Status.EXPIRED,
        Status.CLOSED,
    }
)


class Tier(str, Enum):
    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"
    TIER_3_WATCH = "TIER_3_WATCH"


class Priority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class BenefitType(str, Enum):
    CLOUD_CREDITS = "CLOUD_CREDITS"
    AI_GPU = "AI_GPU"
    DEV_TOOLS = "DEV_TOOLS"
    OBSERVABILITY = "OBSERVABILITY"
    DATABASE = "DATABASE"
    SECURITY_IDENTITY = "SECURITY_IDENTITY"
    DATA_STREAMING = "DATA_STREAMING"
    OTHER = "OTHER"


class ValueDisclosure(str, Enum):
    """How the advertised maximum is classified by the research source.

    A numeric ``advertised_maximum`` may ONLY be stored when this is VERIFIED.
    All other classes preserve the reason no verified number is recorded.
    """

    VERIFIED = "VERIFIED"                          # official current source confirms a figure
    NOT_PUBLICLY_DISCLOSED = "NOT_PUBLICLY_DISCLOSED"
    VARIABLE = "VARIABLE"                          # amount varies / tiered / case-by-case
    HISTORICAL = "HISTORICAL"                      # a past figure, not current
    CONDITIONAL = "CONDITIONAL"                    # depends on stage/spend/negotiation
    NOT_CURRENTLY_VERIFIED = "NOT_CURRENTLY_VERIFIED"


# Classifications for which a numeric advertised_maximum MAY be stored. VERIFIED
# = a firm verified figure; CONDITIONAL = a verified advertised *ceiling* that is
# not guaranteed. All other classes must keep advertised_maximum None. A number
# is never REQUIRED (e.g. a VERIFIED non-cash benefit has no dollar figure).
NUMERIC_VALUE_DISCLOSURES: frozenset["ValueDisclosure"] = frozenset(
    {ValueDisclosure.VERIFIED, ValueDisclosure.CONDITIONAL}
)

# Sentinel preserved verbatim from research when a figure is not public.
UNVERIFIED = "UNVERIFIED / NOT PUBLICLY DISCLOSED"
