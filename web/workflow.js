const WORKSPACE_KEY = 'llm-travel-workspace-v2';
const workflow = { runId: null, packet: [], draft: null, review: null, notice: '', hydratedRunId: null, autoWorkerStatus: null, previewEvidence: [] };
try { const restored = JSON.parse(localStorage.getItem(WORKSPACE_KEY) || '{}'); if (restored.conditions) Object.assign(state, restored.conditions); Object.assign(workflow, restored.workflow || {}); } catch (_) {}
const persistWorkspace = () => localStorage.setItem(WORKSPACE_KEY, JSON.stringify({ conditions: state, workflow }));
const requestJson = async (url, options) => { const response = await fetch(url, options || {}); const body = await response.json().catch(() => ({})); if (!response.ok) throw new Error(body.message || body.error || '処理に失敗しました。'); return body; };
const requirements = () => ({ departure: state.departure, destination: state.destination, nights: Number(state.nights), themes: state.themes, preference: state.preference, budget: { min: state.budgetMin, max: state.budgetMax, per_person: true }, accommodation: state.accommodation, transportation: state.transport, requests: state.requests });
const downloadJson = (name, payload) => { const href = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })); const link = Object.assign(document.createElement('a'), { href, download: name }); link.click(); setTimeout(() => URL.revokeObjectURL(href), 0); };
const baseResearchPage = pages.research, baseReviewPage = reviewPage, baseItineraryPage = itineraryPage, baseImprovementPage = improvementPage, basePublicPage = publicPage, baseRender = render;
const PLANNER_CHAT_KEY = 'llm-travel-planner-chat-v1';
const newPlannerSessionId = () => 'planner-' + Math.random().toString(36).slice(2);
let plannerChat = { sessionId: newPlannerSessionId(), messages: [], ready: null, researchRunId: null, generating: false };
try { const savedPlannerChat = JSON.parse(localStorage.getItem(PLANNER_CHAT_KEY) || '{}'); if (savedPlannerChat && typeof savedPlannerChat.sessionId === 'string' && Array.isArray(savedPlannerChat.messages)) plannerChat = savedPlannerChat; } catch (_) {}
const persistPlannerChat = () => localStorage.setItem(PLANNER_CHAT_KEY, JSON.stringify(plannerChat));
function autoWorkerStatusMarkup(status) {
  if (!status) return '<div class="worker-empty"><span class="worker-state">待機中</span><p>自動調査ワーカーの実行結果はまだありません。Web画面からワーカーを起動することはありません。</p></div>';
  const lists = [...(status.missing_evidence || []), ...(status.required_evidence || [])];
  if (status.outcome === 'reviewed_not_saved') return '<div><span class="worker-state reviewed">レビュー完了・未保存</span><p><b>レビューは通過しましたが、未検証情報のため確定旅程として保存していません。</b></p><p>収集した候補: ' + esc(status.evidence_collected ?? 0) + '件。公式情報で検証された根拠がそろうまで保存・公開はできません。</p><p class="worker-note">記録日時: ' + esc(status.created_at || '未記録') + '</p></div>';
  if (status.outcome === 'unresolved') return '<div><span class="worker-state unresolved">追加調査が必要</span><p><b>自動レビューだけでは旅程を確定できませんでした。</b></p><p>' + esc(status.reason || '追加の根拠が必要です。') + '</p>' + (lists.length ? '<div class="worker-missing"><b>不足している根拠</b><ul>' + lists.map(item => '<li>' + esc(item) + '</li>').join('') + '</ul></div>' : '') + '<p class="worker-note">上記は不足項目の名称です。未検証の候補を事実として表示しているものではありません。</p></div>';
  return '<div><span class="worker-state skipped">今回は処理対象外</span><p>' + esc(status.reason || 'このrunは処理されませんでした。') + '</p><p class="worker-note">別ワーカーによるclaim済み等の場合があります。</p></div>';
}
function autoWorkerCard() {
  const runId = workflow.runId || plannerChat.researchRunId;
  const cls = workflow.autoWorkerStatus ? ' status-' + workflow.autoWorkerStatus.outcome.replace('reviewed_not_saved','reviewed') : '';
  return '<section class="card auto-worker-card' + cls + '"><div class="auto-worker-head"><div><h2>自動調査の状況</h2><p>Phase 1.5ワーカーが別プロセスで処理した結果だけを表示します。</p></div><code>' + esc(runId || 'run未作成') + '</code></div><div id="auto-worker-status">' + autoWorkerStatusMarkup(workflow.autoWorkerStatus) + '</div><div class="worker-actions"><button type="button" class="secondary" data-refresh-worker ' + (runId ? '' : 'disabled') + '>↻ 状況を再読み込み</button>' + (runId ? '<button type="button" class="secondary" data-go="research">根拠候補を見る →</button>' : '') + '</div><p class="worker-note">この画面は読み取り専用です。Webサーバーは自動ワーカーを起動せず、GitHub書き込み資格情報も持ちません。</p></section>';
}
function networkEvidenceMarkup() {
  const items = Array.isArray(workflow.previewEvidence) ? workflow.previewEvidence.slice(0, 8) : [];
  if (!items.length) return '';
  return '<section class="network-evidence"><div><b>インターネット検索済みの公開候補</b><small>候補 ' + esc(items.length) + '件。すべて unverified です。</small></div><ul>' + items.map(item => '<li><b>' + esc(item.title) + '</b><small>' + esc(item.source_type) + ' ／ 取得: ' + esc(item.retrieved_at) + '</small><code>' + esc(item.url) + '</code></li>').join('') + '</ul></section>';
}
function assistantDraftCard() {
  if (!workflow.draft) return '<section id="assistant-draft" class="card assistant-draft empty"><b>旅程下書きを準備中です</b><p>根拠候補が保存されると、ここに日ごとの候補を表示します。時刻・運賃・料金は公式根拠で確認されるまで未確定です。</p></section>';
  const draft = workflow.draft;
  return '<section id="assistant-draft" class="card assistant-draft"><div class="auto-worker-head"><div><h2>自動生成した旅程下書き</h2><p>' + esc(draft.notice) + '</p></div><span class="chip research">' + esc(draft.status) + '</span></div><h3>' + esc(draft.title) + '</h3><ol>' + draft.days.map(day => '<li><b>' + esc(day.day) + '日目・' + esc(day.label) + '</b>　' + esc(day.focus) + '<br><small>根拠: ' + esc(day.source) + ' ／ 時刻: ' + esc(day.time) + ' ／ 移動: ' + esc(day.transport) + ' ／ 費用: ' + esc(day.cost) + '</small></li>').join('') + '</ol>' + networkEvidenceMarkup() + '<div class="save-block"><b>保存・公開はブロック中</b><p>' + esc(draft.save_blocked_reason) + '</p></div><button type="button" class="secondary" data-go="research">根拠候補を確認する →</button></section>';
}
async function refreshAutoWorkerStatus() {
  const runId = workflow.runId || plannerChat.researchRunId;
  if (!runId) return;
  try {
    const payload = await requestJson('/api/workspace/runs/' + encodeURIComponent(runId) + '/auto-worker-status');
    workflow.autoWorkerStatus = payload.auto_worker || null;
    if (workflow.autoWorkerStatus && !workflow.draft) {
      try {
        const drafted = await requestJson('/api/workspace/runs/' + encodeURIComponent(runId) + '/draft', { method: 'POST' });
        workflow.draft = drafted.draft;
      } catch (_) {}
    }
    persistWorkspace();
    const target = document.querySelector('#auto-worker-status'); if (target) target.innerHTML = autoWorkerStatusMarkup(workflow.autoWorkerStatus);
    const draftTarget = document.querySelector('#assistant-draft'); if (draftTarget) draftTarget.outerHTML = assistantDraftCard();
  } catch (error) { const target = document.querySelector('#auto-worker-status'); if (target) target.innerHTML = '<div class="worker-missing"><b>状況を取得できません</b><p>' + esc(error.message) + '</p></div>'; }
}
pages.assistant = () => `<section class="page"><div class="crumb">ホーム　›　AI旅行プランナー</div><h1>AI旅行プランナー</h1><p class="subtitle">一問ずつ条件を確認し、情報収集後に根拠付きの旅程下書きを作成します。</p><section class="card"><div class="planner-messages" aria-live="polite">${plannerChat.messages.map(item => `<article class="planner-message ${item.role}"><b>${item.role === 'assistant' ? '旅行プランナー' : 'あなた'}</b><p>${esc(item.text)}</p></article>`).join('') || '<p class="empty">「はい」と送ると、最初の質問が表示されます。</p>'}</div>${plannerChat.ready ? `<section class="save-block"><b>${plannerChat.generating ? '旅程下書きを生成中です' : '条件の確認が完了しました'}</b><p>${plannerChat.generating ? '情報収集、根拠パケット保存、Codex候補準備を進めています。Claude独立レビューは実行待ちです。' : '旅程下書きの生成を準備しています。'}</p></section>` : `<form id="planner-form" class="actions"><input id="planner-input" aria-label="回答" placeholder="「はい」と入力して開始" required><button class="primary" type="submit">送信</button></form>`}</section>${plannerChat.ready ? autoWorkerCard() + assistantDraftCard() : ''}</section>`;
function bindAssistant() { const form=document.querySelector('#planner-form'); if(form) form.onsubmit=async event=>{event.preventDefault();const input=document.querySelector('#planner-input'),message=input.value.trim();if(!message)return;input.disabled=true;plannerChat.messages.push({role:'user',text:message});persistPlannerChat();try{const turn=await requestJson('/api/planner',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:plannerChat.sessionId,message})});plannerChat.messages.push({role:'assistant',text:turn.reply});if(turn.state==='ready'){plannerChat.ready=turn.planning_brief.requirements;plannerChat.generating=true;plannerChat.researchRunId=turn.research?.run_id||null;workflow.runId=plannerChat.researchRunId;workflow.autoWorkerStatus=null;workflow.packet=[];workflow.draft=null;workflow.review=null;workflow.hydratedRunId=null}persistPlannerChat();persistWorkspace();render('assistant');if(turn.state==='ready')await startPlannerResearch()}catch(error){plannerChat.messages.push({role:'assistant',text:'処理に失敗しました: '+error.message});persistPlannerChat();render('assistant')}};}
async function startPlannerResearch(){ const a=plannerChat.ready,budget=Number(String(a.budget).replace(/[^0-9]/g,''))||0; Object.assign(state,{departure:a.home_region,destination:a.destination,nights:a.nights,themes:a.themes.split(/[、,・]/).filter(Boolean),preference:a.spot_preference,budgetMin:budget,budgetMax:budget,accommodation:a.lodging_type,transport:a.transport.split(/[、,・]/).filter(Boolean),requests:a.special_requests}); workflow.notice='インターネット上の無料公開情報を検索しています。'; workflow.previewEvidence=[]; persistWorkspace(); try { const research=await requestJson('/api/free-research',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({destination:a.destination})}); workflow.previewEvidence=(research.evidence||[]).map(item=>({title:item.title,source_type:item.source_type,url:item.url,retrieved_at:item.retrieved_at})); if(research.evidence&&research.evidence.length){const preview=await requestJson('/api/workspace/draft-preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({requirements:{destination:a.destination,nights:a.nights},evidence:research.evidence})});workflow.draft=preview.draft;workflow.notice='インターネット検索で取得した'+research.evidence.length+'件の未検証候補から、保存前の旅程下書きを表示しています。';}else{workflow.notice='インターネット上の公開情報から候補を取得できませんでした。調査runは作成済みです。';}}catch(error){workflow.notice='インターネット検索による下書き候補を取得できませんでした: '+error.message;} persistWorkspace(); plannerChat.generating=false; persistPlannerChat(); await refreshAutoWorkerStatus(); render('assistant'); }

runResearch = async function () {
  const button = document.querySelector('#research') || document.querySelector('#rerun');
  if (!state.destination.trim()) { alert('行き先を入力してください。'); return; }
  if (button) { button.disabled = true; button.textContent = '公開情報を取得中…'; }
  try {
    const research = await requestJson('/api/free-research', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ destination: state.destination }) });
    evidence = research.evidence || [];
    const created = await requestJson('/api/workspace/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ requirements: requirements(), source_targets: ['nominatim', 'wikimedia', 'open_meteo'] }) });
    workflow.runId = created.run.id; workflow.packet = []; workflow.draft = null; workflow.review = null; workflow.hydratedRunId = null; workflow.autoWorkerStatus = null;
    if (!evidence.length) throw new Error('旅程下書きを作る候補が取得できませんでした。再検索してください。');
    const saved = await requestJson('/api/workspace/runs/' + encodeURIComponent(workflow.runId) + '/packet', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ evidence }) });
    workflow.packet = saved.evidence; selectedEvidence = new Set(evidence.map((_, index) => index)); packetCreated = true;
    const drafted = await requestJson('/api/workspace/runs/' + encodeURIComponent(workflow.runId) + '/draft', { method: 'POST' });
    workflow.draft = drafted.draft;
    workflow.notice = '情報収集が完了し、' + saved.evidence.length + '件の未検証根拠から旅程下書きを自動生成しました。確認へ進んでください。';
    persistWorkspace(); navigate('review');
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
      workflow.packet = saved.evidence; const drafted = await requestJson('/api/workspace/runs/' + encodeURIComponent(workflow.runId) + '/draft', { method: 'POST' }); workflow.draft = drafted.draft; workflow.notice = saved.evidence.length + '件を根拠パケットへ保存し、旅程下書きを更新しました。すべて未検証です。'; packetCreated = true; persistWorkspace(); render('research');
    } catch (error) { workflow.notice = error.message; persistWorkspace(); render('research'); }
  };
  const next = document.querySelector('#next-review'); if (next) next.onclick = () => render('review');
  const agentBrief = document.querySelector('#download-agent-research'); if (agentBrief) agentBrief.onclick = async () => {
    if (!workflow.runId) { alert('先に情報収集を実行してください。'); return; }
    try {
      const payload = await requestJson('/api/workspace/runs/' + encodeURIComponent(workflow.runId) + '/agent-research', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'request' }) });
      downloadJson('agent-web-research-' + workflow.runId + '.json', payload.request);
      workflow.notice = 'Google / TikTok 用の調査依頼JSONを保存しました。結果は未検証の根拠としてだけ取り込めます。'; persistWorkspace(); render('research');
    } catch (error) { alert(error.message); }
  };
  const agentFile = document.querySelector('#agent-research-file'); if (agentFile) agentFile.onchange = async event => {
    const selected = event.target.files && event.target.files[0]; if (!selected || !workflow.runId) return;
    try {
      const imported = JSON.parse(await selected.text()); const candidates = Array.isArray(imported) ? imported : imported.evidence;
      const saved = await requestJson('/api/workspace/runs/' + encodeURIComponent(workflow.runId) + '/agent-research', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ evidence: candidates }) });
      workflow.packet.push(...saved.evidence); workflow.notice = saved.evidence.length + '件のエージェント調査結果を未検証根拠として保存しました。'; persistWorkspace(); render('research');
    } catch (error) { alert(error.message); }
  };
  const manual = document.querySelector('#manual-evidence');
  if (manual) manual.onsubmit = async event => {
    event.preventDefault();
    if (!workflow.runId) { alert('先に情報収集を実行してください。'); return; }
    const form = new FormData(manual);
    try {
      const facts = JSON.parse(form.get('facts'));
      if (!facts || typeof facts !== 'object' || Array.isArray(facts)) throw new Error('確認内容はJSONオブジェクトで入力してください。');
      const saved = await requestJson('/api/research/' + encodeURIComponent(workflow.runId) + '/evidence', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent: 'human', source_type: 'official', title: form.get('title'), url: form.get('url'), facts,
          retrieved_at: new Date().toISOString(), expires_at: form.get('expires_at'), verification_status: 'verified' })
      });
      workflow.packet.push(saved.evidence); workflow.hydratedRunId = null;
      workflow.notice = '運用者が確認した根拠を記録しました。'; persistWorkspace(); render('research');
    } catch (error) { alert(error.message); }
  };
  const complete = document.querySelector('#complete-research');
  if (complete) complete.onclick = async () => {
    if (!workflow.runId) return;
    if (!workflow.packet.some(item => item.verification_status === 'verified')) {
      alert('公式URLを人間が確認した検証済み根拠を、少なくとも1件記録してください。');
      return;
    }
    try {
      await requestJson('/api/research/' + encodeURIComponent(workflow.runId) + '/complete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ state: 'ready' }) });
      workflow.notice = '研究ランを完了として記録しました。保存は旅程の構造検証と二つのレビュー承認後です。'; persistWorkspace(); render('review');
    } catch (error) { alert(error.message); }
  };
};
pages.research = () => baseResearchPage() + '<section class="page workflow-tools">' + autoWorkerCard() + '<section class="card"><h2>Codex / Claude のネット調査を取り込む</h2><p>Google と TikTok の調査は、明示実行した独立エージェントの URL 付き結果だけを読み込みます。取得結果は必ず未検証です。</p><div class="actions"><button class="secondary" id="download-agent-research">調査依頼JSONを保存</button><label class="secondary file-button">調査結果JSONを読み込む<input id="agent-research-file" type="file" accept="application/json"></label></div></section><section class="card"><h2>検証済み根拠を手動で記録</h2><p>公式サイトを人間が確認した後にだけ入力します。候補情報を自動で verified に変更する機能ではありません。</p><form id="manual-evidence" class="manual-evidence"><label>根拠タイトル<input name="title" required maxlength="160" placeholder="例: 事業者公式時刻表（確認済み）"></label><label>公式URL<input name="url" type="url" required placeholder="https://"></label><label>失効日時（JST）<input name="expires_at" type="datetime-local" required></label><label>確認内容（JSON）<textarea name="facts" required placeholder="{&quot;line_name&quot;:&quot;...&quot;,&quot;checked_by&quot;:&quot;operator&quot;}"></textarea></label><button class="secondary" type="submit">検証済み根拠を記録</button><button class="primary" type="button" id="complete-research">研究ランを完了する</button></form></section></section>';
async function hydrateResearchPacket() {
  if (!workflow.runId || workflow.hydratedRunId === workflow.runId) return;
  try {
    const saved = await requestJson('/api/research/' + encodeURIComponent(workflow.runId));
    evidence = saved.evidence || [];
    selectedEvidence = new Set(evidence.map((_, index) => index));
    packetCreated = evidence.length > 0;
    workflow.packet = saved.evidence || [];
    if (workflow.packet.length && !workflow.draft) { try { const drafted = await requestJson('/api/workspace/runs/' + encodeURIComponent(workflow.runId) + '/draft', { method: 'POST' }); workflow.draft = drafted.draft; } catch (_) {} }
    workflow.hydratedRunId = workflow.runId;
    workflow.notice = evidence.length + '件の保存済み根拠パケットを復元しました。';
    persistWorkspace();
    render('research');
  } catch (error) {
    workflow.notice = '保存済み根拠を復元できません: ' + error.message;
    persistWorkspace();
  }
}
pages.review = () => baseReviewPage() + '<section class="page workflow-tools"><section class="card auto-draft"><h2>情報収集から自動生成した旅程下書き <span class="chip research">needs_research</span></h2>' + (workflow.draft ? '<p>' + esc(workflow.draft.notice) + '</p><h3>' + esc(workflow.draft.title) + '</h3><ol>' + workflow.draft.days.map(day => '<li><b>' + day.day + '日目・' + esc(day.label) + '</b>　' + esc(day.focus) + '<br><small>根拠: ' + esc(day.source) + ' ／ 時刻・移動・費用: 未確定</small></li>').join('') + '</ol><div class="save-block"><b>保存・公開はブロック中</b><p>' + esc(workflow.draft.save_blocked_reason) + '</p></div>' : '<p class="empty">情報収集を実行すると、ここに自動生成された下書きが表示されます。</p>') + '</section><section class="card"><h2>手動レビューの受け渡し</h2><p>WebアプリはCodex・Claudeを起動しません。根拠パケットを保存し、明示的に実行したローカル結果だけを読み込みます。</p><div class="actions"><button class="secondary" id="download-review">実行用JSONを保存</button><label class="secondary file-button">結果JSONを読み込む<input id="review-file" type="file" accept="application/json"></label></div><div id="review-import-status" class="empty"></div><div class="actions"><button class="secondary" data-go="research">← 根拠候補へ戻る</button><button class="secondary" data-go="itinerary">詳細旅程の検証画面を見る →</button></div></section></section>';
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
const pageName = () => new URLSearchParams(location.search).get('screen') || location.hash.replace(/^#/, '') || 'home';
const knownPages = new Set(['home', 'assistant', 'research', 'review', 'itinerary', 'improve', 'public', 'settings', 'help']);
render = function (name) {
  const current = knownPages.has(name) ? name : 'home';
  baseRender(current);
  if (current === 'home') persistWorkspace();
  if (current === 'research') { void hydrateResearchPacket(); void refreshAutoWorkerStatus(); }
  if (current === 'assistant') { bindAssistant(); void refreshAutoWorkerStatus(); requestAnimationFrame(() => { const latest = document.querySelector('.planner-message:last-of-type, #planner-form, #planner-start-research'); if (latest) latest.scrollIntoView({ block: 'center', behavior: 'smooth' }); }); }
  if (current === 'review') bindReview();
  if (current === 'public') bindPublic();
  document.querySelectorAll('[data-go]').forEach(button => button.onclick = () => navigate(button.dataset.go));
  document.querySelectorAll('[data-refresh-worker]').forEach(button => button.onclick = async () => { button.disabled = true; workflow.hydratedRunId = null; await refreshAutoWorkerStatus(); if (pageName() === 'research') await hydrateResearchPacket(); button.disabled = false; });
};
function navigate(name) {
  if (!knownPages.has(name)) return;
  if (pageName() === name) { render(name); return; }
  const url = new URL(location.href);
  url.searchParams.set('screen', name);
  url.hash = '';
  history.pushState({}, '', url);
  render(name);
}
document.querySelectorAll('[data-page]').forEach(button => button.onclick = () => navigate(button.dataset.page));
window.addEventListener('hashchange', () => render(pageName()));
window.addEventListener('popstate', () => render(pageName()));
render(pageName());

