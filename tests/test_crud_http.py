"""CRUD behavior and HTTP smoke via TestClient (loopback, in-process)."""
import pytest
from starlette.testclient import TestClient

from app.main import create_app
from app.models import Application, Program
from app.repository import InMemoryRepository


@pytest.fixture
def client():
    return TestClient(create_app())  # seeded


def test_program_crud_roundtrip_in_repository():
    repo = InMemoryRepository()
    prog = repo.add_program(Program(provider="A", name="P"))
    assert prog.id is not None
    assert repo.get_program(prog.id).name == "P"
    repo.update_program(prog.id, Program(provider="A", name="P2"))
    assert repo.get_program(prog.id).name == "P2"
    assert repo.delete_program(prog.id) is True
    assert repo.delete_program(prog.id) is False


def test_application_references_program_in_repository():
    repo = InMemoryRepository()
    prog = repo.add_program(Program(provider="A", name="P"))
    app = repo.add_application(Application(
        program_id=prog.id, provider="A", program="P"))
    assert app.program_id == prog.id
    assert repo.get_application(app.id).program == "P"


def test_all_five_screens_render(client):
    for path in ("/", "/programs", "/applications", "/credits", "/followups"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "StartupOps" in r.text


def test_seed_shows_sample_programs_and_applications(client):
    from app.seed import program_count, submission_count

    progs = client.get("/programs")
    apps = client.get("/applications")
    assert f"{program_count()} shown" in progs.text
    assert f"{submission_count()} shown" in apps.text
    # Sample submissions appear as applications; a catalog-only sample
    # program does not (demonstrates the catalog-vs-submission split).
    assert "Nimbus Cloud Startup Credits" in apps.text
    assert "Vectra for Builders" in apps.text
    assert "Forgeline AI Compute Grant" not in apps.text
    assert "Forgeline AI Compute Grant" in progs.text


def test_create_program_then_application(client):
    # Create a program.
    rp = client.post("/programs", data={
        "provider": "NewCo", "name": "NewCo Startups",
        "tier": "TIER_1", "priority": "HIGH", "status": "READY_TO_APPLY",
    }, follow_redirects=False)
    assert rp.status_code == 303
    program_id = rp.headers["location"].rsplit("/", 1)[1]

    # Record a submission against it.
    ra = client.post("/applications", data={
        "program_id": program_id, "status": "SUBMITTED", "reference": "REF-1",
    }, follow_redirects=False)
    assert ra.status_code == 303
    detail = client.get(ra.headers["location"])
    assert detail.status_code == 200
    # Provider/program denormalized from the program.
    assert "NewCo Startups" in detail.text
    assert "REF-1" in detail.text


def test_application_award_without_approval_fails_safely(client):
    rp = client.post("/programs", data={
        "provider": "BadCo", "name": "BadCo"}, follow_redirects=False)
    program_id = rp.headers["location"].rsplit("/", 1)[1]
    r = client.post("/applications", data={
        "program_id": program_id, "status": "SUBMITTED", "actual_award": "50000",
    }, follow_redirects=False)
    assert r.status_code == 400
    assert "Could not save" in r.text


def test_filter_programs_by_tier(client):
    r = client.get("/programs", params={"tier": "TIER_1"})
    assert r.status_code == 200
    body = r.text.split("<tbody>")[1]
    assert "TIER_3_WATCH" not in body


def test_edit_application_status(client):
    rp = client.post("/programs", data={
        "provider": "EditCo", "name": "EditCo P"}, follow_redirects=False)
    program_id = rp.headers["location"].rsplit("/", 1)[1]
    ra = client.post("/applications", data={
        "program_id": program_id, "status": "SUBMITTED"}, follow_redirects=False)
    app_id = ra.headers["location"].rsplit("/", 1)[1]
    upd = client.post(f"/applications/{app_id}", data={
        "program_id": program_id, "status": "UNDER_REVIEW"}, follow_redirects=False)
    assert upd.status_code == 303
    assert "UNDER_REVIEW" in client.get(f"/applications/{app_id}").text
