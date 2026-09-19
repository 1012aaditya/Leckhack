"use strict";

const $ = (id) => document.getElementById(id);

const SAMPLE = `The implied warranty of habitability may be waived by agreement between \
landlord and tenant, as the court explained in Alvarez v. Northgate Property Management, \
42 F.3d 100 (1994). A landlord may not resort to self-help eviction, Whitfield v. Cedar \
Ridge Apartments, 58 F.3d 900 (1995). The controlling authority remains Smith v. Nowhere, \
999 U.S. 1234 (2022), which every court in the circuit has followed. Id. at 1240.`;

const VERDICT = {
  green:   { label: "looks fine",  icon: "M4 12.5l5.5 5.5L20 7" },
  amber:   { label: "problem",     icon: "M12 8v5M12 17h.01" },
  red:     { label: "fabricated",  icon: "M7 7l10 10M17 7L7 17" },
  unknown: { label: "not checked", icon: "M12 17h.01M9.2 9a2.9 2.9 0 115.4 1.5c-.8 1-2 1.3-2.4 2.3" },
};

/** Text always goes in via textContent — audited input is untrusted. */
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function icon(path, size = 13, width = 2.6) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", size);
  svg.setAttribute("height", size);
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", width);
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  const node = document.createElementNS("http://www.w3.org/2000/svg", "path");
  node.setAttribute("d", path);
  svg.append(node);
  return svg;
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
      box.append(el("span", "chip ok",
        `corpus: ${c.corpus_opinions} opinions · ${volumes} volume(s) of ${reporters}`));
    } else if (!c.database_authoritative) {
      box.append(el("span", "chip warn", "offline sample — cannot confirm fabrication"));
    }
  } catch {
    box.replaceChildren(el("span", "chip warn", "could not reach the server"));
  }
}

function renderQuote(support) {
  const quote = el("blockquote");
  quote.append(el("span", null, `“${support.quote}”`));
  const verified = el("span", "verified");
  verified.append(icon("M4 12.5l5.5 5.5L20 7", 12, 3));
  verified.append(el("span", null, "confirmed word-for-word in the source opinion"));
  quote.append(verified);
  return quote;
}

function renderItem(item, index) {
  const li = el("li", `item ${item.verdict}`);
  li.style.animationDelay = `${Math.min(index, 6) * 45}ms`;

  const head = el("div", "head");
  head.append(el("span", "cite", item.citation.normalized || item.citation.raw));
  if (item.citation.case_name) head.append(el("span", "case-name", item.citation.case_name));

  const meta = VERDICT[item.verdict] || VERDICT.unknown;
  const badge = el("span", "badge");
  badge.append(icon(meta.icon, 11, 3));
  badge.append(el("span", null, meta.label));
  head.append(badge);
  li.append(head);

  li.append(el("p", "explain", item.explanation));

  if (item.claim) {
    const claim = el("p", "claim", "Claimed: ");
    claim.append(el("q", null, item.claim));
    li.append(claim);
  }

  const support = item.support;
  if (support && support.quote && support.quote_verified) li.append(renderQuote(support));

  const match = (item.matches || [])[0];
  if (match && match.url) {
    const box = el("p", "meta");
    const link = el("a", null, "Read the case →");
    link.href = match.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    box.append(link);
    li.append(box);
  }

  const notes = [...(item.notes || [])];
  const goodLaw = item.good_law;
  if (goodLaw && goodLaw.checked && goodLaw.summary) notes.unshift(goodLaw.summary);
  if (notes.length) {
    const list = el("ul", "notes");
    notes.forEach((n) => list.append(el("li", null, n)));
    li.append(list);
  }

  return li;
}

function showSkeleton() {
  const results = $("results");
  $("headline").replaceChildren(el("span", null, "Checking…"));
  const skeleton = el("div", "skeleton");
  for (let i = 0; i < 3; i += 1) skeleton.append(el("div"));
  $("list").replaceChildren(skeleton);
  results.hidden = false;
  results.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function render(report) {
  const headline = $("headline");
  headline.replaceChildren(el("span", null, report.headline));
  headline.append(el("span", "sub", `Checked against: ${report.source_used}`));
  $("list").replaceChildren(...report.citations.map(renderItem));
}

async function send(url, options, pendingMessage) {
  const button = $("check");
  const status = $("status");
  button.disabled = true;
  button.classList.add("busy");
  status.textContent = pendingMessage;
  showSkeleton();

  try {
    const response = await fetch(url, options);
    const body = await response.json();
    if (!response.ok) {
      status.textContent = body.detail || `Error ${response.status}`;
      $("results").hidden = true;
      return;
    }
    status.textContent = "";
    render(body);
  } catch (error) {
    status.textContent = `Could not reach the server: ${error.message}`;
    $("results").hidden = true;
  } finally {
    button.disabled = false;
    button.classList.remove("busy");
  }
}

$("check").addEventListener("click", () => {
  const text = $("input").value.trim();
  if (!text) {
    $("status").textContent = "Paste some text first.";
    $("input").focus();
    return;
  }
  send("/audit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  }, "Checking citations…");
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
