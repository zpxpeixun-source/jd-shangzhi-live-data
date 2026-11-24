#!/usr/bin/env python3
"""校验达人直播工作簿的日期、重复键、空值和金额勾稽。

示例:
  python scripts/validate_workbook.py --workbook 新表.xlsx \
      --from 2026-05-01 --to 2026-11-23 --org-override 12345678=店播
"""
import argparse
import json
from collections import Counter
from datetime import date, timedelta
from openpyxl import load_workbook

SPECS = {
    '达人': dict(dcol=2, acol=3, ncol=4, ocol=1, amount=12, key=(2, 3)),
    '点位': dict(dcol=4, acol=1, ncol=2, ocol=3, amount=16, key=(4, 5)),
    '单品': dict(dcol=5, acol=1, ncol=2, ocol=3, amount=12, key=(5, 1, 6)),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workbook', required=True)
    ap.add_argument('--from', dest='start')
    ap.add_argument('--to', dest='end')
    ap.add_argument('--org-override', action='append', default=[])
    ap.add_argument('--json-out')
    args = ap.parse_args()

    overrides = {}
    for item in args.org_override:
        if '=' in item:
            k, v = item.split('=', 1)
            overrides[k.strip()] = v.strip()

    wb = load_workbook(args.workbook, data_only=True)
    report = {'workbook': args.workbook, 'sheets': {}}
    for name, s in SPECS.items():
        ws = wb[name]
        dates, keys, blanks, na = [], [], Counter(), 0
        for r in range(2, ws.max_row + 1):
            v = [ws.cell(r, c).value for c in range(1, ws.max_column + 1)]
            if v[s['dcol'] - 1] is None:
                continue
            d = str(v[s['dcol'] - 1])[:10]
            dates.append(d)
            keys.append(tuple(str(ws.cell(r, c).value) for c in s['key']))
            for label, col in [('author', s['acol']), ('name', s['ncol']), ('org', s['ocol'])]:
                if not ws.cell(r, col).value:
                    blanks[label] += 1
            na += sum(1 for x in v if x == '#N/A')
        report['sheets'][name] = {
            'rows': len(dates),
            'days': len(set(dates)),
            'min': min(dates) if dates else None,
            'max': max(dates) if dates else None,
            'ordered': dates == sorted(dates),
            'duplicates': len(keys) - len(set(keys)),
            'blanks': dict(blanks),
            'na_cells': na,
            'amount_total': round(sum((ws.cell(r, s['amount']).value or 0) for r in range(2, ws.max_row + 1)), 2),
        }

    if args.start and args.end:
        expected = []
        d = date.fromisoformat(args.start)
        stop = date.fromisoformat(args.end)
        while d <= stop:
            expected.append(d.isoformat())
            d += timedelta(days=1)
        for name, s in SPECS.items():
            got = set()
            ws = wb[name]
            for r in range(2, ws.max_row + 1):
                v = ws.cell(r, s['dcol']).value
                if v is not None:
                    got.add(str(v)[:10])
            report['sheets'][name]['missing_dates'] = [x for x in expected if x not in got]

    for sid, org in overrides.items():
        report.setdefault('org_overrides', {})[sid] = {}
        for name, s in SPECS.items():
            ws = wb[name]
            vals = Counter(ws.cell(r, s['ocol']).value for r in range(2, ws.max_row + 1)
                           if str(ws.cell(r, s['acol']).value) == sid)
            report['org_overrides'][sid][name] = {'rows': sum(vals.values()), 'orgs': dict(vals)}

    report['amount_match'] = abs(report['sheets']['达人']['amount_total'] - report['sheets']['单品']['amount_total']) < 0.01
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.json_out:
        open(args.json_out, 'w', encoding='utf-8').write(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

