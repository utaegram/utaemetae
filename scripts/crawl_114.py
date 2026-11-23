"""114 지역화폐 가맹점(충남 천안시) 전체 목록 수집 → data/merchants_114.json"""
import re, json, time, urllib.request, urllib.parse, html
B = 'https://www.114.co.kr/life/localBillStore/list?' + urllib.parse.urlencode(
    {'keyword': '', 'sigungu': '천안시', 'sido': '충청남도', 'pageSize': 100})
item = re.compile(r'localBillStore/detail/(\d+)">.*?<dt>\s*(.*?)\s*</dt>.*?\[지역화폐\]</i>\s*(.*?)\s*</dd>.*?\[주소\]</i>\s*(.*?)\s*</dd>', re.S)
rows, page, last = [], 0, 260
while page <= last:
    req = urllib.request.Request(f'{B}&page={page}', headers={'User-Agent': 'Mozilla/5.0'})
    for attempt in range(3):
        try: h = urllib.request.urlopen(req, timeout=30).read().decode('utf-8'); break
        except Exception as e: time.sleep(3)
    else: print('fail page', page); page += 1; continue
    m = re.findall(r'page=(\d+)&amp;pageSize|page=(\d+)&pageSize', h)
    nums = [int(a or b) for a, b in m]
    if nums: last = max(last, max(nums))
    for did, name, cur, addr in item.findall(h):
        rows.append({'detail_id': did, 'name': html.unescape(name), 'currency': cur, 'addr': html.unescape(addr)})
    if page % 20 == 0: print('page', page, 'rows', len(rows), flush=True)
    page += 1; time.sleep(0.4)
json.dump(rows, open('data/merchants_114.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('done', len(rows))
