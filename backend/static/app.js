"use strict";

const $ = (id) => document.getElementById(id);

const SAMPLE = `The implied warranty of habitability may be waived by agreement between \
landlord and tenant, as the court explained in Alvarez v. Northgate Property Management, \
42 F.3d 100 (1994). A landlord may not resort to self-help eviction, Whitfield v. Cedar \
Ridge Apartments, 58 F.3d 900 (1995). The controlling authority remains Smith v. Nowhere, \
999 U.S. 1234 (2022), which every court in the circuit has followed. Id. at 1240.`;

const VERDICT_LABEL = {
  green: "looks fine",
  amber: "problem",
  red: "fabricated",
  unknown: "not checked",
};

/** Text goes in via textContent, never innerHTML — audited text is untrusted input. */
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

async function loadComponents() {
  const box = $("components");
  try {
    const health = await (await fetch("/health")).json();
    const c = health.components || {};
    const chips = [
      [`database: ${c.database}`, c.database_authoritative],
      [`support check: ${c.judge}`, c.judge_is_model_based],
      [`retrieval: ${c.embeddings}`, c.embeddings_semantic],
    ];
    box.replaceChildren(
      ...chips.map(([label, ok]) => el("span", `chip ${ok ? "ok" : "warn"}`, label))
    );

    // Coverage is what licenses the tool to call a citation fabricated, so show it.
    const coverage = c.corpus_coverage || [];
    if (coverage.length) {
      const volumes = coverage.reduce((n, r) => n + (r.volumes || 0), 0);
      const reporters = coverage.map((r) => r.reporter).join(", ");
      box.append(
        el("span", "chip ok",
           `corpus: ${c.corpus_opinions} opinions · ${volumes} volume(s) of ${reporters}`)
      );
    } else if (!c.database_authoritative) {
      box.append(
        el("span", "chip warn", "offline sample — cannot confirm fabrication")
      );
    }
  } catch {
    box.replaceChildren(el("span", "chip warn", "could not reach the server"));
  }
}

function renderQuote(support) {
  const quote = el("blockquote");
  quote.append(el("span", null, `“${support.quote}”`));
  quote.append(
    el("span", "verified", "✓ confirmed word-for-word in the source opinion")
  );
  return quote;
}

function renderItem(item, index) {
  const li = el("li", `item ${item.verdict}`);

  const head = el("div", "head");
  head.append(el("span", "cite", item.citation.normalized || item.citation.raw));
  if (item.citation.case_name) {
    head.append(el("span", "case-name", item.citation.case_name));
  }
  head.append(el("span", "badge", VERDICT_LABEL[item.verdict] || item.verdict));
  li.append(head);

  li.append(el("p", "explain", item.explanation));

  if (item.claim) {
    const claim = el("p", "claim", "Claimed: ");
    claim.append(el("q", null, item.claim));
    li.append(claim);
  }

  const support = item.support;
  if (support && support.quote && support.quote_verified) {
    li.append(renderQuote(support));
  }

  const match = (item.matches || [])[0];
  if (match && match.url) {
    const meta = el("p", "meta");
    const link = el("a", null, "Read the case →");
    link.href = match.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    meta.append(link);
    li.append(meta);
  }

  const goodLaw = item.good_law;
  const notes = [...(item.notes || [])];
  if (goodLaw && goodLaw.summary && goodLaw.checked) notes.unshift(goodLaw.summary);
  if (notes.length) {
    const list = el("ul", "notes");
    notes.forEach((n) => list.append(el("li", null, n)));
    li.append(list);
  }

  li.dataset.index = String(index);
  return li;
}

function render(report) {
  const headline = $("headline");
  headline.replaceChildren(el("span", null, report.headline));
  headline.append(
    el("span", "sub", `Checked against: ${report.source_used}`)
  );

  $("list").replaceChildren(...report.citations.map(renderItem));
  const results = $("results");
  results.hidden = false;
  results.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function send(url, options, pendingMessage) {
  const button = $("check");
  const status = $("status");
  button.disabled = true;
  status.textContent = pendingMessage;

  try {
    const response = await fetch(url, options);
    const body = await response.json();
    if (!response.ok) {
      status.textContent = body.detail || `Error ${response.status}`;
      return;
    }
    status.textContent = "";
    render(body);
  } catch (error) {
    status.textContent = `Could not reach the server: ${error.message}`;
  } finally {
    button.disabled = false;
  }
}

$("check").addEventListener("click", () => {
  const text = $("input").value.trim();
  if (!text) {
    $("status").textContent = "Paste some text first.";
    return;
  }
  send(
    "/audit",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    },
    "Checking citations…"
  );
});

$("sample").addEventListener("click", () => {
  $("input").value = SAMPLE;
  $("status").textContent = "";
});

// The PDF control is a styled <label>, so it needs keyboard activation of its own.
document.querySelector(".file").addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    $("pdf").click();
  }
});

$("pdf").addEventListener("change", (event) => {
  const file = event.target.files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  send("/audit/pdf", { method: "POST", body: form }, `Reading ${file.name}…`);
  event.target.value = "";
});

$("input").addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") $("check").click();
});

loadComponents();
