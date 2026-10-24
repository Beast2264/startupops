"""Dashboard aggregation and seed catalog/submission split."""
from datetime import date

from app.enums import Status, ValueDisclosure
from app.models import Application, CreditAward, Followup, Program
from app.seed import program_count, seed, submission_count

TODAY = date(2026, 8, 16)


def test_dashboard_counts_catalog_vs_submissions(service):
    # Catalog: two programs, one with a VERIFIED advertised max.
    p1 = service.create_program(Program(
        provider="A", name="P1",
        value_disclosure=ValueDisclosure.VERIFIED, advertised_maximum=5000.0,
        status=Status.READY_TO_APPLY))
    service.create_program(Program(
        provider="B", name="P2", advertised_maximum_text="UNVERIFIED"))
    # One actual approved submission with an award.
    service.create_application(Application(
        program_id=p1.id, provider="A", program="P1",
        status=Status.APPROVED, actual_award=2000.0))

    s = service.dashboard(TODAY)
    assert s.programs_tracked == 2          # catalog count
    assert s.applications_count == 1        # submission count
    assert s.ready_to_apply == 1            # program-level
    assert s.approved == 1                  # application-level
    # Verified value counts only the VERIFIED program number (by currency).
    assert s.verified_value_by_currency == {"USD": 5000.0}
    assert s.total_actual_awards == 2000.0


def test_conditional_ceiling_not_in_verified_value(service):
    from app.enums import ValueDisclosure
    service.create_program(Program(
        provider="V", name="Verified", value_disclosure=ValueDisclosure.VERIFIED,
        advertised_maximum=1000.0, currency="USD"))
    service.create_program(Program(
        provider="C", name="Conditional", value_disclosure=ValueDisclosure.CONDITIONAL,
        advertised_maximum=100000.0, currency="USD"))
    s = service.dashboard(TODAY)
    # Conditional ceiling is tracked separately, never folded into verified value.
    assert s.verified_value_by_currency == {"USD": 1000.0}
    assert s.conditional_ceiling_by_currency == {"USD": 100000.0}


def test_verified_value_not_summed_across_currencies(service):
    from app.enums import ValueDisclosure
    service.create_program(Program(
        provider="U", name="Usd", value_disclosure=ValueDisclosure.VERIFIED,
        advertised_maximum=100.0, currency="USD"))
    service.create_program(Program(
        provider="E", name="Eur", value_disclosure=ValueDisclosure.VERIFIED,
        advertised_maximum=200.0, currency="EUR"))
    s = service.dashboard(TODAY)
    assert s.verified_value_by_currency == {"USD": 100.0, "EUR": 200.0}


def test_dashboard_deadlines_from_programs_and_followups_due(service):
    service.create_program(Program(
        provider="Z", name="Deadline soon",
        application_deadline=date(2026, 9, 1)))       # within 30 days
    service.create_followup(Followup(
        provider_program="X", next_followup=date(2026, 8, 10)))  # overdue -> due
    service.create_followup(Followup(
        provider_program="Y", next_followup=date(2026, 9, 30)))  # not due

    s = service.dashboard(TODAY)
    assert s.followups_due == 1
    assert len(s.upcoming_deadlines) == 1
    assert s.upcoming_deadlines[0].provider == "Z"


def test_dashboard_credit_expiry_windows(service):
    service.create_credit(CreditAward(
        provider_program="c30", actual_award=100.0,
        expiration_date=date(2026, 9, 5)))    # 20 days
    service.create_credit(CreditAward(
        provider_program="c75", actual_award=100.0,
        expiration_date=date(2026, 10, 30)))  # 75 days

    s = service.dashboard(TODAY)
    assert s.credits_expiring_30 == 1
    assert s.credits_expiring_60 == 1
    assert s.credits_expiring_90 == 2


def test_seed_splits_catalog_and_submissions(service):
    from app.enums import ValueDisclosure
    seed(service.repo)
    programs = service.repo.list_programs()
    apps = service.repo.list_applications()
    by_name = {p.name: p for p in programs}

    # Fictional sample catalog + exactly 2 fictional sample submissions.
    assert len(programs) == program_count()
    assert len(apps) == submission_count() == 2
    assert all(a.status in (Status.SUBMITTED, Status.APPROVED) for a in apps)

    # A numeric advertised maximum exists ONLY on VERIFIED/CONDITIONAL programs.
    for p in programs:
        if p.advertised_maximum is not None:
            assert p.value_disclosure in (
                ValueDisclosure.VERIFIED, ValueDisclosure.CONDITIONAL)

    # Spot-check the sample classifications used to demonstrate the feature.
    assert by_name["Nimbus Cloud Startup Credits"].advertised_maximum == 5000.0
    assert by_name["Forgeline AI Compute Grant"].value_disclosure is ValueDisclosure.CONDITIONAL
    assert by_name["Forgeline AI Compute Grant"].advertised_maximum == 50000.0
    # Non-cash verified benefit keeps text, no dollar figure.
    assert by_name["Ashgrove ID for Startups"].value_disclosure is ValueDisclosure.VERIFIED
    assert by_name["Ashgrove ID for Startups"].advertised_maximum is None
    # Undisclosed/variable stay that way with no invented number.
    assert by_name["Driftwood Data Startup Program"].value_disclosure is ValueDisclosure.NOT_PUBLICLY_DISCLOSED
    assert by_name["Driftwood Data Startup Program"].advertised_maximum is None
    assert by_name["Palisade Pro for Startups"].value_disclosure is ValueDisclosure.VARIABLE

    # One submission approved with an actual award (feeds the Credits screen).
    approved = [a for a in apps if a.status is Status.APPROVED][0]
    assert approved.actual_award == 20000.0
    submitted = [a for a in apps if a.status is Status.SUBMITTED][0]
    assert submitted.actual_award is None


def test_seed_dashboard_shows_sample_submissions(service):
    seed(service.repo)
    s = service.dashboard(date.today())
    assert s.programs_tracked == program_count()
    assert s.applications_count == 2
    assert s.submitted == 1
    assert s.approved == 1
    assert s.total_actual_awards == 20000.0
    # The Forgeline sample deadline (18 days out) surfaces as upcoming.
    assert any(p.provider == "Forgeline AI" for p in s.upcoming_deadlines)
