"""FastAPI application for StartupOps (local-first MVP).

Server-rendered HTML (Jinja2) + minimal JS. Private/internal utility.
Run locally, loopback only:  uvicorn app.main:app --host 127.0.0.1 --port 8000

Catalog vs. submissions: Programs is the catalog; Applications are actual
submissions that reference a program.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Tuple

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from .enums import BenefitType, Priority, Status, Tier, ValueDisclosure
from .models import Application, CreditAward, Followup, Program
from .repository import InMemoryRepository, ReadOnlyError, ReadOnlyRepository, Repository
from .seed import seed
from .services import StartupOpsService


def _env_flag(name: str) -> bool:
    """True when an env var is set to a truthy string (1/true/on/yes)."""
    return os.environ.get(name, "").strip().lower() in ("1", "true", "on", "yes")


def build_default_repository() -> Tuple[Optional[Repository], bool]:
    """Select the data backend AND the read-only safety state from the env.

    STARTUPOPS_DATA_BACKEND selects WHERE data lives:
      * "memory" (default) -> None + do_seed=True (create_app builds a seeded
        in-memory repo). This is what tests use, and what runs out of the box
        with no cloud account.
      * "firestore" / "live" -> your own Firestore database, identified by
        STARTUPOPS_FIRESTORE_PROJECT (required) and STARTUPOPS_FIRESTORE_DATABASE
        (optional, defaults to "(default)"). There is no built-in project — you
        must configure your own Google Cloud project and credentials
        (Application Default Credentials, or FIRESTORE_EMULATOR_HOST for a
        local emulator) before selecting this backend.

    STARTUPOPS_READ_ONLY is a SEPARATE safety switch (default off). When truthy
    the selected backend is wrapped in a ReadOnlyRepository and every write is
    refused — regardless of which backend is in use.

    Returns (repo_or_None, do_seed).
    """
    backend = os.environ.get("STARTUPOPS_DATA_BACKEND", "memory").strip().lower()
    read_only = _env_flag("STARTUPOPS_READ_ONLY") or backend == "firestore-readonly"

    if backend in ("firestore", "live", "firestore-readonly"):
        project = os.environ.get("STARTUPOPS_FIRESTORE_PROJECT", "").strip()
        if not project:
            raise RuntimeError(
                "STARTUPOPS_DATA_BACKEND=firestore requires STARTUPOPS_FIRESTORE_PROJECT "
                "to be set to your own Google Cloud project id. There is no default "
                "project — configure your own GCP project and Application Default "
                "Credentials (or FIRESTORE_EMULATOR_HOST for local testing) first."
            )
        database = os.environ.get("STARTUPOPS_FIRESTORE_DATABASE", "(default)").strip()
        from .firestore_repo import FirestoreRepository
        base: Repository = FirestoreRepository(project=project, database=database)
        return (ReadOnlyRepository(base) if read_only else base), False

    # In-memory backend (default). Honor the read-only flag here too: seed the
    # repo before wrapping, since a read-only repo cannot be seeded afterward.
    if read_only:
        inner = InMemoryRepository()
        seed(inner)
        return ReadOnlyRepository(inner), False
    return None, True

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _safe_url(url: Optional[str]) -> Optional[str]:
    """Only allow http(s) links to render as clickable."""
    if not url:
        return None
    u = url.strip()
    if u.lower().startswith(("http://", "https://")):
        return u
    return None


TEMPLATES.env.filters["safe_url"] = _safe_url


def _parse_date(value: Optional[str]) -> Optional[date]:
    if value is None or value.strip() == "":
        return None
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def _parse_float(value: Optional[str]) -> Optional[float]:
    if value is None or value.strip() == "":
        return None
    return float(value.strip())


def _parse_bool(value: Optional[str]) -> bool:
    return str(value).lower() in ("1", "true", "on", "yes")


def create_app(repo: Optional[Repository] = None, *, do_seed: bool = True) -> FastAPI:
    repo = repo or InMemoryRepository()
    if do_seed and not repo.list_programs():
        seed(repo)
    service = StartupOpsService(repo)

    app = FastAPI(title="StartupOps", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    @app.exception_handler(ReadOnlyError)
    async def _readonly_handler(request: Request, exc: ReadOnlyError):
        # In live read-only mode any write attempt is refused, not written.
        return HTMLResponse(
            f"<h1>Read-only mode</h1><p>{exc}</p><p><a href='/'>Back</a></p>",
            status_code=403,
        )

    def _ctx(request: Request, **extra):
        base = {
            "request": request,
            "statuses": list(Status),
            "tiers": list(Tier),
            "priorities": list(Priority),
            "benefit_types": list(BenefitType),
            "value_disclosures": list(ValueDisclosure),
            "today": date.today(),
        }
        base.update(extra)
        return base

    # ---------------------------------------------------------- dashboard
    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        summary = service.dashboard(date.today())
        return TEMPLATES.TemplateResponse(
            request, "dashboard.html", _ctx(request, summary=summary)
        )

    @app.get("/healthz", response_class=HTMLResponse)
    def healthz():
        return HTMLResponse("ok")

    # ------------------------------------------------------------- programs
    @app.get("/programs", response_class=HTMLResponse)
    def programs_list(
        request: Request,
        tier: Optional[str] = None,
        status: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        programs = service.list_programs(tier=tier, status=status, provider=provider)
        return TEMPLATES.TemplateResponse(
            request, "programs_list.html",
            _ctx(request, programs=programs,
                 f_tier=tier or "", f_status=status or "", f_provider=provider or ""),
        )

    @app.get("/programs/new", response_class=HTMLResponse)
    def program_new(request: Request):
        return TEMPLATES.TemplateResponse(
            request, "program_form.html",
            _ctx(request, program=None, errors=None, form_action="/programs"),
        )

    @app.get("/programs/{program_id}", response_class=HTMLResponse)
    def program_detail(request: Request, program_id: str):
        prog = service.get_program(program_id)
        if not prog:
            return HTMLResponse("Not found", status_code=404)
        apps = [a for a in service.list_applications() if a.program_id == program_id]
        return TEMPLATES.TemplateResponse(
            request, "program_detail.html",
            _ctx(request, program=prog, applications=apps),
        )

    @app.get("/programs/{program_id}/edit", response_class=HTMLResponse)
    def program_edit(request: Request, program_id: str):
        prog = service.get_program(program_id)
        if not prog:
            return HTMLResponse("Not found", status_code=404)
        return TEMPLATES.TemplateResponse(
            request, "program_form.html",
            _ctx(request, program=prog, errors=None,
                 form_action=f"/programs/{program_id}"),
        )

    def _program_from_form(form) -> Program:
        return Program(
            provider=form.get("provider", ""),
            name=form.get("name", ""),
            tier=form.get("tier") or Tier.TIER_3_WATCH,
            priority=form.get("priority") or Priority.MEDIUM,
            benefit_type=form.get("benefit_type") or BenefitType.CLOUD_CREDITS,
            status=form.get("status") or Status.RESEARCHED,
            official_url=form.get("official_url") or None,
            application_url=form.get("application_url") or None,
            value_disclosure=form.get("value_disclosure") or ValueDisclosure.NOT_CURRENTLY_VERIFIED,
            advertised_maximum=_parse_float(form.get("advertised_maximum")),
            advertised_maximum_text=form.get("advertised_maximum_text") or None,
            currency=form.get("currency") or "USD",
            eligibility_summary=form.get("eligibility_summary") or None,
            referral_requirement=_parse_bool(form.get("referral_requirement")),
            funding_requirement=_parse_bool(form.get("funding_requirement")),
            bootstrapped_eligibility=_parse_bool(form.get("bootstrapped_eligibility")),
            existing_customer_eligibility=_parse_bool(
                form.get("existing_customer_eligibility")),
            primary_intended_use=form.get("primary_intended_use") or None,
            architecture_impact=form.get("architecture_impact") or None,
            application_deadline=_parse_date(form.get("application_deadline")),
            date_identified=_parse_date(form.get("date_identified")),
            contact=form.get("contact") or None,
            notes=form.get("notes") or None,
        )

    @app.post("/programs")
    async def program_create(request: Request):
        form = await request.form()
        try:
            prog = _program_from_form(form)
        except (ValidationError, ValueError) as exc:
            return TEMPLATES.TemplateResponse(
                request, "program_form.html",
                _ctx(request, program=None, errors=str(exc), form_action="/programs"),
                status_code=400,
            )
        created = service.create_program(prog)
        return RedirectResponse(f"/programs/{created.id}", status_code=303)

    @app.post("/programs/{program_id}")
    async def program_update(request: Request, program_id: str):
        if not service.get_program(program_id):
            return HTMLResponse("Not found", status_code=404)
        form = await request.form()
        try:
            prog = _program_from_form(form)
        except (ValidationError, ValueError) as exc:
            return TEMPLATES.TemplateResponse(
                request, "program_form.html",
                _ctx(request, program=service.get_program(program_id),
                     errors=str(exc), form_action=f"/programs/{program_id}"),
                status_code=400,
            )
        service.update_program(program_id, prog)
        return RedirectResponse(f"/programs/{program_id}", status_code=303)

    # --------------------------------------------------------- applications
    @app.get("/applications", response_class=HTMLResponse)
    def applications_list(
        request: Request,
        status: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        apps = service.list_applications(status=status, provider=provider)
        return TEMPLATES.TemplateResponse(
            request, "applications_list.html",
            _ctx(request, applications=apps, f_status=status or "", f_provider=provider or ""),
        )

    @app.get("/applications/new", response_class=HTMLResponse)
    def application_new(request: Request):
        return TEMPLATES.TemplateResponse(
            request, "application_form.html",
            _ctx(request, application=None, errors=None,
                 programs=service.list_programs(), form_action="/applications"),
        )

    @app.get("/applications/{app_id}", response_class=HTMLResponse)
    def application_detail(request: Request, app_id: str):
        app_obj = service.get_application(app_id)
        if not app_obj:
            return HTMLResponse("Not found", status_code=404)
        program = service.get_program(app_obj.program_id) if app_obj.program_id else None
        return TEMPLATES.TemplateResponse(
            request, "application_detail.html",
            _ctx(request, application=app_obj, program=program),
        )

    @app.get("/applications/{app_id}/edit", response_class=HTMLResponse)
    def application_edit(request: Request, app_id: str):
        app_obj = service.get_application(app_id)
        if not app_obj:
            return HTMLResponse("Not found", status_code=404)
        return TEMPLATES.TemplateResponse(
            request, "application_form.html",
            _ctx(request, application=app_obj, errors=None,
                 programs=service.list_programs(), form_action=f"/applications/{app_id}"),
        )

    def _application_from_form(form) -> Application:
        # Denormalize provider/program name from the referenced program.
        program_id = form.get("program_id", "")
        provider = form.get("provider", "")
        program_name = form.get("program", "")
        prog = service.get_program(program_id) if program_id else None
        if prog:
            provider = prog.provider
            program_name = prog.name
        return Application(
            program_id=program_id,
            provider=provider,
            program=program_name,
            status=form.get("status") or Status.SUBMITTED,
            reference=form.get("reference") or None,
            confirmation=form.get("confirmation") or None,
            date_started=_parse_date(form.get("date_started")),
            date_submitted=_parse_date(form.get("date_submitted")),
            decision_date=_parse_date(form.get("decision_date")),
            actual_award=_parse_float(form.get("actual_award")),
            currency=form.get("currency") or "USD",
            next_action=form.get("next_action") or None,
            next_action_date=_parse_date(form.get("next_action_date")),
            contact=form.get("contact") or None,
            notes=form.get("notes") or None,
            confirmation_link=form.get("confirmation_link") or None,
        )

    @app.post("/applications")
    async def application_create(request: Request):
        form = await request.form()
        try:
            app_obj = _application_from_form(form)
        except (ValidationError, ValueError) as exc:
            return TEMPLATES.TemplateResponse(
                request, "application_form.html",
                _ctx(request, application=None, errors=str(exc),
                     programs=service.list_programs(), form_action="/applications"),
                status_code=400,
            )
        created = service.create_application(app_obj)
        return RedirectResponse(f"/applications/{created.id}", status_code=303)

    @app.post("/applications/{app_id}")
    async def application_update(request: Request, app_id: str):
        if not service.get_application(app_id):
            return HTMLResponse("Not found", status_code=404)
        form = await request.form()
        try:
            app_obj = _application_from_form(form)
        except (ValidationError, ValueError) as exc:
            return TEMPLATES.TemplateResponse(
                request, "application_form.html",
                _ctx(request, application=service.get_application(app_id), errors=str(exc),
                     programs=service.list_programs(), form_action=f"/applications/{app_id}"),
                status_code=400,
            )
        service.update_application(app_id, app_obj)
        return RedirectResponse(f"/applications/{app_id}", status_code=303)

    # --------------------------------------------------------------- credits
    @app.get("/credits", response_class=HTMLResponse)
    def credits_list(request: Request):
        views = service.list_credit_views(date.today())
        return TEMPLATES.TemplateResponse(
            request, "credits_list.html", _ctx(request, credit_views=views)
        )

    @app.get("/credits/new", response_class=HTMLResponse)
    def credit_new(request: Request):
        return TEMPLATES.TemplateResponse(
            request, "credit_form.html", _ctx(request, errors=None)
        )

    @app.post("/credits")
    async def credit_create(request: Request):
        form = await request.form()
        try:
            credit = CreditAward(
                provider_program=form.get("provider_program", ""),
                benefit_type=form.get("benefit_type") or BenefitType.CLOUD_CREDITS,
                advertised_maximum=_parse_float(form.get("advertised_maximum")),
                advertised_maximum_text=form.get("advertised_maximum_text") or None,
                actual_award=_parse_float(form.get("actual_award")),
                currency=form.get("currency") or "USD",
                activation_date=_parse_date(form.get("activation_date")),
                expiration_date=_parse_date(form.get("expiration_date")),
                amount_used=_parse_float(form.get("amount_used")) or 0.0,
                workload_assignment=form.get("workload_assignment") or None,
                restrictions=form.get("restrictions") or None,
                notes=form.get("notes") or None,
                evidence_link=form.get("evidence_link") or None,
            )
        except (ValidationError, ValueError) as exc:
            return TEMPLATES.TemplateResponse(
                request, "credit_form.html", _ctx(request, errors=str(exc)),
                status_code=400,
            )
        service.create_credit(credit)
        return RedirectResponse("/credits", status_code=303)

    # ------------------------------------------------------------ follow-ups
    @app.get("/followups", response_class=HTMLResponse)
    def followups_list(request: Request):
        views = service.list_followup_views(date.today())
        return TEMPLATES.TemplateResponse(
            request, "followups_list.html", _ctx(request, followup_views=views)
        )

    @app.get("/followups/new", response_class=HTMLResponse)
    def followup_new(request: Request):
        return TEMPLATES.TemplateResponse(
            request, "followup_form.html", _ctx(request, errors=None)
        )

    @app.post("/followups")
    async def followup_create(request: Request):
        form = await request.form()
        try:
            followup = Followup(
                provider_program=form.get("provider_program", ""),
                status=form.get("status") or Status.RESEARCHED,
                last_contact=_parse_date(form.get("last_contact")),
                next_followup=_parse_date(form.get("next_followup")),
                action=form.get("action") or None,
                priority=form.get("priority") or Priority.MEDIUM,
                completed=_parse_bool(form.get("completed")),
                notes=form.get("notes") or None,
            )
        except (ValidationError, ValueError) as exc:
            return TEMPLATES.TemplateResponse(
                request, "followup_form.html", _ctx(request, errors=str(exc)),
                status_code=400,
            )
        service.create_followup(followup)
        return RedirectResponse("/followups", status_code=303)

    return app


# Module-level app for uvicorn. Backend chosen by STARTUPOPS_DATA_BACKEND
# (default = seeded in-memory; "firestore"/"live" = read-only live Firestore).
_repo, _do_seed = build_default_repository()
app = create_app(_repo, do_seed=_do_seed)
