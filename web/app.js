(() => {
  "use strict";

  // Question labels shown as the step heading. The authoritative question
  // text always comes from the server's `reply` field, not from this list.
  const QUESTION_LABELS = [
    "お住まいの地域", "行き先", "宿泊数", "興味のあるテーマ", "穴場・王道の希望",
    "予算", "宿泊タイプ", "現地の交通手段", "特別な要望",
  ];

  const $ = (selector) => document.querySelector(selector);
  const chat = $("#chat"), title = $("#title"), sub = $("#sub"), form = $("#form"),
        next = $("#next"), answer = $("#answer"), sendBtn = $("#send"),
        status = $("#status"), stepsEl = $("#steps"), preview = $("#preview");

  const sessionId = window.crypto && window.crypto.randomUUID
    ? window.crypto.randomUUID()
    : `s-${Date.now()}-${Math.random().toString(16).slice(2)}`;

  let busy = false;
  let currentState = "awaiting_consent";

  function addBubble(text, isUser) {
    const row = document.createElement("div");
    row.className = `row${isUser ? " user" : ""}`;
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = isUser ? "あ" : "AI";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;
    row.append(avatar, bubble);
    chat.appendChild(row);
    chat.scrollTop = chat.scrollHeight;
    return row;
  }

  function showTyping() {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = '<div class="avatar">AI</div><div class="bubble typing"><span></span><span></span><span></span></div>';
    chat.appendChild(row);
    chat.scrollTop = chat.scrollHeight;
    return row;
  }

  function setBusy(value) {
    busy = value;
    next.disabled = value || currentState === "ready";
    sendBtn.disabled = value;
    answer.disabled = value;
  }

  function updateSteps(stepNumber) {
    stepsEl.querySelectorAll(".step").forEach((el) => {
      const n = Number(el.dataset.n);
      el.classList.toggle("active", n === stepNumber);
      el.classList.toggle("done", n < stepNumber);
    });
  }

  function showError(message) {
    let banner = document.querySelector(".error-banner");
    if (!banner) {
      banner = document.createElement("div");
      banner.className = "error-banner";
      form.after(banner);
    }
    banner.textContent = message;
  }

  function clearError() {
    const banner = document.querySelector(".error-banner");
    if (banner) banner.remove();
  }

  async function callPlanner(message) {
    const response = await fetch("/api/planner", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message }),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok || !data) {
      throw new Error((data && data.error) || `サーバーエラー (${response.status})`);
    }
    return data;
  }

  function renderCollecting(stepNumber, replyText) {
    const label = QUESTION_LABELS[stepNumber - 1] || `質問 ${stepNumber}`;
    title.textContent = label;
    sub.textContent = replyText;
    form.innerHTML = `<div class="field"><label>${label}</label>` +
      '<p class="hint">左のチャット欄に回答を入力し、送信してください。</p></div>';
    updateSteps(1);
    next.textContent = "回答を送信して次へ　→";
  }

  function renderReady(data) {
    title.textContent = "詳細な旅行プランを作成します";
    sub.textContent = data.reply;
    form.innerHTML = "";
    next.textContent = "調査中です…";
    updateSteps(2);

    const parts = [];
    if (data.research) {
      parts.push(
        `<span class="tag tag-requested">調査ステータス: ${data.research.state}</span>` +
        `<strong>${data.research.message}</strong>` +
        "<p>交通・営業時間・料金・宿・レストランを出典付きで確認してから、時間単位のプランを表示します。</p>"
      );
    }
    if (data.planning_brief && data.planning_brief.requirements) {
      const rows = Object.entries(data.planning_brief.requirements)
        .map(([key, value]) => `<li><b>${key}</b>: ${value}</li>`)
        .join("");
      parts.push(`<ul class="hint">${rows}</ul>`);
    }
    preview.innerHTML = parts.join("") || preview.innerHTML;
  }

  function applyState(data) {
    currentState = data.state;
    if (data.state === "awaiting_consent") {
      title.textContent = "AI旅行計画を作成しますか？";
      sub.textContent = "「はい」と答えると、あなたに合う旅行プランを一緒に作ります。";
      form.innerHTML = "";
      next.textContent = "はい、作成してください　→";
      updateSteps(1);
    } else if (data.state === "collecting") {
      renderCollecting(data.step, data.reply);
    } else if (data.state === "ready") {
      renderReady(data);
    }
  }

  async function send(forcedMessage) {
    if (busy) return;
    const message = (forcedMessage !== undefined ? forcedMessage : answer.value).trim();
    if (!message) return;
    clearError();
    addBubble(message, true);
    answer.value = "";
    setBusy(true);
    const typingRow = showTyping();
    try {
      const data = await callPlanner(message);
      typingRow.remove();
      if (data.reply) addBubble(data.reply, false);
      applyState(data);
      status.textContent = "● オンライン";
      status.classList.remove("offline");
    } catch (err) {
      typingRow.remove();
      status.textContent = "● オフライン";
      status.classList.add("offline");
      showError(`通信に失敗しました: ${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  next.addEventListener("click", () => {
    send(currentState === "awaiting_consent" ? "はい" : undefined);
  });
  sendBtn.addEventListener("click", () => send());
  answer.addEventListener("keydown", (event) => {
    if (event.key === "Enter") send();
  });

  updateSteps(1);
  addBubble("こんにちは。AI旅行計画を作成しますか？", false);
})();
