# 京东商智达人直播取数工具

从已登录的京东商智后台批量提取“达人 / 点位 / 单品”数据，写入 Excel，并可生成产出分析页。

仓库：<https://github.com/zpxpeixun-source/jd-shangzhi-live-data>

不依赖 npm 包；Node 只负责浏览器会话和接口取数，Python + openpyxl 负责写表和校验。

## 安装为 DSH skill

DSH 会扫描 `<dshHome>/skills/<name>/SKILL.md`。直接克隆到用户 skill 目录：

```powershell
git clone https://github.com/zpxpeixun-source/jd-shangzhi-live-data.git `
  "$HOME\.dsh\skills\jd-shangzhi-live-data"
```

新开会话后可用 `/jd-shangzhi-live-data` 调用，模型也会按 `description` 自动发现。

## 目录

```text
bin/jdsz-live.mjs          取数 CLI
lib/cdp.mjs                Chrome CDP 连接、Cookie 读取
lib/api.mjs                商智接口签名与查询
lib/extract.mjs            单日“达人→内容→单品”提取
templates/*.json           接口请求模板（改版时重抓）
scripts/merge_workbook.py  写表/替换日期/机构映射/排序
scripts/add_analysis.py    生成“产出分析”sheet 和图表
scripts/validate_workbook.py 数据完整性校验
```

## 环境

- Node.js 20+
- Python 3.10+
- `pip install openpyxl`

## 1. 准备已登录的浏览器

Chrome 需要开启调试端口：

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir="$PWD\.jdsz-browser" `
  https://jdsz.jd.com/
```

在弹出的窗口里完成扫码/账号登录。后续会话可复用同一个 `user-data-dir`。

设置 `p-pin`（也可不设，工具会读浏览器里的 `pin` Cookie）：

```powershell
$env:JDSZ_PIN = "你的商家pin"
```

自检：

```bash
node bin/jdsz-live.mjs doctor --cdp-port 9222
```

## 2. 取数

```bash
# 指定日期
node bin/jdsz-live.mjs extract --date 2026-10-01,2026-10-02 --out raw.json

# 日期范围
node bin/jdsz-live.mjs extract --from 2026-05-01 --to 2026-11-23 --out raw.json

# 排除已有日期
node bin/jdsz-live.mjs extract --from 2026-05-01 --to 2026-11-23 \
  --exclude 2026-10-01,2026-10-02 --out raw.json
```

输出为 UTF-8 JSON，结构见 `docs/data-contract.md`。

## 3. 写入 Excel

```bash
python scripts/merge_workbook.py \
  --workbook "往期数据补录.xlsx" \
  --raw raw.json \
  --out "往期数据补录-更新.xlsx" \
  --replace-dates auto \
  --org-override 12345678=店播
```

`--replace-dates auto` 会删除 raw 中出现日期的旧行并替换；不传则追加。

## 4. 分析页

```bash
python scripts/add_analysis.py \
  --workbook "往期数据补录-更新.xlsx" \
  --out "往期数据补录-分析版.xlsx"
```

## 5. 校验

```bash
python scripts/validate_workbook.py \
  --workbook "往期数据补录-分析版.xlsx" \
  --from 2026-05-01 --to 2026-11-23 \
  --org-override 12345678=店播
```

## 给其他产品的调用方式

推荐把取数和写表拆成两步：

1. 调 `bin/jdsz-live.mjs extract`，拿 `raw.json`（纯数据，不含 Cookie）。
2. 调 `scripts/merge_workbook.py` / `add_analysis.py`，输出 xlsx。

CLI 的 stdout 最后一行是 JSON 摘要，可直接解析；进度日志在 stderr。

## 限制

- 需要本机有可调试、已登录的 Chrome；不处理验证码/短信。
- 接口、签名盐、字段顺序可能随商智改版变化；此时用 `templates/` 重新抓包并更新 `lib/api.mjs`。
- `点位` 金额会因同一订单被多条内容重复归因而高于 `达人/单品`，这是平台口径。
- `7日/15日` 指标不可跨日累加，工具只对“当日引导成交金额”做汇总。
- 不直接改原表；始终写新文件。

