"""천안사랑카드 공식앱(chak) 주유소·충전소 목록 → 오피넷 주유소 매칭 → data/stations.json

입력
- data/chak_gas.tsv      : 공식앱에서 읽은 목록 (상호, 주소, 업종)
- data/opinet_raw.txt    : 오피넷 aroundAll 격자 조회 결과 (scripts/fetch_opinet.sh)
- data/merchants_114.json: 114 가맹점 목록 (좌표 찾기용 보조 자료)
매칭 규칙
1) 114에서 같은 가맹점(이름 유사 + 주소 번지 일치)을 찾아 좌표를 얻고, 그 좌표 200m 안의 오피넷 주유소 중 이름이 가장 비슷한 곳
2) 좌표가 없으면 오피넷 주유소 이름이 거의 같은 곳(천안 범위 안)
3) 둘 다 실패: 주유소는 '가격 정보 없음'으로 남기고(좌표 있으면 지도 표시), 충전소는 가스판매소로 보고 제외
"""
import csv, json, math, os, re, sys, time, urllib.request
from difflib import SequenceMatcher
sys.path.insert(0, 'scripts')
from katec import katec_to_wgs84

STRIP = re.compile(r'\(주\)|㈜|주\)|주식회사|\(유\)|HD|SK|GS칼텍스|지에스칼텍스|GS|지에스|현대오일뱅크|S-?OIL|에쓰오일|알뜰|직영|셀프|self|주유소|충전소|LPG|엘피지|가스|에너지|\(.*?\)|[\s\-·.,()]', re.I)
NORM = [('케이케이', 'kk'), ('아이씨', 'ic'), ('이엠', 'em'), ('오공단', '5공단'), ('엘피지', 'lpg'), ('지에스', 'gs')]
def core(n):
    n = n.lower()
    for a, b in NORM: n = n.replace(a, b)
    return STRIP.sub('', n)
def _sim1(a, b):
    a, b = core(a), core(b)
    if not a or not b: return 0
    if len(min(a, b, key=len)) >= 3 and (a in b or b in a): return 0.92
    return SequenceMatcher(None, a, b).ratio()
def sim(a, b):
    # 괄호 안 이름(예: 화이너지(원성깨비주유소))도 후보로 비교
    alts = lambda n: [n] + re.findall(r'\(([^)]{2,})\)', n)
    return max(_sim1(x, y) for x in alts(a) for y in alts(b))
def fits(cat, s):
    p = s['prices']
    return ('K015' in p) if cat == '충전소' else ('B027' in p or 'D047' in p)
def dist_m(a, b, c, d):
    return 6371000 * 2 * math.asin(math.sqrt(math.sin(math.radians(c - a) / 2) ** 2 + math.cos(math.radians(a)) * math.cos(math.radians(c)) * math.sin(math.radians(d - b) / 2) ** 2))
def addr_nums(a):
    """주소 비교용: 도로명+번호, 지번 숫자"""
    keys = set()
    for m in re.finditer(r'([가-힣0-9]+(?:로|길))\s*(\d+(?:-\d+)?)', a): keys.add(m.group(1) + m.group(2))
    for m in re.finditer(r'(\d{2,4}-\d+|\b\d{3,4}\b)', a): keys.add(m.group(1))
    return keys
IN_CHEONAN = lambda lat, lng: 36.66 <= lat <= 36.98 and 127.05 <= lng <= 127.36

# 오피넷
op = {}
for i, line in enumerate(open('data/opinet_raw.txt', encoding='utf-8')):
    prod = ['B027', 'D047', 'K015'][i % 3]
    try: oils = json.loads(line)['RESULT']['OIL']
    except Exception: continue
    for o in oils:
        s = op.setdefault(o['UNI_ID'], {'id': o['UNI_ID'], 'name': o['OS_NM'], 'brand': o['POLL_DIV_CD'], 'x': o['GIS_X_COOR'], 'y': o['GIS_Y_COOR'], 'prices': {}})
        s['prices'][prod] = o['PRICE']
for s in op.values(): s['lat'], s['lng'] = katec_to_wgs84(s['x'], s['y'])

# 114 좌표 캐시
m114 = json.load(open('data/merchants_114.json', encoding='utf-8'))
geo_f = 'data/geo_114.json'
geo = json.load(open(geo_f, encoding='utf-8')) if os.path.exists(geo_f) else {}
def geo_of(did):
    if did not in geo:
        req = urllib.request.Request(f'https://www.114.co.kr/life/localBillStore/detail/{did}', headers={'User-Agent': 'Mozilla/5.0'})
        try:
            h = urllib.request.urlopen(req, timeout=30).read().decode('utf-8')
            g = re.search(r'"latitude":([\d.]+),"longitude":([\d.]+)', h)
            geo[did] = [float(g.group(1)), float(g.group(2))] if g else None
        except Exception: geo[did] = None
        time.sleep(0.3)
    return geo[did]

chak = [dict(zip(['name', 'addr', 'cat'], r)) for r in csv.reader(open('data/chak_gas.tsv', encoding='utf-8'), delimiter='\t')]
seen_chak = set(); out = []; dropped = []
for c in chak:
    if c['cat'] == '기타연료': continue
    key = (core(c['name']), c['addr'][:12])
    if key in seen_chak: continue  # 같은 곳 중복 등록
    seen_chak.add(key)
    # 1) 114에서 같은 가맹점 찾기 → 좌표
    an = addr_nums(c['addr'])
    cand = [m for m in m114 if sim(m['name'], c['name']) >= 0.7 and (addr_nums(m['addr']) & an)]
    if not cand: cand = [m for m in m114 if core(m['name']) and core(m['name']) == core(c['name'])]
    g = None
    for m in cand:
        g = geo_of(m['detail_id'])
        if g: break
    best, how = None, ''
    if g:
        near = [(dist_m(g[0], g[1], s['lat'], s['lng']), s) for s in op.values()]
        near = [(d, s) for d, s in near if d < 200 and fits(c['cat'], s)]
        if near:
            d, s = max(near, key=lambda t: sim(c['name'], t[1]['name']) - t[0] / 400)
            if d < 60 or sim(c['name'], s['name']) >= 0.5: best, how = s, f'좌표 {round(d)}m'
    if not best:
        names = [(sim(c['name'], s['name']), s) for s in op.values() if IN_CHEONAN(s['lat'], s['lng']) and fits(c['cat'], s)]
        sc, s = max(names, key=lambda t: t[0])
        if sc >= 0.85 and (not g or dist_m(g[0], g[1], s['lat'], s['lng']) < 1500): best, how = s, f'이름 {sc:.2f}'
    row = {'chak_name': c['name'], 'addr': '천안시 ' + c['addr'], 'cat': c['cat'], 'how': how}
    if best:
        row['score'] = sim(c['name'], best['name'])
        row.update({'id': best['id'], 'name': best['name'], 'brand': best['brand'], 'x': best['x'], 'y': best['y'],
                    'lat': best['lat'], 'lng': best['lng'], 'prices': best['prices']})
        out.append(row)
    else:
        dropped.append(c)  # 오피넷에 없음: 폐업했거나 차량용이 아닌 판매소(가스 배달 등)로 보고 제외
json.dump(geo, open(geo_f, 'w', encoding='utf-8'))
# 같은 오피넷 주유소에 두 번 붙으면 하나만
best_by_id = {}
for r in out:
    if r['id'] not in best_by_id or r['score'] > best_by_id[r['id']]['score']: best_by_id[r['id']] = r
uniq = list(best_by_id.values())
json.dump(uniq, open('data/stations.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
priced = [r for r in uniq if r['prices']]
print(f'공식 주유소·충전소 {len(seen_chak)} → 오피넷 매칭 {len(uniq)} / 오피넷에 없음(제외) {len(dropped)}')
for r in uniq: print(('O ' if r['prices'] else 'X ') + f"{r['chak_name']} -> {r['name']} [{r['how']}] {r['lat'] and round(r['lat'], 4)}")
print('--- 제외'); [print('  ', d['name'], d['addr'], d['cat']) for d in dropped]
json.dump(dropped, open('data/excluded.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
