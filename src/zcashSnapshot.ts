export const shieldedPools = ['sprout', 'sapling', 'orchard', 'ironwood'] as const;
export const valuePools = [...shieldedPools, 'transparent', 'lockbox'] as const;
export const NU7_HEIGHT = 3543405;
const zatoshiPerZec = 100000000n;

type Pool = typeof valuePools[number];
type Snapshot = {
  status: 'available';
  block_height: number;
  block_hash: string;
  block_timestamp: string;
  fetched_at: string;
  chain_supply_zat: string;
  source: string;
  source_url: string;
  source_license: string;
} & Record<`${Pool}_zat`, string>;

export function zecAmount(value: bigint) {
  const fraction = (value % zatoshiPerZec).toString().padStart(8, '0').replace(/0+$/, '');
  return (value / zatoshiPerZec).toLocaleString('zh-CN') + (fraction ? '.' + fraction : '');
}

export function percent(value: bigint, total: bigint) {
  if (total === 0n) return '—';
  const scaled = (value * 10000n + total / 2n) / total;
  return `${scaled / 100n}.${(scaled % 100n).toString().padStart(2, '0')}%`;
}

function parseZatoshi(value: unknown) {
  if (typeof value !== 'string' || !/^(0|[1-9][0-9]{0,15})$/.test(value)) throw Error('zatoshi');
  return BigInt(value);
}

function parseTime(value: unknown) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value)) {
    throw Error('UTC timestamp');
  }
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp) || new Date(timestamp).toISOString().slice(0, 19) !== value.slice(0, 19)) {
    throw Error('UTC timestamp');
  }
  return timestamp;
}

export function poolView(input: unknown, now = Date.now()) {
  if (!input || typeof input !== 'object' || !('status' in input)) throw Error('snapshot');
  if (input.status === 'unavailable') {
    const reason = 'reason' in input && typeof input.reason === 'string' ? input.reason : '当前没有经过核验的区块快照。';
    return {state: 'unavailable' as const, reason};
  }
  if (input.status !== 'available') throw Error('status');
  const snapshot = input as Snapshot;
  if (!Number.isSafeInteger(snapshot.block_height) || snapshot.block_height < 1 ||
      typeof snapshot.block_hash !== 'string' || !/^[a-f0-9]{64}$/.test(snapshot.block_hash) ||
      typeof snapshot.source !== 'string' || !snapshot.source ||
      typeof snapshot.source_license !== 'string' || !snapshot.source_license ||
      typeof snapshot.source_url !== 'string' || new URL(snapshot.source_url).protocol !== 'https:') {
    throw Error('source or block identity');
  }
  const blockTime = parseTime(snapshot.block_timestamp);
  const fetched = parseTime(snapshot.fetched_at);
  const tolerance = 5 * 60 * 1000;
  if (blockTime > fetched + tolerance || fetched > now + tolerance) throw Error('observation time');
  const total = parseZatoshi(snapshot.chain_supply_zat);
  const balances = valuePools.map(pool => ({pool, balance: parseZatoshi(snapshot[`${pool}_zat`])}));
  if (total === 0n || balances.reduce((sum, item) => sum + item.balance, 0n) !== total) throw Error('pool accounting');
  const shielded = shieldedPools.reduce((sum, pool) => sum + parseZatoshi(snapshot[`${pool}_zat`]), 0n);
  return {state: now - blockTime > 48 * 3600000 ? 'stale' as const : 'current' as const,
    snapshot, total, shielded, balances, sproutFrozen: snapshot.block_height >= NU7_HEIGHT};
}
