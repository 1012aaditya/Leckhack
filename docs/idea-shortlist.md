# LexHack 2026 — Ranked Idea Shortlist

**Status:** planning document. No code committed yet — the track and project are undecided pending this review.
**Prepared:** 2026-09-19
**Method:** desk research across the five LexHack tracks, the open legal-data landscape, prior legal-tech hackathon winners, and the legal constraints that limit what a student team can ship. Sources listed at the bottom; every factual claim below is traceable to one.

---

## 1. What the judges actually score

The brief names three criteria: **real-world impact, practical usability, innovation**. It does not publish weights. Read practically, that rewards a narrow tool that visibly works on real data over a broad platform that demos a happy path.

Two things follow, and they shape the entire ranking:

1. **Verifiable beats generative.** A project whose output a judge can check in thirty seconds ("this citation is real, here is the link; this one is fabricated") scores on all three criteria at once. A project that emits fluent prose scores on none of them, because nobody in the room can tell whether it is right.
2. **A named user beats a category.** "Helps people with legal problems" is not an impact story. "Stops a tenant from losing by default on day 21 because nobody told them the clock was running" is.

---

## 2. Landscape: what is already saturated

Judging panels at legal-tech hackathons see the same three submissions repeatedly. Building any of these means competing on polish alone:

| Saturated pattern | Why it loses |
|---|---|
| RAG chatbot over statutes / "ask the law anything" | Indistinguishable from ChatGPT with a custom header. Unverifiable output. Highest legal risk (see §3). |
| Contract summarizer | Thin wrapper. No measurable claim possible in a weekend. |
| "Plain-language translator" for legal documents | Real need, but the demo is a paragraph in, a paragraph out. No moment. |

Recent winners went the other way — narrow, grounded, and measured. Cambridge's Hack_the_Law 2025 winner (JusticeGPS) shipped confidence scoring, source citations, explainability toggles and a self-critique loop, and reported an accuracy figure. Auckland's 2025 winner was a *privacy-first* rights explainer — the constraint was the pitch. The pattern is consistent: **ship a constraint and a number.**

---

## 3. Constraints that must shape any A2J idea

These are not optional caveats; they are design inputs, and stating them on stage is itself a differentiator because most teams will not have noticed them.

**Unauthorized practice of law (UPL).** The line is settled and it is sharp: *legal information* — general explanations of the law — is protected speech. *Legal advice* — applying law to one specific person's facts — is regulated activity. In 2026 this stopped being theoretical: New York SB 7263 would create a private right of action against chatbot proprietors whose bots give substantive responses amounting to UPL, and Nippon Life sued OpenAI in March 2026 after ChatGPT allegedly helped draft filings containing fabricated authority. **Design implication:** the tool should compute, extract, verify, or route — not opine. Deterministic outputs (a deadline, a form field, a citation verdict) sit on the safe side of the line. Free-text advice does not.

**Hallucination is the incumbent's unsolved problem.** Stanford RegLab's preregistered evaluation found the purpose-built legal research tools — Lexis+ AI, Westlaw AI-Assisted Research, Ask Practical Law — hallucinate **17–33% of the time**, despite vendor "hallucination-free" marketing; general-purpose models err on legal queries at rates as high as 82%. This is the single most exploitable gap in the field for a student team, because *detecting* the failure is far cheaper than *avoiding* it.

**The speed/accuracy trade-off is counterintuitive.** Stanford's Justice Innovation work on legal-aid triage found that a tool 90% accurate but taking 20 minutes is *worse* than one 70% accurate taking 5 minutes plus 5 minutes of human review — because a fast human catches the errors. Build for human-in-the-loop throughput, not autonomous correctness, and say so.

**Rate limits are a real hackathon risk.** CourtListener's default API allowance is **5 requests/minute, 50/hour, 125/day**. A live demo that hits it mid-pitch is a loss. Any project depending on it needs bulk data or an aggressive local cache built on day one — plan for this, do not discover it on Saturday night.

---

## 4. Scoring rubric used below

Each idea is scored 1–5 on four axes. **Feasibility** is weighted hardest because an unfinished project scores zero on everything.

- **Impact** — is there a documented, quantified harm this addresses?
- **Demo** — is there a moment where the judge sees something surprising and checkable?
- **Moat** — how hard is this to dismiss as a GPT wrapper?
- **Feasibility** — can 1–4 students finish it in a hackathon weekend?

---

## 5. The shortlist

### Tier 1 — recommended

---

#### **#1 — Citation Auditor: a verification layer for AI legal output**
**Track:** AI Safety, Ethics & Governance (cross-files as Access to Justice)
**Impact 5 · Demo 5 · Moat 5 · Feasibility 4**

**The problem, with a number.** Purpose-built legal AI hallucinates 17–33% of the time; general models up to 82%. Self-represented litigants and overloaded practitioners are already filing documents containing cases that do not exist — that is the substance of the Nippon Life suit. There is no cheap, open tool that checks an AI's legal output before it reaches a court.

**What you build.** Paste in any AI-generated legal text. The system extracts every case citation and every proposition attached to it, then runs a three-stage check against CourtListener / the Caselaw Access Project:
1. **Existence** — does this case exist? (catches outright fabrication)
2. **Support** — does the retrieved opinion actually say what the text claims it says? (catches the harder, more dangerous failure — a real case cited for a proposition it never held)
3. **Status** — has it been overruled or negatively treated? (catches stale law)

Output is a per-citation verdict — green / amber / red — each linked to the source so a judge can click through and confirm in one second.

**The demo moment.** Paste a plausible-looking ChatGPT answer on stage. Three citations go green, one goes red with "no case by this name in any of 2,000+ courts," one goes amber with "real case, but held the opposite." Then show the click-through. This is unforgettable and entirely checkable.

**The measurable claim.** Generate N legal answers from a public model, run your auditor over them, and report *your own* hallucination rate. You arrive with an empirical finding, not a product pitch — which is exactly what distinguished the winning submissions cited above.

**Data:** CourtListener REST API v4 (9M+ decisions, 2,000+ courts) plus CAP bulk data (official state/federal case law through 2020). **Mitigate the 125/day rate limit with a pre-seeded local cache — this is the top build risk.**

**Risks.** Stage 2 (support) is the hard part and the whole moat; stages 1 and 3 alone are a lookup script. Scope stage 2 to a single well-covered jurisdiction if time runs short. Say clearly that this is a *verification* tool, not advice — it sits cleanly outside UPL.

---

#### **#2 — Default Judgment Guard: the clock nobody tells you about**
**Track:** Access to Justice & Civic Tech
**Impact 5 · Demo 4 · Moat 4 · Feasibility 4**

**The problem, with a number.** Self-representation in state civil courts exceeds 90% on many dockets; as many as two-thirds of litigants in eviction, debt-collection, foreclosure and custody matters appear without a lawyer. Pro se defendants obtain judgment in their favour roughly **12%** of the time; pro se plaintiffs, **3%**. A large share of those losses are not losses on the merits at all — they are *defaults*, entered because nobody answered in time or appeared. 74% of low-income households hit a civil legal problem in a year and 92% of those problems get inadequate help or none.

**What you build.** Photograph a summons or complaint. The system extracts court, case number, case type, and date of service — the LLM does *only* extraction, which is a task it is reliable at — then a **deterministic rules engine** computes the actual answer deadline for that jurisdiction and case type. It returns: a countdown, a calendar invite, a plain-language "here is what happens if you do nothing," and a pre-filled answer form ready to file.

**Why the architecture is the pitch.** The deadline is never guessed by a model. It is computed from codified rules and is auditable. That is a direct, credible answer to the hallucination problem, and it keeps the tool on the *information* side of the UPL line.

**The demo moment.** A real (redacted) summons photographed live → "You have 14 days. 9 remain. If you do nothing, the landlord wins automatically." → a filled form appears.

**Data:** jurisdiction answer-deadline rules (hand-encoded for 1–2 jurisdictions — do not attempt national coverage); court form templates. The Suffolk LIT Lab Document Assembly Line and docassemble (MIT-licensed, court-form interviews, e-filing integration) are the reference implementations to learn from and interoperate with — **not to rebuild**.

**Risks.** OCR on a phone photo of a stapled, skewed court document is genuinely hard; budget for it and have a clean fallback path. Scope to one jurisdiction and one case type (eviction *or* debt collection). The obvious critique is "this is just a date calculator" — pre-empt it by leading with the 12% statistic.

---

### Tier 2 — strong, with a caveat

---

#### **#3 — Unenforceable Clause Detector**
**Track:** Legal Automation & Workflow (cross-files as A2J)
**Impact 4 · Demo 4 · Moat 4 · Feasibility 3**

Upload a residential lease; the tool flags clauses that are **void or unenforceable under that state's law** — waiver of habitability, illegal late fees, self-help eviction, confession of judgment — with the statutory citation for each. The leap over the saturated "summarize my lease" idea is the shift from *description* to *verdict*: not "this clause says X" but "this clause is unenforceable under [statute]; a court will not enforce it against you."

Scope hard to one or two states. Requires hand-encoding a rules table, which is real research time — that is the feasibility hit, and it is also the moat, since no GPT wrapper will have it.

---

#### **#4 — Playbook Redliner with a measured score**
**Track:** Legal Automation & Workflow
**Impact 3 · Demo 3 · Moat 3 · Feasibility 5**

Clause-level extraction against a configurable risk playbook, producing redlines with rationale. Commercially crowded, and on its own it is a wrapper. **The one thing that redeems it:** CUAD (510 contracts, 13,000+ expert annotations across 41 clause categories) lets you report real precision/recall on an expert-annotated benchmark. Almost no hackathon team arrives with measured numbers. Highest feasibility on the list — the safe pick if the team is small or time-boxed.

---

#### **#5 — GPC Honour Check: does the opt-out actually work?**
**Track:** Digital Rights & Policy Tech
**Impact 4 · Demo 5 · Moat 4 · Feasibility 2**

Send a Global Privacy Control signal / opt-out to a site, then *empirically verify* whether tracker behaviour changed — before-and-after network evidence that a legally mandated opt-out was ignored. Compliance theatre caught on camera; the demo is excellent and the finding is genuinely novel.

**Feasibility is the problem.** Headless-browser instrumentation, tracker classification and a defensible methodology are a lot for one weekend, and a null result leaves you with no demo. Pick this only with a strong web-infrastructure person on the team.

---

### Tier 3 — considered and set aside, with reasons

| Idea | Track | Why not |
|---|---|---|
| **Benefits denial appeal builder** (SNAP/Medicaid notice → fair hearing request with the right citation, inside the 90-day window) | A2J | Genuinely valuable and structurally similar to #2, but weaker: denial notices are less standardised than summonses, and national reversal-rate data is not readily published, so the impact claim is harder to evidence. **A good fallback if #2's OCR proves intractable.** |
| **Article 50 / C2PA disclosure checker** | AI Governance | Very timely — Article 50 transparency duties took effect 2 August 2026, and the Commission published its Code of Practice and standard icons in June 2026. But high-risk obligations slipped to December 2027, the legal reasoning content is thin, and judges may read it as a metadata linter. |
| **Legal-domain bias probe harness** | AI Safety | garak, Promptfoo, PyRIT and DeepTeam already occupy this ground with 37–50+ probe modules and standards mappings. Hard to beat in a weekend; risks being "we wrote a config file." |
| **Data-broker delete orchestrator** | Digital Rights | California's DROP platform *is* this, it is live, and brokers must process through it from 1 August 2026. Building on top is redundant. |
| **Privacy policy diff watcher** | Digital Rights | Open Terms Archive already maintains versioned policies; ToS;DR covers the interpretation layer. Little room left. |
| **Court-form guided interview generator** | A2J | Suffolk LIT Lab's Weaver converts a PDF court form into a working interview in about an hour, MIT-licensed. Rebuilding it is a straight loss. |

---

## 6. Recommendation

**Build #1, the Citation Auditor.** It is the only idea here that attacks a documented, quantified failure of the *incumbent commercial products* rather than adding another generator to a crowded field. It produces output a judge can verify live, it lets you arrive with an original empirical measurement, it sits unambiguously outside the UPL line, and it reads equally well as AI-safety infrastructure and as consumer protection for pro se litigants.

**If the team skews product/design rather than ML, build #2 instead.** Its impact narrative is the strongest on the list — the gap between "lost on the merits" and "lost because nobody said the clock was running" is vivid, human, and backed by hard numbers.

**If the team is one or two people, build #4** and win on measured rigour rather than ambition.

Do not attempt two tracks. The brief permits cross-track projects and both recommendations naturally cross-file, but the build should target one.

---

## 7. Open questions before committing

These change the recommendation and I cannot resolve them from the brief:

1. **Jurisdiction.** Everything above assumes US law, because that is where the open data is (CourtListener, CAP, Eviction Lab, LSC). If the team is outside the US, #2 and #3 need entirely different rule sources and the recommendation shifts toward #1 or #4, which are jurisdiction-portable.
2. **Team size and composition.** ML-heavy, product-heavy, or solo — this decides between #1, #2 and #4.
3. **Hackathon dates and build window.** The brief mentions a Devpost deadline but no dates, and the Devpost page is unreachable from this environment. A short window argues for #4.
4. **Sponsor tooling.** Adaption Labs credits are offered to all participants; unknown whether any track or prize requires using specific sponsor tools.

---

## 8. Sources

- [LSC — The Justice Gap: Measuring the Unmet Civil Legal Needs of Low-income Americans](https://www.lsc.gov/about-lsc/what-legal-aid/unmet-need-legal-aid/justice-gap-measuring-unmet-civil-legal-needs-low)
- [The Justice Gap Report — Executive Summary](https://justicegap.lsc.gov/resource/executive-summary/)
- [Pro Se Litigation Statistics 2026](https://thelawlion.com/blog/pro-se-litigation-statistics)
- [Reintroducing the Civil Justice Gap — American Academy of Arts & Sciences](https://www.amacad.org/publication/achieving-civil-justice/section/3)
- [Magesh et al., Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools — Stanford RegLab](https://reglab.stanford.edu/publications/hallucination-free-assessing-the-reliability-of-leading-ai-legal-research-tools/)
- [Legal GenAI tools mislead 17% of time: Stanford study — Legal Dive](https://www.legaldive.com/news/legal-genai-tools-mislead-17-percent-of-time-stanford-HAI-hallucinations-incorrect-law-citations/717128/)
- [CourtListener REST API v4 documentation](https://www.courtlistener.com/help/api/rest/)
- [Full CourtListener Data Access via API Now Included with Membership — Free Law Project](https://free.law/2026/05/07/api-included-in-memberships/)
- [CourtListener and Caselaw Access Project — Library of Congress research guide](https://guides.loc.gov/free-case-law/courtlistener-and-caselaw-access-project)
- [New York Bill Would Create Liability for Chatbot Proprietors Offering Professional Advice — Holland & Knight](https://www.hklaw.com/en/insights/publications/2026/03/new-york-bill-would-create-liability-for-chatbot-proprietors)
- [Access to Justice, AI, and the Unauthorized Practice of Law — Pro Bono Institute](https://www.probonoinst.org/2026/07/28/access-to-justice-ai-and-the-unauthorized-practice-of-law/)
- [Modernizing Unauthorized Practice of Law Regulations — NCSC white paper](https://www.ncsc.org/sites/default/files/media/document/AI_UPL_WhitePaper.pdf)
- [Legal Aid Intake & Screening AI — Stanford Justice Innovation](https://justiceinnovation.law.stanford.edu/legal-aid-intake-screening-ai/)
- [AI for Legal Help 2026 Class Report — Stanford Justice Innovation](https://justiceinnovation.law.stanford.edu/ai-for-legal-help-2026-class-report-scoping-building-and-testing-new-legal-aid-tech-systems/)
- [CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review](https://arxiv.org/abs/2103.06268)
- [Document Assembly Line — Suffolk LIT Lab](https://assemblyline.suffolklitlab.org/)
- [docassemble](https://docassemble.org/)
- [Eviction Lab — Map & Data](https://evictionlab.org/map/)
- [LSC Civil Court Data Initiative](https://civilcourtdata.lsc.gov/)
- [Hack_the_Law Cambridge — Hackathon 2025](https://hackthelaw-cambridge.com/hackathon-2025/)
- [Legal tech hackathon challenges students to rethink access to justice — University of Auckland](https://www.auckland.ac.nz/en/news/2025/08/20/legal-tech-hackathon-challenges-students-to-rethink-access-to-justice.html)
- [EU AI Act Implementation Timeline](https://artificialintelligenceact.eu/implementation-timeline/)
- [EU AI Act and C2PA: What Article 50 Requires for AI Content](https://c2paviewer.com/articles/eu-ai-act-content-credentials)
- [EU AI Act High-Risk Deadline Pushed to December 2027 — Cloud Security Alliance](https://labs.cloudsecurityalliance.org/research/csa-research-note-eu-ai-act-omnibus-vii-deadline-delay-20260/)
- [Delete Request and Opt-Out Platform (DROP) — CPPA](https://www.cppa.ca.gov/data_brokers/)
- [California DELETE Act: What Data Brokers Must Do by August 1 — TrustArc](https://trustarc.com/resource/california-delete-act-drop-platform-data-brokers/)
- [LLM Red Teaming Guide 2026: Tools, Attacks & Methodology](https://appsecsanta.com/ai-security-tools/llm-red-teaming)
- [DeepTeam — red teaming framework for LLMs and AI agents](https://github.com/confident-ai/deepteam)
- [Open Terms Archive — Datasets](https://opentermsarchive.org/en/datasets/)
