import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { getAllCookies, cookieHeader, findCookie } from './cdp.mjs';

export const API_PATH = '/szpaas/lowcode/brandajax/query/contentNewSummary.ajax';
export const SALT = '372ad2c2b6'; // 商智前端签名盐，页面改版时可能变化
const GATEWAY = 'https://zhgateway.jd.com';
const REFERER = 'https://jdsz.jd.com/brandweb/brand/view/contentMarketing/contentSummary.html';

export async function getApiContext({ port = 9222, pin = process.env.JDSZ_PIN } = {}) {
  const cookies = await getAllCookies(port);
  const resolvedPin = pin || findCookie(cookies, 'pin') || findCookie(cookies, 'ppzh_pin');
  if (!resolvedPin) throw new Error('未找到 pin，请先登录商智，或设置 JDSZ_PIN。');
  return {
    port,
    pin: resolvedPin,
    cookie: cookieHeader(cookies),
    cookies,
  };
}

export function loadTemplate(rootDir, name) {
  const p = path.join(rootDir, 'templates', `${name}.json`);
  return JSON.parse(fs.readFileSync(p, 'utf8').replace(/^\uFEFF/, ''));
}

export function clone(o) { return JSON.parse(JSON.stringify(o)); }

export function setDate(body, date) {
  for (const f of body.filterList || []) {
    if (f.propertyName === 'dt') f.values = [date];
  }
  body.commonParam.traceId = crypto.randomUUID();
  body.commonParam.batchId = crypto.randomUUID();
  return body;
}

export function addFilter(body, propertyName, values, op = 'in') {
  body.filterList = (body.filterList || []).filter(f => f.propertyName !== propertyName);
  body.filterList.push({ propertyName, values: values.map(String), op, type: 'string' });
  return body;
}

function headers(ctx) {
  return {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
    'resAppKey': 'lowcode5061',
    'p-pin': ctx.pin,
    'Referer': REFERER,
    'Origin': 'https://jdsz.jd.com',
    'Cookie': ctx.cookie,
  };
}

function signedUrl(apiPath, ctx) {
  const uuid = crypto.randomUUID();
  const ts = Date.now();
  const mnp = crypto.createHash('md5').update(apiPath + uuid + ts + SALT).digest('hex');
  return `${GATEWAY}${apiPath}?User-mup=${ts}&User-mnp=${mnp}&uuid=${uuid}`;
}

async function parse(res, label) {
  const text = await res.text();
  let json;
  try { json = JSON.parse(text); } catch {
    throw new Error(`${label}: HTTP ${res.status}, 非 JSON: ${text.slice(0, 200)}`);
  }
  const code = String(json.header?.code);
  if (!['0', '200', '2000'].includes(code)) {
    throw new Error(`${label}: code=${json.header?.code} ${json.header?.desc || ''} ${text.slice(0, 200)}`);
  }
  return json;
}

export async function signedPost(apiPath, body, ctx) {
  const res = await fetch(signedUrl(apiPath, ctx), {
    method: 'POST',
    headers: headers(ctx),
    body: JSON.stringify(body),
  });
  return parse(res, apiPath);
}

export async function signedForm(apiPath, params, ctx) {
  const res = await fetch(signedUrl(apiPath, ctx), {
    method: 'POST',
    headers: { ...headers(ctx), 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams(params),
  });
  return parse(res, apiPath);
}

export async function query(body, ctx) {
  return signedPost(API_PATH, body, ctx);
}

export async function getContentAttrs({ date, rows }, ctx) {
  return signedPost('/szpaas/brandajax/common/getDimensionAttr.ajax', {
    dimName: 'jdr_sch_content_entity',
    expandParam: {
      startTime: date,
      endTime: date,
      time_interval: 'BY_DAY',
      data: rows.map(r => ({
        content_id: String(r.content_id),
        content_type_cd: String(r.content_type_cd),
        author_id: String(r.author_id),
      })),
    },
  }, ctx);
}

export async function getSkuNames(skuIds, ctx) {
  const out = new Map();
  const ids = [...new Set(skuIds.map(String))];
  for (let i = 0; i < ids.length; i += 100) {
    const batch = ids.slice(i, i + 100);
    const j = await signedForm('/szpaas/brandajax/common/getSkuImg.ajax', { proId: batch.join(',') }, ctx);
    for (const d of (j.body?.data || [])) out.set(String(d.ProId), d.ProName || '');
  }
  return out;
}
