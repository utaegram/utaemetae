"""114 천안사랑카드 가맹점 ↔ 오피넷 주유소 매칭 (이름 유사도 + 좌표 거리) → data/stations.json"""
import json, re, sys, math, time, urllib.request, os
from difflib import SequenceMatcher
sys.path.insert(0, 'scripts')
from katec import katec_to_wgs84

GAS = re.compile(r'주유|충전소|LPG|엘피지|가스|에너지|오일|석유', re.I)
NOT_GAS = re.compile(r'씨유|CU|세븐일레븐|이마트24|돈가스|빨래방|수학|교습|GS ?25|\(GS\) ?25|GS\)25|편의점|세차|카센|정비|타이어|학원|식당|커피|마트|도시가스|전기차|T ?world|보일러|오일교환')
STRIP = re.compile(r'\(주\)|㈜|주식회사|\(유\)|유한회사|HD|SK|GS칼텍스|GS|현대오일뱅크|S-?OIL|에쓰오일|알뜰|NH|농협|직영|셀프|SELF|주유소|충전소|\(.*?\)|[\s/\-·.,()]', re.I)
core = lambda n: STRIP.sub('', n)
def dist_m(a, b, c, d):
    return 6371000*2*math.asin(math.sqrt(math.sin(math.radians(c-a)/2)**2 + math.cos(math.radians(a))*math.cos(math.radians(c))*math.sin(math.radians(d-b)/2)**2))

# 오피넷 주유소(격자 조회: 3줄마다 휘발유/경유/LPG)
op = {}
for i, line in enumerate(open('data/opinet_raw.txt', encoding='utf-8')):
    prod = ['B027', 'D047', 'K015'][i % 3]
    try: oils = json.loads(line)['RESULT']['OIL']
    except Exception: continue
    for o in oils:
        s = op.setdefault(o['UNI_ID'], {'id': o['UNI_ID'], 'name': o['OS_NM'], 'brand': o['POLL_DIV_CD'], 'x': o['GIS_X_COOR'], 'y': o['GIS_Y_COOR'], 'prices': {}})
        s['prices'][prod] = o['PRICE']
for s in op.values(): s['lat'], s['lng'] = katec_to_wgs84(s['x'], s['y'])

# 114 주유소 후보 + 상세페이지 좌표(캐시)
merchants = json.load(open('data/merchants_114.json', encoding='utf-8'))
cands = [m for m in merchants if GAS.search(m['name']) and not NOT_GAS.search(m['name'])]
cache_f = 'data/geo_114.json'
geo = json.load(open(cache_f, encoding='utf-8')) if os.path.exists(cache_f) else {}
for m in cands:
    if m['detail_id'] in geo: continue
    req = urllib.request.Request(f"https://www.114.co.kr/life/localBillStore/detail/{m['detail_id']}", headers={'User-Agent': 'Mozilla/5.0'})
    try:
        h = urllib.request.urlopen(req, timeout=30).read().decode('utf-8')
        g = re.search(r'"latitude":([\d.]+),"longitude":([\d.]+)', h)
        geo[m['detail_id']] = [float(g.group(1)), float(g.group(2))] if g else None
    except Exception: geo[m['detail_id']] = None
    time.sleep(0.3)
json.dump(geo, open(cache_f, 'w', encoding='utf-8'))

matched, unmatched = {}, []
for m in cands:
    g = geo.get(m['detail_id']); c = core(m['name']); best = None
    for s in op.values():
        sim = SequenceMatcher(None, c, core(s['name'])).ratio() if c else 0
        d = dist_m(g[0], g[1], s['lat'], s['lng']) if g else None
        # 가까우면(150m) 이름이 달라도 인정, 500m 이내는 이름 유사 필요, 좌표 없으면 이름 거의 일치 필요
        ok = (d is not None and (d < 40 or (d < 500 and sim >= 0.5))) or (d is None and sim >= 0.9)
        if ok:
            score = sim - (d or 0)/1000
            if not best or score > best[0]: best = (score, s, d, sim)
    if best:
        s = best[1]
        if s['id'] not in matched:
            matched[s['id']] = {**s, 'merchant_name': m['name'], 'addr': m['addr'], 'dist_m': round(best[2] or -1), 'name_sim': round(best[3], 2), 'verify': best[3] < 0.5}
    else:
        unmatched.append({**m, 'geo': g})
out = sorted(matched.values(), key=lambda s: s['name'])
json.dump(out, open('data/stations.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(unmatched, open('data/unmatched.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'merchants {len(merchants)} / gas candidates {len(cands)} / matched {len(out)} / unmatched {len(unmatched)}')
