"""Service-level credit remaining and follow-up date calculation."""
from datetime import date

from app.enums import BenefitType, Status
from app.models import CreditAward, Followup

TODAY = date(2026, 8, 16)


def test_credit_view_computes_remaining_and_expiry(service):
    service.create_credit(CreditAward(
        provider_program="Acme Cloud",
        benefit_type=BenefitType.CLOUD_CREDITS,
        actual_award=1000.0,
        amount_used=400.0,
        expiration_date=date(2026, 9, 5),  # 20 days out
    ))
    views = service.list_credit_views(TODAY)
    assert len(views) == 1
    v = views[0]
    assert v.remaining == 600.0
    assert v.percentage_remaining == 60.0
    assert v.days_until_expiration == 20
    assert v.expiration_bucket == "30"


def test_credit_without_award_shows_no_remaining(service):
    service.create_credit(CreditAward(
        provider_program="Unverified Co",
        advertised_maximum_text="UNVERIFIED / NOT PUBLICLY DISCLOSED",
    ))
    v = service.list_credit_views(TODAY)[0]
    assert v.remaining is None
    assert v.percentage_remaining is None


def test_followup_days_and_overdue(service):
    service.create_followup(Followup(
        provider_program="Late Co", next_followup=date(2026, 8, 10),  # overdue
    ))
    service.create_followup(Followup(
        provider_program="Soon Co", next_followup=date(2026, 8, 20),  # 4 days
    ))
    views = service.list_followup_views(TODAY)
    by_name = {v.followup.provider_program: v for v in views}
    assert by_name["Late Co"].days_until_followup == -6
    assert by_name["Late Co"].overdue is True
    assert by_name["Soon Co"].days_until_followup == 4
    assert by_name["Soon Co"].overdue is False


def test_completed_followup_not_overdue(service):
    service.create_followup(Followup(
        provider_program="Done Co", next_followup=date(2026, 8, 1), completed=True,
    ))
    v = service.list_followup_views(TODAY)[0]
    assert v.overdue is False
