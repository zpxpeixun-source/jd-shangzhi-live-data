---
name: jd-shangzhi-live-data
description: 从京东商智批量提取达人直播数据并写入 Excel 时使用；覆盖登录态 CDP、接口签名、直播/视频/图文内容类型识别、达人→点位→单品归因、历史补数/重拉、机构映射、校验和产出分析页。
whenToUse: 用户要求从京东商智取达人直播数据、补历史日期、重拉某几天、识别内容类型、更新机构、生成产出分析或校验数据完整性时。
---

# 京东商智达人直播数据

把商智后台的“内容概况(新)”数据，按 **日期 → 有产出的达人 → 该达人有产出的内容 → 这些内容下的商品** 取成三张表：

- `达人`：按日期 + 达人汇总
- `点位`：按日期 + 内容拆分
- `单品`：按日期 + SKU 拆分

只保留 `当日引导成交人数 > 0` 的记录。

## 前置条件

1. Chrome 以调试端口启动，并已登录 `https://jdsz.jd.com`：
   ```powershell
   chrome.exe --remote-debugging-port=9222 --user-data-dir="$PWD\.browser-profile" https://jdsz.jd.com/
   ```
2. Node.js ≥ 20（使用内置 `fetch` 和 `WebSocket`，无 npm 依赖）。
3. Python ≥ 3.10，且安装 `openpyxl`。
4. 取得当前商家的 `p-pin`：优先读环境变量 `JDSZ_PIN`，否则读浏览器 `pin` Cookie。

先自检：

```bash
node bin/jdsz-live.mjs doctor --cdp-port 9222
```

## 取数

```bash
# 单日/多日
node bin/jdsz-live.mjs extract --date 2026-10-01,2026-10-02 --out raw.json

# 日期范围
node bin/jdsz-live.mjs extract --from 2026-05-01 --to 2026-10-31 --out raw.json

# 排除已有日期
node bin/jdsz-live.mjs extract --from 2026-05-01 --to 2026-11-23 \
  --exclude 2026-10-01,2026-10-02 --out raw.json
```

输出结构：

```json
{
  "days": [
    {
      "date": "2026-10-01",
      "creators": [{"author": "...", "authorName": "...", "metrics": [19 个指标]}],
      "contents": [{"author": "...", "contentId": "...", "contentName": "...", "metrics": [21 个指标]}],
      "products": [{"author": "...", "skuId": "...", "skuName": "...", "metrics": [16 个指标]}]
    }
  ],
  "errors": []
}
```

默认只取**直播**：`lib/extract.mjs` 会给达人、内容、互动查询加 `content_type_cd=200` 过滤。类型编码：

- `200` = 直播
- `11` = 视频
- `25` = 图文

如果已有内容 ID 需要补类型（例如历史表混入了视频/图文），用批量类型查询：

```bash
node bin/jdsz-live.mjs types \
  --ids content_ids.json \
  --from 2026-05-01 --to 2026-11-23 \
  --out content_type_map.json
```

`content_ids.json` 是内容 ID 数组，输出是 `{内容ID: 类型编码}`。用这个映射给 `点位` 加“内容类型”列，再按类型拆标签页。

**单品类型**：只有同一达人同一天仅一种内容类型时才能直接映射；若同一天既有直播又有视频，SKU 金额是合并的，需按内容类型分别查单品。拆分后若各类型金额之和大于原合并金额，说明订单被多类型重复归因，应保留“混合”并保留原金额，不要强行分配。

## 写入工作簿

```bash
python scripts/merge_workbook.py \
  --workbook "往期数据补录.xlsx" \
  --raw raw.json \
  --out "往期数据补录-更新.xlsx" \
  --replace-dates auto \
  --org-override 12345678=店播
```

- `--replace-dates auto`：删除 raw 中出现日期的旧行，再整段替换，适合“重拉”。
- `--replace-dates 2026-10-01,...`：只替换指定日期。
- 不传：只追加，同键去重。
- 机构优先级：`--org-override` → `背景` 表 → 原表达人机构 → `未知`。
- 会按日期排序、补空白机构/名称、去掉 `#N/A` 占位行、冻结表头。

## 生成分析页

```bash
python scripts/add_analysis.py \
  --workbook "往期数据补录-更新.xlsx" \
  --out "往期数据补录-分析版.xlsx"
```

新增 `产出分析` sheet：KPI、关键洞察、月度产出、达人排行、每日时间线、商品排行，以及月度趋势、达人 Top10、商品 Top10 三张图。

## 校验

```bash
python scripts/validate_workbook.py \
  --workbook "往期数据补录-分析版.xlsx" \
  --from 2026-05-01 --to 2026-11-23 \
  --org-override 12345678=店播 \
  --json-out validation.json
```

检查日期覆盖、排序、重复键、空值、`#N/A`、达人/单品金额勾稽、店铺自播机构。

## 关键口径

- **内容类型**：主表只保留 `content_type_cd=200` 直播；视频/图文不要混入直播汇总。
- 三层过滤：达人 `当日引导成交人数 > 0` → 内容 `> 0` → 单品 `> 0`。
- 单品查询必须限定同一达人下的内容 ID，不能跨达人混查。
- 点位金额可能因同一订单被多条内容重复归因而高于达人/单品，这是商智口径。
- 接口是异步离线数据，历史日期可能返回 0 条；0 条日期不要伪造行。
- `7日/15日` 是窗口指标，跨日求和不具备可加性；分析页只用当日金额做汇总。
- 商智接口和签名盐可能改版；若 `doctor` 正常但查询报签名/权限错，重新抓包更新 `templates/*.json` 和 `lib/api.mjs` 中的 `SALT`。

## 接口摘要

- 查询：`POST https://zhgateway.jd.com/szpaas/lowcode/brandajax/query/contentNewSummary.ajax`
- 名称：`POST /szpaas/brandajax/common/getDimensionAttr.ajax`
- 商品名：`POST /szpaas/brandajax/common/getSkuImg.ajax`（form: `proId=...`）
- 签名：`md5(path + uuid + timestamp + SALT)`，Query 带 `User-mup/User-mnp/uuid`，Header 带 `p-pin`。

## 安全

- 不把 Cookie、`p-pin`、账号密码写进 skill 或仓库。
- 只使用已登录会话，不绕过验证码/短信验证。
- 不直接覆盖原表；始终写新文件，保留备份。
- 运行前确认目标工作簿的表头与列顺序符合 `scripts/merge_workbook.py` 中的约定。

