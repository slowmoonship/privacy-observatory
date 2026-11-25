import assert from 'node:assert/strict';
import {test} from 'node:test';
import {poolView, percent, zecAmount, NU7_HEIGHT} from '../src/zcashSnapshot.ts';

const now = Date.parse('2026-11-24T14:01:00Z');
const fixture = {
  status: 'available', block_height: NU7_HEIGHT, block_hash: 'f'.repeat(64),
  block_timestamp: '2026-11-24T14:00:00Z', fetched_at: '2026-11-24T14:01:00Z',
  source: 'TEST fixture', source_url: 'https://example.invalid/', source_license: 'test only',
  chain_supply_zat: '100000001', transparent_zat: '30000000', lockbox_zat: '10000000',
  sprout_zat: '1', sapling_zat: '20000000', orchard_zat: '20000000', ironwood_zat: '20000000',
};

test('six-pool identity, shielded composition, units and NU7 frozen Sprout', () => {
  const view = poolView(fixture, now);
  assert.equal(view.state, 'current');
  assert.equal(view.total, 100000001n);
  assert.equal(view.shielded, 60000001n);
  assert.equal(poolView({...fixture, nsm_zat: '20000000'}, now).total, view.total);
  assert.equal(percent(view.shielded, view.total), '60.00%');
  assert.equal(percent(0n, 0n), '—');
  assert.equal(zecAmount(100000001n), '1.00000001');
  assert.equal(view.sproutFrozen, true);
  assert.equal(poolView({...fixture, block_height: NU7_HEIGHT - 1}, now).sproutFrozen, false);
});

test('missing, stale, invalid and unsafe snapshot data', () => {
  assert.equal(poolView({status: 'unavailable'}, now).state, 'unavailable');
  assert.equal(poolView(fixture, now + 49 * 3600000).state, 'stale');
  for (const changes of [{block_hash: 'no'}, {chain_supply_zat: '100000000'},
    {sprout_zat: 1}, {ironwood_zat: null}, {orchard_zat: '-1'},
    {fetched_at: '2026-12-01T00:00:00Z'}, {block_timestamp: '2026-02-30T00:00:00Z'},
    {source_url: 'javascript:void(0)'}]) {
    assert.throws(() => poolView({...fixture, ...changes}, now));
  }
});
