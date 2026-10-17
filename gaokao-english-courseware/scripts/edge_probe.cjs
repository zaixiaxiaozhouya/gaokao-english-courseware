/**
 * 用真实浏览器（无头 + CDP）驱动学生版页面，实测「划词 → 朗读 → 加入生词本 → 在线翻译」，
 * 抓取控制台错误、耗时、TTS/音频调用与 DOM 变化。
 *
 * 用法：
 *   node scripts/edge_probe.cjs <html绝对路径> [debugPort] [浏览器可执行文件]
 * 前置：脚本会自己拉起无头浏览器（Edge / Chrome / Chromium 任一，自动探测）。
 * 跨平台：Windows / macOS / Linux 都按"平台候选路径 → PATH 常见名字 → 第 3 个参数"顺序查找。
 */
const http = require("http");
const os = require("os");
const { spawn, execFileSync } = require("child_process");
const path = require("path");
const fs = require("fs");

/* WebSocket：优先用 ws 包（本脚本用的是 ws 的 .on 事件风格），
   没有 ws 时用 Node 22+ 内置 WebSocket 做一个薄适配层（浏览器风格 → ws 风格）。 */
function loadWs() {
  const cands = ["ws"].concat(
    String(process.env.NODE_PATH || "").split(path.delimiter).filter(Boolean).map((d) => path.join(d, "ws")));
  for (const c of cands) {
    try { return require(c); } catch (e) { /* 继续找下一个 */ }
  }
  if (typeof globalThis.WebSocket === "function") {
    return class BrowserWsShim {
      constructor(url) {
        this._ws = new globalThis.WebSocket(url);
        this._h = {};
        const emit = (ev, arg) => (this._h[ev] || []).forEach((f) => f(arg));
        this._ws.addEventListener("open", (e) => emit("open", e));
        this._ws.addEventListener("message", (e) => emit("message", { toString: () => String(e.data) }));
        this._ws.addEventListener("close", (e) => emit("close", e));
        this._ws.addEventListener("error", (e) => emit("error", e));
      }
      on(ev, fn) { (this._h[ev] = this._h[ev] || []).push(fn); return this; }
      send(s) { this._ws.send(s); }
      close() { try { this._ws.close(); } catch (e) { /* ignore */ } }
    };
  }
  console.error("缺少 WebSocket 实现：请 `npm i ws` 并把其 node_modules 放进 NODE_PATH，或升级到 Node 22+");
  process.exit(2);
}
const WebSocket = loadWs();

/* 浏览器：命令行指定 > 平台候选路径 > PATH 里的常见命令名 */
function findBrowser() {
  if (process.argv[4] && fs.existsSync(process.argv[4])) return process.argv[4];
  const cands = [];
  if (process.platform === "win32") {
    cands.push(
      "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
      "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
      "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe");
  } else if (process.platform === "darwin") {
    cands.push(
      "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
      "/Applications/Chromium.app/Contents/MacOS/Chromium",
      "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser");
  } else {
    cands.push("/usr/bin/microsoft-edge", "/usr/bin/google-chrome", "/usr/bin/chromium",
               "/usr/bin/chromium-browser", "/snap/bin/chromium");
  }
  for (const c of cands) if (fs.existsSync(c)) return c;
  for (const name of ["msedge", "microsoft-edge", "google-chrome", "chrome", "chromium", "chromium-browser"]) {
    try {
      const out = execFileSync(process.platform === "win32" ? "where" : "which", [name], { encoding: "utf8" });
      const p = String(out).split(/\r?\n/)[0].trim();
      if (p && fs.existsSync(p)) return p;
    } catch (e) { /* 没装，试下一个 */ }
  }
  return null;
}

const target = process.argv[2];
const port = Number(process.argv[3] || 9333);
if (!target) { console.error("用法: node edge_probe.cjs <html> [port] [browserPath]"); process.exit(2); }

const EDGE = findBrowser();
if (!EDGE) {
  console.error("找不到 Edge/Chrome/Chromium：请安装其中一个，或用第 3 个参数直接指定可执行文件路径。");
  process.exit(2);
}
const userDir = path.join(os.tmpdir(), "edge-probe-profile-" + port);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const getJSON = (url) => new Promise((resolve, reject) => {
  http.get(url, (res) => { let d = ""; res.on("data", (c) => (d += c)); res.on("end", () => { try { resolve(JSON.parse(d)); } catch (e) { reject(e); } }); })
      .on("error", reject);
});

const DIAG = `
window.__diag = { errors: [], audio: [], spoken: [], fetches: [], speakCalls: [] };
window.addEventListener("error", function(e){ window.__diag.errors.push("error: " + (e.message || e.type)); });
window.addEventListener("unhandledrejection", function(e){ window.__diag.errors.push("rejection: " + String((e.reason && e.reason.message) || e.reason)); });
try {
  var OrigAudio = window.Audio;
  window.Audio = function(src){
    window.__diag.audio.push("new:" + String(src).slice(0, 90));
    return new OrigAudio(src);
  };
  /* 不改写 play()，只监听真实的播放/错误事件 —— 这样才能判断音频到底有没有播起来 */
  var OP = window.HTMLMediaElement.prototype.play;
  window.HTMLMediaElement.prototype.play = function(){
    var self = this;
    window.__diag.audio.push("play:" + String(self.src || "").slice(0, 90));
    self.addEventListener("playing", function(){ window.__diag.audio.push("playing:" + String(self.src || "").slice(0, 60)); });
    self.addEventListener("error", function(){ window.__diag.audio.push("error:code=" + (self.error && self.error.code)); });
    try { return OP.apply(this, arguments); } catch(e){ window.__diag.audio.push("throw:" + e.message); throw e; }
  };
} catch(e){}
try {
  var syn = window.speechSynthesis;
  if (syn) {
    var os = syn.speak.bind(syn);
    syn.speak = function(u){ window.__diag.spoken.push(u && u.text); return os(u); };
    var oc = syn.cancel.bind(syn);
    syn.cancel = function(){ window.__diag.speakCalls.push("cancel"); return oc(); };
  }
} catch(e){}
try {
  var of = window.fetch;
  window.fetch = function(u){ window.__diag.fetches.push(String(u).slice(0, 110)); return of.apply(this, arguments); };
} catch(e){}
`;

const PROBE = `(async function(){
  var sleep = function(ms){ return new Promise(function(r){ setTimeout(r, ms); }); };
  var out = {};
  out.url = location.href.slice(-40);
  out.questions = document.querySelectorAll(".q").length;
  out.blanks = document.querySelectorAll("#passage .blank").length;
  out.mode = document.body.className;
  out.netBtn = (document.querySelector("#netBtn")||{}).textContent;
  // 划词：从原文任意文本节点里找一个长单词（两档标注会把段落切碎，所以用 TreeWalker）
  var p = document.querySelector("#passage p");
  var node = null, m = null;
  var w = document.createTreeWalker(document.querySelector("#passage"), NodeFilter.SHOW_TEXT, null);
  while (w.nextNode()) {
    var mm = /[A-Za-z]{6,}/.exec(w.currentNode.nodeValue || "");
    if (mm) { node = w.currentNode; m = mm; break; }
  }
  if (!node) { out.fatal = "no-word-found"; return JSON.stringify(out); }
  var tn = node;
  out.word = m[0];
  var r = document.createRange();
  r.setStart(tn, m.index); r.setEnd(tn, m.index + m[0].length);
  var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r);
  var t0 = performance.now();
  p.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, button: 0 }));
  out.wordCardMs = Math.round(performance.now() - t0);
  out.popoverShown = document.querySelector("#popover").classList.contains("show");
  out.popoverHead = (document.querySelector("#popover").textContent || "").slice(0, 50);
  // 朗读
  var t1 = performance.now();
  var speakBtn = document.querySelector('[data-w="speak"]');
  if (speakBtn) speakBtn.click();
  out.speakClickMs = Math.round(performance.now() - t1);
  await sleep(150);
  out.ttsVoices = (window.speechSynthesis && window.speechSynthesis.getVoices() || []).length;
  out.ttsSpeaking = !!(window.speechSynthesis && window.speechSynthesis.speaking);
  out.spoken = window.__diag.spoken.slice(0, 3);
  await sleep(1400);
  out.audio = window.__diag.audio.slice(0, 4);
  out.toastAfterSpeak = (document.querySelector("#toast") || {}).textContent;
  // 词典卡按钮清单（按需求应已无 speak/audio/book）
  out.cardButtons = Array.prototype.map.call(document.querySelectorAll("#popover [data-w]"), function(b){ return b.getAttribute("data-w"); });
  out.cardHasIpa = (document.querySelector("#popover").textContent || "").indexOf("/") >= 0;
  // 加入生词表：唯一入口=手动输入
  var rows0 = document.querySelectorAll("#glossary .gl-row").length;
  var input = document.querySelector("#glInput");
  input.value = out.word;
  var t2 = performance.now();
  document.querySelector("#glAddBtn").click();
  out.addMs = Math.round(performance.now() - t2);
  out.rows0 = rows0;
  out.rows1 = document.querySelectorAll("#glossary .gl-row").length;
  out.glTitle = (document.querySelector("#glossaryTitle") || {}).textContent;
  out.markedInPassage = !!document.querySelector('#passage .vocab[data-key="' + out.word.toLowerCase() + '"]');
  out.rowText = (document.querySelector("#glossary .gl-row.origin-user") || {}).textContent;
  out.toastAfterAdd = (document.querySelector("#toast") || {}).textContent;
  out.strongMarks = document.querySelectorAll("#passage .vocab:not(.idx)").length;
  out.dimMarks = document.querySelectorAll("#passage .vocab.idx").length;
  out.sayButtons = document.querySelectorAll("#glossary .gl-say").length;
  out.hasExport = !!document.querySelector("#glExportBtn");
  out.hasSentenceBook = !!document.querySelector("#sentenceBox");
  // 选择题（完形）专项：选项注释、邻空标记、分析模式下接入的答案
  if (document.querySelector(".opt")) {
    out.optWithIpa = document.querySelectorAll(".opt .oipa").length;
    out.optWithPos = document.querySelectorAll(".opt .opos").length;
    out.optAddBtns = document.querySelectorAll(".opt .oadd").length;
    out.neighborMarks = document.querySelectorAll(".q .blank.other").length;
    out.passageBlanks = document.querySelectorAll("#passage .blank:not(.other)").length;
    var mb = document.querySelector("#modeBtn");
    if (mb) { mb.click(); await sleep(300); }
    out.modeAfter = document.body.className;
    var bFirst = document.querySelector("#passage .blank:not(.other)");
    out.firstBlank = bFirst ? (bFirst.getAttribute("data-no") + "=" + bFirst.textContent) : null;
    var qOther = document.querySelector(".q .blank.other");
    out.qNeighbor = qOther ? qOther.textContent : null;
  }
  await sleep(2500);
  out.fetches = window.__diag.fetches.slice(0, 5);
  out.errors = window.__diag.errors.slice(0, 6);
  out.rowTextAfterOnline = (document.querySelector("#glossary .gl-row.origin-user") || {}).textContent;
  return JSON.stringify(out);
})()`;

(async () => {
  const edge = spawn(EDGE, [
    "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
    "--remote-debugging-port=" + port, "--user-data-dir=" + userDir,
    "--autoplay-policy=no-user-gesture-required", "about:blank",
  ], { stdio: "ignore" });

  let targets = null;
  for (let i = 0; i < 40 && !targets; i++) {
    await sleep(400);
    try { targets = await getJSON("http://127.0.0.1:" + port + "/json/list"); } catch (e) { targets = null; }
  }
  if (!targets) { console.error("无法连接 Edge 调试端口"); edge.kill(); process.exit(1); }
  const page = targets.find((t) => t.type === "page");
  const ws = new WebSocket(page.webSocketDebuggerUrl, { perMessageDeflate: false });
  let id = 0;
  const pending = new Map();
  const events = [];
  ws.on("message", (raw) => {
    const msg = JSON.parse(raw.toString());
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    else if (msg.method) events.push(msg);
  });
  const send = (method, params) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params: params || {} })); });
  await new Promise((r) => ws.on("open", r));

  await send("Page.enable");
  await send("Runtime.enable");
  await send("Log.enable");
  await send("Page.addScriptToEvaluateOnNewDocument", { source: DIAG });

  const url = "file:///" + target.replace(/\\/g, "/");
  await send("Page.navigate", { url });
  await sleep(2500);

  const r = await send("Runtime.evaluate", { expression: PROBE, awaitPromise: true, returnByValue: true });
  let out;
  try { out = JSON.parse(r.result.result.value); } catch (e) { out = { evalError: r.result && r.result.exceptionDetails, raw: r.result }; }

  const consoleMsgs = events.filter((e) => e.method === "Log.entryAdded" || e.method === "Runtime.consoleAPICalled")
    .map((e) => JSON.stringify(e.params).slice(0, 200)).slice(0, 8);

  console.log(JSON.stringify({ probe: out, console: consoleMsgs }, null, 2));
  ws.close(); edge.kill();
})();
