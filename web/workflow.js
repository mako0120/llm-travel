const WORKSPACE_KEY = 'llm-travel-workspace-v2';
const workflow = { runId: null, packet: [], review: null, notice: '' };
try { const restored = JSON.parse(localStorage.getItem(WORKSPACE_KEY) || '{}'); if (restored.conditions) Object.assign(state, restored.conditions); Object.assign(workflow, restored.workflow || {}); } catch (_) {}
const persistWorkspace = () => localStorage.setItem(WORKSPACE_KEY, JSON.stringify({ conditions: state, workflow }));
const requestJson = async (url, options) => { const response = await fetch(url, options || {}); const body = await response.json().catch(() => ({})); if (!response.ok) throw new Error(body.message || body.error || '処理に失敗しました。'); return body; };
const requirements = () => ({ departure: state.departure, destination: state.destination, nights: Number(state.nights), themes: state.themes, preference: state.preference, budget: { min: state.budgetMin, max: state.budgetMax, per_person: true }, accommodation: state.accommodation, transportation: state.transport, requests: state.requests });
const downloadJson = (name, payload) => { const href = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })); const link = Object.assign(document.createElement('a'), { href, download: name }); link.click(); setTimeout(() => URL.revokeObjectURL(href), 0); };
const baseReviewPage = reviewPage, baseItineraryPage = itineraryPage, baseImprovementPage = improvementPage, basePublicPage = publicPage, baseRender = render;
runResearch = async function () {
  const button = document.querySelector('#research') || document.querySelector('#rerun');
  if (!state.destination.trim()) { alert('行き先を入力してください。'); return; }
  if (button) { button.disabled = true; button.textContent = '公開情報を取得中…'; }
  try {
    const results = await Promise.all([
      requestJson('/api/free-research', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ destination: state.destination }) }),
      requestJson('/api/workspace/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ requirements: requirements(), source_targets: ['nominatim', 'wikimedia', 'open_meteo'] }) })
    ]);
    evidence = results[0].evidence || []; selectedEvidence = new Set(); packetCreated = false;
    workflow.runId = results[1].run.id; workflow.packet = []; workflow.review = null;
    workflow.notice = '研究ランを作成しました。候補を選択して根拠パケットへ保存してください。';
    persistWorkspace(); render('research');
  } catch (error) { workflow.notice = error.message; persistWorkspace(); alert(error.message); } finally { if (button) button.disabled = false; }
};
bindResearch = function () {
  const rerun = document.querySelector('#rerun'); if (rerun) rerun.onclick = runResearch;
  document.querySelectorAll('[data-evidence]').forEach(el => el.onchange = () => { const id = Number(el.dataset.evidence); if (el.checked) selectedEvidence.add(id); else selectedEvidence.delete(id); packetCreated = false; render('research'); });
  document.querySelectorAll('[data-add]').forEach(el => el.onclick = () => { selectedEvidence.add(Number(el.dataset.add)); packetCreated = false; render('research'); });
  const packet = document.querySelector('#packet'); if (packet) packet.onclick = async () => {
    if (!workflow.runId) { alert('研究ランがありません。再検索してください。'); return; }
    const chosen = Array.from(selectedEvidence).map(index => evidence[index]).filter(Boolean);
    packet.disabled = true; packet.textContent = 'SQLiteへ保存中…';
    try {
      const saved = await requestJson('/api/workspace/runs/' + encodeURIComponent(workflow.runId) + '/packet', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ evidence: chosen }) });
      workflow.packet = saved.evidence; workflow.notice = saved.evidence.length + '件を根拠パケットへ保存しました。すべて未検証です。'; packetCreated = true; persistWorkspace(); render('research');
    } catch (error) { workflow.notice = error.message; persistWorkspace(); render('research'); }
  };
  const next = document.querySelector('#next-review'); if (next) next.onclick = () => render('review');
};
pages.review = () => baseReviewPage() + '<section class="page workflow-tools"><section class="card"><h2>手動レビューの受け渡し</h2><p>WebアプリはCodex・Claudeを起動しません。根拠パケットを保存し、明示的に実行したローカル結果だけを読み込みます。</p><div class="actions"><button class="secondary" id="download-review">実行用JSONを保存</button><label class="secondary file-button">結果JSONを読み込む<input id="review-file" type="file" accept="application/json"></label></div><div id="review-import-status" class="empty"></div><div class="actions"><button class="secondary" data-go="research">← 根拠候補へ戻る</button><button class="secondary" data-go="itinerary">詳細旅程の検証画面を見る →</button></div></section></section>';
function bindReview() {
  const output = document.querySelector('#review-import-status'); if (output) output.textContent = workflow.review ? workflow.review.summary : 'レビュー結果はまだ読み込まれていません。';
  const download = document.querySelector('#download-review'); if (download) { download.disabled = !workflow.packet.length; download.onclick = () => downloadJson('review-input-' + (workflow.runId || 'draft') + '.json', { requirements: requirements(), evidence: workflow.packet, instructions: ['Run manually: python scripts/run_dual_agent_review.py input.json output.json', 'The browser never starts agents.', 'Unverified evidence must not be saved as an itinerary.'] }); }
  const file = document.querySelector('#review-file'); if (file) file.onchange = async event => { const selected = event.target.files && event.target.files[0]; if (!selected) return; try { const result = JSON.parse(await selected.text()); if (!result.chatgpt_codex || !result.claude) throw new Error('Codex と Claude の両方を含む実行結果JSONを選択してください。'); workflow.review = { imported_at: new Date().toISOString(), summary: '手動で読み込んだ実行結果です。検証済み根拠がないため旅程保存はまだできません。' }; workflow.notice = '実行結果をローカル下書きへ読み込みました。'; persistWorkspace(); render('review'); } catch (error) { alert(error.message); } };
}
pages.itinerary = () => baseItineraryPage() + '<section class="page workflow-tools"><div class="workflow-status"><b>現在の研究ラン</b><small>' + (workflow.runId || '未作成') + ' / 根拠パケット ' + workflow.packet.length + '件 / ' + (workflow.review ? '実行結果読込済み' : 'レビュー未読込') + '</small></div></section>';
pages.improve = () => baseImprovementPage() + '<section class="page workflow-tools"><div class="workflow-status"><b>改善対象</b><small>保存済みかつ検証済みの詳細旅程だけが、理由付きの不変バージョンとして改善できます。</small></div></section>';
pages.public = () => basePublicPage() + '<section class="page workflow-tools"><div id="public-api-status" class="workflow-status"><small>公開APIを確認中です。</small></div></section>';
pages.settings = () => '<section class="page"><h1>設定 / Provider 状態</h1><p class="subtitle">研究モードと商用モードの接続条件を、根拠とともに確認します。</p><section class="card"><table><thead><tr><th>提供元</th><th>研究モード</th><th>商用モード</th></tr></thead><tbody><tr><td>Nominatim</td><td>明示検索・毎秒一件以下</td><td>自己ホストまたは商用接続が必要</td></tr><tr><td>Open-Meteo</td><td>予報候補のみ</td><td>商用ライセンスと専用接続が必要</td></tr><tr><td>Wikimedia</td><td>ライセンス付き調査候補</td><td>帰属とページ単位の利用条件を確認</td></tr><tr><td>GTFS-JP</td><td>事業者公式フィードを選択</td><td>事業者別の利用条件と鮮度を確認</td></tr><tr><td>Google / TikTok / 食べログ</td><td>未設定</td><td>許可済み公式接続のみ</td></tr></tbody></table><p>詳細な根拠と運用条件はリポジトリの <code>docs/provider-operation-policy.md</code> に記録しています。</p></section></section>';
async function bindPublic() { const target = document.querySelector('#public-api-status'); if (!target) return; try { const data = await requestJson('/api/public/itineraries'); target.innerHTML = '<b>公開API接続済み</b><small>公開済み・検証済みプラン ' + data.itineraries.length + '件。詳細と共有は <a href="public.html">公開プランページ</a> で確認できます。</small>'; } catch (error) { target.textContent = '公開APIを読み込めません: ' + error.message; } }
const pageName = () => location.hash.replace(/^#/, '') || 'home';
const knownPages = new Set(['home', 'research', 'review', 'itinerary', 'improve', 'public', 'settings', 'help']);
render = function (name) {
  const current = knownPages.has(name) ? name : 'home';
  baseRender(current);
  if (current === 'home') persistWorkspace();
  if (current === 'review') bindReview();
  if (current === 'public') bindPublic();
  document.querySelectorAll('[data-go]').forEach(button => button.onclick = () => navigate(button.dataset.go));
};
function navigate(name) {
  if (!knownPages.has(name)) return;
  if (pageName() === name) render(name);
  else location.hash = name;
}
document.querySelectorAll('[data-page]').forEach(button => button.onclick = () => navigate(button.dataset.page));
window.addEventListener('hashchange', () => render(pageName()));
render(pageName());

