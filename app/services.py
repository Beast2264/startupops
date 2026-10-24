"""Business logic for StartupOps.

Sits between the web routes and the repository. Handles aggregation,
enrichment (computed fields), and filtering. All "today"-dependent logic
accepts an explicit ``today`` for deterministic testing.

Catalog vs. submissions:
  * "programs tracked" counts the PROGRAM catalog.
  * submitted / under review / approved / rejected count actual APPLICATIONS.
  * advertised verified value sums PROGRAM advertised maximums (disclosed
    numbers only); actual awards sum APPLICATION awards.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from . import calculations as calc
from .enums import Status, ValueDisclosure
from .models import Application, CreditAward, Followup, Program
from .repository import Repository


# --- enriched view objects (models + computed fields for templates) ---

@dataclass
class CreditView:
    credit: CreditAward
    remaining: Optional[float]
    percentage_remaining: Optional[float]
    days_until_expiration: Optional[int]
    expiration_bucket: Optional[str]


@dataclass
class FollowupView:
    followup: Followup
    days_until_followup: Optional[int]
    overdue: bool


@dataclass
class DashboardSummary:
    programs_tracked: int = 0
    applications_count: int = 0
    ready_to_apply: int = 0
    submitted: int = 0
    under_review: int = 0
    approved: int = 0
    rejected_or_not_eligible: int = 0
    # Verified advertised value, grouped by currency (never summed across
    # currencies). CONDITIONAL ceilings are tracked separately so an
    # unguaranteed ceiling is never presented as verified value.
    verified_value_by_currency: Dict[str, float] = field(default_factory=dict)
    conditional_ceiling_by_currency: Dict[str, float] = field(default_factory=dict)
    total_actual_awards: float = 0.0
    followups_due: int = 0
    upcoming_deadlines: List[Program] = field(default_factory=list)
    credits_expiring_30: int = 0
    credits_expiring_60: int = 0
    credits_expiring_90: int = 0
    program_status_counts: Dict[str, int] = field(default_factory=dict)


class StartupOpsService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    # ------------------------------------------------------------- programs
    def list_programs(
        self,
        tier: Optional[str] = None,
        status: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> List[Program]:
        programs = self.repo.list_programs()
        if tier:
            programs = [p for p in programs if p.tier.value == tier]
        if status:
            programs = [p for p in programs if p.status.value == status]
        if provider:
            needle = provider.lower()
            programs = [p for p in programs if needle in p.provider.lower()]
        return sorted(programs, key=lambda p: (p.tier.value, p.provider.lower()))

    def get_program(self, program_id: str) -> Optional[Program]:
        return self.repo.get_program(program_id)

    def create_program(self, program: Program) -> Program:
        return self.repo.add_program(program)

    def update_program(self, program_id: str, program: Program) -> Program:
        return self.repo.update_program(program_id, program)

    # --------------------------------------------------------- applications
    def list_applications(
        self,
        status: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> List[Application]:
        apps = self.repo.list_applications()
        if status:
            apps = [a for a in apps if a.status.value == status]
        if provider:
            needle = provider.lower()
            apps = [a for a in apps if needle in a.provider.lower()]
        return sorted(apps, key=lambda a: a.provider.lower())

    def get_application(self, app_id: str) -> Optional[Application]:
        return self.repo.get_application(app_id)

    def create_application(self, app: Application) -> Application:
        return self.repo.add_application(app)

    def update_application(self, app_id: str, app: Application) -> Application:
        return self.repo.update_application(app_id, app)

    # --------------------------------------------------------------- credits
    def list_credit_views(self, today: date) -> List[CreditView]:
        views: List[CreditView] = []
        for c in self.repo.list_credits():
            views.append(
                CreditView(
                    credit=c,
                    remaining=calc.remaining_amount(c.actual_award, c.amount_used),
                    percentage_remaining=calc.percentage_remaining(
                        c.actual_award, c.amount_used
                    ),
                    days_until_expiration=calc.days_until(c.expiration_date, today),
                    expiration_bucket=calc.expiration_bucket(c.expiration_date, today),
                )
            )
        return views

    def create_credit(self, credit: CreditAward) -> CreditAward:
        return self.repo.add_credit(credit)

    # ------------------------------------------------------------ follow-ups
    def list_followup_views(self, today: date) -> List[FollowupView]:
        views: List[FollowupView] = []
        for f in self.repo.list_followups():
            d = calc.days_until(f.next_followup, today)
            overdue = (d is not None and d < 0 and not f.completed)
            views.append(FollowupView(followup=f, days_until_followup=d, overdue=overdue))
        return sorted(
            views,
            key=lambda v: (
                v.followup.completed,
                v.days_until_followup if v.days_until_followup is not None else 10**6,
            ),
        )

    def create_followup(self, followup: Followup) -> Followup:
        return self.repo.add_followup(followup)

    # ------------------------------------------------------------- dashboard
    def dashboard(self, today: date) -> DashboardSummary:
        programs = self.repo.list_programs()
        apps = self.repo.list_applications()
        credits = self.repo.list_credits()
        followups = self.repo.list_followups()

        s = DashboardSummary()
        s.programs_tracked = len(programs)
        s.applications_count = len(apps)

        # Program-level pipeline state + advertised value (per currency).
        prog_counts: Dict[str, int] = {st.value: 0 for st in Status}
        for p in programs:
            prog_counts[p.status.value] += 1
            if p.advertised_maximum is None:
                continue
            cur = p.currency or "USD"
            if p.value_disclosure is ValueDisclosure.VERIFIED:
                s.verified_value_by_currency[cur] = round(
                    s.verified_value_by_currency.get(cur, 0.0) + p.advertised_maximum, 2)
            elif p.value_disclosure is ValueDisclosure.CONDITIONAL:
                s.conditional_ceiling_by_currency[cur] = round(
                    s.conditional_ceiling_by_currency.get(cur, 0.0) + p.advertised_maximum, 2)
        s.program_status_counts = prog_counts
        s.ready_to_apply = prog_counts[Status.READY_TO_APPLY.value]

        # Application-level (actual submission) outcomes + actual awards.
        app_counts: Dict[str, int] = {st.value: 0 for st in Status}
        for a in apps:
            app_counts[a.status.value] += 1
            if a.actual_award is not None:  # model-enforced: approved only
                s.total_actual_awards += a.actual_award
        s.submitted = app_counts[Status.SUBMITTED.value]
        s.under_review = app_counts[Status.UNDER_REVIEW.value]
        s.approved = (
            app_counts[Status.APPROVED.value] + app_counts[Status.PARTIALLY_APPROVED.value]
        )
        s.rejected_or_not_eligible = (
            app_counts[Status.REJECTED.value]
            + app_counts[Status.NOT_ELIGIBLE.value]
            + prog_counts[Status.NOT_ELIGIBLE.value]
        )

        # Follow-ups due = not completed and due today or overdue.
        for f in followups:
            d = calc.days_until(f.next_followup, today)
            if not f.completed and d is not None and d <= 0:
                s.followups_due += 1

        # Upcoming application deadlines within 30 days (program-level).
        upcoming = [
            p for p in programs
            if calc.within_days(p.application_deadline, 30, today)
        ]
        s.upcoming_deadlines = sorted(
            upcoming, key=lambda p: p.application_deadline  # type: ignore[arg-type]
        )

        # Credits expiring windows (cumulative).
        for c in credits:
            d = calc.days_until(c.expiration_date, today)
            if d is None or d < 0:
                continue
            if d <= 30:
                s.credits_expiring_30 += 1
            if d <= 60:
                s.credits_expiring_60 += 1
            if d <= 90:
                s.credits_expiring_90 += 1

        return s
