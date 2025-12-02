let currentId = null;
let locked = false;
let mode = "all"; 

function $id(id){ return document.getElementById(id); }

function setLocked(v){
  locked = v;
  document.querySelectorAll("#choices button").forEach(b => b.disabled = v);
}

function updateModeUI(){
  const btn = $id("modeBtn");
  if (!btn) return;
  btn.textContent = mode === "wrong" ? "間違いノート：ON" : "間違いノート：OFF";
}

function updateWrongCount(n){
  const el = $id("wrongInline");
  if (el) el.textContent = String(n ?? 0);
}

async function loadCategories() {
  const res = await fetch("/api/categories");
  const data = await res.json();

  const select = $id("category");
  select.innerHTML = "";

  const optAll = document.createElement("option");
  optAll.value = "all";
  optAll.textContent = "すべて";
  select.appendChild(optAll);

  (data.categories || []).forEach(cat => {
    const opt = document.createElement("option");
    opt.value = cat;
    opt.textContent = cat;
    select.appendChild(opt);
  });
}

async function loadQuestion() {
  const cat = $id("category").value || "all";

  // reset UI
  locked = false;
  $id("result").textContent = "";
  $id("examples").innerHTML = "";
  const choicesEl = $id("choices");
  choicesEl.innerHTML = "";

  const res = await fetch(`/api/next?category=${encodeURIComponent(cat)}&mode=${encodeURIComponent(mode)}`);
  const q = await res.json();

  if (q.error) {
    $id("qArea").style.display = "none";
    alert(q.error);
    return;
  }

  currentId = q.id;
  $id("prompt").textContent = q.prompt;
  $id("qArea").style.display = "block";

  (q.choices || []).forEach((text, idx) => {
    const btn = document.createElement("button");
    btn.className = "choiceBtn";
    btn.innerHTML = `<span class="k">${idx+1}</span><span>${escapeHtml(text)}</span>`;
    btn.onclick = () => submitAnswer(idx, btn);
    choicesEl.appendChild(btn);
  });

  updateWrongCount(q.wrong_count);

  setLocked(false);
}

async function submitAnswer(choiceIdx, btnEl) {
  if (locked) return;
  setLocked(true);

  const res = await fetch("/api/answer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: currentId, choice: choiceIdx })
  });
  const data = await res.json();

  if (data.correct) {
    btnEl.classList.add("correct");
    $id("result").textContent = "✅ 正解！";
  } else {
    btnEl.classList.add("wrong");
    $id("result").textContent = `❌ 不正解（正解：${data.correctText}）`;
    const correctBtn = document.querySelectorAll("#choices button")[data.correctIndex];
    if (correctBtn) correctBtn.classList.add("correct");
  }

  const examplesEl = $id("examples");
  examplesEl.innerHTML = "";
  (data.examples || []).forEach(ex => {
    const li = document.createElement("li");
    li.textContent = ex;
    examplesEl.appendChild(li);
  });

  const scoreText = `${data.stats.score} / ${data.stats.total}`;
  $id("statsInline").textContent = scoreText;
  updateWrongCount(data.stats.wrong_count);

}

async function resetQuiz() {
  const res = await fetch("/api/reset", { method: "POST" });
  const data = await res.json();
  $id("statsInline").textContent = "0 / 0";
  updateWrongCount(data?.stats?.wrong_count ?? 0);
  await loadQuestion();
}

async function clearWrong() {
  await fetch("/api/wrong/clear", { method: "POST" });
  updateWrongCount(0);
  if (mode === "wrong") {
    await loadQuestion(); 
  }
}

function toggleMode(){
  mode = (mode === "all") ? "wrong" : "all";
  updateModeUI();
  loadQuestion();
}

function escapeHtml(s){
  return String(s)
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#39;");
}

document.addEventListener("keydown", (e) => {
  if (e.key === "n" || e.key === "N") $id("nextBtn")?.click();
  if (e.key === "r" || e.key === "R") $id("resetBtn")?.click();

  // 1~4 选项
  if (!locked && ["1","2","3","4"].includes(e.key)) {
    const idx = Number(e.key) - 1;
    const btn = document.querySelectorAll("#choices button")[idx];
    if (btn) btn.click();
  }

  if (e.key === "w" || e.key === "W") $id("modeBtn")?.click();
});

document.addEventListener("DOMContentLoaded", async () => {
  $id("nextBtn").onclick = loadQuestion;
  $id("resetBtn").onclick = resetQuiz;
  $id("category").addEventListener("change", loadQuestion);

  $id("modeBtn") && ($id("modeBtn").onclick = toggleMode);
  $id("clearWrongBtn") && ($id("clearWrongBtn").onclick = clearWrong);

  updateModeUI();
  await loadCategories();
  await loadQuestion();
});