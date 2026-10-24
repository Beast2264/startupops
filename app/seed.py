"""Sample/demo data — FICTIONAL, for local development only.

Every provider name, program, reference number, confirmation string, and
dollar figure below is made up for demonstration purposes. None of it reflects
any real program, any real submission, or any real award. It exists only to
show each screen (Dashboard / Programs / Applications / Credits / Follow-ups)
populated with plausible-looking data so you can see the app working before
you start entering your own records.

Dates are computed relative to ``date.today()`` (not hard-coded) so the
upcoming-deadline, credit-expiration, and follow-up-overdue views always have
something relevant to show, no matter when you run this.

Catalog vs. submissions (see app/models.py for the full rule):
  * ``Program``     — a benefit/credit program you have identified. May exist
                      with no application yet.
  * ``Application`` — an actual submission you made, referencing a program.

If you adapt this file with real program research, keep the
``value_disclosure`` discipline: a numeric ``advertised_maximum`` may only be
set when the classification is VERIFIED or CONDITIONAL (enforced by the
Program model), and treat any public program figures as unverified until you
confirm them yourself on the provider's current site — program terms change
often and this file (or copies of it) can go stale.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from .enums import BenefitType, Priority, Status, Tier, ValueDisclosure
from .models import Application, CreditAward, Followup, Program
from .repository import Repository

VD = ValueDisclosure
BT = BenefitType


def _today() -> date:
    return date.today()


def _programs() -> list[dict]:
    today = _today()
    return [
        dict(provider="Nimbus Cloud", name="Nimbus Cloud Startup Credits",
             tier=Tier.TIER_1, benefit=BT.CLOUD_CREDITS, disclosure=VD.VERIFIED,
             amount=5000.0, currency="USD",
             text="$5,000 in credits for 12 months (FICTIONAL sample program)",
             url="https://example.com/nimbus-cloud-startups",
             notes="Sample data — not a real provider or offer."),
        dict(provider="Vectra Analytics", name="Vectra for Builders",
             tier=Tier.TIER_1, benefit=BT.OBSERVABILITY, disclosure=VD.VERIFIED,
             amount=20000.0, currency="USD",
             text="$20,000 in observability credits for 12 months (FICTIONAL sample program)",
             url="https://example.com/vectra-for-builders",
             notes="Sample data — not a real provider or offer."),
        dict(provider="Forgeline AI", name="Forgeline AI Compute Grant",
             tier=Tier.TIER_1, benefit=BT.AI_GPU, disclosure=VD.CONDITIONAL,
             amount=50000.0, currency="USD",
             text="Up to $50,000 of GPU compute, subject to qualification (FICTIONAL sample program)",
             url="https://example.com/forgeline-ai-grant",
             notes="Sample data — ceiling only, not a guaranteed award.",
             application_deadline=today + timedelta(days=18)),
        dict(provider="Ashgrove Security", name="Ashgrove ID for Startups",
             tier=Tier.TIER_2, benefit=BT.SECURITY_IDENTITY, disclosure=VD.VERIFIED,
             amount=None, currency=None,
             text="One year free for up to 25 users (FICTIONAL sample program, non-cash benefit)",
             url="https://example.com/ashgrove-id-for-startups",
             notes="Sample data — non-cash benefit, no dollar figure invented."),
        dict(provider="Driftwood Data", name="Driftwood Data Startup Program",
             tier=Tier.TIER_2, benefit=BT.DATABASE, disclosure=VD.NOT_PUBLICLY_DISCLOSED,
             amount=None, currency=None,
             text="Program exists; current public credit amount not disclosed (FICTIONAL sample program)",
             url="https://example.com/driftwood-data-startups",
             notes="Sample data — illustrates an undisclosed-value program."),
        dict(provider="Palisade DevTools", name="Palisade Pro for Startups",
             tier=Tier.TIER_2, benefit=BT.DEV_TOOLS, disclosure=VD.VARIABLE,
             amount=None, currency=None,
             text="Credit amount varies by plan/stage (FICTIONAL sample program)",
             url="https://example.com/palisade-pro-for-startups",
             notes="Sample data — illustrates a variable-value program."),
        dict(provider="Solmark Streaming", name="Solmark Streaming Credits",
             tier=Tier.TIER_3_WATCH, benefit=BT.DATA_STREAMING,
             disclosure=VD.NOT_CURRENTLY_VERIFIED, amount=None, currency=None,
             text="Watch item; value not yet verified (FICTIONAL sample program)",
             url="https://example.com/solmark-streaming-credits",
             notes="Sample data — illustrates a not-yet-verified watch item."),
    ]


_TIER_META = {
    Tier.TIER_1: Priority.HIGH,
    Tier.TIER_2: Priority.MEDIUM,
    Tier.TIER_3_WATCH: Priority.LOW,
}


def _to_program(row: dict, today: date) -> Program:
    deadline: Optional[date] = row.get("application_deadline")
    return Program(
        provider=row["provider"],
        name=row["name"],
        tier=row["tier"],
        priority=_TIER_META[row["tier"]],
        benefit_type=row["benefit"],
        status=Status.RESEARCHED,
        official_url=row["url"],
        value_disclosure=row["disclosure"],
        advertised_maximum=row["amount"],
        advertised_maximum_text=row["text"],
        currency=row["currency"],
        primary_intended_use=row["benefit"].value,
        application_deadline=deadline,
        date_identified=today,
        notes=row["notes"],
    )


def seed(repo: Repository) -> None:
    """Populate the repository with FICTIONAL sample data demonstrating every
    screen. Intended for a fresh repository (local dev / first run only)."""
    today = _today()
    programs = {p.name: p for p in (
        repo.add_program(_to_program(row, today)) for row in _programs()
    )}

    # Two fictional submissions: one still pending, one approved with an
    # actual award (so the Credits screen has something to show).
    nimbus = programs["Nimbus Cloud Startup Credits"]
    vectra = programs["Vectra for Builders"]

    nimbus_app = repo.add_application(Application(
        program_id=nimbus.id, provider=nimbus.provider, program=nimbus.name,
        status=Status.SUBMITTED, reference="SAMPLE-REF-0001",
        confirmation="Sample confirmation — application received",
        date_submitted=today - timedelta(days=5),
        notes="Fictional sample submission.",
    ))

    vectra_app = repo.add_application(Application(
        program_id=vectra.id, provider=vectra.provider, program=vectra.name,
        status=Status.APPROVED, reference="SAMPLE-REF-0002",
        confirmation="Sample confirmation — approved",
        date_submitted=today - timedelta(days=40),
        decision_date=today - timedelta(days=20),
        actual_award=20000.0, currency="USD",
        notes="Fictional sample approval, used to populate the Credits screen.",
    ))

    # Credit awards tied to the approved sample application.
    repo.add_credit(CreditAward(
        application_id=vectra_app.id, program_id=vectra.id,
        provider_program=f"{vectra.provider} — {vectra.name}",
        benefit_type=BT.OBSERVABILITY,
        actual_award=20000.0, currency="USD",
        activation_date=today - timedelta(days=20),
        expiration_date=today + timedelta(days=25),  # shows in the 30-day bucket
        amount_used=6500.0,
        notes="Fictional sample credit award, expiring soon by design (demo).",
    ))
    repo.add_credit(CreditAward(
        provider_program="Sample Cloud Co — Longer-Runway Credit",
        benefit_type=BT.CLOUD_CREDITS,
        actual_award=8000.0, currency="USD",
        activation_date=today - timedelta(days=10),
        expiration_date=today + timedelta(days=80),  # shows in the 90-day bucket
        amount_used=1000.0,
        notes="Fictional sample credit award with more runway (demo).",
    ))

    # Follow-ups: one overdue, one upcoming, plus the Forgeline deadline watch.
    repo.add_followup(Followup(
        application_id=nimbus_app.id, program_id=nimbus.id,
        provider_program=f"{nimbus.provider} — {nimbus.name}",
        status=Status.SUBMITTED,
        next_followup=today - timedelta(days=3),
        action="Sample: check on application status (overdue by design, demo).",
        priority=Priority.HIGH,
    ))
    repo.add_followup(Followup(
        provider_program="Sample Cloud Co — Longer-Runway Credit",
        status=Status.RESEARCHED,
        next_followup=today + timedelta(days=10),
        action="Sample: confirm renewal terms before credit expires.",
        priority=Priority.MEDIUM,
    ))
    forgeline = programs["Forgeline AI Compute Grant"]
    repo.add_followup(Followup(
        program_id=forgeline.id,
        provider_program=f"{forgeline.provider} — {forgeline.name}",
        status=Status.RESEARCHED,
        next_followup=today + timedelta(days=11),
        action=f"Decide go/no-go before the {forgeline.application_deadline} deadline (sample).",
        priority=Priority.HIGH,
    ))


def program_count() -> int:
    return len(_programs())


def submission_count() -> int:
    return 2
