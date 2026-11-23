"""오피넷 격자 결과 → 천안 주유소 상세(주소·좌표·가격) 수집"""
import json, re, urllib.request, pathlib, time
key = re.search(r'OPINET_KEY=(\S+)', pathlib.Path('.env').read_text()).group(1)
ids = {}
for line in open('data/opinet_raw.txt', encoding='utf-8'):
    line = line.strip()
    if not line: continue
    try: oils = json.loads(line)['RESULT']['OIL']
    except Exception: continue
    for o in oils: ids[o['UNI_ID']] = o['OS_NM']
print('unique stations in grid:', len(ids))
out = []
for i, uid in enumerate(ids):
    url = f'https://www.opinet.co.kr/api/detailById.do?code={key}&id={uid}&out=json'
    d = json.loads(urllib.request.urlopen(url, timeout=20).read().decode('utf-8'))['RESULT']['OIL'][0]
    addr = (d.get('NEW_ADR') or '') + ' ' + (d.get('VAN_ADR') or '')
    if '천안' not in addr: continue
    out.append({'id': uid, 'name': d['OS_NM'], 'brand': d.get('POLL_DIV_CO'), 'addr': (d.get('NEW_ADR') or d.get('VAN_ADR')).strip(),
                'old_addr': d.get('VAN_ADR'), 'tel': d.get('TEL'), 'x': d['GIS_X_COOR'], 'y': d['GIS_Y_COOR'],
                'lpg': d.get('LPG_YN'), 'self': d.get('SELF_DIV_CD') if 'SELF_DIV_CD' in d else None,
                'prices': {p['PRODCD']: p['PRICE'] for p in d.get('OIL_PRICE', [])}})
json.dump(out, open('data/cheonan_stations.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('cheonan stations:', len(out))
