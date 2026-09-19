# LexHack 2026

Working repository for a LexHack 2026 submission — a virtual student hackathon at the
intersection of AI, law, and civic technology.

**Current stage: working software.** All four stages are built and tested. It runs with
no credentials at all — every live component has a deterministic offline twin, so the
demo cannot be broken by a dead venue wifi.

## Run it

**One command.** It creates its own virtualenv, installs what it needs, and prints the URL:

```bash
cd backend
./run.sh
```

Then open **<http://localhost:8000>**.

Add the sample corpus if you want the fabrication checks to have something to work with:

```bash
./run.sh --demo-data
```

Other options: `PORT=9000 ./run.sh` if 8000 is taken.

### With Docker instead

```bash
docker compose up --build
```

Also <http://localhost:8000>.

### By hand

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://localhost:8000
```

Needs Python 3.10+. **No API keys required** — every live component has an offline
fallback, so it runs and demos with nothing configured.

### If it will not start

| What you see | Cause |
|---|---|
| Nothing at localhost:8000 | The server has to be running in a terminal. `./run.sh` and leave it open. |
| `Address already in use` | `PORT=8001 ./run.sh` |
| `Could not import module "app.main"` | Run it from inside `backend/`, not the repo root. |
| `command not found: uvicorn` | The virtualenv is not active. Use `./run.sh`, which handles it. |

**What it does.** Paste in AI-generated legal text. For every case cited it answers four
questions: *could* this citation exist at all, does the case exist, does the opinion
actually support the claim made about it, and has a later case overruled it.

The first of those needs no database, no model and no network. Reporters publish over
known date ranges, so `42 F.2d 300 (2015)` is impossible — F.2d ended in 1993 — and
`12 F.5d 40` names a reporter that has never existed. Those are decidable for all 1,342
reporter editions in `reporters-db`, including ones we hold no case law for. Every quote shown is confirmed to appear verbatim
in the source opinion — findings that fail that check are discarded rather than
displayed.

## Where things are

| Path | Contents |
|---|---|
| [`backend/`](backend/) | The application. Runs offline; see [`backend/README.md`](backend/README.md). |
| [`docs/idea-shortlist.md`](docs/idea-shortlist.md) | Researched, ranked shortlist of candidate projects across all five tracks, with impact evidence, data sources, demo plans, risks, and a recommendation. **Start here.** |
| [`docs/tech-stack.md`](docs/tech-stack.md) | Proposed stack for the recommended project (Citation Auditor), with build order, risk register, and the alternate stacks for the two runner-up ideas. |
| [`docs/features.md`](docs/features.md) | Plain-English description of what the tool does and who it helps. Doubles as Devpost submission copy. |
| [`docs/data-sources.md`](docs/data-sources.md) | How to obtain the case law database — licensing, bulk downloads, free student API access, and a pre-weekend setup checklist. |

## Hackathon brief (reference)

**Tracks**

- Access to Justice & Civic Tech
- AI Safety, Ethics & Governance
- Legal Automation & Workflow Innovation
- Digital Rights & Policy Tech
- Open Innovation (AI x Law)

**Judging criteria:** real-world impact, practical usability, innovation.

**Submission requirements (Devpost)**

- Project name and short summary
- Problem and solution write-up
- Working link or code repository
- Demo video (2–3 minutes) or visual walkthrough with screenshots
- Tech stack list

**Team size:** up to 4 students.

## Next steps

- [ ] Get CourtListener API access (EDU membership is free — see `docs/data-sources.md`)
- [ ] Run `backend/scripts/probe_courtlistener.py` to confirm the live response shape
- [ ] Download a CAP slice and run `backend/scripts/load_cap.py` (pipeline built and tested; only the download is left)
- [ ] Re-run `eval_run.py` on real data — the current numbers are machinery, not a measurement
- [ ] Add `ANTHROPIC_API_KEY` so stage 2 uses the model judge rather than word matching
- [x] ~~Stage 2: does the cited case actually support the claim?~~
- [x] ~~Stage 3: is the case still good law?~~
- [x] ~~Frontend~~
