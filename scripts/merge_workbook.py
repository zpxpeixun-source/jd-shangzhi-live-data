#!/usr/bin/env python3
"""把 jdsz-live 生成的 raw JSON 写入既有工作簿。

示例:
  python scripts/merge_workbook.py --workbook 原表.xlsx --raw raw.json \
      --out 新表.xlsx --replace-dates auto --org-override 12345678=店播

说明:
  --replace-dates auto  删除 raw 中出现的所有日期后整段替换（推荐重拉）
  --replace-dates 2026-10-01,...  只替换指定日期
  不传 --replace-dates  则只追加 raw 中的日期（同键去重）
"""
import argparse
import json
import re
from collections import Counter
from copy import copy
from datetime import date, datetime, timedelta
from openpyxl import load_workbook

SHEETS = {
    '达人': dict(ncols=23, dcol=2, acol=3, ncol=4, ocol=1,
                 key=lambda v: (v[1], str(v[2]))),
    '点位': dict(ncols=27, dcol=4, acol=1, ncol=2, ocol=3,
                 key=lambda v: (v[3], str(v[4]))),
    '单品': dict(ncols=23, dcol=5, acol=1, ncol=2, ocol=3,
                 key=lambda v: (v[4], str(v[0]), str(v[5]))),
}


def norm_date(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.strftime('%Y-%m-%d')
    if isinstance(v, date):
        return v.strftime('%Y-%m-%d')
    if isinstance(v, (int, float)) and 20000 < float(v) < 80000:
        return (datetime(1899, 12, 30) + timedelta(days=float(v))).strftime('%Y-%m-%d')
    s = str(v).strip()
    m = re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})', s)
    if m:
        return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    if s.isdigit() and 20000 < int(s) < 80000:
        return (datetime(1899, 12, 30) + timedelta(days=int(s))).strftime('%Y-%m-%d')
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workbook', required=True)
    ap.add_argument('--raw', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--replace-dates', default='')
    ap.add_argument('--org-override', action='append', default=[],
                    help='ID=机构，可重复，例如 12345678=店播')
    ap.add_argument('--background-sheet', default='背景')
    args = ap.parse_args()

    raw = json.load(open(args.raw, encoding='utf-8'))
    days = raw.get('days', [])
    all_dates = {d['date'] for d in days}
    if args.replace_dates == 'auto':
        replace = all_dates
    elif args.replace_dates:
        replace = {x.strip() for x in args.replace_dates.split(',') if x.strip()}
    else:
        replace = set()

    overrides = {}
    for item in args.org_override:
        if '=' in item:
            k, v = item.split('=', 1)
            overrides[str(k).strip()] = v.strip()

    wb = load_workbook(args.workbook, data_only=False)
    bg = wb[args.background_sheet]
    org_map, bg_name = {}, {}
    for r in range(2, bg.max_row + 1):
        a, o, n = bg.cell(r, 1).value, bg.cell(r, 2).value, bg.cell(r, 4).value
        if a not in (None, ''):
            k = str(a).strip()
            if o not in (None, ''):
                org_map.setdefault(k, str(o).strip())
            if n not in (None, ''):
                bg_name.setdefault(k, str(n).strip())

    ws = wb['达人']
    existing_org, existing_name = {}, {}
    for r in range(2, ws.max_row + 1):
        a, o, n = ws.cell(r, 3).value, ws.cell(r, 1).value, ws.cell(r, 4).value
        if a not in (None, ''):
            k = str(a).strip()
            if o not in (None, '', '#N/A'):
                existing_org.setdefault(k, str(o).strip())
            if n not in (None, '', '#N/A'):
                existing_name.setdefault(k, str(n).strip())

    def resolve_org(a):
        k = str(a)
        return overrides.get(k) or org_map.get(k) or existing_org.get(k) or '未知'

    def resolve_name(a, n):
        return n if n not in (None, '', '#N/A') else (existing_name.get(str(a)) or bg_name.get(str(a)) or '')

    new_rows = {'达人': [], '点位': [], '单品': []}
    for day in days:
        dt = day['date']
        for x in day.get('creators', []):
            new_rows['达人'].append([resolve_org(x['author']), dt, str(x['author']),
                                    resolve_name(x['author'], x.get('authorName', '')), *x['metrics']])
        for x in day.get('contents', []):
            new_rows['点位'].append([str(x['author']), resolve_name(x['author'], x.get('authorName', '')),
                                    resolve_org(x['author']), dt, str(x['contentId']),
                                    x.get('contentName', ''), *x['metrics']])
        for x in day.get('products', []):
            new_rows['单品'].append([str(x['author']), resolve_name(x['author'], x.get('authorName', '')),
                                    resolve_org(x['author']), '', dt, int(x['skuId']),
                                    x.get('skuName') or '未知', *x['metrics']])

    report = {'replace': sorted(replace), 'sheets': {}}
    for name, cfg in SHEETS.items():
        ws = wb[name]
        template = [copy(ws.cell(2, c)._style) for c in range(1, cfg['ncols'] + 1)]
        keep = []
        removed = 0
        for r in range(2, ws.max_row + 1):
            v = [ws.cell(r, c).value for c in range(1, cfg['ncols'] + 1)]
            d = norm_date(v[cfg['dcol'] - 1])
            if not d:
                continue
            v[cfg['dcol'] - 1] = d
            author = v[cfg['acol'] - 1]
            v[cfg['ocol'] - 1] = resolve_org(author)
            v[cfg['ncol'] - 1] = resolve_name(author, v[cfg['ncol'] - 1])
            if name == '单品' and not v[6]:
                v[6] = '未知'
            if d in replace:
                removed += 1
                continue
            keep.append(v)

        rows = keep + new_rows[name]
        best, order = {}, []
        for v in rows:
            k = cfg['key'](v)
            score = sum(1 for x in v if x not in (None, ''))
            if k not in best:
                best[k] = (score, v)
                order.append(k)
            elif score > best[k][0]:
                best[k] = (score, v)
        rows = sorted((best[k][1] for k in order), key=lambda v: v[cfg['dcol'] - 1])

        if ws.max_row > 1:
            ws.delete_rows(2, ws.max_row - 1)
        for i, v in enumerate(rows, 2):
            for c, val in enumerate(v, 1):
                cell = ws.cell(i, c)
                cell.value = val
                cell._style = copy(template[c - 1])
        ws.freeze_panes = 'A2'
        report['sheets'][name] = {'kept': len(keep), 'removed': removed,
                                  'added': len(new_rows[name]), 'final': len(rows)}

    wb.save(args.out)
    report['out'] = args.out
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

