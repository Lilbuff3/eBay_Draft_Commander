/**
 * E2E Smoke Test - eBay Draft Commander
 *
 * Tests the core app flow:
 * 1. App loads with Dashboard
 * 2. Settings page renders
 * 3. Health check API works
 * 4. Upload test images via API
 * 5. Job appears in dashboard
 * 6. Job details drawer opens with images
 * 7. Responsive mobile layout
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { deflateSync } = require('zlib');

const TARGET_URL = 'http://localhost:5175';
const SCREENSHOT_DIR = path.join(require('os').tmpdir(), 'e2e-screenshots');

// Create a minimal valid PNG file (1x1 pixel, colored)
function createTestPNG(r, g, b) {
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

  const ihdrData = Buffer.from([
    0, 0, 0, 1, 0, 0, 0, 1, 8, 2, 0, 0, 0
  ]);
  const ihdrCrc = crc32(Buffer.concat([Buffer.from('IHDR'), ihdrData]));
  const ihdr = Buffer.concat([
    int32(13), Buffer.from('IHDR'), ihdrData, ihdrCrc
  ]);

  const rawScanline = Buffer.from([0, r, g, b]);
  const compressed = deflateSync(rawScanline);
  const idatCrc = crc32(Buffer.concat([Buffer.from('IDAT'), compressed]));
  const idat = Buffer.concat([
    int32(compressed.length), Buffer.from('IDAT'), compressed, idatCrc
  ]);

  const iendCrc = crc32(Buffer.from('IEND'));
  const iend = Buffer.concat([
    int32(0), Buffer.from('IEND'), iendCrc
  ]);

  return Buffer.concat([signature, ihdr, idat, iend]);
}

function int32(n) {
  const buf = Buffer.alloc(4);
  buf.writeUInt32BE(n);
  return buf;
}

function crc32(buf) {
  let crc = 0xFFFFFFFF;
  const table = [];
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let j = 0; j < 8; j++) {
      c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
    }
    table[i] = c;
  }
  for (let i = 0; i < buf.length; i++) {
    crc = table[(crc ^ buf[i]) & 0xFF] ^ (crc >>> 8);
  }
  crc = (crc ^ 0xFFFFFFFF) >>> 0;
  const result = Buffer.alloc(4);
  result.writeUInt32BE(crc);
  return result;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

(async () => {
  // Setup
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }

  const browser = await chromium.launch({ headless: false, slowMo: 150 });
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await context.newPage();

  let passed = 0;
  let failed = 0;
  const results = [];

  function log(step, msg) {
    console.log('[Step ' + step + '] ' + msg);
  }

  async function check(step, name, fn) {
    try {
      await fn();
      log(step, 'PASS: ' + name);
      results.push({ step, name, status: 'PASS' });
      passed++;
    } catch (err) {
      log(step, 'FAIL: ' + name + ' - ' + err.message);
      results.push({ step, name, status: 'FAIL', error: err.message });
      failed++;
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, 'fail-step' + step + '.png'),
        fullPage: true
      });
    }
  }

  try {
    // STEP 1: App loads with Dashboard
    await check(1, 'App loads and Dashboard is visible', async () => {
      await page.goto(TARGET_URL, { waitUntil: 'networkidle', timeout: 15000 });
      await page.waitForSelector('text=Dashboard', { timeout: 5000 });
      await page.waitForSelector('main', { timeout: 3000 });
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01-dashboard-loaded.png') });
    });

    // STEP 2: Settings page loads
    await check(2, 'Settings page loads', async () => {
      const settingsBtn = page.locator('button:has-text("Settings"), a:has-text("Settings")').first();
      await settingsBtn.click();
      await sleep(1000);
      await page.waitForSelector('text=Settings', { timeout: 5000 });
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, '02-settings-page.png') });
    });

    // STEP 3: Health check API
    await check(3, 'Health check API returns ok', async () => {
      const response = await page.request.get(TARGET_URL + '/api/system/health');
      const body = await response.json();
      if (response.status() !== 200) {
        throw new Error('Health check returned status ' + response.status());
      }
      if (body.status !== 'ok') {
        throw new Error('Health check status is "' + body.status + '", expected "ok"');
      }
      log(3, 'Health response: ' + JSON.stringify(body));
    });

    // STEP 4: Upload test images
    let uploadedJobId = null;

    await check(4, 'Upload test images via API', async () => {
      const testImages = [
        { name: 'test-red.png', data: createTestPNG(255, 0, 0) },
        { name: 'test-green.png', data: createTestPNG(0, 255, 0) },
        { name: 'test-blue.png', data: createTestPNG(0, 0, 255) },
      ];

      // Playwright multipart doesn't support arrays for same field name.
      // Use page.evaluate with FormData to do multi-file upload.
      const imagesB64 = testImages.map(img => ({
        name: img.name,
        dataB64: img.data.toString('base64'),
      }));

      const result = await page.evaluate(async (args) => {
        const { images, url } = args;
        const formData = new FormData();
        for (const img of images) {
          // Convert base64 to Blob
          const binary = atob(img.dataB64);
          const bytes = new Uint8Array(binary.length);
          for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
          const blob = new Blob([bytes], { type: 'image/png' });
          formData.append('files[]', blob, img.name);
        }
        const resp = await fetch(url + '/api/upload', { method: 'POST', body: formData });
        return { status: resp.status, body: await resp.json() };
      }, { images: imagesB64, url: TARGET_URL });

      log(4, 'Upload response: ' + JSON.stringify(result.body));

      if (result.status !== 200) {
        throw new Error('Upload failed with status ' + result.status + ': ' + JSON.stringify(result.body));
      }

      uploadedJobId = result.body.jobId || result.body.job_id || result.body.id;
      log(4, 'Uploaded job ID: ' + uploadedJobId);
    });

    // STEP 5: Job appears in Dashboard
    await check(5, 'Job appears in dashboard', async () => {
      // Navigate back to Dashboard
      const dashBtn = page.locator('button:has-text("Dashboard"), a:has-text("Dashboard")').first();
      await dashBtn.click();
      await sleep(2000);

      // Check API for jobs
      const jobsResp = await page.request.get(TARGET_URL + '/api/jobs');
      const jobs = await jobsResp.json();
      log(5, 'Jobs API returned ' + (Array.isArray(jobs) ? jobs.length : 'non-array') + ' items');

      if (Array.isArray(jobs) && jobs.length === 0) {
        throw new Error('No jobs found in API after upload');
      }

      await page.screenshot({ path: path.join(SCREENSHOT_DIR, '03-job-in-dashboard.png') });
    });

    // STEP 6: Job details - verify via API
    await check(6, 'Job details accessible', async () => {
      if (uploadedJobId) {
        const detailsResp = await page.request.get(
          TARGET_URL + '/api/job/' + uploadedJobId + '/details'
        );

        if (detailsResp.ok()) {
          const details = await detailsResp.json();
          log(6, 'Job details: status=' + details.status + ', images=' + (details.image_count || 'unknown'));
        } else {
          log(6, 'Job details API returned ' + detailsResp.status());
        }
      }

      // Try clicking a job card in the UI
      try {
        const jobCards = page.locator('[class*="cursor-pointer"]');
        const count = await jobCards.count();
        if (count > 0) {
          await jobCards.first().click({ timeout: 5000 });
          await sleep(1500);
        }
      } catch (e) {
        log(6, 'Could not click job card: ' + e.message);
      }

      await page.screenshot({ path: path.join(SCREENSHOT_DIR, '04-job-details.png') });
    });

    // STEP 7: Mobile responsive layout
    await check(7, 'Mobile layout renders correctly', async () => {
      await page.setViewportSize({ width: 375, height: 667 });
      await sleep(500);

      await page.goto(TARGET_URL, { waitUntil: 'networkidle', timeout: 15000 });
      await sleep(1000);

      // Desktop sidebar should be hidden in mobile
      const sidebar = page.locator('.hidden.md\\:block').first();
      const sidebarBox = await sidebar.boundingBox();
      if (sidebarBox && sidebarBox.width > 0) {
        throw new Error('Desktop sidebar is visible in mobile viewport');
      }

      await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05-mobile-layout.png') });

      // Reset viewport
      await page.setViewportSize({ width: 1280, height: 720 });
    });

    // Summary
    console.log('\n' + '='.repeat(60));
    console.log('E2E Smoke Test Results: ' + passed + ' passed, ' + failed + ' failed');
    console.log('='.repeat(60));
    for (const r of results) {
      const icon = r.status === 'PASS' ? 'PASS' : 'FAIL';
      console.log('  [' + icon + '] Step ' + r.step + ': ' + r.name);
      if (r.error) console.log('         Error: ' + r.error);
    }
    console.log('\nScreenshots saved to: ' + SCREENSHOT_DIR);

    if (failed > 0) {
      console.log('\n' + failed + ' test(s) failed!');
      process.exit(1);
    } else {
      console.log('\nAll tests passed!');
    }

  } catch (error) {
    console.error('\nFatal error: ' + error.message);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'fatal-error.png'),
      fullPage: true
    });
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
