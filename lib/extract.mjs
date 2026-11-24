import { query, setDate, addFilter, clone, getContentAttrs, getSkuNames } from './api.mjs';

const CREATOR_DAY_IDX = 9;   // author_id + 19 metrics; 当日引导成交人数
const CONTENT_DAY_IDX = 12;  // content_id,type,cate,author_id + 8 metrics; 当日引导成交人数
const PRODUCT_DAY_IDX = 7;   // sku_id,author_id + 5 metrics; 当日引导成交人数
const CONTENT_TYPE = process.env.JDSZ_CONTENT_TYPE || '200'; // 200=直播，11=视频，图文见商智维度

const INTERACTION_METRICS = [
  'jdr_sch_content_valid_action_page_content__page_cnt_lead_view_zh',
  'jdr_sch_content_valid_action_page_content__page_qtty_lead_view_zh',
];
const sleep = ms => new Promise(r => setTimeout(r, ms));
const num = v => (v === null || v === undefined || v === '' ? null : Number(v));

async function retry(fn, label, tries = 4) {
  let last;
  for (let i = 0; i < tries; i++) {
    try { return await fn(); } catch (e) {
      last = e;
      console.error(`RETRY ${label} ${i + 1}/${tries}: ${e.message}`);
      await sleep(700 * (i + 1));
    }
  }
  throw last;
}

export async function extractDate(date, ctx, templates) {
  const t0 = Date.now();
  const cBody = clone(templates.creator);
  setDate(cBody, date);
  addFilter(cBody, 'content_type_cd', [CONTENT_TYPE], 'in');
  cBody.commonParam.pageSize = 1000;
  const cj = await retry(() => query(cBody, ctx), `creators ${date}`);
  const creatorsRaw = (cj.body?.data || []).filter(r => Number(r[CREATOR_DAY_IDX]) > 0);
  if (!creatorsRaw.length) {
    return { date, creators: [], contents: [], products: [] };
  }
  const authorIds = creatorsRaw.map(r => String(r[0]));

  const ct = clone(templates.content);
  setDate(ct, date);
  addFilter(ct, 'author_id', authorIds, 'in');
  addFilter(ct, 'content_type_cd', [CONTENT_TYPE], 'in');
  ct.dimList.push('author_id');
  ct.groupList.push('author_id');
  ct.attributeList.push('author_id');
  ct.commonParam.pageSize = 1000;
  const ctj = await retry(() => query(ct, ctx), `content ${date}`);
  const contentRows = ctj.body?.data || [];

  const it = clone(templates.content);
  setDate(it, date);
  addFilter(it, 'author_id', authorIds, 'in');
  addFilter(it, 'content_type_cd', [CONTENT_TYPE], 'in');
  it.dimList.push('author_id');
  it.groupList.push('author_id');
  it.attributeList.push('author_id');
  it.metricList = [...INTERACTION_METRICS];
  it.commonParam.sortField = INTERACTION_METRICS[0];
  it.commonParam.pageSize = 1000;
  const itj = await retry(() => query(it, ctx), `interaction ${date}`);
  const interMap = new Map((itj.body?.data || []).map(r => [`${r[3]}|${r[0]}`, [num(r[4]), num(r[5])]]));

  const posContent = contentRows.filter(r => Number(r[CONTENT_DAY_IDX]) > 0);

  const attrs = new Map();
  const authorName = new Map();
  if (posContent.length) {
    try {
      const aj = await retry(() => getContentAttrs({
        date,
        rows: posContent.map(r => ({ content_id: r[0], content_type_cd: r[1], author_id: r[3] })),
      }, ctx), `attrs ${date}`);
      for (const d of (aj.body?.data || [])) {
        const a = d.attrs || {};
        if (a.content_id) attrs.set(String(a.content_id), a);
        if (a.author_id && a.jdr_sch_content_author_name) {
          authorName.set(String(a.author_id), a.jdr_sch_content_author_name);
        }
      }
    } catch (e) {
      console.error(`ATTR FAIL ${date}: ${e.message}`);
    }
  }

  const creators = creatorsRaw.map(r => ({
    author: String(r[0]),
    authorName: authorName.get(String(r[0])) || '',
    metrics: r.slice(1, 20).map(num),
  }));

  const contents = posContent.map(r => {
    const cid = String(r[0]);
    const author = String(r[3]);
    const inter = interMap.get(`${author}|${cid}`) || [null, null];
    const m = r.slice(4, 23).map(num);
    return {
      author,
      authorName: authorName.get(author) || '',
      contentId: cid,
      contentName: attrs.get(cid)?.jdr_sch_content_name || '',
      publishTime: attrs.get(cid)?.jdr_sch_video_submit_tm || '',
      metrics: [...m.slice(0, 7), inter[0], inter[1], ...m.slice(7)],
    };
  });

  let products = [];
  if (posContent.length) {
    const contentIds = posContent.map(r => String(r[0]));
    const pt = clone(templates.product);
    setDate(pt, date);
    addFilter(pt, 'content_id', contentIds, 'in');
    pt.dimList.push('author_id');
    pt.groupList.push('author_id');
    pt.attributeList.push('author_id');
    pt.commonParam.pageSize = 1000;
    const ptj = await retry(() => query(pt, ctx), `product ${date}`);
    const posProducts = (ptj.body?.data || []).filter(r => Number(r[PRODUCT_DAY_IDX]) > 0);
    const skuNames = await getSkuNames(posProducts.map(r => String(r[0])), ctx);
    products = posProducts.map(r => {
      const author = String(r[1]);
      const sku = String(r[0]);
      return {
        author,
        authorName: authorName.get(author) || '',
        skuId: sku,
        skuName: skuNames.get(sku) || '',
        metrics: r.slice(2, 18).map(num),
      };
    });
  }

  console.error(`DONE ${date}: creators=${creators.length} contents=${contents.length} products=${products.length} in ${((Date.now()-t0)/1000).toFixed(1)}s`);
  return { date, creators, contents, products };
}

export function datesBetween(from, to) {
  const out = [];
  const d = new Date(from + 'T00:00:00Z');
  const stop = new Date(to + 'T00:00:00Z');
  while (d <= stop) {
    out.push(d.toISOString().slice(0, 10));
    d.setUTCDate(d.getUTCDate() + 1);
  }
  return out;
}
