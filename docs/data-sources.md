# Where the Case Law Data Actually Comes From

The Citation Auditor is only as good as the database behind it. This document answers
the practical question: **how do we get millions of real court decisions onto our laptop,
legally and for free, before the hackathon starts?**

Short answer: it is genuinely free and genuinely open, and most of it does not need an API
at all.

---

## The three layers

Use all three. They cover different weaknesses.

| Layer | Source | What it gives us | Needs internet at demo time? |
|---|---|---|---|
| **1. The offline bulk copy** | Caselaw Access Project (CAP) | 6.4M cases, full opinion text, loaded into our own database | **No** |
| **2. The live checker** | CourtListener citation-lookup API | Instant verdict on whether a citation resolves, including recent cases | Yes |
| **3. The citation graph** | CourtListener bulk CSV (`search_opinionscited`) | Which cases cite which — powers the "still good law?" check | **No** |

---

## Layer 1 — Caselaw Access Project (the foundation)

**What it is.** Harvard Law School Library digitised its entire shelf of US case law —
roughly **40 million pages, 6.4 million cases** — covering state, federal and territorial
courts.

**The licensing, which is the important bit.** CAP is released under **CC0**. The original
access limitations **expired in March 2024**, and the data is now fully open with no
restriction on access or use. CC0 means we are not even legally required to credit anyone.

*We should credit them anyway.* It costs one line in the README and judges notice teams
that engage properly with the open-data ecosystem rather than just consuming it.

**How to actually get it.** Two routes:

1. **Hugging Face** — `free-law/Caselaw_Access_Project`. Easiest by a wide margin: a few
   lines of Python and it streams. **Use this one.** Note there is also a `TeraflopAI`
   mirror that requires sharing contact details — prefer the `free-law` one.
2. **case.law/download** — direct bulk files from Harvard.

**Worth 20 minutes of investigation:** there is a companion dataset,
`free-law/Caselaw_Access_Project_FAISS_index` — a pre-built vector index over the corpus.
If its embedding model suits us, it could remove a chunk of day-2 work. Check what model it
was built with before relying on it; if it does not match, build our own index over a
smaller slice.

**The one real limitation — state this honestly in the demo.** CAP covers official,
book-published case law **through 2020**. Anything decided after that is not in CAP. That
is precisely what Layer 2 is for.

**Do not download all 6.4 million cases.** You do not have the time, disk, or need. Pick a
slice: Supreme Court plus one or two state jurisdictions is plenty for a convincing demo,
and it will load in minutes rather than hours.

---

## Layer 2 — CourtListener API (live checks and recent cases)

**Free account gets you in.** Full API access is available to everyone with a CourtListener
account; members get elevated limits.

**The unlock for us: EDU membership is free.** Free Law Project offers **complimentary
memberships with generous API access to anyone with an active `.edu` email address**, or
with a recently published paper. No contact form, no waiting for approval. This is a
student hackathon — we are exactly the intended audience.

> **Action item, do this first.** Register a CourtListener account and apply for EDU
> membership *before* the build weekend, not during it. If your student email is not a
> `.edu` (many universities outside the US use `.ac.uk`, `.edu.in`, `.ac.in` and similar),
> **email Free Law Project and ask.** They are a nonprofit whose entire mission is open
> access to law, and a student access-to-justice project is squarely what they exist to
> support. Worst case they say no and we lean harder on Layers 1 and 3.

**Rate limits**, for reference:
- General REST API: 5 requests/minute, 50/hour, 125/day at the default tier
- Citation-lookup endpoint: **60 valid citations/minute**, up to 250 citations per request,
  returning a `429` with a `wait_until` timestamp when exceeded

---

## Layer 3 — CourtListener bulk data (the citation graph)

Free CSV dumps generated straight from CourtListener's PostgreSQL tables, importable with
`COPY FROM`. No API, no rate limit, no key.

The table we care about is **`search_opinionscited`**, with columns
`(id, depth, cited_opinion_id, citing_opinion_id)`. That is the citation graph: which
opinion cites which, and how many times.

This is what makes the "is it still good law?" check possible offline. We find every case
citing our target, pull those passages, and look for negative treatment. Without this table
that feature is not buildable in a weekend.

Also available: courts, dockets, opinion clusters, and opinions.

---

## Why this design removes our biggest risk

The original worry was a live demo dying on a rate limit mid-pitch. With this setup that
cannot happen:

- Everything needed for the demo is **already sitting in our own Postgres** before we walk
  in — full opinion text from CAP, citation graph from the bulk CSV.
- The live API becomes a *bonus* (catching post-2020 cases), not a dependency.
- If the venue wifi fails entirely, **the demo still runs.**

Pre-seed the cache with every case in the demo script, and record a backup video anyway.

---

## Setup checklist (do before the weekend)

- [ ] Create a CourtListener account, generate an API token
- [ ] Apply for EDU membership — or email FLP if your student email is not `.edu`
- [ ] Pull a CAP slice from Hugging Face; load into Postgres
- [ ] Download `search_opinionscited` bulk CSV; `COPY FROM` into the same database
- [ ] Check whether the prebuilt FAISS index is usable before building your own
- [ ] Test the citation-lookup endpoint with a known-real and a known-fake citation
- [ ] Credit CAP, Free Law Project and eyecite in the README

---

## Sources

- [Caselaw Access Project](https://case.law/)
- [About the Caselaw Access Project — coverage and CC0 licensing](https://case.law/about/)
- [Transitions for the Caselaw Access Project — Harvard Library Innovation Lab (March 2024 restriction expiry)](https://lil.law.harvard.edu/blog/2024/03/26/transitions-for-the-caselaw-access-project)
- [`free-law/Caselaw_Access_Project` on Hugging Face](https://huggingface.co/datasets/free-law/Caselaw_Access_Project)
- [`free-law/Caselaw_Access_Project_FAISS_index` on Hugging Face](https://huggingface.co/datasets/free-law/Caselaw_Access_Project_FAISS_index)
- [Full CourtListener Data Access via API Now Included with Membership — Free Law Project](https://free.law/2026/05/07/api-included-in-memberships/)
- [Free Law Project Membership (including EDU memberships)](https://free.law/membership/)
- [Membership-Based API Usage Restrictions](https://free.law/membership/allowed-api-usage/)
- [Bulk Legal Data — CourtListener](https://www.courtlistener.com/help/api/bulk-data/)
- [Citation Lookup and Verification API — CourtListener](https://www.courtlistener.com/help/api/rest/citation-lookup/)
- [API throttles and limits — 60/minute and 250/request](https://github.com/freelawproject/courtlistener/discussions/6895)
- [CourtListener and Caselaw Access Project — Library of Congress research guide](https://guides.loc.gov/free-case-law/courtlistener-and-caselaw-access-project)
