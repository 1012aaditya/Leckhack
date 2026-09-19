# What Our Project Does — In Plain English

Feature list for the Citation Auditor. Written in simple language so it can be reused
directly in the Devpost submission and the demo script.

---

## The problem in one paragraph

AI chatbots invent court cases. They produce a case name, a volume number, a year — all of
it looking completely real — for a case that has never existed. This is not rare. Studies
of the expensive, professional legal AI tools found they get it wrong **17 to 33 percent of
the time**. Regular chatbots are wrong far more often on legal questions. People have
already filed these fake cases in real courts and been punished for it.

Right now there is no quick, free way to check.

## What we built in one sentence

**A spell-checker for legal citations.** Paste in anything an AI wrote about the law, and
we tell you which cases are real, which are fake, and which are being described wrongly.

---

## The main features

### 1. Paste it in, get a report

You paste the AI's answer into a box. Or upload a PDF. That is the whole setup. No
account, no configuration.

### 2. "Is this case even real?"

We pull out every case mentioned and look each one up in a database of over 9 million
real court decisions from more than 2,000 courts.

If the case does not exist, it goes **red**. This catches the AI making things up
completely.

Important detail: **no AI is involved in this check.** It is a straight database lookup.
A case either exists or it does not — that is a fact, not an opinion, so we do not let a
chatbot decide it.

### 3. "Okay, the case is real — but does it actually say that?"

This is the sneaky problem, and the one we care most about.

An AI will often cite a **real** case for something that case never said. That is much
harder to spot than a fake name, because when you look it up, the case is right there and
looks fine. People get caught out by this.

So we go and read the actual court opinion, find the parts that relate to what the AI
claimed, and check whether the case genuinely supports it. If it does not, it goes
**amber**.

### 4. "Is this case still good law?"

Sometimes a case is real, and did say that, but a later court overruled it. Relying on it
today would be a mistake.

We find later cases that mention it and flag anything that looks like the case was
criticised or overturned.

We are honest about this one: it is a **warning signal, not a guarantee**. The professional
tools that do this properly cost thousands of pounds a year. We say so clearly in the app
rather than pretending otherwise.

### 5. Every answer comes with proof

We never just say "this is wrong." Every single verdict shows you:

- the **exact words** from the real court opinion, and
- a **link** to the real document

So you never have to trust us. You click, and you check for yourself in about two seconds.

### 6. We check our own homework

Here is the obvious catch: what if our tool makes things up too? An AI checker that
hallucinates is worse than nothing.

So we built a rule into the system: before we show you any quote, the software confirms
that quote appears **word for word** in the real document. If it does not match exactly,
we throw it away and do not show it. The checker is not allowed to invent its evidence.

### 7. Traffic lights

Every citation gets a simple colour:

- 🟢 **Green** — real case, says what was claimed, still good law
- 🟡 **Amber** — real case, but something is off
- 🔴 **Red** — this case does not exist

Plus a plain-English sentence explaining each one. No legal jargon.

### 8. A score for the whole document

At the top: *"3 of 7 citations in this document have problems."*

One number that tells you whether to trust the thing you are holding.

### 9. The scoreboard (our favourite part)

We can run the checker across hundreds of AI-written legal answers automatically and
measure **how often that AI invents cases**.

This means we do not just show up with an app. We show up with our own real finding about
how trustworthy these tools actually are.

---

## What it deliberately does NOT do

This is a feature, not a gap, and we will say so in the pitch.

**We do not give legal advice.** We never tell anyone what to do about their case. We only
check whether a citation is accurate.

That matters. In law there is a hard line between *legal information* (fine) and *legal
advice* (regulated — you need a licence). Tools that cross it are in real trouble: New York
has proposed a law letting people sue chatbot owners over it, and OpenAI was sued in March
2026 over a chatbot helping draft filings with fake authority in them.

Our tool sits safely on the right side of that line. It checks facts. It does not advise.

---

## Who it helps

- **People representing themselves in court.** Over 90% of people in many types of civil
  case have no lawyer. Many now ask ChatGPT for help. If it hands them a fake case and they
  file it, they are in a worse position than when they started.
- **Overworked legal aid staff**, who have far more cases than time.
- **Anyone using AI for legal work** who does not want to be the next person in the news.

---

## Build priority

| Priority | Feature | Notes |
|---|---|---|
| Must have | 1, 2, 7 | Working fake-case detection. Demo-able on its own. |
| Must have | 3, 5, 6 | The hard part and the real differentiator. |
| Should have | 8, 9 | The score and the measurement study. |
| Stretch | 4 | Good-law checking. Cut first if time runs out. |

---

## Sources for the numbers used above

- [Stanford RegLab — Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools](https://reglab.stanford.edu/publications/hallucination-free-assessing-the-reliability-of-leading-ai-legal-research-tools/)
- [Legal GenAI tools mislead 17% of time: Stanford study — Legal Dive](https://www.legaldive.com/news/legal-genai-tools-mislead-17-percent-of-time-stanford-HAI-hallucinations-incorrect-law-citations/717128/)
- [CourtListener REST API v4 — coverage figures](https://www.courtlistener.com/help/api/rest/)
- [Pro Se Litigation Statistics 2026](https://thelawlion.com/blog/pro-se-litigation-statistics)
- [New York Bill Would Create Liability for Chatbot Proprietors Offering Professional Advice — Holland & Knight](https://www.hklaw.com/en/insights/publications/2026/03/new-york-bill-would-create-liability-for-chatbot-proprietors)
- [Access to Justice, AI, and the Unauthorized Practice of Law — Pro Bono Institute](https://www.probonoinst.org/2026/07/28/access-to-justice-ai-and-the-unauthorized-practice-of-law/)
