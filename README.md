# LexHack 2026

Working repository for a LexHack 2026 submission — a virtual student hackathon at the
intersection of AI, law, and civic technology.

**Current stage: building.** Project chosen — the Citation Auditor, which checks whether
the court cases in AI-generated legal text are real. The backend spine runs today without
any API access, using an offline sample of real cases.

```bash
cd backend && pip install -r requirements-dev.txt
python scripts/audit_cli.py "Bush v. Gore, 531 U.S. 98 (2000)."
```

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
- [ ] Stage 2: does the cited case actually support the claim?
- [ ] Stage 3: is the case still good law?
- [ ] Frontend
