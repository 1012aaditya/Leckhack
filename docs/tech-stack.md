# Tech Stack — Citation Auditor (Shortlist #1)

Stack for the recommended project: a verification layer that checks AI-generated legal
text citation by citation. See [`idea-shortlist.md`](idea-shortlist.md) for why this
project. §7 at the bottom covers what changes if #2 or #4 is chosen instead.

---

## 1. Shape of the system

```
  Browser                  API                        External
  ───────                  ───                        ────────
  Next.js  ──paste text──▶  FastAPI
                             │
                             ├─▶ eyecite ─────────────── extract + normalize citations
                             │                            (local, no network)
                             │
                             ├─▶ Stage 1: EXISTS? ─────▶ CourtListener
                             │                            /api/rest/v4/citation-lookup/
                             │
                             ├─▶ Stage 2: SUPPORTS? ──▶ pgvector cache ──▶ Claude judge
                             │                            (voyage-law-2 embeddings)
                             │
                             └─▶ Stage 3: STILL GOOD? ─▶ citing opinions ─▶ Claude classify
                                                          │
  ◀── per-citation verdict ──────────────────────────────┘
      green / amber / red + verbatim quote + source link
```

---

## 2. The picks

| Layer | Choice | Why this one |
|---|---|---|
| **Backend** | Python 3.12 + **FastAPI** | Effectively forced: `eyecite` is Python, and it is not worth reimplementing. FastAPI's async model matters because citations are checked concurrently. |
| **Citation extraction** | **eyecite** + `reporters-db` + `courts-db` | Free Law Project's extractor, tested against 50M+ citations, used to annotate CourtListener and CAP. Handles full cites, short form (`531 U.S., at 99`), `supra`, `id.`, `ibid.` — the cases a regex will silently miss. Built on Hyperscan, so it is fast. **Do not hand-roll this.** |
| **Stage 1 — existence** | **CourtListener Citation Lookup API** (`POST /api/rest/v4/citation-lookup/`) | Purpose-built for exactly this. Takes raw text (≤64,000 chars, ~50 pages) or a volume/reporter/page triple, and returns a per-citation status: `200` resolved, `404` valid format but no such case, `300` ambiguous, `400` unrecognized reporter. Free Law Project documents it as *"a guardrail to help prevent hallucinated citations."* Quote that line in the pitch — the authority on US case law data built this endpoint for your exact problem. |
| **Stage 2 — support** | **pgvector** retrieval + **Claude** as judge | Retrieve the opinion, chunk it, embed, pull top-k passages for the claimed proposition, then have Claude return a structured verdict. This is the hard stage and the entire moat. |
| **Embeddings** | **voyage-law-2** | Legal-domain model trained on 1T legal tokens. Leads MTEB legal retrieval; +6% over OpenAI v3-large across eight legal datasets, and 84.44 vs 68.40 NDCG@10 on long-context legal retrieval — which is the regime you are in, since opinions are long. A one-line swap that measurably improves the hard stage. |
| **LLM** | **Claude** — `claude-sonnet-5` for extraction/classification, `claude-opus-5` for the Stage 2 judge | Judge quality is where accuracy is won; everything else is cheap and high-volume. Use tool-use / structured outputs to force schema-valid verdicts. |
| **Database** | **Supabase** (Postgres + pgvector) | One service covers the opinion cache, embeddings, and audit-run history. Free tier is sufficient. Avoids standing up Redis or a separate vector DB for a weekend build. |
| **Frontend** | **Next.js 15** (App Router) + Tailwind + shadcn/ui | Ships a credible-looking report UI fast. Stream verdicts in as they resolve so the demo has visible motion instead of a spinner. |
| **Document input** | **PyMuPDF** | Briefs arrive as PDF. Text extraction only — no OCR needed, unlike shortlist #2. |
| **Eval harness** | pytest + a script writing JSON results | This produces the measured hallucination rate that is the actual differentiator. Build it on day one, not the night before. |
| **Deploy** | Vercel (frontend) + Fly.io or Render (API) + Supabase (DB) | Split deploy because the backend must be Python. |

---

## 3. Three design decisions that matter more than the framework choices

**The auditor must not hallucinate.** An auditing tool that invents its own findings is
worse than no tool, and a judge will probe exactly this. Force every Stage 2 verdict to
carry a **verbatim quote** from the retrieved opinion, then verify in code that the quote
is a literal substring of the source before rendering it. Any verdict failing that check
is discarded, not displayed. This is a deterministic guard around a probabilistic
component, and it is the single most important line of defence in the project.

**Never let a model decide whether a case exists.** Stage 1 is a pure API lookup with no
LLM in the path. Existence is a fact, not a judgment. The model is confined to Stages 2
and 3, where the question is genuinely semantic. Being able to say "the fabrication check
has no model in it at all" is a strong answer to the obvious challenge from the floor.

**Be honest about Stage 3.** There is no open Shepard's or KeyCite. What you can do is
retrieve opinions citing the target, find the passages that discuss it, and classify
treatment. That is a **negative-treatment signal, not a validation service** — label it
that way in the UI. Overclaiming here is the easiest way to lose credibility with a legal
judge, and being visibly careful about it is a point in your favour.

---

## 4. Build order

**Day 1 — the spine.** FastAPI skeleton, eyecite extraction, Stage 1 wired to the
citation-lookup endpoint, results rendering in a plain list. At the end of day 1 you can
already detect fabricated citations. **If the rest fails, this alone is a demo.**

**Day 2 — the moat.** Opinion fetch and cache into Postgres, chunking, voyage-law-2
embeddings, pgvector retrieval, the Claude judge with the verbatim-quote guard. Then the
eval harness: generate N legal answers from a public model, run the auditor, write results
to JSON.

**Day 3 — the pitch.** Stage 3, report UI polish with streaming verdicts, the results
chart, demo script, video. Freeze code by midday and rehearse against the cache.

---

## 5. Risk register

| Risk | Mitigation |
|---|---|
| **Stage 2 is the whole project and also the hardest part** | Scope to one well-covered jurisdiction if it slips. Stages 1 + 3 alone are a lookup script — protect day 2. |
| **Live API dependency during the pitch** | Pre-seed the cache with every case in the demo script, and record a backup video. Never let the demo's success depend on a network call. |
| **Rate limiting** | Far less severe than first assessed — see §6. Still: cache every opinion body on first fetch, and batch citations into single lookup requests (250 per request allowed). |
| **The auditor's own errors** | The verbatim-quote substring check. Show a deliberately caught failure in the demo — it turns a weakness into evidence of rigour. |
| **"Isn't this just a lookup?"** | Lead the demo with the Stage 2 case: a *real* citation used for a proposition the case never held. That is the failure mode Stage 1 cannot catch and the one that gets lawyers sanctioned. |

---

## 6. Correction to the earlier rate-limit note

`idea-shortlist.md` originally flagged CourtListener's **125 requests/day** default
allowance as the top build risk for this project. That figure is real but applies to the
general REST API. The **citation-lookup endpoint has its own throttle: 60 valid citations
per minute**, with up to 250 citations per request and a `429` carrying a `wait_until`
timestamp when exceeded.

That is comfortably above anything a demo requires, so rate limiting drops from the top
risk to a routine engineering concern for this project. The 125/day limit still applies to
fetching full opinion bodies, which is why the Postgres cache stays in the design. The
shortlist has been updated to match.

---

## 7. If a different project is chosen

**#2 Default Judgment Guard** — different problem shape, different stack. Claude's vision
capability for reading the photographed summons (a multimodal model handles skewed phone
photos of stapled court documents better than a traditional OCR pipeline, and extraction is
the only model-dependent step). Rules engine as plain Python over a YAML table of
jurisdiction deadlines — deliberately boring and auditable, because "the deadline is never
guessed by a model" is the pitch. `pypdf` for filling form fields, `ics` for the calendar
invite. Study the Suffolk LIT Lab Document Assembly Line for form handling; interoperate
rather than rebuild.

**#4 Playbook Redliner** — the lightest stack on the list. Python, CUAD loaded from
Hugging Face, Claude for clause extraction against the 41 categories, scikit-learn for
precision/recall, Streamlit or a minimal Next.js front end. No database needed. Nearly all
the effort goes into the eval, which is the point of picking this one.

---

## 8. Sources

- [eyecite — Free Law Project](https://free.law/projects/eyecite/)
- [eyecite on GitHub](https://github.com/freelawproject/eyecite)
- [Citation Lookup and Verification API — CourtListener](https://www.courtlistener.com/help/api/rest/citation-lookup/)
- [API throttles and limits — 60/minute and 250/request (freelawproject/courtlistener discussion #6895)](https://github.com/freelawproject/courtlistener/discussions/6895)
- [CourtListener REST API v4](https://www.courtlistener.com/help/api/rest/)
- [Domain-Specific Embeddings and Retrieval: Legal Edition (voyage-law-2) — Voyage AI](https://blog.voyageai.com/2024/04/15/domain-specific-embeddings-and-retrieval-legal-edition-voyage-law-2/)
- [voyage-law-2 — Pinecone model docs](https://docs.pinecone.io/models/voyage-law-2)
- [CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review](https://arxiv.org/abs/2103.06268)
- [Document Assembly Line — Suffolk LIT Lab](https://assemblyline.suffolklitlab.org/)
