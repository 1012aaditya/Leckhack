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

## The four stages

| Stage | Question | Where | Needs |
|---|---|---|---|
| 0 | *Could* this citation exist at all? | `app/plausibility.py` | nothing |
| 1 | Does this case exist? | `app/sources/` | a database |
| 2 | Does the opinion support the claim? | `app/retrieval.py`, `app/judge.py` | opinion text |
| 3 | Has a later case overruled it? | `app/goodlaw.py` | a citation graph |

Stage 0 is the one with no dependencies at all. Legal citations are not arbitrary
strings: reporters publish over known date ranges, volumes fill in order, pages are
bounded. Those constraints make some citations self-contradicting regardless of what
any database holds.

```
42 F.2d 300 (2015)   F.2d stopped publishing in 1993
58 F.3d 900 (1985)   F.3d did not begin until 1993
12 F.5d 40           no such reporter has ever been published
```

None of those needs a lookup, a model, or a network connection to reject. It matters
for two reasons beyond novelty. It **covers what the corpus cannot** — a partial corpus
must stay silent about reporters it never loaded, but a structural contradiction is
decidable for every one of the 1,342 reporter editions in `reporters-db`. And it is
**explainable**: "F.3d began publishing in 1993" is a reason a lawyer can check in
seconds, unlike a similarity score.

It also closes a blind spot in the parser itself. eyecite discards citations whose
reporter it does not recognise — correct for a parser, a gap for a fabrication
detector, since an AI that invents the reporter as well as the case would otherwise
draw no comment at all. Those are scanned for separately and reported.

## Four rules the code enforces

**No model decides whether a case exists.** Stages 0 and 1 have no model in them at
all — stage 0 is arithmetic over publication dates, stage 1 is a database lookup. Existence is a fact, not a judgement. A test pins the reason: eyecite
accepts the fabricated `999 U.S. 1234` without complaint, because the *format* is valid.
Only the lookup exposes it.

**The auditor may not assert what it cannot show.** Every quote passes `quote_guard`,
which confirms it appears verbatim in the source opinion — folding typographic and
whitespace variants, never dropping words. A finding whose quote fails is downgraded to
`unclear` and the quote discarded. `tests/test_judge.py` runs a deliberately fabricating
judge through the pipeline to prove it gets blocked.

**Absence is only evidence from a complete volume.** Holding one case from F.3d volume
42 says nothing about whether `42 F.3d 988` exists; holding *all* of volume 42 says
everything. The loader cannot infer completeness from an arbitrary slice, so the
operator asserts it with `--complete-volumes`, and without that assertion a miss is
reported as unchecked rather than fabricated. A database outage is likewise never
reported as fabrication.

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
  extract.py      parse    eyecite, offline, no model
  plausibility.py stage 0  structural checks: no database, no model, no network
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
