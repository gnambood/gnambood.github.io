"use strict";

/* GitHub Pages reads a published JSON snapshot. It never calls the AWS API.
 * Add vehicle scenarios only by exporting real saved model outputs and citations.
 */
const QUESTIONS = {
  reliability: "What do owners mention about reliability and common problems?",
  maintenance: "What maintenance issues and repair costs do owners mention?",
  comfort: "What do owners say about comfort and everyday driving?",
  fuel_economy: "What do owners mention about fuel economy and efficiency?"
};
const els = {
  make: document.getElementById("makeSelect"),
  model: document.getElementById("modelSelect"),
  year: document.getElementById("yearSelect"),
  mileage: document.getElementById("mileageSelect"),
  condition: document.getElementById("conditionSelect"),
  question: document.getElementById("questionSelect"),
  title: document.getElementById("vehicleTitle"),
  note: document.getElementById("dataModeNote"),
  modeTag: document.getElementById("modeTag"),
  prompt: document.getElementById("promptText"),
  button: document.getElementById("runDemo"),
  results: document.getElementById("results"),
  bar: document.getElementById("bar")
};
const money = number => "$" + Math.round(number).toLocaleString("en-US");
const signedMoney = number => (number >= 0 ? "+" : "−") + money(Math.abs(number));
const option = (value, label) => {
  const element = document.createElement("option");
  element.value = value;
  element.textContent = label;
  return element;
};
let snapshot = null;
const entries = () => Object.entries(snapshot?.vehicles ?? {});
const currentVehicle = () => snapshot?.vehicles?.[els.model.value];
const currentPrice = () => {
  const vehicle = currentVehicle();
  const key = [els.year.value, els.mileage.value, els.condition.value].join("|");
  return vehicle?.price_grid?.[key] ?? null;
};
const currentEvidence = () =>
  currentVehicle()?.reviews?.[[els.year.value, els.question.value].join("|")] ?? null;

function selectOptions(element, values, label = value => String(value)) {
  element.replaceChildren(...values.map(value => option(String(value), label(value))));
}

function validateSnapshot(data) {
  if (data?.schema_version !== 1 || !data.vehicles || !data.evaluation) {
    throw new Error("Unsupported saved-output format");
  }
  if (!Object.keys(data.vehicles).length) throw new Error("No published vehicle examples");
  for (const vehicle of Object.values(data.vehicles)) {
    for (const price of Object.values(vehicle.price_grid ?? {})) {
      const keys = ["predicted_price", "comparable_q25", "comparable_median", "comparable_q75", "comparable_count"];
      if (keys.some(key => !Number.isFinite(price[key])) ||
          price.comparable_q25 > price.comparable_median ||
          price.comparable_median > price.comparable_q75) {
        throw new Error("Invalid price/comparable values");
      }
    }
    for (const record of Object.values(vehicle.reviews ?? {})) {
      const ids = (record.sources ?? []).map(source => source.review_id);
      if (new Set(ids).size !== ids.length || ids.some(id => !/^edm_[a-z0-9]+$/i.test(id))) {
        throw new Error("Invalid cited review IDs");
      }
    }
  }
}

function populateMakes() {
  selectOptions(els.make, [...new Set(entries().map(([, vehicle]) => vehicle.display_make))]);
  populateModels();
}
function populateModels() {
  const models = entries().filter(([, vehicle]) => vehicle.display_make === els.make.value);
  els.model.replaceChildren(...models.map(([key, value]) => option(key, value.display_model)));
  populateFields();
}
function populateFields() {
  const vehicle = currentVehicle();
  if (!vehicle) return;
  selectOptions(els.year, vehicle.years);
  selectOptions(els.mileage, vehicle.mileages, value => Number(value).toLocaleString("en-US") + " mi");
  selectOptions(els.condition, vehicle.conditions, value => String(value).replace(/\b\w/g, match => match.toUpperCase()));
  populateQuestions();
}
function populateQuestions() {
  const chosen = els.question.value;
  const topics = Object.entries(snapshot?.questions ?? QUESTIONS);
  els.question.replaceChildren(...topics.map(([key, label]) => {
    const supported = Boolean(currentVehicle()?.reviews?.[[els.year.value, key].join("|")]);
    return option(key, supported ? label : label + " (not in saved snapshot)");
  }));
  if (topics.some(([key]) => key === chosen)) els.question.value = chosen;
  syncPrompt();
}
function syncPrompt() {
  const vehicle = currentVehicle();
  if (!vehicle) return;
  els.title.textContent = els.year.value + " " + vehicle.display_make + " " + vehicle.display_model;
  els.prompt.textContent = snapshot.questions?.[els.question.value] ?? QUESTIONS.reliability;
  els.button.textContent = "Explore saved result";
  els.results.classList.remove("show");
  els.bar.style.width = "0";
  if (els.results.dataset.loaded === "true") showResult(false);
}

function renderPrice(price) {
  document.getElementById("predPrice").textContent = money(price.predicted_price);
  document.getElementById("q1").textContent = money(price.comparable_q25) + " Q1";
  document.getElementById("q3").textContent = money(price.comparable_q75) + " Q3";
  document.getElementById("medianPrice").textContent = money(price.comparable_median);
  document.getElementById("compMeta").textContent =
    price.comparable_count + " observed comparable listings · " + price.market_year;
  const span = Math.max(1, price.comparable_q75 - price.comparable_q25);
  const pct = Math.max(2, Math.min(98, 100 * (price.predicted_price - price.comparable_q25) / span));
  const pin = document.getElementById("estimatePin");
  pin.style.left = pct + "%";
  pin.dataset.label = money(price.predicted_price);
  renderBenchmark();
}
function renderBenchmark() {
  const price = currentPrice();
  if (!price) return;
  const key = document.getElementById("benchmarkSelect")?.value || "comparable_median";
  const label = {
    comparable_q25: "the lower quartile",
    comparable_median: "the observed comparable median",
    comparable_q75: "the upper quartile"
  }[key] || "the median";
  const difference = price.predicted_price - price[key];
  const relative = price[key] ? Math.abs(100 * difference / price[key]).toFixed(1) + "%" : "n/a";
  const value = document.getElementById("benchmarkDifference");
  const description = document.getElementById("benchmarkDescription");
  if (value) value.textContent = signedMoney(difference);
  if (description) description.textContent =
    relative + " " + (difference >= 0 ? "above" : "below") + " " + label +
    " (historical observations; not a confidence interval).";
}
function renderSources(sources) {
  const root = document.getElementById("reviewSources");
  root.replaceChildren();
  const detail = document.getElementById("sourceDetail");
  if (!sources.length) {
    detail.textContent = "No citations were published for this saved question.";
    return;
  }
  sources.forEach((source, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "source";
    button.setAttribute("aria-pressed", String(index === 0));
    const title = document.createElement("b");
    title.textContent = "[" + source.review_id + "] " + (source.review_title || "Owner review");
    const meta = document.createElement("span");
    meta.className = "source-meta";
    meta.textContent = source.vehicle_year ? "Owner review: " + source.vehicle_year : "Year not recorded";
    button.append(title, meta);
    const selectSource = () => {
      root.querySelectorAll("button").forEach(other => other.setAttribute("aria-pressed", String(other === button)));
      detail.textContent = "Recorded source " + source.review_id + " · " +
        (source.review_title || "Owner review") + " · " + (source.vehicle_year || "year unknown") +
        ". The original review text is not published in this static snapshot.";
      if (source.excerpt) detail.textContent += " Recorded excerpt: " + source.excerpt;
    };
    button.addEventListener("click", selectSource);
    root.append(button);
    if (index === 0) selectSource();
  });
}
function renderEvidence() {
  const record = currentEvidence();
  const heading = document.getElementById("reviewHeading");
  const answer = document.getElementById("reviewAnswer");
  const verification = document.getElementById("verification");
  const suggestion = document.getElementById("reviewSuggestion");
  suggestion.classList.remove("show");
  suggestion.replaceChildren();
  if (!record) {
    heading.textContent = "No saved answer for this topic";
    answer.textContent = "This question was not included in the exported, verified snapshot. " +
      "The page will not produce a new answer or use unrelated reviews.";
    verification.textContent = "No new retrieval or generation performed.";
    renderSources([]);
    els.note.textContent = "Only the reliability review summary is recorded for this Ford F-150 snapshot. " +
      "The saved price estimate remains available.";
    return;
  }
  heading.textContent = record.heading || "Saved owner-review evidence";
  answer.textContent = record.answer || "Saved review response unavailable.";
  verification.textContent = record.citation_valid
    ? "✓ Saved citation IDs validated in the recorded output · No live retrieval"
    : "Recorded sources shown without a new citation-verification run";
  renderSources(record.sources ?? []);
  els.note.textContent = "Browsing the verified saved 2021 price result and the recorded owner-review evidence. " +
    "No AWS, cloud model, or new inference is used.";
}

function addBar(root, label, value, maximum, suffix = "") {
  const row = document.createElement("div");
  row.className = "bar-row";
  const head = document.createElement("div");
  head.className = "bar-head";
  const name = document.createElement("span");
  name.textContent = label;
  const amount = document.createElement("b");
  amount.textContent = Math.round(value * 100) / 100 + suffix;
  head.append(name, amount);
  const track = document.createElement("div");
  track.className = "metric-track";
  track.setAttribute("role", "progressbar");
  track.setAttribute("aria-label", label);
  track.setAttribute("aria-valuemin", "0");
  track.setAttribute("aria-valuemax", String(maximum));
  track.setAttribute("aria-valuenow", String(value));
  const fill = document.createElement("div");
  fill.className = "metric-fill";
  fill.style.width = Math.max(0, Math.min(100, value * 100 / maximum)) + "%";
  track.append(fill); row.append(head, track); root.append(row);
}
function renderMetrics() {
  const focus = document.getElementById("metricFocus")?.value || "price";
  const root = document.getElementById("metricBars");
  const explanation = document.getElementById("metricExplanation");
  if (!root || !explanation) return;
  root.replaceChildren();
  const metrics = snapshot.evaluation;
  if (focus === "price") {
    const m = metrics.price_test;
    addBar(root, "Earlier baseline MAE", m.mae_v0, m.mae_v0, " USD");
    addBar(root, "Final CatBoost MAE", m.mae_final, m.mae_v0, " USD");
    explanation.textContent = "Chronological held-out prices: lower mean absolute error is better. " +
      "Final test R² " + m.r2.toFixed(3) + "; " + m.within_5000_percent.toFixed(1) +
      "% of predictions fell within ±$5,000. These project-level results are not per-vehicle error bars.";
  } else if (focus === "retrieval") {
    const m = metrics.retrieval;
    addBar(root, "Vehicle identity Hit@5", m.hit_at_5_percent, 100, "%");
    addBar(root, "MRR@10", m.mrr_at_10 * 100, 100, "%");
    explanation.textContent = m.matched_reviews.toLocaleString("en-US") + " matched reviews. " +
      "Recorded median retrieval time " + m.median_ms + " ms; p95 " + m.p95_ms +
      " ms in the original benchmark (not the static page).";
  } else {
    const m = metrics.answerability;
    addBar(root, "Precision", m.precision_percent, 100, "%");
    addBar(root, "Recall", m.recall_percent, 100, "%");
    addBar(root, "F1", m.f1_percent, 100, "%");
    explanation.textContent = m.benchmark + ". This weak-label evaluation is not a claim of universal RAG accuracy.";
  }
}
function showResult(scroll = true) {
  const price = currentPrice();
  if (!price) {
    els.note.textContent = "No exported price inference exists for this combination.";
    return;
  }
  renderPrice(price);
  renderEvidence();
  renderMetrics();
  els.results.classList.add("show");
  els.results.dataset.loaded = "true";
  els.modeTag.textContent = "STATIC · SAVED EVIDENCE";
  els.button.textContent = "Saved result loaded ✓";
  els.bar.style.width = "100%";
  if (scroll) els.results.scrollIntoView({behavior: "smooth", block: "nearest"});
}

async function loadSnapshot() {
  try {
    const url = new URL("./data/auto-market-snapshots.v1.json", document.baseURI);
    if (url.origin !== location.origin) throw new Error("Saved bundle must be same-origin");
    const response = await fetch(url, {cache: "force-cache"});
    if (!response.ok) throw new Error("HTTP " + response.status);
    const data = await response.json();
    validateSnapshot(data);
    snapshot = data;
    populateMakes();
    els.button.disabled = false;
    els.note.textContent = entries().length + " verified saved vehicle scenario(s). " +
      "No AWS is contacted. The original trained model is not running on this page.";
    els.modeTag.textContent = "OFFLINE · SAVED 2021 OUTPUT";
  } catch (error) {
    els.modeTag.textContent = "SNAPSHOT UNAVAILABLE";
    els.note.textContent = "Unable to load the published data bundle: " + error.message;
    els.button.disabled = true;
  }
}
els.make.addEventListener("change", populateModels);
els.model.addEventListener("change", populateFields);
els.year.addEventListener("change", populateQuestions);
[els.mileage, els.condition].forEach(field => field.addEventListener("change", syncPrompt));
els.question.addEventListener("change", () => {
  syncPrompt();
  if (els.results.dataset.loaded === "true") showResult(false);
});
els.button.addEventListener("click", () => showResult());
document.getElementById("benchmarkSelect")?.addEventListener("change", renderBenchmark);
document.getElementById("metricFocus")?.addEventListener("change", renderMetrics);

document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(other => {
    other.classList.toggle("active", other === tab);
    other.setAttribute("aria-selected", String(other === tab));
  });
  document.querySelectorAll(".tabpane").forEach(pane => {
    pane.classList.toggle("active", pane.id === tab.dataset.tab);
  });
}));

if (new URLSearchParams(location.search).get("embed") === "1") {
  document.documentElement.classList.add("embed-mode");
  const sendHeight = () => {
    if (window.parent !== window) window.parent.postMessage(
      {type: "auto-market-height", height: document.documentElement.scrollHeight},
      location.origin
    );
  };
  new ResizeObserver(sendHeight).observe(document.body);
  window.addEventListener("load", sendHeight);
}
loadSnapshot();
