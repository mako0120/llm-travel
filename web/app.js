(() => {
  "use strict";
  // This screen is local: no fetch, provider calls or persistence.
  // A downloaded brief is unverified input, not a plan or an approved rule.
  const FIELDS = [
    ["home_region", "出発地"], ["destination", "行き先"], ["nights", "宿泊数"],
    ["themes", "テーマ"], ["spot_preference", "スポットの好み"], ["budget", "予算"],
    ["lodging_type", "宿泊タイプ"], ["transport", "移動手段"], ["special_requests", "特別な要望"],
  ];
  const form = document.querySelector("#trip-form");
  const summary = document.querySelector("#summary");
  const status = document.querySelector("#status");
  const confirmation = document.querySelector("#confirmation");
  const sample = document.querySelector("#sample");
  const clear = document.querySelector("#clear");
  const heading = document.querySelector("#form-title");
  const dialog = document.querySelector("#replace-dialog");
  let reviewed = null;
  let pendingAction = null;

  function confirmReplace(action, isSample = false) {
    pendingAction = action;
    document.querySelector("#dialog-title").textContent = isSample ? "サンプルに置き換えますか？" : "入力をクリアしますか？";
    document.querySelector("#dialog-description").textContent = isSample ? "入力中の条件は合成サンプルに置き換わります。" : "この画面の入力内容を消します。保存済みの条件ファイルは残ります。";
    document.querySelector("#confirm-replace").textContent = isSample ? "置き換える" : "クリアする";
    dialog.returnValue = "cancel";
    dialog.showModal();
  }
  dialog.addEventListener("close", () => {
    if (dialog.returnValue === "confirm" && pendingAction) pendingAction();
    pendingAction = null;
  });

  function values() {
    return Object.fromEntries(FIELDS.map(([key]) => [key, form.elements.namedItem(key).value.trim()]));
  }

  function renderSummary() {
    const data = reviewed || values();
    summary.replaceChildren();
    let count = 0;
    for (const [key, label] of FIELDS) {
      const value = data[key];
      if (value) count += 1;
      const row = document.createElement("div");
      row.className = "summary-row";
      const term = document.createElement("dt");
      term.textContent = label;
      const detail = document.createElement("dd");
      detail.className = value ? "" : "empty";
      let display = value;
      if (value && key === "budget") display = `${Number(value).toLocaleString("ja-JP")} 円`;
      if (value && key === "nights") display = `${value} 泊`;
      detail.textContent = display || "未入力";
      row.append(term, detail);
      summary.append(row);
    }
    document.querySelector("#count").textContent = `${count} / 9`;
    document.querySelector("#progress").value = count;
    clear.disabled = count === 0;
  }

  function setStep(id) {
    document.querySelectorAll(".steps li").forEach((step) => {
      if (step.id === id) step.setAttribute("aria-current", "step");
      else step.removeAttribute("aria-current");
    });
  }

  function edit() {
    reviewed = null;
    document.querySelector("#download").removeAttribute("href");
    form.hidden = false;
    confirmation.hidden = true;
    sample.hidden = false;
    heading.textContent = "旅行の希望を整理します";
    document.querySelector("#form-description").textContent = "9つの項目で、行き先や予算をまとめます。";
    setStep("step-input");
    status.textContent = "";
    renderSummary();
    heading.focus();
  }

  form.addEventListener("input", (event) => {
    event.target.setCustomValidity("");
    status.textContent = "";
    renderSummary();
  });
  form.addEventListener("change", renderSummary);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = values();
    for (const [key] of FIELDS) {
      const field = form.elements.namedItem(key);
      field.setCustomValidity(field.required && !data[key] ? "空白だけではなく、条件を入力してください。" : "");
    }
    if (!form.reportValidity()) return;
    reviewed = { ...data, special_requests: data.special_requests || "なし" };
    const brief = {
      format: "llm-travel-local-brief", version: "1.0", synthetic: true,
      state: "awaiting_research", verification_status: "unverified",
      requirements: { ...reviewed },
      notice: "研究用の条件下書きです。旅程・料金・営業時間・交通は未検証。AIの実行やレビューは行っていません。",
    };
    document.querySelector("#download").href = "data:application/json;charset=utf-8," +
      encodeURIComponent(JSON.stringify(brief, null, 2));
    form.hidden = true;
    confirmation.hidden = false;
    sample.hidden = true;
    heading.textContent = "旅の条件を確認しましょう";
    document.querySelector("#form-description").textContent = "下書きの内容を確認し、必要なら編集してください。";
    status.textContent = "入力内容を確認できます。まだ送信・保存はしていません。";
    setStep("step-review");
    renderSummary();
    heading.focus();
  });
  document.querySelector("#edit").addEventListener("click", edit);
  clear.addEventListener("click", () => {
    confirmReplace(() => {
      form.reset();
      for (const [key] of FIELDS) form.elements.namedItem(key).setCustomValidity("");
      edit();
      status.textContent = "入力内容をクリアしました。";
    });
  });
  function fillSample() {
    const example = ["東京都", "京都府", "2", "街歩き・グルメ", "どちらも楽しみたい", "50000", "ホテル", "公共交通機関", "朝はゆっくり出発したい（合成サンプル）"];
    FIELDS.forEach(([key], index) => {
      const field = form.elements.namedItem(key);
      field.value = example[index];
      field.setCustomValidity("");
    });
    renderSummary();
    status.textContent = "合成サンプルを入力しました。自由に編集できます。";
  }
  sample.addEventListener("click", () => {
    if (Object.values(values()).some(Boolean)) confirmReplace(fillSample, true);
    else fillSample();
  });
  document.querySelector("#download").addEventListener("click", () => {
    if (!reviewed) return;
    setStep("step-wait");
    status.textContent = "条件ファイルのダウンロードを開始しました。調査は自動では始まりません。";
  });
  renderSummary();
})();
