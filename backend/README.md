# Citation Auditor — backend

Checks whether the court cases in AI-generated legal text are real.

**Everything here runs without API access.** With no token configured it falls back to an
offline sample of real cases, so the full pipeline works today and switching to the live
database is a one-line config change.

## Run it

```bash
pip install -r requirements-dev.txt
python scripts/audit_cli.py "Bush v. Gore, 531 U.S. 98 (2000). Smith v. Nowhere, 999 U.S. 1234 (2022)."
```

Or as an HTTP service:

```bash
uvicorn app.main:app --reload
curl -X POST localhost:8000/audit -H 'Content-Type: application/json' \
  -d '{"text":"See Bush v. Gore, 531 U.S. 98 (2000)."}'
```

`GET /health` reports which database is in use.

## Tests

```bash
pytest
```

## Turning on the live database

1. Get a CourtListener token (see [`../docs/data-sources.md`](../docs/data-sources.md) —
   EDU membership is free for students).
2. `cp .env.example .env` and fill in `COURTLISTENER_TOKEN`.
3. Run `python scripts/probe_courtlistener.py` **first**. It dumps raw API responses for a
   real, a fake, and a malformed citation. The response parsing in
   `app/sources/courtlistener.py` was written from documentation rather than a live call,
   so confirm it against reality before trusting it.

Nothing else changes — `get_source()` picks the live database as soon as a token is present.

## How it is laid out

| File | Job |
|---|---|
| `app/extract.py` | Stage 0. eyecite pulls citations out of text. Offline, no model. |
| `app/sources/` | Stage 1. Does this case exist? `fixtures.py` offline, `courtlistener.py` live. |
| `app/quote_guard.py` | The self-check. Rejects any quote not found verbatim in the source. |
| `app/audit.py` | Orchestration, and the traffic-light decision. |
| `app/models.py` | Shared data shapes and the report summary. |
| `app/main.py` | HTTP surface. |

## Three rules the code enforces

**No model decides whether a case exists.** Stage 1 is a database lookup and nothing else.
Existence is a fact, not a judgement. `app/extract.py` carries a test pinning the reason:
a fabricated citation is well-formed, so extraction accepts `999 U.S. 1234` happily — only
the lookup exposes it.

**A non-authoritative source may never call a case fake.** The offline sample holds six
cases; a miss means "not in our sample", not "fabricated". `CaseLawSource.is_authoritative`
carries this, and `audit.py` checks it before showing a red light. A database outage is
reported as unchecked, never as fabrication.

**The report never claims more than it checked.** "Checked and fine" and "not checked" are
counted separately, so the headline cannot say all citations passed when some were never
verified.

## Still to build

- Stage 2 — does the case actually support the claim? (retrieval + judged verdict, guarded
  by `quote_guard`)
- Stage 3 — is it still good law? (citation graph from CourtListener bulk CSV)
- Postgres cache so opinion text is local and the demo survives dead wifi
- Frontend
