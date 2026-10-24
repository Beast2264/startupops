"""FirestoreRepository tests against the local Firestore emulator.

These are SKIPPED unless FIRESTORE_EMULATOR_HOST is set (i.e. an emulator is
running). They never touch a real GCP database. Run via:

    gcloud emulators firestore start --host-port=127.0.0.1:8080   # terminal 1
    $env:FIRESTORE_EMULATOR_HOST="127.0.0.1:8080"; python -m pytest tests/test_firestore_emulator.py
"""
import os
from datetime import date

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason="Firestore emulator not running (FIRESTORE_EMULATOR_HOST unset)",
)

from app.enums import BenefitType, Status, ValueDisclosure  # noqa: E402
from app.firestore_repo import FirestoreRepository  # noqa: E402
from app.models import Application, CreditAward, Followup, Program  # noqa: E402
from app.services import StartupOpsService  # noqa: E402

TODAY = date(2026, 8, 16)
TEST_PROJECT = "startupops-emulator-test"


@pytest.fixture
def fs_repo():
    repo = FirestoreRepository(project=TEST_PROJECT)
    # Start each test from a clean slate.
    for coll in ("programs", "applications", "credit_awards", "followups"):
        for doc in repo._db.collection(coll).stream():
            doc.reference.delete()
    return repo


def test_program_crud_roundtrip(fs_repo):
    created = fs_repo.add_program(Program(
        provider="Twilio",
        name="Twilio AI Startup Searchlight",
        status=Status.RESEARCHED,
        application_deadline=date(2026, 9, 11),
    ))
    assert created.id
    got = fs_repo.get_program(created.id)
    assert got is not None
    assert got.name == "Twilio AI Startup Searchlight"
    # Types survive: date stays date, enum stays enum.
    assert isinstance(got.application_deadline, date)
    assert got.application_deadline == date(2026, 9, 11)
    assert got.status is Status.RESEARCHED
    assert fs_repo.delete_program(created.id) is True
    assert fs_repo.get_program(created.id) is None


def test_application_crud_roundtrip(fs_repo):
    prog = fs_repo.add_program(Program(
        provider="Cloudflare", name="Cloudflare for Startups"))
    created = fs_repo.add_application(Application(
        program_id=prog.id,
        provider="Cloudflare",
        program="Cloudflare for Startups",
        status=Status.SUBMITTED,
        date_submitted=date(2026, 8, 15),
        reference="CF-1",
    ))
    assert created.id

    got = fs_repo.get_application(created.id)
    assert got is not None
    assert got.program_id == prog.id
    assert isinstance(got.date_submitted, date)
    assert got.status is Status.SUBMITTED

    updated = fs_repo.update_application(
        created.id,
        got.model_copy(update={"status": Status.UNDER_REVIEW}),
    )
    assert updated.status is Status.UNDER_REVIEW
    assert fs_repo.get_application(created.id).status is Status.UNDER_REVIEW

    assert fs_repo.delete_application(created.id) is True
    assert fs_repo.get_application(created.id) is None
    assert fs_repo.delete_application(created.id) is False


def test_credit_roundtrip_and_remaining_via_service(fs_repo):
    fs_repo.add_credit(CreditAward(
        provider_program="Acme Cloud",
        benefit_type=BenefitType.CLOUD_CREDITS,
        actual_award=1000.0,
        amount_used=250.0,
        expiration_date=date(2026, 9, 5),
    ))
    service = StartupOpsService(fs_repo)
    views = service.list_credit_views(TODAY)
    assert len(views) == 1
    assert views[0].remaining == 750.0
    assert views[0].percentage_remaining == 75.0
    assert isinstance(views[0].credit.expiration_date, date)


def test_dashboard_over_firestore(fs_repo):
    p1 = fs_repo.add_program(Program(
        provider="A", name="P1",
        value_disclosure=ValueDisclosure.VERIFIED, advertised_maximum=5000.0))
    fs_repo.add_program(Program(provider="B", name="P2"))
    fs_repo.add_application(Application(
        program_id=p1.id, provider="A", program="P1",
        status=Status.APPROVED, actual_award=2000.0))
    fs_repo.add_followup(Followup(
        provider_program="A", next_followup=date(2026, 8, 1)))  # overdue

    service = StartupOpsService(fs_repo)
    s = service.dashboard(TODAY)
    assert s.programs_tracked == 2
    assert s.applications_count == 1
    assert s.approved == 1
    assert s.verified_value_by_currency == {"USD": 5000.0}
    assert s.total_actual_awards == 2000.0
    assert s.followups_due == 1


def test_list_isolated_by_collection(fs_repo):
    prog = fs_repo.add_program(Program(provider="A", name="P"))
    fs_repo.add_application(Application(
        program_id=prog.id, provider="A", program="P"))
    fs_repo.add_credit(CreditAward(provider_program="C"))
    fs_repo.add_followup(Followup(provider_program="F"))
    assert len(fs_repo.list_programs()) == 1
    assert len(fs_repo.list_applications()) == 1
    assert len(fs_repo.list_credits()) == 1
    assert len(fs_repo.list_followups()) == 1
