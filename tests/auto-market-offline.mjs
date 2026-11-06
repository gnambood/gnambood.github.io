// Browser-level check of the saved example while ECS compute is paused.
// Usage: node tests/auto-market-offline.mjs (after installing Playwright/Chromium).

import assert from 'node:assert/strict';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const pageErrors = [];
  const cloudRequests = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('request', (request) => {
    if (request.url().includes('.ecs.ca-central-1.on.aws')) {
      cloudRequests.push(request.url());
    }
  });

  const url = pathToFileURL(path.resolve('auto-market-assistant.html')).href;
  await page.goto(url);
  await page.waitForFunction(() => document.querySelector('#questionSelect').options.length > 0);

  assert.equal(await page.locator('#makeSelect option').count(), 1);
  assert.equal(await page.locator('#modelSelect option').count(), 1);
  assert.equal(await page.locator('#questionSelect option').count(), 1);
  assert.equal(await page.locator('#questionSelect').inputValue(), 'reliability');
  assert.match(await page.locator('#modeTag').innerText(), /OFFLINE/);
  assert.equal(cloudRequests.length, 0, 'Offline mode must not contact ECS');

  await page.locator('#runDemo').click();
  assert.equal(await page.locator('#results').isVisible(), true);
  assert.equal(await page.locator('#predPrice').innerText(), '$10,739');
  assert.equal(await page.locator('#medianPrice').innerText(), '$11,995');
  assert.equal(await page.locator('#reviewSources .source').count(), 3);
  assert.match(await page.locator('#verification').innerText(), /source IDs validated/);
  assert.match(await page.locator('#dataModeNote').innerText(), /precomputed/i);
  assert.equal(cloudRequests.length, 0);
  assert.deepEqual(pageErrors, []);

  // The embedded view uses the same offline example.
  await page.goto(url + '?embed=1');
  await page.waitForFunction(() => document.querySelector('#questionSelect').options.length > 0);
  await page.locator('#runDemo').click();
  assert.equal(await page.locator('#results').isVisible(), true);
  assert.equal(cloudRequests.length, 0);
  assert.deepEqual(pageErrors, []);

  console.log('Offline vehicle demo and embedded view passed.');
} finally {
  await browser.close();
}
