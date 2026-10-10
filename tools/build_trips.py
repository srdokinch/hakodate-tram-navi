"""parse_tram.py の出力(停留場別時刻)を列車単位の運行(trip)に組み立てる。
使い方: python3 build_trips.py tram.json > trips.json
"""
import json, sys

TRUNK = ['湯の川', '湯の川温泉', 'アリーナ前', '駒場車庫前', '競馬場前', '深堀町', '柏木町', '杉並町',
         '五稜郭公園前', '中央病院前', '千代台', '堀川町', '昭和橋', '千歳町', '新川町', '松風町',
         '函館駅前', '市役所前', '魚市場通', '十字街']
B5 = ['末広町', '大町', '函館どつく前']
B2 = ['宝来町', '青柳町', '谷地頭']
STOPS = TRUNK + B5 + B2
TERM_FLAG = {'末': '末広町', '駅': '函館駅前'}
MAXGAP = 5

def stop_deps(data, kind, stop, pole):
    """[(time, routes(set), flag, dest)] を返す。"""
    out = []
    for b in data:
        if b['kind'] == kind and b['stop'] == stop and b['pole'] == pole:
            for r in b['routes']:
                routes = set(r['route'].split())
                for t, f in r['deps']:
                    out.append((t, routes, f, r.get('dest')))
    return sorted(out, key=lambda x: x[0])

def chain(data, kind, seq, pole, warn, active=None):
    """seq の順に停留場をたどって trip を作る。active は途中から合流する運行。"""
    active = list(active or [])
    trips = []
    for stop in seq:
        deps = stop_deps(data, kind, stop, pole)
        used = set()
        # 到着済み(終点到達)の trip を確定
        for tr in list(active):
            if tr['end'] == stop:
                active.remove(tr)
        nxt = []
        for tr in sorted(active, key=lambda x: x['times'][-1][1]):
            last = tr['times'][-1][1]
            cand = [i for i, d in enumerate(deps) if i not in used and last + 1 <= d[0] <= last + MAXGAP
                    and (tr['routes'] & d[1])]
            if not cand:
                if any(tr['routes'] & d[1] for d in deps):
                    warn.append(f"{kind} pole{pole} {stop}: trip from {tr['times'][0]} lost at {last}")
                continue
            i = cand[0]
            used.add(i)
            tr['times'].append((stop, deps[i][0]))
            if len(deps[i][1]) == 1:
                tr['routes'] = deps[i][1]
            nxt.append(tr)
        for i, d in enumerate(deps):
            if i in used:
                continue
            end = TERM_FLAG.get(d[2]) or d[3]
            tr = {'routes': set(d[1]), 'times': [(stop, d[0])], 'low': d[2] == '低', 'end': end, 'flag': d[2]}
            trips.append(tr)
            nxt.append(tr)
        active = nxt
    return trips, active

def main(path):
    data = json.load(open(path))
    # 十字街の⑤列が2つに割れているのを統合(行先 None → 函館どつく前)
    for b in data:
        for r in b['routes']:
            if not r.get('dest'):
                r['dest'] = '函館どつく前' if '⑤' in r['route'] else '谷地頭'
    warn, result = [], {}
    for kind in ('weekday', 'holiday'):
        trips = []
        # 下り(湯の川→)
        trunk, act = chain(data, kind, TRUNK, 1, warn)
        b5, _ = chain(data, kind, B5, 1, warn, [t for t in act if '⑤' in t['routes']])
        b2, _ = chain(data, kind, B2, 1, warn, [t for t in act if '②' in t['routes']])
        down = trunk + b5 + b2
        # 上り(→湯の川): 両支線を十字街で合流させる
        u5, a5 = chain(data, kind, list(reversed(B5)), 2, warn)
        u2, a2 = chain(data, kind, list(reversed(B2)), 2, warn)
        ut, _ = chain(data, kind, list(reversed(TRUNK)), 2, warn, a5 + a2)
        up = u5 + u2 + ut
        for dirn, ts in (('down', down), ('up', up)):
            for t in ts:  # 終点への到着は時刻表に無いので推定(+2分)
                last_stop, last_t = t['times'][-1]
                term = {'大町': '函館どつく前', '青柳町': '谷地頭', '湯の川温泉': '湯の川'}.get(last_stop)
                if term and (t['end'] in (None, term)):
                    t['times'].append((term, last_t + 2))
                    t['est'] = True
            for t in ts:
                route = '②' if t['routes'] == {'②'} else '⑤' if t['routes'] == {'⑤'} else '②⑤'
                last_stop = t['times'][-1][0]
                trips.append({'dir': dirn, 'route': route, 'low': t['low'], 'flag': t['flag'], 'estEnd': t.get('est', False),
                              'to': t['end'] or ('湯の川' if dirn == 'up' else last_stop),
                              'stops': [[STOPS.index(s), m] for s, m in t['times']]})
        trips.sort(key=lambda t: t['stops'][0][1])
        result[kind] = trips
    for w in warn:
        print('WARN', w, file=sys.stderr)
    json.dump({'stops': STOPS, 'trips': result}, sys.stdout, ensure_ascii=False, separators=(',', ':'))

if __name__ == '__main__':
    main(sys.argv[1])
