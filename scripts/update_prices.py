"""천안사랑카드 가맹 주유소(data/stations.json)의 가격을 오피넷에서 새로 받아 web/stations.json 으로 저장.

사용: python scripts/update_prices.py   (프로젝트 폴더에서 실행, .env 또는 환경변수 OPINET_KEY 필요)

호출 수: 5km 반경 원 9개 × 제품 3종 = 27회 (예전 격자 방식 108회의 1/4).
오피넷 무료 API 한도는 1,500 call/일이라, 1시간마다 돌아도 648회로 한도 안에 들어온다.

환경변수
  OPINET_KEY          오피넷 API 키 (필수)
  FORCE=1             최근 갱신 시각과 상관없이 강제로 받는다 (수동 실행용)
  MIN_INTERVAL_MIN    이 시간(분) 안에 갱신된 자료가 있으면 건너뛴다 (기본 45)
  REFRESH_MIN         가격이 그대로여도 이 시간(분)이 지나면 기준 시각을 새로 쓴다 (기본 180)
  RETRY_DELAY_SEC     건일 때 재시도 전 대기 초 (기본 60)

종료 코드
  0  정상 (갱신했거나, 바뀐 값이 없어 그대로 둠, 또는 최근 갱신이라 건너뜀)
  1  실패 (키 없음 / 두 번 모두 가격 0건)
"""
import json, os, re, sys, time, pathlib, urllib.request
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from katec import katec_to_wgs84

KST = timezone(timedelta(hours=9))
PRODUCTS = ('B027', 'D047', 'K015')   # 휘발유, 경유, 자동차부탄
SEARCH_RADIUS = 5000                  # 오피넷 aroundAll.do 최대 반경(m)
COVER_RADIUS = 4700                   # 원이 겹쳐 덮이도록 조금 작게 잡는다 (경계 주유소 누락 방지)

MIN_INTERVAL = int(os.environ.get('MIN_INTERVAL_MIN', '45'))
REFRESH_MIN = int(os.environ.get('REFRESH_MIN', '180'))
RETRY_DELAY = int(os.environ.get('RETRY_DELAY_SEC', '60'))
FORCE = os.environ.get('FORCE', '').lower() in ('1', 'true', 'yes', 'y')


def now_kst():
    return datetime.now(KST)


def parse_kst(text):
    try:
        return datetime.strptime(text, '%Y-%m-%d %H:%M').replace(tzinfo=KST)
    except Exception:
        return None


def get_key():
    key = os.environ.get('OPINET_KEY')
    if not key and (ROOT / '.env').exists():
        m = re.search(r'OPINET_KEY=(\S+)', (ROOT / '.env').read_text(encoding='utf-8'))
        key = m and m.group(1)
    if not key:
        sys.exit('OPINET_KEY 가 없습니다 (.env 또는 환경변수)')
    return key


def cover_cells(points):
    """주유소 좌표 전체를 5km 반경 원 9개 안팎으로 덮는 중심점 목록 (격자 36개 → 9개로 줄임).

    후보는 주유소 좌표와 2km 격자점. 아직 안 덮인 주유소를 가장 많이 덮는 후보를 고르는 탐욕 방식이라
    결과가 늘 같고, 주유소 목록이 바뀌어도 알아서 다시 계산된다.
    """
    pts = [(float(x), float(y)) for x, y in points]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    cands = list(pts)
    for x in range(int(min(xs)) - 3000, int(max(xs)) + 3001, 2000):
        for y in range(int(min(ys)) - 3000, int(max(ys)) + 3001, 2000):
            cands.append((float(x), float(y)))
    left = set(range(len(pts)))
    cells = []
    while left:
        best, best_n = None, -1
        for c in cands:
            n = sum(1 for i in left if (c[0] - pts[i][0]) ** 2 + (c[1] - pts[i][1]) ** 2 <= COVER_RADIUS ** 2)
            if n > best_n:
                best, best_n = c, n
        if best_n <= 0:
            break
        cells.append(best)
        left = {i for i in left if (best[0] - pts[i][0]) ** 2 + (best[1] - pts[i][1]) ** 2 > COVER_RADIUS ** 2}
    return cells


def collect(key, cells, want):
    """한 바퀴 돌며 가격을 모은다. 실패 원인을 구분해 남기기 위해 통계와 원본 응답 표본을 함께 돌려준다."""
    prices = {}
    stats = {'calls': 0, 'ok': 0, 'errors': 0, 'items': 0, 'matched': 0}
    errs, samples = [], []
    for x, y in cells:
        for prod in PRODUCTS:
            url = (f'https://www.opinet.co.kr/api/aroundAll.do?code={key}&x={x}&y={y}'
                   f'&radius={SEARCH_RADIUS}&sort=1&prodcd={prod}&out=json')
            stats['calls'] += 1
            try:
                raw = urllib.request.urlopen(url, timeout=20).read().decode('utf-8', 'replace')
            except Exception as e:
                stats['errors'] += 1
                if len(errs) < 5:
                    errs.append(f'{x:.0f},{y:.0f} {prod} 요청 실패: {type(e).__name__}: {e}')
                continue
            stats['ok'] += 1
            if len(samples) < 2:
                samples.append(raw[:300].replace('\n', ' ').replace('\r', ' '))
            try:
                oils = json.loads(raw)['RESULT']['OIL']
            except Exception as e:
                stats['errors'] += 1
                if len(errs) < 5:
                    errs.append(f'{x:.0f},{y:.0f} {prod} 응답 해석 실패: {type(e).__name__}: {e}')
                continue
            if isinstance(oils, dict):      # 결과가 1건이면 목록이 아니라 객체로 올 때가 있다
                oils = [oils]
            stats['items'] += len(oils)
            for o in oils:
                uid = o.get('UNI_ID')
                if uid in want and o.get('PRICE'):
                    prices.setdefault(uid, {})[prod] = o.get('PRICE')
                    stats['matched'] += 1
    return prices, stats, errs, samples


def report_failure(stats, errs, samples, label):
    print(f'[{label}] 가격 0건: 호출 {stats["calls"]}회 / 정상응답 {stats["ok"]}회 / 오류 {stats["errors"]}회 '
          f'/ 응답에 담긴 주유소 {stats["items"]}곳')
    for e in errs:
        print('  ·', e)
    for i, s in enumerate(samples, 1):
        print(f'  응답 표본{i}: {s}')
    if stats['ok'] and not stats['items']:
        print('  → 응답은 왔지만 주유소 목록이 비어 있습니다 (키 한도 초과·차단 또는 서버 쪽 빈 응답)')
    elif not stats['ok']:
        print('  → 요청 자체가 모두 실패했습니다 (네트워크·오피넷 장애)')


def main():
    key = get_key()
    base = json.load(open(ROOT / 'data/stations.json', encoding='utf-8'))
    want = {s['id'] for s in base}
    out_path = ROOT / 'web' / 'stations.json'
    old = None
    if out_path.exists():
        try:
            old = json.load(open(out_path, encoding='utf-8'))
        except Exception:
            old = None

    last = parse_kst((old or {}).get('updated', ''))
    if last and not FORCE:
        gap = (now_kst() - last).total_seconds() / 60
        if gap < MIN_INTERVAL:
            print(f'최근 갱신({last:%m-%d %H:%M}) 뒤 {gap:.0f}분밖에 지나지 않아 이번 실행은 건너뜁니다 '
                  f'(최소 간격 {MIN_INTERVAL}분, 오피넷 호출 절약)')
            return 0

    cells = cover_cells([(s['x'], s['y']) for s in base])
    print(f'조회 격자 {len(cells)}곳 × 제품 {len(PRODUCTS)}종 = 최대 {len(cells) * len(PRODUCTS)}회 호출')

    prices, stats, errs, samples = collect(key, cells, want)
    if not prices:
        report_failure(stats, errs, samples, '1차')
        print(f'{RETRY_DELAY}초 뒤 한 번 더 시도합니다')
        time.sleep(RETRY_DELAY)
        prices, stats2, errs2, samples2 = collect(key, cells, want)
        if not prices:
            report_failure(stats2, errs2, samples2, '재시도')
            print('두 번 모두 가격을 하나도 받지 못했습니다. 기존 자료는 그대로 두고 이번 실행은 실패로 끝냅니다.')
            return 1
    if stats['errors']:
        print(f'일부 조회 실패 {stats["errors"]}/{stats["calls"]}회 (받은 곳은 반영)')
    if len(prices) < len(base) // 2:
        print(f'주의: {len(base)}곳 중 {len(prices)}곳만 받았습니다. 못 받은 곳은 이전 값을 유지합니다.')

    BRAND = {'SKE': 'SK에너지', 'GSC': 'GS칼텍스', 'HDO': 'HD현대오일뱅크', 'SOL': 'S-OIL', 'RTO': '알뜰주유소',
             'RTX': '알뜰(고속도로)', 'NHO': '농협알뜰', 'ETC': '자가상표', 'E1G': 'E1', 'SKG': 'SK가스'}
    new = []
    for s in base:
        lat, lng = katec_to_wgs84(s['x'], s['y'])
        p = prices.get(s['id'], s['prices'])      # 이번에 못 받으면 이전 값 유지
        new.append({'id': s['id'], 'name': s['name'], 'merchant': s['chak_name'], 'addr': s['addr'],
                    'brand': BRAND.get(s['brand'], s['brand']), 'lat': round(lat, 6), 'lng': round(lng, 6),
                    'gas': p.get('B027'), 'diesel': p.get('D047'), 'lpg': p.get('K015')})

    changed = old is None or old.get('stations') != new
    refresh_due = last is None or (now_kst() - last).total_seconds() / 60 >= REFRESH_MIN
    if not changed and not refresh_due:
        print(f'가격 변동 없음 - 파일을 그대로 둡니다 (마지막 기준 {last:%Y-%m-%d %H:%M}, '
              f'기준 시각은 {REFRESH_MIN}분마다 새로 씀)')
        return 0

    stamp = now_kst()
    out_path.parent.mkdir(exist_ok=True)
    json.dump({'updated': stamp.strftime('%Y-%m-%d %H:%M'), 'stations': new},
              open(out_path, 'w', encoding='utf-8'), ensure_ascii=False)
    why = '가격 변동 있음' if changed else f'가격은 그대로, 기준 시각만 갱신({REFRESH_MIN}분 경과)'
    print(f'{stamp:%Y-%m-%d %H:%M} 갱신: {len(prices)}/{len(base)}곳 가격 수신 - {why}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
