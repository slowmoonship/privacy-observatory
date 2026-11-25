const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');

const base = process.env.PHASE3_BASE_URL || 'http://127.0.0.1:8765/privacy-observatory/';
const downloads = process.env.PHASE3_DOWNLOAD_DIR;
const screenshots = process.env.PHASE2_SCREENSHOTS;

async function tooltip(page, selector, unit) {
  const chart = page.locator(selector + ' .chart');
  await chart.scrollIntoViewIfNeeded();
  const rect = await chart.boundingBox();
  await page.mouse.move(rect.x + rect.width * 0.68, rect.y + rect.height * 0.55);
  await page.waitForFunction(({selector, unit}) => {
    const text = document.querySelector(selector + ' .chart').innerText;
    return /\d{4}-\d{2}-\d{2}/.test(text) && /Monero|Zcash/.test(text) && text.includes(unit);
  }, {selector, unit}, {timeout: 5000});
  await page.mouse.move(1, 1);
}

async function dataDownloads(page, mode) {
  const out = path.join(downloads, mode);
  await fs.mkdir(out, {recursive: true});
  const links = page.locator('#datasets a[download]');
  assert.equal(await links.count(), 6);
  for (const link of await links.all()) {
    const [, id, filename] = (await link.getAttribute('href')).match(/datasets\/([^/]+)\/([^/]+)$/);
    const pending = page.waitForEvent('download');
    await link.click();
    const download = await pending;
    assert.equal(download.suggestedFilename(), filename);
    const target = path.join(out, filename);
    await download.saveAs(target);
    const bytes = await fs.readFile(target);
    const manifest = await page.request.get(base + 'datasets/' + id + '/manifest.json').then(r => r.json());
    assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), manifest.files[filename].sha256);
    assert.equal(bytes.length, manifest.files[filename].bytes);
  }
}

async function poolStates(page) {
  const selector = '**/datasets/zcash-pool-status.json';
  const valid = {
    status: 'available', block_height: 3543405, block_hash: 'f'.repeat(64),
    block_timestamp: new Date(Date.now() - 60000).toISOString(), fetched_at: new Date().toISOString(),
    source: 'TEST fixture', source_url: 'https://example.invalid/', source_license: 'test only',
    chain_supply_zat: '100000001', transparent_zat: '30000000', lockbox_zat: '10000000',
    sprout_zat: '1', sapling_zat: '20000000', orchard_zat: '20000000', ironwood_zat: '20000000',
  };
  for (const [state, body] of [
    ['current', valid],
    ['stale', {...valid, block_timestamp: new Date(Date.now() - 49 * 3600000).toISOString()}],
    ['invalid', {...valid, lockbox_zat: '10000001'}],
  ]) {
    await page.route(selector, route => route.fulfill({json: body}));
    await page.reload();
    await page.locator(`[data-pool-state="${state}"]`).waitFor();
    if (state === 'invalid') {
      assert.equal(await page.locator('[data-pool-total]').count(), 0);
    } else {
      assert.equal(await page.locator('[data-pool-total]').getAttribute('data-pool-total'), '100000001');
      assert.equal(await page.locator('[data-pool-shielded]').getAttribute('data-pool-shielded'), '60000001');
      assert.equal(await page.locator('[data-pool-share]').innerText(), '60.00%');
      assert.match(await page.locator('[data-pool=sprout]').innerText(), /不可支出/);
      assert.equal(await page.locator('[data-pool=ironwood] dd small').innerText(), '屏蔽池余额的 33.33%');
      assert(await page.evaluate(() => document.documentElement.scrollWidth === innerWidth), 'pool fixture overflow');
    }
    await page.unroute(selector);
  }
}

async function main() {
  assert(downloads, 'PHASE3_DOWNLOAD_DIR is required');
  const browser = await chromium.launch({headless: true, args: ['--no-sandbox'], executablePath: process.env.CHROMIUM_PATH});
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
      const fetchJson = file => page.request.get(base + 'datasets/' + file).then(r => r.json());
      const [charts, catalog, econ, pool] = await Promise.all([
        fetchJson('chart-data.json'), fetchJson('index.json'), fetchJson('network-economics.json'),
        fetchJson('zcash-pool-status.json'),
      ]);
      assert.equal(pool.status, 'unavailable');
      assert.deepEqual(Object.keys(pool).sort(), ['reason', 'status']);
      await page.locator('[data-pool-state=unavailable]').waitFor();
      assert.equal(await page.locator('#pools a[download]').count(), 0);
      assert((await page.locator('link[rel=icon]').getAttribute('href')).startsWith('data:'));
      await page.getByRole('heading', {name: '数据集目录'}).waitFor();
      assert.equal(await page.locator('#datasets article').count(), 4);
      await page.getByRole('link', {name: '数据集目录 ↘'}).click();
      assert.equal(new URL(page.url()).hash, '#datasets');

      for (const asset of ['xmr', 'zec']) {
        for (const [field, dataset] of [
          ['market_cap_usd', 'privacy_market_daily'], ['transaction_count', 'privacy_network_daily'],
          ['current_supply_native', 'privacy_network_daily'],
        ]) {
          const [day, value] = charts[dataset][asset][field].filter(([, v]) => v !== null).at(-1);
          const element = page.locator(`[data-asset="${asset}"] [data-metric="${field}"]`);
          assert.equal(await element.getAttribute('title'), value);
          assert.equal(await element.locator('..').locator(':scope > small').innerText(), day + ' UTC');
        }
      }

      for (const id of new Set(charts.privacy_protocol_registry.map(r => r.protocol_id))) {
        const rows = charts.privacy_protocol_registry.filter(r => r.protocol_id === id);
        const card = page.locator(`[data-protocol="${id}"]`);
        await card.locator('summary').click();
        assert.equal(await card.getByText('项目主页 ↗').getAttribute('href'), rows[0].website_url);
        assert.deepEqual(await card.locator('li code').allTextContents(), rows.map(row => row.deployment_address));
        for (const [index, row] of rows.entries()) {
          assert.equal(await card.getByText('部署文档 ↗').nth(index).getAttribute('href'), row.deployment_source_url);
          assert.match(await card.locator('li').nth(index).innerText(), new RegExp(row.verified_utc));
        }
        await card.locator('summary').click();
      }

      await page.getByLabel('市值时间范围').selectOption('all');
      await tooltip(page, '#compare', 'USD');
      for (const [section, metricLabel, fields, rangeLabel] of [
        ['#activity', '网络活动指标', ['transaction_count', 'tx_ma7', 'tx_ma30', 'block_count'], '网络活动时间范围'],
        ['#economics', '网络经济指标', ['fee_native', 'fee_mean_native', 'fee_usd', 'fee_mean_usd', 'issuance',
          'current_supply_native', 'supply_growth_365d'], '网络经济时间范围'],
      ]) {
        for (const field of fields) {
          await page.getByLabel(metricLabel).selectOption(field);
          const native = ['fee_native', 'fee_mean_native', 'issuance', 'current_supply_native'].includes(field);
          if (native) await page.getByLabel('原生币种').selectOption('zec');
          const chartCard = page.locator(`${section} [data-metric-id="${field}"]`);
          await chartCard.locator('canvas').first().waitFor();
          const series = await chartCard.locator('[data-series]').all();
          assert.equal(series.length, native ? 1 : 2);
          for (const card of series) {
            const asset = await card.getAttribute('data-series');
            const column = econ.columns.indexOf(field);
            const [day, value] = column >= 0 ?
              econ.series[asset].map(row => [row[0], row[column + 1]]).filter(([, v]) => v !== null).at(-1) :
              charts.privacy_network_daily[asset][field].filter(([, v]) => v !== null).at(-1);
            assert.equal(await card.getAttribute('data-date'), day);
            assert.equal(await card.getAttribute('data-value'), value);
          }
          assert.equal(await chartCard.locator('a[download]').count(), econ.columns.includes(field) ? 0 : 2);
        }
        await page.getByLabel(rangeLabel).selectOption('90');
        await page.getByLabel(rangeLabel).selectOption('all');
      }
      await tooltip(page, '#activity', '块');
      await tooltip(page, '#economics', '%');
      for (const [asset, unit] of [['xmr', 'H/s'], ['zec', 'GSol/s']]) {
        await page.getByLabel('算力网络').selectOption(asset);
        const section = page.locator('#design [data-metric-id=hashrate]');
        assert.equal(await section.locator('[data-series]').count(), 1);
        assert.equal(await section.locator('[data-series]').getAttribute('data-value'),
          econ.series[asset].at(-1)[econ.columns.indexOf('hashrate') + 1]);
        await page.getByLabel('算力时间范围').selectOption('90');
        await tooltip(page, '#design', unit);
      }
      await page.getByLabel('网络经济指标').selectOption('fee_mean_usd');
      await page.getByLabel('网络活动指标').selectOption('tx_ma30');
      assert.equal(await page.locator('.chart').count(), 4);
      for (const source of await page.locator('.chart-source a').all()) {
        assert.match(await source.getAttribute('href'), /^https:\/\/(github.com\/coinmetrics\/|creativecommons.org\/)/);
      }
      assert.match(await page.locator('#economics').innerText(), /UTC 日收盘参考价/);

      const hrefs = await page.locator('a[href^="/privacy-observatory/datasets/"]').evaluateAll(links =>
        [...new Set(links.map(link => link.href))]);
      assert.equal(hrefs.length, 22);
      for (const url of hrefs) {
        const response = await page.request.get(url);
        assert.equal(response.status(), 200, url);
        if (url.endsWith('.html')) {
          assert.match(await response.text(), /<h1>.+<\/h1>/);
        }
      }
      await dataDownloads(page, mode);
      assert.equal(catalog.filter(r => r.status === 'Blocked').length, 1);
      for (const resource of ['data/pools.json', 'datasets/zcash_value_pools_daily/zcash_value_pools_daily.csv',
        'datasets/zcash_value_pools_daily/zcash_value_pools_daily.parquet', 'datasets/audit_phase2/evidence.json',
        'datasets/_sources/coin_metrics_pages.json.gz', 'docs/v1.0-phase1/evidence.json']) {
        assert.equal((await page.request.get(base + resource)).status(), 404, resource);
      }
      assert(await page.evaluate(() => document.documentElement.scrollWidth === innerWidth), 'horizontal overflow');
      assert.deepEqual(failures, []);
      if (screenshots) {
        await fs.mkdir(screenshots, {recursive: true});
        await page.evaluate(() => window.scrollTo({top: 0, behavior: 'instant'}));
        await page.screenshot({path: path.join(screenshots, mode + '.png'), fullPage: true});
      }

      await poolStates(page);
      assert.deepEqual(failures, []);
      await page.route('**/datasets/network-economics.json', route => route.fulfill({status: 503, body: '{}'}));
      await page.reload();
      await page.getByText('部分研究数据暂不可用，缺失值保留为空。').waitFor();
      await page.locator('#economics .chart-empty').waitFor();
      assert.equal(await page.locator('#datasets a[download]').count(), 6);
      await page.route('**/datasets/chart-data.json', route => route.fulfill({status: 503, body: '{}'}));
      await page.reload();
      await page.getByText('部分研究数据暂不可用，缺失值保留为空。').waitFor();
      assert((await page.locator('[data-asset=xmr] [data-metric=market_cap_usd]').innerText()).includes('—'));
      await context.close();
      console.log(mode, width, height, 'metrics, 4 chart tooltips, 6 downloads, 22 links, pool states and layout passed');
    }
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
