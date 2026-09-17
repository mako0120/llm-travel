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
function renderPlan(payload) {
  list.hidden = true; plan.hidden = false; status.textContent = '';
  const {published, itinerary, comparison} = payload;
  document.querySelector('#plan-title').textContent = published.title;
  document.querySelector('#published-date').textContent = `公開日 ${new Date(published.created_at).toLocaleDateString('ja-JP')}`;
  document.querySelector('#plan-meta').textContent = `${itinerary.primary?.length || 0}件の行程 · 根拠確認済み保存版`;
  renderTimeline(document.querySelector('#timeline'), itinerary.primary); renderDetails(itinerary);
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
