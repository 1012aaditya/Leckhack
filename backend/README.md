# Citation Auditor — backend

Checks whether the court cases in AI-generated legal text are real, whether they say
what was claimed, and whether they are still good law.

**It runs with no credentials.** Every live component has a deterministic offline twin,
so the full three-stage pipeline works today and the demo cannot be broken by a dead
venue wifi. Adding an API key upgrades a stage in place; it never switches the app on.

## Run it

```bash
pip install -r requirements-dev.txt
uvicorn app.main:app --reload      # whole product, UI included, on one port
```

Open <http://localhost:8000>, or use the command line:

```bash
python scripts/audit_cli.py "A tenant may waive habitability, Alvarez v. Northgate, 42 F.3d 100 (1994)."
```

Measure it:

```bash
python scripts/eval_run.py         # precision/recall against labelled cases
pytest                             # 84 tests
```

## The three stages

| Stage | Question | Where |
|---|---|---|
| 1 | Does this case exist? | `app/sources/` |
| 2 | Does the opinion actually support the claim? | `app/retrieval.py`, `app/judge.py` |
| 3 | Has a later case overruled it? | `app/goodlaw.py` |

Stage 1 alone is a working product — it catches outright fabrication. Stages 2 and 3
are additive, and the report says plainly when they could not run.

## Four rules the code enforces

**No model decides whether a case exists.** Stage 1 is a database lookup with nothing
else in the path. Existence is a fact, not a judgement. A test pins the reason: eyecite
accepts the fabricated `999 U.S. 1234` without complaint, because the *format* is valid.
Only the lookup exposes it.

**The auditor may not assert what it cannot show.** Every quote passes `quote_guard`,
which confirms it appears verbatim in the source opinion — folding typographic and
whitespace variants, never dropping words. A finding whose quote fails is downgraded to
`unclear` and the quote discarded. `tests/test_judge.py` runs a deliberately fabricating
judge through the pipeline to prove it gets blocked.

**A non-authoritative source may never call a case fake.** The offline corpus missing a
citation means "not in our sample", not "fabricated". `CaseLawSource.is_authoritative`
carries this and the pipeline checks it before showing a red light. A database outage is
reported as unchecked, never as fabrication.

**The report never claims more than it checked.** "Checked and fine" and "not checked"
are counted separately, synthetic demo text is labelled as synthetic wherever it appears,
and the offline fallback says it is weaker than the real check.

## Loading real case law

The synthetic demo corpus is a placeholder. To run on genuine Caselaw Access Project
data (CC0, unrestricted since March 2024):

```bash
python scripts/load_cap.py --inspect path/to/cap.jsonl     # check the shape FIRST
python scripts/load_cap.py path/to/cap.jsonl --index       # import + build the index
python scripts/load_citation_graph.py opinions-cited.csv.gz  # stage 3
```

Handles CAP's classic `casebody.data.opinions`, the 2024 static.case.law
`casebody.opinions`, and flattened single-`text`-column exports, from `.json`, `.jsonl`,
`.gz`, `.zip`, `.tar.gz` or a directory tree. Records it cannot read are skipped rather
than failing the import.

Once real data is present it replaces the demo corpus automatically and becomes the
primary source, with CourtListener chained after it for anything outside the slice.

**Coverage decides what may be called fabricated.** The loader records which reporter
volumes it holds completely. A missing citation inside a covered volume is reported as
fabricated; one outside coverage is reported as unchecked. A partial corpus cannot prove
a case does not exist, and the tool does not pretend otherwise.

## Turning on the live components

| Key | Upgrades | Get it |
|---|---|---|
| `COURTLISTENER_TOKEN` | Stage 1 → real database of 9M+ decisions | Free EDU membership, see [`../docs/data-sources.md`](../docs/data-sources.md) |
| `ANTHROPIC_API_KEY` | Stage 2 → `claude-opus-5` instead of word matching | console.anthropic.com |
| `VOYAGE_API_KEY` | Retrieval → `voyage-law-2` legal embeddings | voyageai.com |

Run `python scripts/probe_courtlistener.py` **first** once you have a CourtListener
token. It dumps raw responses for a real, a fabricated and a malformed citation. The
response parsing in `app/sources/courtlistener.py` was written from documentation, not
from a live call — confirm it against reality before trusting it.

## Layout

```
app/
  extract.py      stage 0  eyecite, offline, no model
  ingest/         loaders  real CAP data and the CourtListener citation graph
  sources/        stage 1  existence: local.py corpus, courtlistener.py live,
                           fixtures.py demo, chain.py ordering
  retrieval.py    stage 2  chunking and passage search
  embeddings.py   stage 2  voyage-law-2, or deterministic local hashing
  judge.py        stage 2  claude-opus-5, or a lexical fallback; plus the guard
  goodlaw.py      stage 3  citation-graph treatment scan
  quote_guard.py           verbatim verification — the self-check
  audit.py                 pipeline and verdict composition
  store.py                 SQLite: opinions, chunks, vectors, citation graph
  main.py                  API + serves the frontend
static/                    zero-build single-page frontend
fixtures/                  offline corpus and the labelled eval set
scripts/                   CLI, eval harness, API probe
```

## Known limits

- **The lexical fallback is weak.** It cannot separate "the lease contained a clause
  purporting to waive X" from "X may be waived". It is deliberately conservative — it
  returns `unclear` rather than guessing — but stage 2 only gets good with a model judge.
- **Stage 3 is a signal, not a citator.** There is no open Shepard's or KeyCite. This
  scans later opinions for overruling language and says so in the UI.
- **The eval numbers are not yet a measurement.** Against the offline corpus,
  "fabricated" only means "absent from a small fixture file", and the eval text was
  written alongside the corpus it is scored on. The harness prints this warning itself.
- **PDF support is text extraction only.** Scanned pages need OCR, which this does not do.
- **The CourtListener response shape is unverified** — see the probe script above.
