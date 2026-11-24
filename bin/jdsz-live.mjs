#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { getApiContext, loadTemplate } from '../lib/api.mjs';
import { connectPage, getAllCookies, findCookie } from '../lib/cdp.mjs';
import { extractDate, datesBetween } from '../lib/extract.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');

function parse(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) { out._.push(a); continue; }
    const key = a.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith('--')) { out[key] = true; }
    else { out[key] = next; i++; }
  }
  return out;
}

function usage() {
  console.log(`jdsz-live — 京东商智达人直播数据取数 CLI

用法:
  node bin/jdsz-live.mjs doctor  [--cdp-port 9222] [--pin PIN]
  node bin/jdsz-live.mjs extract --from 2026-05-01 --to 2026-10-31 --out raw.json
  node bin/jdsz-live.mjs extract --date 2026-10-01,2026-10-02 --out raw.json

参数:
  --from / --to     日期范围（含首尾）
  --date            指定日期，逗号分隔，可重复
  --exclude         排除日期，逗号分隔
  --out             输出 JSON 路径，默认 raw.json
  --cdp-port        Chrome 调试端口，默认 9222
  --pin             商智 p-pin；默认读 JDSZ_PIN 或浏览器 pin Cookie
  --sleep           每日间隔毫秒，默认 120

前置:
  1. Chrome 以 --remote-debugging-port=9222 启动
  2. 已打开并登录 https://jdsz.jd.com
  3. Node >= 20（内置 fetch/WebSocket）

输出 JSON 结构: { days:[{date,creators,contents,products}], errors:[] }
`);
}

function splitList(v) {
  if (!v || v === true) return [];
  return String(v).split(',').map(s => s.trim()).filter(Boolean);
}

async function doctor(opts) {
  const port = Number(opts['cdp-port'] || 9222);
  const { cdp, target } = await connectPage(port);
  try {
    const cookies = await getAllCookies(port);
    const pin = opts.pin || process.env.JDSZ_PIN || findCookie(cookies, 'pin') || findCookie(cookies, 'ppzh_pin');
    console.log(JSON.stringify({
      ok: true,
      port,
      title: target.title,
      url: target.url,
      pin: pin || null,
      cookieCount: cookies.filter(c => c.domain.endsWith('jd.com')).length,
    }, null, 2));
  } finally {
    cdp.close();
  }
}

async function extract(opts) {
  const port = Number(opts['cdp-port'] || 9222);
  const from = opts.from;
  const to = opts.to;
  const single = splitList(opts.date);
  let dates;
  if (single.length) dates = single;
  else if (from && to) dates = datesBetween(from, to);
  else throw new Error('请提供 --from/--to 或 --date');
  const exclude = new Set(splitList(opts.exclude));
  dates = dates.filter(d => !exclude.has(d));
  if (!dates.length) throw new Error('没有待取日期');

  const out = path.resolve(opts.out || 'raw.json');
  const templates = {
    creator: loadTemplate(ROOT, 'creator'),
    content: loadTemplate(ROOT, 'content'),
    product: loadTemplate(ROOT, 'product'),
  };
  const ctx = await getApiContext({ port, pin: opts.pin });
  let state = { days: [], errors: [] };
  if (fs.existsSync(out)) {
    try { state = JSON.parse(fs.readFileSync(out, 'utf8')); } catch {}
  }
  const done = new Set(state.days.map(d => d.date));
  const queue = dates.filter(d => !done.has(d));
  console.error(`QUEUE ${queue.length} dates, pin=${ctx.pin}, out=${out}`);

  for (const date of queue) {
    try {
      const data = await extractDate(date, ctx, templates);
      state.days.push(data);
      state.days.sort((a, b) => a.date.localeCompare(b.date));
      fs.writeFileSync(out, JSON.stringify(state, null, 2), 'utf8');
      console.error(`OK ${date} creators=${data.creators.length} contents=${data.contents.length} products=${data.products.length}`);
    } catch (e) {
      console.error(`FAIL ${date}: ${e.message}`);
      state.errors.push({ date, error: e.message });
      fs.writeFileSync(out, JSON.stringify(state, null, 2), 'utf8');
    }
    const ms = Number(opts.sleep ?? 120);
    if (ms > 0) await new Promise(r => setTimeout(r, ms));
  }

  const summary = {
    out,
    dates: state.days.length,
    errors: state.errors.length,
    creators: state.days.reduce((n, d) => n + d.creators.length, 0),
    contents: state.days.reduce((n, d) => n + d.contents.length, 0),
    products: state.days.reduce((n, d) => n + d.products.length, 0),
  };
  console.log(JSON.stringify(summary, null, 2));
}

const opts = parse(process.argv.slice(2));
const cmd = opts._[0] || 'help';
try {
  if (cmd === 'doctor') await doctor(opts);
  else if (cmd === 'extract') await extract(opts);
  else { usage(); process.exit(cmd === 'help' ? 0 : 1); }
} catch (e) {
  console.error('ERROR', e.message);
  process.exit(1);
}
