'use strict';
const FUEL_LABEL = { gas: '휘발유', diesel: '경유', lpg: 'LPG' };
const state = { fuel: 'gas', sort: 'price', me: null, sel: null, stations: [] };
const $ = (s) => document.querySelector(s);

const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch {} },
};

const map = L.map('map', { zoomControl: false, attributionControl: true }).setView([36.815, 127.14], 12);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19, attribution: '&copy; OpenStreetMap',
}).addTo(map);
L.control.zoom({ position: 'bottomright' }).addTo(map);
const layer = L.layerGroup().addTo(map);
let lastFar = null;
map.on('zoomend', () => { const far = map.getZoom() < 14; if (far !== lastFar) { lastFar = far; if (state.stations.length) render(); } });
let meMarker = null;

function distKm(a, b) {
  const R = 6371, r = Math.PI / 180;
  const dLat = (b.lat - a.lat) * r, dLng = (b.lng - a.lng) * r;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
const won = (n) => n.toLocaleString('ko-KR');
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const shortName = (n) => n.replace(/^\s*(\(주\)|㈜|주식회사)\s*/, '');
const bare = (n) => n.replace(/\(주\)|㈜|주식회사|\s/g, '').toLowerCase();
const sameName = (a, b) => bare(a) === bare(b);

function visible() {
  const f = state.fuel;
  const rows = state.stations.filter((s) => s[f]).map((s) => ({ ...s, d: state.me ? distKm(state.me, s) : null }));
  const byPrice = [...rows].sort((a, b) => a[f] - b[f]);
  const cut = byPrice.length ? byPrice[Math.min(2, byPrice.length - 1)][f] : 0; // 3위 가격 이하(동률 포함)
  const cheapIds = new Set(byPrice.filter((s) => s[f] <= cut).map((s) => s.id));
  const min = byPrice.length ? byPrice[0][f] : 0;
  rows.forEach((s) => {
    s.cheap = cheapIds.has(s.id); s.best = s[f] === min;
    s.priceRank = byPrice.filter((x) => x[f] < s[f]).length + 1; // 동률은 같은 순위
  });
  if (state.sort === 'dist' && state.me) rows.sort((a, b) => a.d - b.d);
  else rows.sort((a, b) => a[f] - b[f] || (a.d ?? 0) - (b.d ?? 0));
  return rows;
}

function render() {
  const f = state.fuel, rows = visible();
  $('#count').textContent = `${FUEL_LABEL[f]} 파는 가맹 주유소 ${rows.length}곳`;

  layer.clearLayers();
  const far = map.getZoom() < 14;
  for (const s of rows) {
    const isSel = state.sel === s.id;
    const cls = ['pin', s.cheap ? 'cheap' : '', s.best ? 'best' : '', isSel ? 'sel' : ''].join(' ');
    const html = far && !s.cheap && !isSel ? '<span class="dot"></span>' : `<span class="${cls}">${won(s[f])}</span>`;
    const m = L.marker([s.lat, s.lng], {
      icon: L.divIcon({ className: '', html, iconSize: null }),
      zIndexOffset: isSel ? 3000 : s.best ? 2000 : s.cheap ? 1000 : 0,
      title: shortName(s.name),
    }).addTo(layer);
    m.on('click', () => select(s.id, true));
  }

  const list = $('#list');
  if (!rows.length) { list.innerHTML = '<li class="empty">표시할 주유소가 없어요</li>'; return; }
  list.innerHTML = rows.map((s, i) => {
    const kakao = `https://map.kakao.com/link/to/${encodeURIComponent(shortName(s.name))},${s.lat},${s.lng}`;
    const naver = `https://map.naver.com/p/search/${encodeURIComponent(shortName(s.name))}`;
    const dist = s.d != null ? `${s.d < 1 ? Math.round(s.d * 1000) + 'm' : s.d.toFixed(1) + 'km'} · ` : '';
    const badge = s.best ? '<span class="badge">최저가</span>' : s.cheap ? '<span class="badge">TOP3</span>' : '';
    return `<li class="item ${s.cheap ? 'top3' : ''} ${s.best ? 'best' : ''} ${state.sel === s.id ? 'sel' : ''}" data-id="${s.id}">
      <span class="rank">${state.sort === 'price' || !state.me ? s.priceRank : i + 1}</span>
      <span class="name">${badge}${esc(shortName(s.name))}</span>
      <span class="price">${won(s[f])}<small>원</small></span>
      <span class="meta">${dist}${esc(s.brand || '')} · ${esc(s.addr.replace(/^(충청남도 )?천안시 /, ''))}</span>
      <div class="actions">
        <a class="go" href="${kakao}" target="_blank" rel="noopener">카카오맵 길찾기</a>
        <a href="${naver}" target="_blank" rel="noopener">네이버지도</a>
        ${s.merchant && sameName(s.merchant, s.name) ? '' : `<span class="meta" style="white-space:normal">천안사랑카드 가맹 등록명: ${esc(s.merchant)}</span>`}
      </div>
    </li>`;
  }).join('');
}

function select(id, fromMap) {
  state.sel = state.sel === id && !fromMap ? null : id;
  render();
  const s = state.stations.find((x) => x.id === id);
  if (state.sel && s) {
    map.panTo([s.lat, s.lng]);
    const el = document.querySelector(`.item[data-id="${id}"]`);
    if (el && fromMap) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

$('#list').addEventListener('click', (e) => {
  if (e.target.closest('a')) return;
  const li = e.target.closest('.item');
  if (li) select(li.dataset.id, false);
});

document.querySelectorAll('.fuel button').forEach((b) => b.addEventListener('click', () => {
  state.fuel = b.dataset.fuel; store.set('fuel', state.fuel); state.sel = null;
  document.querySelectorAll('.fuel button').forEach((x) => x.setAttribute('aria-selected', String(x === b)));
  render();
}));

function setSort(v) {
  state.sort = v;
  document.querySelectorAll('.sort button').forEach((x) => x.classList.toggle('on', x.dataset.sort === v));
  render();
}
document.querySelectorAll('.sort button').forEach((b) => b.addEventListener('click', () => {
  if (b.dataset.sort === 'dist' && !state.me) { locate(true); return; }
  setSort(b.dataset.sort);
}));

function locate(thenSortByDist) {
  if (!navigator.geolocation) { alert('이 브라우저는 위치 기능을 지원하지 않아요.'); return; }
  $('#locate').textContent = '찾는 중…';
  navigator.geolocation.getCurrentPosition((p) => {
    state.me = { lat: p.coords.latitude, lng: p.coords.longitude };
    if (meMarker) meMarker.remove();
    meMarker = L.marker([state.me.lat, state.me.lng], { icon: L.divIcon({ className: '', html: '<div class="me"></div>', iconSize: [16, 16] }), zIndexOffset: 3000 }).addTo(map);
    map.setView([state.me.lat, state.me.lng], 14);
    $('#locate').textContent = '◎ 내 위치';
    if (thenSortByDist) setSort('dist'); else render();
  }, () => {
    $('#locate').textContent = '◎ 내 위치';
    alert('위치를 가져오지 못했어요. 위치 권한을 확인해 주세요.');
  }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 });
}
$('#locate').addEventListener('click', () => locate(false));

(async function init() {
  const saved = store.get('fuel');
  if (saved && FUEL_LABEL[saved]) document.querySelector(`.fuel button[data-fuel="${saved}"]`).click();
  try {
    const res = await fetch('stations.json', { cache: 'no-cache' });
    const data = await res.json();
    state.stations = data.stations;
    $('#updated').textContent = data.updated;
  } catch {
    $('#list').innerHTML = '<li class="empty">데이터를 불러오지 못했어요. 잠시 후 다시 열어 주세요.</li>';
    return;
  }
  render();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
})();
