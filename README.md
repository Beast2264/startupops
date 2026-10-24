# StartupOps

A small, boring, **local-first** web app for tracking startup/vendor benefit
programs — cloud credits, AI/GPU grants, dev-tool programs, deadlines, and
what you've actually applied to vs. just researched. Built for self-funded
founders who want something they can run on their own machine in five
minutes, read top to bottom in an afternoon, and bend into whatever shape
their own tracking needs take.

No account, no sign-up, no mandatory cloud bill, no vendor lock-in. Runs
entirely on your own computer by default.

## Who this is for

If you're bootstrapping and juggling a half-dozen startup-credit programs
across different providers — what you've applied to, what's pending, what
got approved, what's expiring — and a spreadsheet is starting to creak, this
might save you some time. It's deliberately small: one Python process,
server-rendered HTML, no build step, no framework you need a course to
learn.

## What it does

Five screens:

1. **Dashboard** — programs tracked (catalog), applications submitted,
   pipeline counts (ready / submitted / under review / approved / rejected),
   total advertised *verified* value, total actual awards, follow-ups due,
   upcoming application deadlines (30 days), and credits expiring within
   30/60/90 days.
2. **Programs** — the **catalog** of programs you've identified (provider,
   tier, priority, benefit, URLs, advertised max, eligibility, deadline). A
   program may exist with no application. Create / view / edit / filter.
3. **Applications** — **actual submissions** you've made. Each references a
   catalog program and carries submission facts (status, reference no.,
   confirmation, dates, and — only after approval — an actual award).
4. **Credits** — actual awards with computed **remaining = actual award −
   amount used**, percentage remaining, and expiration countdown.
5. **Follow-ups** — next-contact tracking with days-until and overdue flags.

It ships with **fictional sample data** (`app/seed.py`, clearly labeled as
such) so every screen has something to look at the first time you run it.

### Catalog vs. submission

`programs` (catalog) and `applications` (submissions) are **separate
collections**. A program you've researched is not a submission — the model
keeps those honest and distinct, including a rule that an actual award can
only be recorded once an application is approved (an advertised maximum is
marketing, not money in hand).

## Quick start

Needs Python 3.12+.

```bash
python -m venv .venv

# Windows
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pytest       # 50 passed, 5 skipped (optional Firestore tests)
.\.venv\Scripts\python run.py

# macOS/Linux
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pytest
./.venv/bin/python run.py
```

Open **http://127.0.0.1:8000**. That's the whole setup — no account, no
cloud, nothing to configure.

## Before you expose this beyond your own machine

`run.py` binds to `127.0.0.1` (loopback) only — reachable from your machine
alone. **This app has no authentication of any kind.** If you ever deploy it
somewhere other machines or the public internet can reach (a VPS, a cloud
VM, Cloud Run, etc.), add your own access control first — a reverse proxy
with auth, a VPN, or a platform-level layer like Cloud Run + IAP. The
included `Dockerfile` is a starting point for containerizing it; it does not
add authentication on its own.

## Stack

- **Python + FastAPI** (server-rendered **Jinja2** HTML, minimal JS)
- **Pydantic** models for validation
- **In-memory repository** by default — nothing persisted between restarts,
  nothing installed or configured, nothing talking to any external service.
- An **optional** Firestore-backed repository behind the same interface, if
  you want cloud persistence later (see below). Entirely opt-in.

No React, Next.js, Kubernetes, Redis, Celery, or Kafka.

## Project layout

```
app/
  enums.py          status/tier/priority/benefit enums
  models.py         Program / Application / CreditAward / Followup + validation
  calculations.py   pure date/amount helpers (deterministic, testable)
  repository.py     Repository interface + InMemoryRepository (default backend)
  firestore_repo.py optional FirestoreRepository (same interface; your own GCP project)
  services.py       aggregation, enrichment, filtering
  seed.py           FICTIONAL sample data demonstrating every screen
  main.py           FastAPI app + routes
  templates/        Jinja2 templates
  static/style.css
tests/              pytest suite (incl. Firestore-emulator tests, auto-skipped
                     unless FIRESTORE_EMULATOR_HOST is set)
run.py              loopback dev launcher (127.0.0.1 only)
requirements.txt
.env.example        documents every environment variable the app reads
```

## Making it yours

- **Replace the sample data**: `app/seed.py` is one plain-Python file with
  clear comments — swap in your own programs/applications, or delete the
  seed call to start empty.
- **Rename the brand**: search for `StartupOps` in `app/templates/base.html`
  and this README.
- **Change the data model**: `app/models.py` has four plain Pydantic classes.
  Add a field there and to the matching form template in `app/templates/`
  and it flows through automatically.
- **Add a screen**: `app/main.py` has one FastAPI route group per screen —
  copy the Programs or Applications pattern.
- **Pick your persistence**: default in-memory is great for trying things
  out; for something that survives a restart, either drop in a simple
  file/SQLite-backed store behind the `Repository` interface, or use the
  optional Firestore backend below.

## Optional: Firestore persistence

A second `Repository` implementation, `FirestoreRepository`, lives behind
the exact same interface as the default in-memory one. It requires **your
own** Google Cloud project — there is no built-in project, no bundled
credentials, and no way for this app to reach anyone else's data.

```bash
export STARTUPOPS_DATA_BACKEND=firestore
export STARTUPOPS_FIRESTORE_PROJECT=your-own-gcp-project-id
# optional, defaults to "(default)":
# export STARTUPOPS_FIRESTORE_DATABASE="(default)"
```

Requires Application Default Credentials for your project (`gcloud auth
application-default login`) and the Firestore API enabled on it. To try this
without touching any real cloud project, run the Firestore *emulator* and set
`FIRESTORE_EMULATOR_HOST` instead — see `tests/test_firestore_emulator.py`
for the exact commands; those tests auto-skip when no emulator is running.
Full variable reference in `.env.example`.

## Data-integrity rules worth knowing

- **Advertised maximum ≠ actual award.** An `actual_award` may only be
  recorded once an application reaches `APPROVED` or `PARTIALLY_APPROVED`.
- **Remaining credit** is derived only from a real award, never a marketing
  maximum.
- A numeric `advertised_maximum` may only be stored when `value_disclosure`
  is `VERIFIED` or `CONDITIONAL` — the model structurally refuses an
  invented/unverified figure.
- The app refuses to store obvious secrets (passwords, API keys, tokens) in
  free-text fields. Store links to documents, never credentials.

## Not yet implemented (deliberately)

- Authentication (add your own before exposing this beyond your own machine)
- Scheduled reminder checks
- Email notifications

No automated vendor submission, no provider emails, no Gmail/Calendar/Drive
access, no external API calls.

## License

License to be finalized by the maintainers before this repository goes
public — check back here, or the repository's `LICENSE` file, for the final
terms.

## Contributing

Issues and pull requests are welcome once this repository is public. Keep
changes small and in the spirit of the project: boring, readable, and easy
for a solo founder to understand end to end.
