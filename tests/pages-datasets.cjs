const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');

async function main() {
  const base = process.env.PHASE3_BASE_URL || 'http://127.0.0.1:8765/privacy-observatory/';
  const downloads = process.env.PHASE3_DOWNLOAD_DIR;
  assert(downloads, 'PHASE3_DOWNLOAD_DIR is required');
  const browser = await chromium.launch({
    headless: true, args: ['--no-sandbox'], executablePath: process.env.CHROMIUM_PATH,
  });
  try {
    for (const [mode, width, height] of [['desktop', 1440, 900], ['mobile', 390, 844]]) {
      const context = await browser.newContext({viewport: {width, height}, acceptDownloads: true});
      const page = await context.newPage();
      const failures = [];
      page.on('pageerror', error => failures.push(error.message));
      page.on('console', message => { if (message.type() === 'error') failures.push(message.text()); });
      page.on('response', response => {
        if (response.url().startsWith(base) && response.status() >= 400) failures.push(response.url());
      });
      await page.goto(base, {waitUntil: 'networkidle'});
      await page.reload({waitUntil: 'networkidle'});
      const icon = await page.locator('link[rel=icon]').getAttribute('href');
      assert(icon.startsWith('data:'));
      const charts = await page.request.get(base + 'datasets/chart-data.json').then(r => r.json());
      const catalog = await page.request.get(base + 'datasets/index.json').then(r => r.json());
      await page.getByRole('heading', {name: '数据集目录'}).waitFor();
      assert.equal(await page.locator('#datasets article').count(), 4);
      await page.getByRole('link', {name: '数据集目录 ↘'}).click();
      assert.equal(new URL(page.url()).hash, '#datasets');

      for (const asset of ['xmr', 'zec']) {
        const values = [
          ['market_cap_usd', charts.privacy_market_daily],
          ['transaction_count', charts.privacy_network_daily],
        ];
        if (asset === 'xmr') values.push(['current_supply_native', charts.privacy_network_daily]);
        for (const [field, series] of values) {
          const [day, raw] = series[asset][field].filter(([, v]) => v !== null).at(-1);
          const metric = page.locator(`[data-asset="${asset}"] [data-metric="${field}"]`);
          assert.equal(await metric.getAttribute('title'), raw);
          assert.equal(await metric.locator('..').locator(':scope > small').innerText(), day + ' UTC');
          const formatted = new Intl.NumberFormat('zh-CN', {maximumFractionDigits: field === 'market_cap_usd' ? 2 : 0})
            .format(field === 'market_cap_usd' ? Number(raw) / 1e8 : Number(raw));
          assert((await metric.innerText()).includes(formatted));
        }
      }
      for (const id of new Set(charts.privacy_protocol_registry.map(r => r.protocol_id))) {
        const deployments = charts.privacy_protocol_registry.filter(r => r.protocol_id === id);
        const card = page.locator(`[data-protocol="${id}"]`);
        assert.equal(await card.getAttribute('href'), deployments[0].website_url);
        assert.equal(await card.locator('small').innerText(), deployments.map(r => r.chain_name).join(' · '));
      }
      assert.equal(await page.locator('canvas').count(), 1);
      for (const [label, dataset] of [['历史市值', 'privacy_market_daily'], ['交易活动', 'privacy_network_daily']]) {
        await page.getByRole('button', {name: label}).click();
        assert.equal(await page.getByRole('button', {name: label}).getAttribute('class'), 'active');
        await page.getByLabel('时间范围').selectOption('90');
        await page.getByLabel('时间范围').selectOption('all');
        assert((await page.locator('.chart-card a[download]').first().getAttribute('href')).includes(dataset));
        assert((await page.locator('.chart-card').innerText()).includes('下载包含完整历史'));
        const chart = page.locator('.chart');
        await chart.scrollIntoViewIfNeeded();
        const rect = await chart.boundingBox();
        await page.mouse.move(rect.x + rect.width * 0.7, rect.y + rect.height * 0.6);
        await page.waitForFunction(() => /\d{4}-\d{2}-\d{2}.*Monero.*Zcash/s.test(
          document.querySelector('.chart').innerText));
        await page.mouse.move(2, 2);

      }
      assert.equal(await page.locator('#pools a[download]').count(), 0);

      const hrefs = await page.locator('a[href^="/privacy-observatory/datasets/"]').evaluateAll(links =>
        [...new Set(links.map(link => link.href))]);
      assert.equal(hrefs.length, 22);
      for (const url of hrefs) {
        const response = await page.request.get(url);
        assert.equal(response.status(), 200, url);
        if (url.endsWith('.html')) {
          const document = await context.newPage();
          await document.goto(url);
          await document.locator('h1').waitFor();
          await document.close();
        }
      }
      const out = path.join(downloads, mode);
      await fs.mkdir(out, {recursive: true});
      const links = page.locator('#datasets a[download]');
      assert.equal(await links.count(), 6);
      for (const link of await links.all()) {
        const href = await link.getAttribute('href');
        const [, id, filename] = href.match(/datasets\/([^/]+)\/([^/]+)$/);
        const downloadPromise = page.waitForEvent('download');
        await link.click();
        const download = await downloadPromise;
        assert.equal(download.suggestedFilename(), filename);
        const target = path.join(out, filename);
        await download.saveAs(target);
        const bytes = await fs.readFile(target);
        const manifest = await page.request.get(base + 'datasets/' + id + '/manifest.json').then(r => r.json());
        assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), manifest.files[filename].sha256);
        assert.equal(bytes.length, manifest.files[filename].bytes);
      }
      assert.equal(catalog.filter(r => r.status === 'Blocked').length, 1);
      for (const resource of ['data/pools.json', 'datasets/zcash_value_pools_daily/zcash_value_pools_daily.csv',
        'datasets/zcash_value_pools_daily/zcash_value_pools_daily.parquet', 'datasets/audit_phase2/evidence.json',
        'datasets/_sources/coin_metrics_pages.json.gz']) {
        assert.equal((await page.request.get(base + resource)).status(), 404, resource);
      }
      assert(await page.evaluate(() => document.documentElement.scrollWidth === innerWidth), 'horizontal overflow');
      assert.deepEqual(failures, []);
      await page.route('**/datasets/chart-data.json', route => route.fulfill({status: 503, body: '{}'}));
      await page.reload();
      await page.getByRole('status').waitFor();
      assert((await page.locator('[data-asset=xmr] [data-metric=market_cap_usd]').innerText()).includes('—'));
      await context.close();
      console.log(mode, width, height, '6 browser downloads, 22 unique links, content, navigation, fallback and layout passed');
    }
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
