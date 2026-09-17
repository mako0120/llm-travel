const status = document.querySelector('#status');
const plan = document.querySelector('#plan');
const list = document.querySelector('#plan-list');
const params = new URLSearchParams(location.search);
const yen = new Intl.NumberFormat('ja-JP', {style: 'currency', currency: 'JPY', maximumFractionDigits: 0});

function text(value) { return document.createTextNode(value ?? '未確認'); }
function item(tag, value, className) { const node = document.createElement(tag); if (className) node.className = className; node.append(text(value)); return node; }
function lineRow(entry) {
  const row = document.createElement('li');
  row.append(item('time', entry.time || '—'));
  const body = document.createElement('div');
  const title = document.createElement('strong'); title.append(text(entry.schedule || entry.place)); body.append(title);
  const meta = document.createElement('p'); meta.append(text(`${entry.place || ''} · ${entry.transport_mode || '移動未確認'} ${Number.isFinite(entry.transport_duration_minutes) ? entry.transport_duration_minutes + '分' : ''}`)); body.append(meta);
  if (entry.label) body.append(item('span', entry.label, 'label'));
  row.append(body); return row;
}
function renderTimeline(target, entries) { target.replaceChildren(...(entries || []).map(lineRow)); }
function renderDetails(itinerary) {
  const target = document.querySelector('#details'); target.replaceChildren();
  const food = item('p', `食事候補：${(itinerary.food_options || []).map(x => `${x.name}（評価 ${x.rating}・口コミ ${x.review_count}件）`).join(' ／ ') || '未確認'}`);
  const stay = item('p', `宿泊候補：${(itinerary.lodging_options || []).map(x => `${x.name}（${yen.format(x.nightly_cost)}）`).join(' ／ ') || '未確認'}`);
  const cost = itinerary.cost_totals || {}; const total = Object.values(cost).reduce((sum, value) => sum + (Number(value) || 0), 0);
  const budget = item('p', `合計費用：${yen.format(total)}（移動 ${yen.format(cost.transport || 0)}／宿泊 ${yen.format(cost.lodging || 0)}／食事 ${yen.format(cost.food || 0)}／入場 ${yen.format(cost.admission || 0)}）`);
  target.append(food, stay, budget);
}
function renderMap(itinerary) {
  const points = itinerary.map_points || []; if (!points.length) return;
  document.querySelector('#shared-map').hidden = false;
  const target = document.querySelector('#map-points'); target.replaceChildren(); const canvas = document.querySelector('#map-canvas'); canvas.replaceChildren();
  const lats = points.map(x => x.latitude), lons = points.map(x => x.longitude); const latSpan = Math.max(...lats) - Math.min(...lats) || 1; const lonSpan = Math.max(...lons) - Math.min(...lons) || 1;
  points.forEach((point, index) => { const row = document.createElement('li'); row.append(text(`${index + 1}. ${point.label}（${point.latitude.toFixed(4)}, ${point.longitude.toFixed(4)}）`)); target.append(row); });
  points.forEach((point, index) => { const node = document.createElement('span'); node.className = 'map-node'; node.style.left = `${12 + ((point.longitude - Math.min(...lons)) / lonSpan) * 76}%`; node.style.top = `${82 - ((point.latitude - Math.min(...lats)) / latSpan) * 64}%`; node.textContent = index + 1; node.title = point.label; canvas.append(node); });
}
function renderPlan(payload) {
  list.hidden = true; plan.hidden = false; status.textContent = '';
  const {published, itinerary, comparison} = payload;
  document.querySelector('#plan-title').textContent = published.title;
  document.querySelector('#published-date').textContent = `公開日 ${new Date(published.created_at).toLocaleDateString('ja-JP')}`;
  document.querySelector('#plan-meta').textContent = `${itinerary.primary?.length || 0}件の行程 · 根拠確認済み保存版`;
  renderTimeline(document.querySelector('#timeline'), itinerary.primary); renderMap(itinerary); renderDetails(itinerary);
  const community = payload.community; document.querySelector('#community-summary').textContent = community.approved_count ? `参考評価 ${community.average_rating} / 5（${community.approved_count}件）— ${community.note}` : 'まだ公開済みの旅行者評価はありません。';
  document.querySelector('#feedback-form').onsubmit = async event => { event.preventDefault(); const form = new FormData(event.currentTarget); const response = await fetch(`/api/public/itineraries/${encodeURIComponent(published.slug)}/feedback`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({rating:Number(form.get('rating')), comment:form.get('comment')})}); const data = await response.json(); status.textContent = response.ok ? data.message : data.error; if (response.ok) event.currentTarget.reset(); };
  if (comparison?.before) { const box = document.querySelector('#comparison'); box.hidden = false; document.querySelector('#comparison-summary').textContent = comparison.summary; renderTimeline(document.querySelector('#before'), comparison.before.primary); renderTimeline(document.querySelector('#after'), itinerary.primary); }
  document.querySelector('#copy').onclick = async () => { await navigator.clipboard.writeText(location.href); status.textContent = 'リンクをコピーしました。'; };
}
function renderList(itineraries) {
  status.textContent = ''; list.replaceChildren();
  if (!itineraries.length) { list.append(document.querySelector('#empty').content.cloneNode(true)); return; }
  for (const record of itineraries) { const article = document.createElement('article'); article.className = 'plan-card'; const a = document.createElement('a'); a.href = `?plan=${encodeURIComponent(record.slug)}`; a.append(item('p', `公開日 ${new Date(record.created_at).toLocaleDateString('ja-JP')}`), item('h2', record.title), item('span', '行程と改善履歴を見る →')); article.append(a); list.append(article); }
}
async function load() {
  try { const slug = params.get('plan'); const response = await fetch(slug ? `/api/public/itineraries/${encodeURIComponent(slug)}` : '/api/public/itineraries'); if (!response.ok) throw new Error('読み込めませんでした'); const data = await response.json(); slug ? renderPlan(data) : renderList(data.itineraries); } catch (error) { status.textContent = error.message; }
}
load();
