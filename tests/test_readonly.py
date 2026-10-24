"""Read-only repository wrapper: reads pass through, writes are refused.

Also verifies the live-data / read-only decoupling: live Firestore mode is
writable by default, and the read-only wrapper is engaged only by the explicit
STARTUPOPS_READ_ONLY safety flag (or the legacy firestore-readonly alias).
"""
import pytest
from starlette.testclient import TestClient

from app.main import build_default_repository, create_app
from app.models import Program
from app.repository import (
    InMemoryRepository,
    ReadOnlyError,
    ReadOnlyRepository,
)


def _seeded_inner():
    inner = InMemoryRepository()
    inner.add_program(Program(provider="A", name="P"))
    return inner


def test_reads_pass_through():
    ro = ReadOnlyRepository(_seeded_inner())
    assert len(ro.list_programs()) == 1
    assert ro.list_applications() == []
    assert ro.list_credits() == []
    assert ro.list_followups() == []


def test_writes_are_refused():
    ro = ReadOnlyRepository(_seeded_inner())
    with pytest.raises(ReadOnlyError):
        ro.add_program(Program(provider="B", name="Q"))
    with pytest.raises(ReadOnlyError):
        ro.add_application(None)  # never reached; guard raises first
    with pytest.raises(ReadOnlyError):
        ro.delete_program("program-0001")


def test_default_backend_is_memory(monkeypatch):
    monkeypatch.delenv("STARTUPOPS_DATA_BACKEND", raising=False)
    monkeypatch.delenv("STARTUPOPS_READ_ONLY", raising=False)
    repo, do_seed = build_default_repository()
    assert repo is None       # create_app builds a seeded in-memory repo
    assert do_seed is True


# --- live-data vs. read-only-safety decoupling -----------------------------

def _fake_live_backend(monkeypatch):
    """Swap FirestoreRepository for a writable in-memory stand-in so
    build_default_repository() never constructs a real GCP client."""
    import app.firestore_repo as fr
    monkeypatch.setattr(fr, "FirestoreRepository", lambda **kw: InMemoryRepository())


def test_live_backend_is_writable_by_default(monkeypatch):
    """Live data must NOT imply read-only: no wrapper unless explicitly asked."""
    monkeypatch.setenv("STARTUPOPS_DATA_BACKEND", "firestore")
    monkeypatch.setenv("STARTUPOPS_FIRESTORE_PROJECT", "fake-test-project")
    monkeypatch.delenv("STARTUPOPS_READ_ONLY", raising=False)
    _fake_live_backend(monkeypatch)
    repo, do_seed = build_default_repository()
    assert not isinstance(repo, ReadOnlyRepository)
    assert do_seed is False


def test_read_only_flag_wraps_live_backend(monkeypatch):
    """The explicit safety flag re-enables the read-only wrapper over live data."""
    monkeypatch.setenv("STARTUPOPS_DATA_BACKEND", "firestore")
    monkeypatch.setenv("STARTUPOPS_FIRESTORE_PROJECT", "fake-test-project")
    monkeypatch.setenv("STARTUPOPS_READ_ONLY", "true")
    _fake_live_backend(monkeypatch)
    repo, do_seed = build_default_repository()
    assert isinstance(repo, ReadOnlyRepository)
    assert do_seed is False


def test_legacy_firestore_readonly_alias_still_read_only(monkeypatch):
    """Back-compat: the explicit 'firestore-readonly' backend stays read-only."""
    monkeypatch.setenv("STARTUPOPS_DATA_BACKEND", "firestore-readonly")
    monkeypatch.setenv("STARTUPOPS_FIRESTORE_PROJECT", "fake-test-project")
    monkeypatch.delenv("STARTUPOPS_READ_ONLY", raising=False)
    _fake_live_backend(monkeypatch)
    repo, _ = build_default_repository()
    assert isinstance(repo, ReadOnlyRepository)


def test_firestore_backend_without_project_raises(monkeypatch):
    """The explicit guard fires before ever touching a GCP client."""
    monkeypatch.setenv("STARTUPOPS_DATA_BACKEND", "firestore")
    monkeypatch.delenv("STARTUPOPS_FIRESTORE_PROJECT", raising=False)
    with pytest.raises(RuntimeError, match="STARTUPOPS_FIRESTORE_PROJECT"):
        build_default_repository()


# --- HTTP-level proof over the exact failing code path ---------------------

def test_live_like_writable_backend_persists_via_http():
    """Simulates live mode with writes ENABLED: POST /programs persists through
    the normal application data layer (the path that previously 403'd)."""
    repo = InMemoryRepository()  # stands in for a writable live backend
    client = TestClient(create_app(repo, do_seed=False))
    r = client.post(
        "/programs",
        data={"provider": "LiveCo", "name": "Live Program"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    program_id = r.headers["location"].rsplit("/", 1)[1]
    stored = repo.get_program(program_id)
    assert stored is not None
    assert stored.name == "Live Program"


def test_read_only_safety_still_denies_writes_via_http():
    """With the read-only wrapper active, reads work but the previously-seen
    403 read-only response is preserved (the safety brake still works)."""
    client = TestClient(create_app(ReadOnlyRepository(_seeded_inner()), do_seed=False))
    assert client.get("/programs").status_code == 200  # reads intact
    r = client.post(
        "/programs",
        data={"provider": "X", "name": "Y"},
        follow_redirects=False,
    )
    assert r.status_code == 403
    assert "read-only live mode" in r.text
