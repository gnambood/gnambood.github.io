// End-to-end test: serve the actual static files over HTTP and block cloud requests.
import assert from "node:assert/strict";
import {createServer} from "node:http";
import {readFile} from "node:fs/promises";
import path from "node:path";
import {chromium} from "playwright";

const root = process.cwd();
const extensions = {".html":"text/html", ".js":"text/javascript", ".json":"application/json", ".css":"text/css"};
const server = createServer(async (request, response) => {
  const url = new URL(request.url, "http://127.0.0.1");
  const requested = url.pathname === "/" ? "/index.html" : url.pathname;
  const file = path.resolve(root, "." + requested);
  if (!file.startsWith(root + path.sep)) {
    response.writeHead(403).end("Forbidden");
    return;
  }
  try {
    const bytes = await readFile(file);
    response.writeHead(200, {"Content-Type": extensions[path.extname(file)] || "application/octet-stream"});
    response.end(bytes);
  } catch {
    response.writeHead(404).end("Not Found");
  }
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
const base = "http://127.0.0.1:" + server.address().port;
const browser = await chromium.launch({headless: true});
try {
  const page = await browser.newPage({viewport: {width: 1280, height: 900}});
  const errors = [], network = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("request", request => network.push(request.url()));
  const response = await page.goto(base + "/auto-market-assistant.html");
  assert.equal(response.status(), 200);
  await page.waitForFunction(() => document.querySelector("#questionSelect").options.length === 4);
  assert.equal(await page.locator("#makeSelect option").count(), 1);
  assert.equal(await page.locator("#modelSelect option").count(), 1);
  assert.equal(await page.locator("#yearSelect option").count(), 1);
  assert.equal(await page.locator("#questionSelect option").count(), 4);
  assert.match(await page.locator("#modeTag").innerText(), /OFFLINE|STATIC/);
  assert.match(await page.locator("#dataModeNote").innerText(), /No AWS/i);

  await page.locator("#runDemo").click();
  assert(await page.locator("#results").isVisible());
  assert.equal(await page.locator("#predPrice").innerText(), "$10,739");
  assert.equal(await page.locator("#medianPrice").innerText(), "$11,995");
  assert.equal(await page.locator("#reviewSources button.source").count(), 3);
  assert.match(await page.locator("#verification").innerText(), /saved citation IDs validated/i);

  await page.locator("#benchmarkSelect").selectOption("comparable_q25");
  assert.equal(await page.locator("#benchmarkDifference").innerText(), "+$1,239");
  await page.locator("#benchmarkSelect").selectOption("comparable_median");
  assert.equal(await page.locator("#benchmarkDifference").innerText(), "−$1,256");
  await page.locator("#reviewSources button.source").nth(1).click();
  assert.match(await page.locator("#sourceDetail").innerText(), /Ron's Review/);

  await page.locator('[data-tab="metrics"]').click();
  await page.locator("#metricFocus").selectOption("retrieval");
  assert.match(await page.locator("#metricExplanation").innerText(), /70,665/);
  assert.equal(await page.locator("#metricBars .bar-row").count(), 2);
  await page.locator("#metricFocus").selectOption("answerability");
  assert.equal(await page.locator("#metricBars .bar-row").count(), 3);
  assert.match(await page.locator("#metricExplanation").innerText(), /weakly supervised/i);

  await page.locator("#questionSelect").selectOption("maintenance");
  assert.match(await page.locator("#reviewHeading").innerText(), /No saved answer/);
  assert.equal(await page.locator("#reviewSources button.source").count(), 0);
  assert.equal(await page.locator("#predPrice").innerText(), "$10,739");
  await page.locator("#questionSelect").selectOption("reliability");
  assert.equal(await page.locator("#reviewSources button.source").count(), 3);

  // The iframe/embed view uses the same local JSON and never contacts AWS.
  await page.goto(base + "/auto-market-assistant.html?embed=1");
  await page.waitForFunction(() => document.querySelector("#runDemo").disabled === false);
  await page.locator("#runDemo").click();
  assert(await page.locator("#results").isVisible());

  // Narrow viewport must not overflow horizontally.
  await page.setViewportSize({width: 375, height: 810});
  const width = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth
  }));
  assert(width.content <= width.viewport + 4, JSON.stringify(width));

  assert.deepEqual(errors, [], "Client-side exceptions are not allowed");
  assert(
    network.every(url => url.startsWith(base + "/")),
    "The demo must never request AWS or any external host: " + JSON.stringify(network)
  );
  assert(network.some(url => url.includes("/data/auto-market-snapshots.v1.json")));
  console.log("Saved scenario, price comparison, citations, evidence gaps, metrics, embed and no-AWS browser checks passed.");
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
