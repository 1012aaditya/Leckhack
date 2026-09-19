# LexHack 2026

Working repository for a LexHack 2026 submission — a virtual student hackathon at the
intersection of AI, law, and civic technology.

**Current stage: working software.** All three stages are built and tested. It runs with
no credentials at all — every live component has a deterministic offline twin, so the
demo cannot be broken by a dead venue wifi.

```bash
cd backend && pip install -r requirements-dev.txt
uvicorn app.main:app --reload     # whole product, UI included, on one port
```

Then open <http://localhost:8000>. Or from the terminal:

```bash
python scripts/audit_cli.py "A tenant may waive habitability, Alvarez v. Northgate, 42 F.3d 100 (1994)."
python scripts/eval_run.py        # measured precision/recall
pytest                            # 60 tests
```

**What it does.** Paste in AI-generated legal text. For every case cited it answers three
questions: does this case exist, does the opinion actually support the claim made about
it, and has a later case overruled it. Every quote shown is confirmed to appear verbatim
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
- [ ] Load real Caselaw Access Project data, replacing the synthetic demo corpus
- [ ] Re-run `eval_run.py` on real data — the current numbers are machinery, not a measurement
- [ ] Add `ANTHROPIC_API_KEY` so stage 2 uses the model judge rather than word matching
- [x] ~~Stage 2: does the cited case actually support the claim?~~
- [x] ~~Stage 3: is the case still good law?~~
- [x] ~~Frontend~~
