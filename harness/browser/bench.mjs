#!/usr/bin/env node

// Use locally installed Playwright browsers (npm package-local)
if (!process.env.PLAYWRIGHT_BROWSERS_PATH) {
  process.env.PLAYWRIGHT_BROWSERS_PATH = '0';
}

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const ROOT = path.resolve(new URL('.', import.meta.url).pathname, '../..');
const RESULTS_DIR = path.join(ROOT, 'results', 'browser');
const TESTDATA = path.join(ROOT, 'testdata');

const WARMUP = 5;
const MEASURED = 30;

const MIME = {
  '.html': 'text/html',
  '.js':   'application/javascript',
  '.mjs':  'application/javascript',
  '.wasm': 'application/wasm',
  '.json': 'application/json',
  '.bin':  'application/octet-stream',
  '.rgba': 'application/octet-stream',
};

// ── HTTP server with COOP/COEP for memory measurement ───────────────

function startServer() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const url = new URL(req.url, 'http://localhost');
      let filePath = path.join(ROOT, decodeURIComponent(url.pathname));

      if (filePath.endsWith('/')) filePath += 'index.html';

      if (!fs.existsSync(filePath)) {
        res.writeHead(404);
        res.end('Not Found');
        return;
      }

      const ext = path.extname(filePath);
      const contentType = MIME[ext] || 'application/octet-stream';

      res.writeHead(200, {
        'Content-Type': contentType,
        'Cross-Origin-Opener-Policy': 'same-origin',
        'Cross-Origin-Embedder-Policy': 'require-corp',
      });
      fs.createReadStream(filePath).pipe(res);
    });

    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      console.log(`HTTP server listening on http://127.0.0.1:${port}`);
      resolve({ server, port });
    });
  });
}

// ── Statistics helpers ──────────────────────────────────────────────

function stats(arr) {
  const sorted = [...arr].sort((a, b) => a - b);
  const n = sorted.length;
  const mean = sorted.reduce((s, v) => s + v, 0) / n;
  const median = n % 2 === 1
    ? sorted[Math.floor(n / 2)]
    : (sorted[n / 2 - 1] + sorted[n / 2]) / 2;
  const variance = sorted.reduce((s, v) => s + (v - mean) ** 2, 0) / (n - 1);
  const stdev = Math.sqrt(variance);
  return { n, mean, median, stdev, min: sorted[0], max: sorted[n - 1], values: sorted };
}

// ── Run a single benchmark configuration ────────────────────────────

async function runConvBenchmark(page, baseUrl, tc, w, h, k) {
  const url = `${baseUrl}/harness/browser/conv.html?tc=${tc}&w=${w}&h=${h}&k=${k}`;
  const label = `conv_${w}x${h}_k${k}_${tc}`;
  console.log(`  ${label} ...`);

  const imgFile = path.join(TESTDATA, `image_${w}x${h}.rgba`);
  const imgBase64 = fs.readFileSync(imgFile).toString('base64');

  await page.goto(url, { waitUntil: 'domcontentloaded' });

  await page.waitForFunction('window.__ready === true || window.__error', { timeout: 60000 });
  const err = await page.evaluate('window.__error');
  if (err) throw new Error(`${label}: ${err}`);

  const initTime = await page.evaluate('window.__initTimeMs');

  let memBefore = null;
  try {
    memBefore = await page.evaluate(() =>
      performance.measureUserAgentSpecificMemory
        ? performance.measureUserAgentSpecificMemory()
        : null
    );
  } catch { /* not available */ }

  const timings = await page.evaluate(async ({ imgB64, warmup, measured }) => {
    const raw = Uint8Array.from(atob(imgB64), c => c.charCodeAt(0));
    const times = [];
    for (let i = 0; i < warmup; i++) {
      window.__run(raw);
    }
    for (let i = 0; i < measured; i++) {
      const t0 = performance.now();
      window.__run(raw);
      const t1 = performance.now();
      times.push(t1 - t0);
    }
    return times;
  }, { imgB64: imgBase64, warmup: WARMUP, measured: MEASURED });

  let memAfter = null;
  try {
    memAfter = await page.evaluate(() =>
      performance.measureUserAgentSpecificMemory
        ? performance.measureUserAgentSpecificMemory()
        : null
    );
  } catch { /* not available */ }

  const memDelta = (memBefore && memAfter)
    ? (memAfter.bytes - memBefore.bytes)
    : null;

  const s = stats(timings);
  console.log(`    init=${initTime.toFixed(2)}ms  exec: mean=${s.mean.toFixed(3)}ms median=${s.median.toFixed(3)}ms stdev=${s.stdev.toFixed(3)}ms`);

  return {
    test: 'conv', toolchain: tc,
    params: { w, h, k },
    initTimeMs: initTime,
    execution: s,
    memoryDelta: memDelta,
  };
}

async function runJsonBenchmark(page, baseUrl, tc, n) {
  const url = `${baseUrl}/harness/browser/json.html?tc=${tc}&n=${n}`;
  const label = `json_${n}_${tc}`;
  console.log(`  ${label} ...`);

  const jsonFile = path.join(TESTDATA, `users_${n}.json`);
  const jsonStr = fs.readFileSync(jsonFile, 'utf-8');

  await page.goto(url, { waitUntil: 'domcontentloaded' });

  await page.waitForFunction('window.__ready === true || window.__error', { timeout: 60000 });
  const err = await page.evaluate('window.__error');
  if (err) throw new Error(`${label}: ${err}`);

  const initTime = await page.evaluate('window.__initTimeMs');

  let memBefore = null;
  try {
    memBefore = await page.evaluate(() =>
      performance.measureUserAgentSpecificMemory
        ? performance.measureUserAgentSpecificMemory()
        : null
    );
  } catch { /* not available */ }

  const timings = await page.evaluate(async ({ input, warmup, measured }) => {
    const times = [];
    for (let i = 0; i < warmup; i++) {
      window.__run(input);
    }
    for (let i = 0; i < measured; i++) {
      const t0 = performance.now();
      window.__run(input);
      const t1 = performance.now();
      times.push(t1 - t0);
    }
    return times;
  }, { input: jsonStr, warmup: WARMUP, measured: MEASURED });

  let memAfter = null;
  try {
    memAfter = await page.evaluate(() =>
      performance.measureUserAgentSpecificMemory
        ? performance.measureUserAgentSpecificMemory()
        : null
    );
  } catch { /* not available */ }

  const memDelta = (memBefore && memAfter)
    ? (memAfter.bytes - memBefore.bytes)
    : null;

  const s = stats(timings);
  console.log(`    init=${initTime.toFixed(2)}ms  exec: mean=${s.mean.toFixed(3)}ms median=${s.median.toFixed(3)}ms stdev=${s.stdev.toFixed(3)}ms`);

  return {
    test: 'json', toolchain: tc,
    params: { n },
    initTimeMs: initTime,
    execution: s,
    memoryDelta: memDelta,
  };
}

// ── Main ────────────────────────────────────────────────────────────

async function main() {
  fs.mkdirSync(RESULTS_DIR, { recursive: true });

  const { server, port } = await startServer();
  const baseUrl = `http://127.0.0.1:${port}`;

  const browser = await chromium.launch({
    headless: true,
    channel: 'chromium',
    args: [
      '--disable-extensions',
      '--disable-background-networking',
      '--disable-default-apps',
      '--no-first-run',
      '--disable-gpu',
      '--enable-experimental-web-platform-features',
    ],
  });

  const toolchains = ['go', 'tinygo', 'rust'];

  const convDims = [
    { w: 256, h: 256 },
    { w: 512, h: 512 },
    { w: 1024, h: 1024 },
    { w: 1920, h: 1080 },
  ];
  const kernels = [3, 5];
  const jsonSizes = [100, 1000, 10000];

  const allResults = [];

  console.log('\n============================================');
  console.log(' Browser Benchmark Suite');
  console.log(` ${new Date().toISOString()}`);
  console.log(`  Chromium: ${browser.version()}`);
  console.log('============================================\n');

  // B1: Convolution
  console.log('>>> B1: Image Convolution');
  for (const k of kernels) {
    for (const { w, h } of convDims) {
      for (const tc of toolchains) {
        const context = await browser.newContext();
        const page = await context.newPage();
        try {
          const result = await runConvBenchmark(page, baseUrl, tc, w, h, k);
          allResults.push(result);
        } catch (e) {
          console.error(`    ERROR: ${e.message}`);
          allResults.push({
            test: 'conv', toolchain: tc,
            params: { w, h, k },
            error: e.message,
          });
        }
        await context.close();
      }
    }
  }

  // B2: JSON Round-trip
  console.log('\n>>> B2: JSON Round-trip');
  for (const n of jsonSizes) {
    for (const tc of toolchains) {
      const context = await browser.newContext();
      const page = await context.newPage();
      try {
        const result = await runJsonBenchmark(page, baseUrl, tc, n);
        allResults.push(result);
      } catch (e) {
        console.error(`    ERROR: ${e.message}`);
        allResults.push({
          test: 'json', toolchain: tc,
          params: { n },
          error: e.message,
        });
      }
      await context.close();
    }
  }

  // Write results
  const outFile = path.join(RESULTS_DIR, 'results.json');
  fs.writeFileSync(outFile, JSON.stringify(allResults, null, 2));
  console.log(`\nResults written to ${outFile}`);

  // Also write per-test summary files for convenience
  const convResults = allResults.filter(r => r.test === 'conv' && !r.error);
  const jsonResults = allResults.filter(r => r.test === 'json' && !r.error);
  fs.writeFileSync(path.join(RESULTS_DIR, 'conv_results.json'), JSON.stringify(convResults, null, 2));
  fs.writeFileSync(path.join(RESULTS_DIR, 'json_results.json'), JSON.stringify(jsonResults, null, 2));

  await browser.close();
  server.close();

  console.log('\n============================================');
  console.log(' Browser benchmarks complete.');
  console.log(`  Results saved to: ${RESULTS_DIR}/`);
  console.log('============================================');
}

main().catch(e => {
  console.error('Fatal:', e);
  process.exit(1);
});
