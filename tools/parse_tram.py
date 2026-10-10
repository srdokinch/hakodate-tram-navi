"""函館市電の停留場別時刻表(Excel HTML)を解析して JSON にする。
使い方: python3 parse_tram.py <html_dir> > tram.json
"""
import html, json, re, sys, glob, os

def cells_of(row):
    out, col = [], 0
    for m in re.finditer(r'<td([^>]*)>(.*?)</td>', row, re.S):
        attrs, body = m.group(1), m.group(2)
        span = int((re.search(r'colspan=(\d+)', attrs) or [0, 1])[1])
        txt = html.unescape(re.sub(r'<[^>]+>', '', body))
        txt = re.sub(r'\s+', ' ', txt).strip()
        out.append((col, span, txt))
        col += span
    return out

def parse_sheet(path):
    t = open(path, 'rb').read().decode('cp932', errors='replace')
    t = re.sub(r"<span\s+style='display:none'>.*?</span>", '', t, flags=re.S)
    rows = [cells_of(r) for r in re.findall(r'<tr[^>]*>(.*?)</tr>', t, re.S)]
    blocks, cur = [], None
    for cells in rows:
        texts = [c[2] for c in cells]
        joined = ' '.join(texts)
        m = re.search(r'停留場名：', joined)
        if m:
            name = next((x for x in texts if '[標柱' in x), '')
        if '区分：' in joined:
            kind = 'weekday' if '平日' in joined else 'holiday'
            stop_name, pole = re.match(r'(.+?) \[標柱 (\d+)\]', name).groups()
            code = next((x for x in texts if re.fullmatch(r'DY\d+', x)), '')
            cur = {'kind': kind, 'stop': stop_name, 'pole': int(pole), 'code': code, 'routes': [], 'notes': ''}
            blocks.append(cur)
            continue
        if cur is None:
            continue
        if texts and texts[0].startswith('系統'):
            cur['routes'] = [{'route': c[2], 'from': c[0], 'to_col': c[0] + c[1], 'deps': []}
                             for c in cells[1:-1] if c[2]]
        elif texts and texts[0].startswith('行先'):
            for r, c in zip(cur['routes'], [c for c in cells[1:-1] if c[2]]):
                r['dest'] = re.sub(r'\s*\(.*\)', '', c[2]).strip()
        elif texts and texts[0].startswith('経由'):
            for r, c in zip(cur['routes'], [c for c in cells[1:-1] if c[2]]):
                r['via'] = re.sub(r'\s*\(.*\)', '', c[2]).strip()
        elif texts and texts[0] == '適用':
            cur['notes'] = ' '.join(texts[1:-1])
        else:
            hm = re.fullmatch(r'([0-9０-９]+)時', texts[0] if texts else '')
            if hm:
                hour = int(hm.group(1).translate(str.maketrans('０１２３４５６７８９', '0123456789')))
                for col, span, txt in cells[1:-1]:
                    for tok in re.findall(r'([^\d,\s]*)(\d{1,2})', txt):
                        flag, mm = tok
                        r = next((r for r in cur['routes'] if r['from'] <= col < r['to_col']), None)
                        if r is None:
                            print(f'WARN unmatched {path} {hour}:{mm} col={col}', file=sys.stderr)
                            continue
                        r['deps'].append([hour * 60 + int(mm), flag])
    return blocks

def main(d):
    res = []
    for p in sorted(glob.glob(os.path.join(d, '[0-9][0-9]-[0-9].html'))):
        for b in parse_sheet(p):
            for r in b['routes']:
                r.pop('from'); r.pop('to_col')
                r['deps'].sort()
            res.append(b)
    json.dump(res, sys.stdout, ensure_ascii=False)

if __name__ == '__main__':
    main(sys.argv[1])
