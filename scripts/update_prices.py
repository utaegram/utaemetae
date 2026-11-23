"""천안사랑카드 가맹 주유소(data/stations.json)의 가격을 오피넷에서 새로 받아 web/stations.json 으로 저장.

사용: python scripts/update_prices.py   (프로젝트 폴더에서 실행, .env 또는 환경변수 OPINET_KEY 필요)
천안 범위만 반경 5km 격자로 조회하므로 1회 실행에 약 90회 호출합니다.
"""
import json, os, re, sys, time, pathlib, urllib.request
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from katec import katec_to_wgs84

key = os.environ.get('OPINET_KEY')
if not key and (ROOT / '.env').exists():
    m = re.search(r'OPINET_KEY=(\S+)', (ROOT / '.env').read_text(encoding='utf-8'))
    key = m and m.group(1)
if not key:
    sys.exit('OPINET_KEY 가 없습니다 (.env 또는 환경변수)')

base = json.load(open(ROOT / 'data/stations.json', encoding='utf-8'))
want = {s['id'] for s in base}
xs = [s['x'] for s in base]; ys = [s['y'] for s in base]
prices = {}
for x in range(int(min(xs)) - 2000, int(max(xs)) + 7000, 7000):
    for y in range(int(min(ys)) - 2000, int(max(ys)) + 7000, 7000):
        for prod in ('B027', 'D047', 'K015'):
            url = f'https://www.opinet.co.kr/api/aroundAll.do?code={key}&x={x}&y={y}&radius=5000&sort=1&prodcd={prod}&out=json'
            try:
                oils = json.loads(urllib.request.urlopen(url, timeout=20).read().decode('utf-8'))['RESULT']['OIL']
            except Exception as e:
                print('skip', x, y, prod, e); continue
            for o in oils:
                if o['UNI_ID'] in want:
                    prices.setdefault(o['UNI_ID'], {})[prod] = o['PRICE']

BRAND = {'SKE': 'SK에너지', 'GSC': 'GS칼텍스', 'HDO': 'HD현대오일뱅크', 'SOL': 'S-OIL', 'RTO': '알뜰주유소',
         'RTX': '알뜰(고속도로)', 'NHO': '농협알뜰', 'ETC': '자가상표', 'E1G': 'E1', 'SKG': 'SK가스'}
out = []
for s in base:
    lat, lng = katec_to_wgs84(s['x'], s['y'])
    p = prices.get(s['id'], s['prices'])  # 이번에 못 받으면 이전 값 유지
    out.append({'id': s['id'], 'name': s['name'], 'merchant': s['merchant_name'], 'addr': s['addr'],
                'brand': BRAND.get(s['brand'], s['brand']), 'lat': round(lat, 6), 'lng': round(lng, 6),
                'gas': p.get('B027'), 'diesel': p.get('D047'), 'lpg': p.get('K015'), 'verify': s.get('verify', False)})
kst = datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')
(ROOT / 'web').mkdir(exist_ok=True)
if not prices:  # 한 곳도 못 받았으면(호출 한도 초과 등) 기존 파일과 기준 시각을 그대로 둔다
    sys.exit(f'{kst} 가격을 하나도 받지 못해 갱신하지 않았습니다 (오피넷 호출 한도 확인)')
json.dump({'updated': kst, 'stations': out}, open(ROOT / 'web/stations.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'{kst} 갱신: {len(prices)}/{len(base)}곳 가격 수신')
