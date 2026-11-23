"""천안사랑카드 공식앱(chak) 목록(data/chak_gas.tsv) ↔ 현재 매칭 결과(data/stations.json) 대조"""
import csv, json, re
from difflib import SequenceMatcher
STRIP = re.compile(r'\(주\)|㈜|주\)|주식회사|HD|SK|GS|지에스|\(GS\)|현대오일뱅크|S-?OIL|직영|셀프|self|주유소|충전소|LPG|엘피지|\(.*?\)|[\s\-·.,()]', re.I)
core = lambda n: STRIP.sub('', n).lower()
def addr_key(a):
    # 도로명+번호 또는 지번 숫자
    m = re.search(r'([가-힣0-9]+(?:로|길))\s*(\d+(?:-\d+)?)', a)
    return (m.group(1), m.group(2)) if m else None
chak = [dict(zip(['name', 'addr', 'cat'], r)) for r in csv.reader(open('data/chak_gas.tsv', encoding='utf-8'), delimiter='\t')]
st = json.load(open('data/stations.json', encoding='utf-8'))
used = set(); res = []
for s in st:
    best = None
    for i, c in enumerate(chak):
        ak1, ak2 = addr_key(s['addr']), addr_key(c['addr'])
        addr_ok = ak1 and ak2 and ak1 == ak2
        sim = max(SequenceMatcher(None, core(c['name']), core(n)).ratio() for n in (s['name'], s['merchant_name']))
        score = sim + (1 if addr_ok else 0)
        if (addr_ok or sim >= 0.8) and (not best or score > best[0]): best = (score, i, c)
    if best: used.add(best[1])
    res.append((s, best[2] if best else None))
inapp = [r for r in res if r[1]]; notin = [r for r in res if not r[1]]
print(f'현재 107곳 중 공식앱에서 확인: {len(inapp)} / 공식앱에 없음: {len(notin)}')
print('\n[공식앱에 없음]')
for s, _ in notin: print(' -', s['name'], '|', s['merchant_name'], '|', s['addr'][9:40], '| 확인필요' if s['verify'] else '')
print('\n[확인필요였는데 공식앱에서 확인됨]')
for s, c in inapp:
    if s['verify']: print(' +', s['name'], '<-', c['name'])
print('\n[공식앱엔 있는데 현재 앱에 없는 주유소/충전소]')
for i, c in enumerate(chak):
    if i not in used and c['cat'] != '기타연료': print(' *', c['name'], '|', c['addr'], '|', c['cat'])
json.dump({s['id']: (c['name'] if c else None) for s, c in res}, open('data/chak_match.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
