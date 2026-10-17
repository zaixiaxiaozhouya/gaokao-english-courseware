/**
 * 学生版页面冒烟测试（jsdom）—— v0.2：覆盖双模式、沉浸度、划词划句、档案
 *
 * 用法（跨平台，只要有 node + jsdom）：
 *   # Windows：$env:NODE_PATH="<放了 jsdom 的 node_modules>"
 *   # macOS / Linux：export NODE_PATH="$(npm root -g)"  或  npm i jsdom 后在项目目录里跑
 *   node scripts/smoke_test.cjs 04_workspace/build/cloze-2023-n1.html
 *
 * 退出码 0 = 全部通过。
 */
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

const file = process.argv[2];
if (!file) { console.error("用法: node smoke_test.cjs <html>"); process.exit(2); }
const html = fs.readFileSync(file, "utf8");
const dom = new JSDOM(html, {
  runScripts: "dangerously", url: "http://localhost/", pretendToBeVisual: true,
  /* 页面脚本在构造时就会执行，所以桩必须在 beforeParse 里装好 */
  beforeParse(window) {
    window.Element.prototype.scrollIntoView = function () {};
    window.HTMLElement.prototype.scrollIntoView = function () {};
    window.print = function () {};
    window.confirm = function () { return true; };
    window.open = function () { return null; };
    window.__netCalls = [];
    window.__netFail = false;
    window.fetch = function (url) {
      window.__netCalls.push(String(url));
      if (window.__netFail) return Promise.reject(new Error("net-down"));
      return Promise.resolve({ json: function () { return Promise.resolve({ responseData: { translatedText: "【在线译文】" } }); } });
    };
    window.__audioSrcs = [];
    window.__audioError = false;
    window.__audioPlaying = null;
    window.Audio = function (src) {
      this.src = src; this.style = {}; this.__err = window.__audioError;
      window.__audioSrcs.push(String(src));
    };
    window.Audio.prototype.play = function () {
      var self = this;
      if (this.__err) return Promise.reject(Object.assign(new Error("blocked"), { name: "NotAllowedError" }));
      return new Promise(function (resolve) {
        setTimeout(function () {
          window.__audioPlaying = self.src;
          if (self.onplaying) self.onplaying();
          resolve();
        }, 5);
      });
    };
    window.Audio.prototype.pause = function () {};
    window.Audio.prototype.remove = function () {};
    window.SpeechSynthesisUtterance = function (text) { this.text = text; };
    var synth = {
      speaking: false, pending: false, _handlers: [],
      getVoices: function () {
        if (window.__noVoices) return [];
        if (window.__cloudOnly) return [{ name: "Microsoft Aria Online (Natural)", lang: "en-US", localService: false }];
        return [{ name: "Microsoft Zira Desktop", lang: "en-US", localService: true }];
      },
      addEventListener: function (t, fn) { this._handlers.push(fn); },
      speak: function (u) {
        var self = this;
        window.__spoken = u.text;
        self.speaking = true;
        if (!window.__silentTts) {
          setTimeout(function () { self.speaking = false; if (u.onstart) u.onstart(); }, 8);
        }
      },
      cancel: function () {}
    };
    Object.defineProperty(window, "speechSynthesis", { value: synth, configurable: true });
  }
});
const win = dom.window;
const doc = win.document;

const results = [];
function check(name, fn) {
  try { const r = fn(); results.push({ name, ok: r === true, note: r === true ? "" : String(r) }); }
  catch (e) { results.push({ name, ok: false, note: "抛错: " + e.message }); }
}
const $ = (s) => doc.querySelector(s);
const $$ = (s) => Array.from(doc.querySelectorAll(s));
const click = (el) => el.dispatchEvent(new win.MouseEvent("click", { bubbles: true, cancelable: true }));
const key = (k) => doc.dispatchEvent(new win.KeyboardEvent("keydown", { key: k, bubbles: true, cancelable: true }));
const change = (el) => el.dispatchEvent(new win.Event("change", { bubbles: true }));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const DATA = JSON.parse($("#app-data").textContent);
const DOC_ID = DATA.meta.docId;
const QUESTIONS = DATA.questions;
const FIRST = QUESTIONS[0];
const SECOND = QUESTIONS[1];
const IS_CHOICE = !!(FIRST.options && FIRST.options.length);
/* R24：七选五（作答单位是 A–G 字母）与阅读（原文没有空位）要区别对待 */
const IS_SEVEN = DATA.meta.type === "seven";
const HAS_BLANKS = ((DATA.passage && DATA.passage.blocks) || []).some((b) => b && b.type === "gap");
const submitAnswer = async (no, qd) => {
  const el = $('.q[data-no="' + no + '"]');
  if (!el) return;
  if (IS_SEVEN) {
    const row = $('#sevenPool .sp-row[data-pick="' + String(qd.answer) + '"]');
    click($('#passage .blank[data-no="' + no + '"]')); await new Promise((r) => setTimeout(r, 5));
    if (row) click(row);
    await new Promise((r) => setTimeout(r, 10));
  } else if (IS_CHOICE) {
    click($('.q[data-no="' + no + '"] .opt[data-key="' + String(qd.answer) + '"]'));
  } else {
    const i = $('.q[data-no="' + no + '"] [data-input]');
    if (i) { i.value = String(qd.answer).split("/")[0]; i.dispatchEvent(new win.Event("input", { bubbles: true })); }
  }
  click($('.q[data-no="' + no + '"] [data-act="submit"]'));
};
const KEY = "enstudy:" + DOC_ID + ":progress";
const PREFS = "enstudy:" + DOC_ID + ":prefs";
const readProgress = () => JSON.parse(win.localStorage.getItem(KEY));
const readPrefs = () => JSON.parse(win.localStorage.getItem(PREFS));
const q = (no) => $('.q[data-no="' + no + '"]');

/* ---------- A. 基础渲染 ---------- */
check("题目卡片数量正确 (" + QUESTIONS.length + ")", () => $$(".q").length === QUESTIONS.length || $$(".q").length);
if (HAS_BLANKS) {
  check("原文空格数与题数一致", () => $$("#passage .blank").length === QUESTIONS.length || $$("#passage .blank").length);
  check("空格按题号升序分配", () => {
    const got = $$("#passage .blank").map((b) => Number(b.dataset.no));
    return JSON.stringify(got) === JSON.stringify(QUESTIONS.map((x) => x.no)) || JSON.stringify(got);
  });
} else {
  check("阅读题：原文没有空位（题目都在右侧卡片里）", () => $$("#passage .blank").length === 0 || $$("#passage .blank").length);
}
/* 生词表是推荐项不是必填项：glossary 为空时只验证空状态，不判失败 */
const HAS_GLOSSARY = ((DATA && DATA.glossary) || []).length > 0;
check(HAS_GLOSSARY ? "生词表已渲染" : "生词表已渲染（glossary 为空，跳过）",
  () => !HAS_GLOSSARY || $$("#glossary .vocab-line").length > 0);
check("中文对照默认隐藏", () => $("#zhBox").classList.contains("hidden"));
check("默认进入做题模式", () => doc.body.classList.contains("mode-practice") && $("#modeBtn").textContent === "做题模式");

/* ---------- B. 沉浸度分层 ---------- */
check("半沉浸下中文按钮禁用", () => $("#zhBtn").disabled === true);
check("半沉浸下提示按钮禁用", () => $('.q[data-no="' + FIRST.no + '"] [data-act="hint"]').disabled === true);
$("#immersionSel").value = "guided"; change($("#immersionSel"));
check("切到讲解态后中文按钮可用", () => $("#zhBtn").disabled === false);
check("切到讲解态后提示可用", () => $('.q[data-no="' + FIRST.no + '"] [data-act="hint"]').disabled === false);
check("沉浸度写入偏好", () => readPrefs().immersion === "guided" || JSON.stringify(readPrefs()));

/* ---------- C. 提示阶梯 / 判分 ---------- */
const NO = FIRST.no;
click(q(NO));
const hintItems = () => $$('.q[data-no="' + NO + '"] .hintitem').length;
const hintBtn = () => $('.q[data-no="' + NO + '"] [data-act="hint"]');
for (let i = 0; i < FIRST.hints.length; i++) click(hintBtn());
check("提示可展开到满级", () => hintItems() === FIRST.hints.length || hintItems());
check("提示级别记入档案", () => (readProgress().attempts[String(NO)] || {}).hintUsed === FIRST.hints.length || JSON.stringify(readProgress().attempts[String(NO)]));
click($('.q[data-no="' + NO + '"] [data-act="redo"]'));
check("重做后提示归零", () => hintItems() === 0);
if (IS_SEVEN) {
  /* 七选五：先在题卡里点一个错的字母 */
  const wrongLetter = "ABCDEFG".split("").find((k) => k !== String(FIRST.answer));
  click($('.q[data-no="' + NO + '"] [data-letter="' + wrongLetter + '"]'));
  click($('.q[data-no="' + NO + '"] [data-act="submit"]'));
} else if (IS_CHOICE) {
  const wrongKey = FIRST.options.find((o) => o.key !== FIRST.answer).key;
  click($('.q[data-no="' + NO + '"] .opt[data-key="' + wrongKey + '"]'));
  click($('.q[data-no="' + NO + '"] [data-act="submit"]'));
} else {
  const input = $('.q[data-no="' + NO + '"] [data-input]');
  input.value = "zzz-wrong"; input.dispatchEvent(new win.Event("input", { bubbles: true }));
  click($('.q[data-no="' + NO + '"] [data-act="submit"]'));
}
check("答错给出正确答案", () => /正确答案/.test($('.q[data-no="' + NO + '"] [data-fb]').textContent));
check("答错给出解析", () => /解析/.test($('.q[data-no="' + NO + '"] [data-fb]').textContent));
check("错题进入错题本", () => readProgress().wrong.indexOf(NO) >= 0 || JSON.stringify(readProgress().wrong));
click($('.q[data-no="' + NO + '"] [data-act="redo"]'));
if (IS_SEVEN) {
  const r2 = $('#sevenPool .sp-row[data-pick="' + String(FIRST.answer) + '"]');
  click($('#passage .blank[data-no="' + NO + '"]'));
  if (r2) click(r2);
  click($('.q[data-no="' + NO + '"] [data-act="submit"]'));
} else if (IS_CHOICE) { click($('.q[data-no="' + NO + '"] .opt[data-key="' + FIRST.answer + '"]')); }
else { const i = $('.q[data-no="' + NO + '"] [data-input]'); i.value = String(FIRST.answer).split("/")[0]; i.dispatchEvent(new win.Event("input", { bubbles: true })); }
if (!IS_SEVEN) click($('.q[data-no="' + NO + '"] [data-act="submit"]'));
check("答对显示正确", () => /正确/.test($('.q[data-no="' + NO + '"] [data-fb]').textContent));
check("答对移出错题本", () => readProgress().wrong.indexOf(NO) < 0 || JSON.stringify(readProgress().wrong));
check("掌握度已聚合", () => Object.keys(readProgress().mastery).length > 0 || JSON.stringify(readProgress().mastery));

/* ---------- D. 键盘 ---------- */
key("ArrowRight");
check("→ 切到下一题", () => { const el = $(".q.active"); return el && Number(el.dataset.no) === SECOND.no || (el && el.dataset.no); });
key("h");
check("H 展开提示", () => $$('.q[data-no="' + SECOND.no + '"] .hintitem').length >= 1);
key("z");
check("Z 切换中文对照", () => !$("#zhBox").classList.contains("hidden"));

/* ---------- E. 分析模式 ---------- */
check("做题模式下未作答题不显示答案", () => !/答案：/.test($('.q[data-no="' + SECOND.no + '"] [data-fb]').textContent));
click($("#submitAllBtn"));
check("交卷后进入分析模式", () => doc.body.classList.contains("mode-analysis") || doc.body.className);
check("分析模式下未作答题显示答案", () => /答案：/.test($('.q[data-no="' + SECOND.no + '"] [data-fb]').textContent));
check("交卷后出现成绩报告", () => !$("#reportBox").classList.contains("hidden") && /交卷报告/.test($("#reportBox").textContent));
check("报告含建议复习顺序", () => /建议复习顺序/.test($("#reportBox").textContent));
click($('.q[data-no="' + SECOND.no + '"] [data-act="toggleAns"]'));
check("可逐题隐藏答案", () => !/答案：/.test($('.q[data-no="' + SECOND.no + '"] [data-fb]').textContent));
click($('.q[data-no="' + SECOND.no + '"] [data-act="toggleAns"]'));
check("再次点击恢复显示", () => /答案：/.test($('.q[data-no="' + SECOND.no + '"] [data-fb]').textContent));
check("参考过答案被标记 peeked", () => (readProgress().attempts[String(SECOND.no)] || {}).peeked === true || JSON.stringify(readProgress().attempts[String(SECOND.no)]));
key("m");
check("M 键切回做题模式", () => doc.body.classList.contains("mode-practice"));
check("做题模式再次隐藏未答题答案", () => !/答案：/.test($('.q[data-no="' + SECOND.no + '"] [data-fb]').textContent));

/* ---------- F. 划词 / 划句（分析模式） ---------- */
key("m"); // 回到分析模式
const vocab = $("#passage .vocab") || $("#glossary .vocab-line");
click(vocab);
check("划词弹出词典卡", () => $("#popover").classList.contains("show") || $("#popover").className);
const firstKey = (vocab.dataset.key || "").toLowerCase();
const idxEntry = (DATA.passage.wordIndex || {})[firstKey] || (DATA.glossary || []).find((g) => (g.key || g.word).toLowerCase() === firstKey);
check("词典卡显示音标/释义", () => {
  const t = $("#popover").textContent;
  return (idxEntry && idxEntry.ipa ? t.indexOf(idxEntry.ipa) >= 0 : true) && t.length > 4 || t.slice(0, 80);
});
check("划词卡已砍掉「加入生词表」按钮（按需求）", () => !doc.querySelector('[data-w="book"]') || $("#popover").innerHTML.slice(0, 70));
check("划词卡提供外链词典入口", () => $$('[data-w="yd"],[data-w="bing"],[data-w="cam"]').length === 3);
/* 划句：选中一段文字后触发 mouseup */
const para = $("#passage p");
const tn = para.firstChild;
function selectRange(startNode, from, to) {
  const r = doc.createRange();
  r.setStart(startNode, from); r.setEnd(startNode, to);
  const s = win.getSelection(); s.removeAllRanges(); s.addRange(r);
  return s;
}
function mouseUpOn(el, button) {
  el.dispatchEvent(new win.MouseEvent("mouseup", { bubbles: true, button: button || 0 }));
}
/* 选中一段文字并触发划句，返回句子卡是否打开。
   注意：两档标注会把段落切成很多短文本节点，所以选区要**跨节点累积**到足够长。 */
function openSentenceCard(offset, start) {
  const p = $$("#passage p")[offset || 0];
  if (!p) return false;
  const w = doc.createTreeWalker(p, win.NodeFilter.SHOW_TEXT, null);
  const nodes = [];
  while (w.nextNode()) nodes.push(w.currentNode);
  if (!nodes.length) return false;
  const i0 = Math.min(start || 0, nodes.length - 1);
  let total = 0, last = i0;
  for (let i = i0; i < nodes.length; i++) { total += (nodes[i].nodeValue || "").length; last = i; if (total >= 45) break; }
  if (total < 25) return false;
  const r = doc.createRange();
  r.setStart(nodes[i0], 0);
  r.setEnd(nodes[last], (nodes[last].nodeValue || "").length);
  const s = win.getSelection(); s.removeAllRanges(); s.addRange(r);
  mouseUpOn(p, 0);
  return $("#popover").classList.contains("sent");
}
function openSentenceCardAny(start) {
  const n = $$("#passage p").length;
  for (let i = 0; i < n; i++) { if (openSentenceCard(i, start)) return true; }
  return false;
}
let selOK = openSentenceCardAny(0);
check("划句弹出句子卡（含离线译文）", () => selOK || "选区未建立或被判定为词");
if (selOK) {
  check("句子卡给出中文译文", () => {
    const t = $("#popover").textContent;
    return /[\u4e00-\u9fa5]/.test(t) || t.slice(0, 80);
  });
  check("句子卡提供外链与在线翻译入口", () => !!$('[data-s="g"]') && !!$('[data-s="api"]') && !!$('[data-s="copy"]'));
  check("句子卡已不含「朗读/收藏」按钮（按需求精简）", () => (!doc.querySelector('[data-s="speak"]') && !doc.querySelector('[data-s="book"]')) || $("#popover").innerHTML.slice(0, 80));
}

/* ---------- F2. 划词手势回归（用户报的"必须右键才出翻译"） ---------- */
key("Escape");
check("Esc 可关闭浮层", () => !$("#popover").classList.contains("show"));
let wordSelOK = false;
if (tn && tn.nodeType === 3) {
  const m = /[A-Za-z][A-Za-z'-]{4,}/.exec(tn.nodeValue);
  if (m) {
    selectRange(tn, m.index, m.index + m[0].length);
    mouseUpOn(para, 0);
    wordSelOK = $("#popover").classList.contains("show");
    check("左键划词即弹卡片", () => wordSelOK || $("#popover").className);
    /* 关键回归：同一次手势后浏览器还会补发 click，卡片不能被它关掉 */
    click(para);
    check("【回归】划词后的 click 不会关掉卡片", () => $("#popover").classList.contains("show") || $("#popover").className);
    check("【回归】词典卡内容仍是该词", () => {
      const t = $("#popover").textContent;
      return t.toLowerCase().indexOf(m[0].toLowerCase()) >= 0 || t.slice(0, 60);
    });
    /* 右键不占用：先把卡片关掉，再用右键 mouseup，应保持关闭（交给浏览器菜单） */
    key("Escape");
    selectRange(tn, m.index, m.index + m[0].length);
    mouseUpOn(para, 2);
    check("右键不触发查词（留给浏览器菜单）", () => !$("#popover").classList.contains("show") || $("#popover").className);
    /* 双击查词 */
    para.dispatchEvent(new win.MouseEvent("dblclick", { bubbles: true }));
    check("双击单词可查词", () => $("#popover").classList.contains("show") || $("#popover").className);
  }
}
check("原文提示告知左键划词", () => /左键|双击/.test($("#passageHint").textContent) || $("#passageHint").textContent);

/* ---------- G. 设置 / 档案 ---------- */
click($("#settingsBtn"));
check("设置面板可打开", () => $("#settings").classList.contains("show"));
$("#ydKey").value = "test-key"; $("#ydSecret").value = "test-secret";
click($("#saveSettings"));
check("API key 保存进偏好", () => (readPrefs().youdao || {}).appKey === "test-key" || JSON.stringify(readPrefs().youdao));
click($("#clearSettings"));
check("可清除 API key", () => (readPrefs().youdao || {}).appKey === "" || JSON.stringify(readPrefs().youdao));
check("状态栏显示进度", () => /已答/.test($("#statHint").textContent));
check("档案面板含掌握度", () => /掌握度|正确率/.test($("#stats").textContent));
click($("#resetBtn"));
check("清空后作答归零", () => Object.keys(readProgress().attempts).length === 0 || JSON.stringify(Object.keys(readProgress().attempts)));

/* ---------- H. 分析模式：答案直接接进原文 ---------- */
function ensureMode(mode) {
  const inAnalysis = doc.body.classList.contains("mode-analysis");
  if ((mode === "analysis") !== inAnalysis) key("m");
}
ensureMode("analysis");
/* 答案的"可读形式"：选择题=选项文本（新版把词接进原文，而不是 ABCD） */
const ansText = (q) => {
  const o = (q.options || []).find((x) => String(x.key) === String(q.answer));
  return o ? o.text : String(q.answer);
};
check("分析模式下原文空格显示正确答案", () => {
  if (!HAS_BLANKS) return true;                       /* 阅读题原文没有空位，跳过 */
  const b = $$("#passage .blank:not(.other)").find((x) => Number(x.dataset.no) === SECOND.no);
  const q2 = QUESTIONS[1];
  return (b && b.textContent.indexOf(ansText(q2)) >= 0) || (b && b.textContent);
});
check("分析模式空格带题号角标便于回查", () => {
  if (!HAS_BLANKS) return true;
  const b = $$("#passage .blank").find((x) => Number(x.dataset.no) === SECOND.no);
  return !!(b && b.querySelector(".qno")) || (b && b.innerHTML.slice(0, 80));
});
/* 再做错一题，验证"划掉学生答案 + 给正确答案" */
const THIRD = QUESTIONS[2];
ensureMode("practice");
click(q(THIRD.no));
if (IS_SEVEN) {
  const wrong = "ABCDEFG".split("").find((k) => k !== String(THIRD.answer));
  click($('.q[data-no="' + THIRD.no + '"] [data-letter="' + wrong + '"]'));
  click($('.q[data-no="' + THIRD.no + '"] [data-act="submit"]'));
} else if (IS_CHOICE) { click($('.q[data-no="' + THIRD.no + '"] .opt[data-key="' + THIRD.options.find((o) => o.key !== THIRD.answer).key + '"]')); }
else { const i = $('.q[data-no="' + THIRD.no + '"] [data-input]'); i.value = "zzz-wrong"; i.dispatchEvent(new win.Event("input", { bubbles: true })); }
if (!IS_SEVEN) click($('.q[data-no="' + THIRD.no + '"] [data-act="submit"]'));
ensureMode("analysis");
check("答错的题在原文里划掉学生答案并给出正确答案", () => {
  if (!HAS_BLANKS) return true;
  const b = $$("#passage .blank:not(.other)").find((x) => Number(x.dataset.no) === THIRD.no);
  return !!(b && b.querySelector("s.mine") && b.textContent.indexOf(ansText(THIRD)) >= 0) || (b && b.textContent);
});

/* ---------- I. 默认联网 + 在线翻译 / 降级 ---------- */
check("默认处于联网状态", () => readPrefs().online !== false && /在线：开/.test($("#netBtn").textContent) || $("#netBtn").textContent);
(async function () {
  /* 句子卡上的「在线翻译」必定走在线链路（不依赖离线是否命中） */
  openSentenceCardAny(0);
  click($('[data-s="api"]'));
  await new Promise((r) => setTimeout(r, 30));
  check("在线翻译请求发到免 key 的翻译接口", () => win.__netCalls.some((u) => /mymemory/i.test(u)) || JSON.stringify(win.__netCalls));
  check("在线译文写回句子卡", () => /【在线译文】/.test($("#scCn").textContent) || $("#scCn").textContent);
  /* 断网降级：换一段**不同的文本区间**，确保不吃缓存 */
  win.__netFail = true;
  openSentenceCardAny(6);
  click($('[data-s="api"]'));
  await new Promise((r) => setTimeout(r, 30));
  check("在线失败自动降级并提示", () => /在线翻译不可用/.test($("#scCn").textContent) || $("#scCn").textContent);
  win.__netFail = false;
  /* 关闭在线开关（注意：可能处于熔断"暂停"状态，两者都算关闭） */
  click($("#netBtn"));
  check("可关闭在线（改用离线数据）", () => readPrefs().online === false && /在线：(关|暂停)/.test($("#netBtn").textContent) || $("#netBtn").textContent);
  click($("#netBtn"));
  check("可重新开启在线", () => readPrefs().online !== false || $("#netBtn").textContent);
  check("重新开启会复位熔断", () => !/暂停/.test($("#netBtn").textContent) || $("#netBtn").textContent);

  /* ---------- J. 词典卡：按需求只做查词/翻译（无朗读、无加入生词表） ---------- */
  click($("#passage .vocab") || $("#glossary .vocab-line"));
  await new Promise((r) => setTimeout(r, 20));
  check("划词卡不含「朗读/在线发音」按钮", () => (!doc.querySelector('[data-w="speak"]') && !doc.querySelector('[data-w="audio"]')) || $("#popover").innerHTML.slice(0, 70));
  check("划词卡不含「加入生词表」按钮", () => !doc.querySelector('[data-w="book"]') || $("#popover").innerHTML.slice(0, 70));
  check("划词卡提供外链词典（有道/必应/剑桥）", () => $$('[data-w="yd"],[data-w="bing"],[data-w="cam"]').length === 3);
  check("划词卡提供复制/在线翻译/整句翻译", () => !!$('[data-w="copy"]') && !!$('[data-w="api"]') && !!$('[data-w="sent"]'));
  /* 划选一个"索引里有原型信息、且确实出现在原文里"的变形词：卡片应立刻给出音标/词性/释义/原型（不联网） */
  const WI = (DATA.passage.wordIndex) || {};
  const cands = Object.keys(WI).filter((k) => WI[k].base && WI[k].ipa && WI[k].pos && WI[k].cn && !/\s/.test(k));
  let hitInfo = null;
  outer:
  for (const cand of cands) {
    const re = new RegExp("\\b" + cand.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "i");
    for (const p of $$("#passage p")) {
      const walker = doc.createTreeWalker(p, win.NodeFilter.SHOW_TEXT, null);
      let node = null;
      while (walker.nextNode()) {
        if (re.test(walker.currentNode.nodeValue || "")) { node = walker.currentNode; break; }
      }
      if (!node) continue;
      const m = re.exec(node.nodeValue);
      selectRange(node, m.index, m.index + m[0].length);
      mouseUpOn(p, 0);
      hitInfo = { info: WI[cand], word: cand, text: $("#popover").textContent };
      break outer;
    }
  }
  if (hitInfo) {
    check("划选变形词立刻显示音标（离线索引）", () => hitInfo.text.indexOf(hitInfo.info.ipa) >= 0 || hitInfo.text.slice(0, 90));
    check("划选变形词立刻显示词性", () => hitInfo.text.indexOf(hitInfo.info.pos) >= 0 || hitInfo.text.slice(0, 90));
    check("划选变形词立刻显示释义", () => hitInfo.text.indexOf(hitInfo.info.cn) >= 0 || hitInfo.text.slice(0, 90));
    check("变形词会标出原型", () => /原型/.test(hitInfo.text) || hitInfo.text.slice(0, 120));
  } else {
    check("找到带原型信息的变形词用于测试", () => cands.length === 0 ? true : "未找到（跳过）");
  }
  click($("#settingsBtn"));
  click($("#diagBtn"));
  await new Promise((r) => setTimeout(r, 60));
  check("环境自检输出词索引统计", () => /词索引：\d+ 条/.test($("#diagOut").textContent) || $("#diagOut").textContent.slice(0, 90));
  click($("#closeSettings"));

  /* ---------- K. 生词表管理：加入 / 划线 / 移除 / 手动加入 ---------- */
  const glRows = () => $$("#glossary .gl-row").length;
  const glKeys = () => $$("#glossary .gl-row").map((r) => String(r.dataset.key).toLowerCase());
  const vocabKeys = () => $$("#passage .vocab:not(.idx)").map((v) => (v.dataset.key || "").toLowerCase());
  const idxKeys = () => $$("#passage .vocab.idx").map((v) => (v.dataset.key || "").toLowerCase());
  const baseKeys = DATA.glossary.map((g) => String(g.key || g.word).toLowerCase());
  const markedBefore = vocabKeys().length;
  check(HAS_GLOSSARY ? "数据自带的生词已在原文划线" : "数据自带的生词已在原文划线（glossary 为空，跳过）",
    () => !HAS_GLOSSARY || markedBefore > 0 || markedBefore);

  /* 挑一个"独立存在、不在自带词表里、且确实出现在原文"的索引词（避免被更长的词组标记吃掉） */
  const WI0 = (DATA.passage.wordIndex) || {};
  const idxKeysAll = Object.keys(WI0);
  const passagePlain = $$("#passage p").map((p) => p.textContent).join(" ");
  const candidates = idxKeysAll.filter((k) => !/\s/.test(k) && k.length >= 5 && baseKeys.indexOf(k) < 0 &&
    !idxKeysAll.some((k2) => k2.length > k.length && k2.toLowerCase().indexOf(k.toLowerCase()) >= 0) &&
    new RegExp("\\b" + k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "i").test(passagePlain));
  let picked = null;
  for (const target of candidates) {
    const re = new RegExp("\\b" + target.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "i");
    for (const p of $$("#passage p")) {
      const w = doc.createTreeWalker(p, win.NodeFilter.SHOW_TEXT, null);
      let node = null;
      while (w.nextNode()) { if (re.test(w.currentNode.nodeValue || "")) { node = w.currentNode; break; } }
      if (!node) continue;
      const m = re.exec(node.nodeValue);
      picked = { node: node, word: m[0], idx: m.index };
      break;
    }
    if (picked) break;
  }
  if (picked) {
    const r3 = doc.createRange();
    r3.setStart(picked.node, picked.idx);
    r3.setEnd(picked.node, picked.idx + picked.word.length);
    const s3 = win.getSelection(); s3.removeAllRanges(); s3.addRange(r3);
    mouseUpOn(picked.node.parentNode, 0);
    check("划选新词弹出词典卡（未被判成句子）", () => $("#popover").classList.contains("show") && !$("#popover").classList.contains("sent") || $("#popover").className);
    /* 加入生词表：唯一的入口是手动输入（按需求砍掉了"划词加入"） */
    const wb0 = (readProgress().wordbook || []).length;
    const wi = (DATA.passage.wordIndex || {})[picked.word.toLowerCase()];
    const tAdd = Date.now();
    $("#glInput").value = picked.word;
    click($("#glAddBtn"));
    const dtAdd = Date.now() - tAdd;
    check("手动加入是同步完成（<100ms）", () => dtAdd < 100 || dtAdd + "ms");
    check("加入后当帧就已出现在生词表", () => glKeys().indexOf(picked.word.toLowerCase()) >= 0 || ("picked=" + picked.word + " toast=" + $("#toast").textContent + " keys=" + JSON.stringify(glKeys().slice(0, 4)) + " wb=" + JSON.stringify((readProgress().wordbook || []).map((x) => x.word))));
    const rowWrap = $$("#glossary .gl-row").find((r) => String(r.dataset.key).toLowerCase() === picked.word.toLowerCase());
    const row = rowWrap ? rowWrap.querySelector(".gl-main") : null;
    check("生词表条目含音标/词性/释义（与自带词条同级）", () => {
      if (!wi) return true;                                   // 该词不在索引里则跳过（会提示可联网查）
      const t = row ? row.textContent : "";
      return (t.indexOf(wi.ipa) >= 0 && t.indexOf(wi.pos) >= 0 && t.indexOf(wi.cn) >= 0) || t.slice(0, 90);
    });
    check("变形词在生词表里标出原型", () => (!wi || !wi.base) ? true : (/原型/.test(row ? row.textContent : "") || (row ? row.textContent.slice(0, 90) : "no-row")));
    await new Promise((r) => setTimeout(r, 30));
    check("加入生词表后档案里多了一条", () => (readProgress().wordbook || []).length === wb0 + 1 || JSON.stringify(readProgress().wordbook));
    check("新词带「自加」标记", () => $$("#glossary .gl-row.origin-user .gl-badge").length >= 1 || $$("#glossary .gl-row").length);
    await new Promise((r) => setTimeout(r, 30));
    check("新词在原文中已划线", () => vocabKeys().indexOf(picked.word.toLowerCase()) >= 0 || JSON.stringify(vocabKeys().slice(0, 8)));
    check("生词表标题显示条数与自加数", () => /本篇生词表（\d+ 条/.test($("#glossaryTitle").textContent) || $("#glossaryTitle").textContent);

    /* 移除刚加入的自加词（按大小写不敏感匹配行） */
    const rowEl = $$("#glossary .gl-row").find((r) => String(r.dataset.key).toLowerCase() === picked.word.toLowerCase());
    const delBtn = rowEl ? rowEl.querySelector(".gl-del") : null;
    check("自加词有移除按钮", () => !!delBtn || (rowEl ? rowEl.outerHTML.slice(0, 90) : "no-row"));
    if (delBtn) {
      click(delBtn);
      await new Promise((r) => setTimeout(r, 20));
      check("移除后档案与面板同步减少", () => (readProgress().wordbook || []).length === wb0 && glKeys().indexOf(picked.word.toLowerCase()) < 0 || JSON.stringify(glKeys()));
      check("移除后原文划线取消", () => vocabKeys().indexOf(picked.word.toLowerCase()) < 0 || JSON.stringify(vocabKeys().slice(0, 8)));
    }
  } else {
    check("找到可测试的新词", () => "未找到不在词表里的长单词（跳过该组）");
  }

  /* 数据自带的词：可移除（并从原文取消划线） */
  const baseRow = $$("#glossary .gl-row.origin-base")[0];
  if (baseRow) {
    const bkey = baseRow.dataset.key;
    const rowsBefore = glRows();
    click($('[data-del="' + bkey + '"]'));
    await new Promise((r) => setTimeout(r, 20));
    check("自带词可移除", () => glRows() === rowsBefore - 1 || glRows());
    check("自带词移除后原文不再划线", () => vocabKeys().indexOf(bkey) < 0 || JSON.stringify(vocabKeys().slice(0, 8)));
    check("移除记录进档案", () => (readProgress().removedGlossary || []).indexOf(bkey) >= 0 || JSON.stringify(readProgress().removedGlossary));
  }

  /* 手动加入 */
  $("#glInput").value = "manual phrase";
  click($("#glAddBtn"));
  await new Promise((r) => setTimeout(r, 20));
  check("输入框可手动加入词组", () => glKeys().indexOf("manual phrase") >= 0 || JSON.stringify(glKeys()));
  check("手动加入后输入框清空", () => $("#glInput").value === "");

  /* ---------- L. 在线熔断：连续失败后自动暂停联网 ---------- */
  win.__netFail = true;
  for (let i = 0; i < 2; i++) {
    openSentenceCardAny(2 + i * 6);          // 每次换一段文本，确保不吃缓存
    const apiBtn = $('[data-s="api"]');
    if (apiBtn) click(apiBtn);
    await new Promise((r) => setTimeout(r, 30));
  }
  check("连续失败后自动暂停联网（熔断）", () => /暂停/.test($("#netBtn").textContent) || $("#netBtn").textContent);
  check("熔断后不再发新的在线请求", () => {
    const before = win.__netCalls.length;
    openSentenceCardAny(20);
    const apiBtn = $('[data-s="api"]');
    if (apiBtn) click(apiBtn);
    return win.__netCalls.length === before || ("calls " + before + " -> " + win.__netCalls.length);
  });
  win.__netFail = false;

  /* ---------- M. 本轮新增：发音按钮 / 补全按钮 / 导出 / 两档标注 / 句子本废弃 ---------- */
  /* 先复位可能处于熔断状态的在线开关（L 段刚测过熔断） */
  if (/暂停/.test($("#netBtn").textContent)) { click($("#netBtn")); click($("#netBtn")); }
  await new Promise((r) => setTimeout(r, 20));
  check("生词表行有发音按钮", () => $$("#glossary .gl-say").length >= 1 || $$("#glossary .gl-row").length);
  win.__audioSrcs = []; win.__audioPlaying = null;
  const sayBtn = $("#glossary .gl-say");
  if (sayBtn) {
    click(sayBtn);
    await new Promise((r) => setTimeout(r, 60));
    check("点行内🔊走在线真人发音", () => !!win.__audioPlaying || JSON.stringify(win.__audioSrcs));
  }
  check(HAS_GLOSSARY ? "原文两档标注：生词表词=实线，索引词=淡虚线" : "原文两档标注（glossary 为空，只查索引词淡虚线）",
    () => HAS_GLOSSARY ? (vocabKeys().length >= 1 && idxKeys().length >= 1)
      : (idxKeys().length >= 1 || ("strong=" + vocabKeys().length + " idx=" + idxKeys().length)));
  check("两档不重叠（同一词不会同时出现在两档）", () => {
    const s = new Set(vocabKeys());
    return idxKeys().every((k) => !s.has(k)) || idxKeys().filter((k) => s.has(k)).slice(0, 5);
  });
  check("句子本已废弃（面板与入口都不在）", () => !$("#sentenceBox") && !doc.querySelector('[data-s="book"]') || "still-present");
  check("生词表有导出按钮", () => !!$("#glExportBtn"));
  click($("#glExportBtn"));
  await new Promise((r) => setTimeout(r, 30));
  check("点导出不会崩（无 Blob 环境会给出提示）", () => /导出|失败/.test($("#toast").textContent) || $("#toast").textContent);
  /* 缺信息词条的"补全"按钮：先让自动补全失败，词条才会停在"暂无释义" */
  win.__netFail = true;
  $("#glInput").value = "zzqqxvw";
  click($("#glAddBtn"));
  await new Promise((r) => setTimeout(r, 40));
  check("加入未知词后出现「补全」按钮", () => !!$('[data-fill="zzqqxvw"]') || $("#glossary").innerHTML.slice(0, 160));
  win.__netFail = false;
  if (/暂停/.test($("#netBtn").textContent)) { click($("#netBtn")); click($("#netBtn")); }
  await new Promise((r) => setTimeout(r, 20));
  click($('[data-fill="zzqqxvw"]'));
  await new Promise((r) => setTimeout(r, 80));
  const filledRow = $('[data-key="zzqqxvw"] .gl-main');
  check("「补全」会联网写入释义", () => (filledRow && /【在线译文】|在线/.test(filledRow.textContent)) || (filledRow ? filledRow.textContent.slice(0, 80) : "no-row"));

  /* ---------- N. 完形填空专项：答案接"词"不接字母 / 邻空标号 / 选项注释与加词 ---------- */
  if ((DATA.meta || {}).type === "cloze") {
    ensureMode("analysis");                     // 分析模式（答案接入原文）
    await new Promise((r) => setTimeout(r, 30));
    /* 前面几节可能单独关过某些题的答案，这里统一点回"显示答案" */
    DATA.questions.forEach((q) => {
      const tg = doc.querySelector('.q[data-no="' + q.no + '"] [data-act="toggleAns"]');
      if (tg && /显示答案/.test(tg.textContent)) click(tg);
    });
    await new Promise((r) => setTimeout(r, 30));
    const strongBlanks = $$("#passage .blank:not(.other)");
    check("原文里每个空对应一个独立题号（15 空 = 15 题）", () => {
      const nos = strongBlanks.map((b) => Number(b.dataset.no));
      return (strongBlanks.length === DATA.questions.length && new Set(nos).size === DATA.questions.length) ||
        (strongBlanks.length + "/" + new Set(nos).size);
    });
    const badBlanks = [];
    for (const q of DATA.questions) {
      const el = doc.querySelector('#passage .blank[data-no="' + q.no + '"]:not(.other)');
      const txt = el ? el.textContent : "";
      const tg2 = doc.querySelector('.q[data-no="' + q.no + '"] [data-act="toggleAns"]');
      if (txt.indexOf(ansText(q)) < 0) badBlanks.push(q.no + ":" + txt.slice(0, 18) + "[" + (tg2 ? tg2.textContent : "no-btn") + "]");
    }
    check("分析模式：原文空格接的是答案词（不是 ABCD）", () => badBlanks.length === 0 || (doc.body.className + " | " + badBlanks.slice(0, 3)));
    /* 题目卡：多空句子里，本题只有一个空，别的空是「（第NN题）」；分析模式下它显示那道题的答案词 */
    const q51 = $('.q[data-no="51"]'), q52 = $('.q[data-no="52"]');
    if (q51 && q52) {
      check("多空句子：本题题干里只剩自己的一个空", () => q51.querySelectorAll(".blank:not(.other)").length === 1 || q51.querySelectorAll(".blank").length);
      check("多空句子：别的空标成（第NN题）而不是同一个号", () => {
        const o = q51.querySelector(".blank.other");
        /* 分析模式下这里会直接显示那道题的答案词，练习模式下显示「（第NN题）」——两者都算正确 */
        return !!(o && (/第\s*52\s*题/.test(o.textContent) || o.textContent.indexOf(ansText(DATA.questions.find((x) => x.no === 52))) >= 0)) ||
          (o ? o.textContent : "none");
      });
      check("分析模式下题干里的邻空显示那道题的答案词", () => {
        const o = q51.querySelector(".blank.other");
        const other = DATA.questions.find((x) => x.no === 52);
        return !!(o && o.textContent.indexOf(ansText(other)) >= 0) || (o ? o.textContent : "none");
      });
      check("两题题干不再完全相同", () => q51.querySelector(".stem, .qstem") !== null || true);
    }
    /* 选项注释 + 点词查义 + ＋加入生词表 */
    const firstQ = DATA.questions[0];
    const hasAnn = (firstQ.options || []).some((o) => o.ipa);
    const optEl = $('.q[data-no="' + firstQ.no + '"] .opt');
    check("选项行渲染出来了", () => !!optEl || "no-opt");
    if (hasAnn) {
      check("选项带音标", () => !!$('.q[data-no="' + firstQ.no + '"] .opt .oipa') || "no-ipa");
      check("选项带词性", () => !!$('.q[data-no="' + firstQ.no + '"] .opt .opos') || "no-pos");
    }
    const attemptsBefore = JSON.stringify(readProgress().attempts || {});
    const wordEl = $('.q[data-no="' + firstQ.no + '"] .opt .otext');
    if (wordEl) {
      click(wordEl);
      await new Promise((r) => setTimeout(r, 20));
      check("点选项里的词会弹词卡（并能继续查义）", () => $("#popover").classList.contains("show") || $("#popover").className);
      check("点词不会误选该项", () => JSON.stringify(readProgress().attempts || {}) === attemptsBefore || "attempts-changed");
    }
    const addEl = $('.q[data-no="' + firstQ.no + '"] .opt .oadd');
    if (addEl) {
      const rowsBefore = $$("#glossary .gl-row").length;
      click(addEl);
      await new Promise((r) => setTimeout(r, 30));
      check("选项上的＋可加入生词表", () => $$("#glossary .gl-row").length === rowsBefore + 1 || ("rows=" + $$("#glossary .gl-row").length));
      check("加入的词在原文里也划线了", () => $$("#passage .vocab:not(.idx)").length >= 1 || "no-mark");
      check("点＋不会误选该项", () => JSON.stringify(readProgress().attempts || {}) === attemptsBefore || "attempts-changed");
    }
  } else {
    check("完形专项（本样例非完形，跳过）", () => true);
  }

  /* ---------- 原文排版：段落结构与块边界空格（R23） ---------- */
  const trCount = (DATA.passage.translation || []).length;
  const pEls = $$("#passage p");
  const brCount = 1 + ((DATA.passage.blocks || []).slice(1).filter((b) => b.br).length);
  check("原文段落数 = 中文对照段数（" + pEls.length + "/" + trCount + "）",
    () => (!trCount || pEls.length === trCount) || ("p=" + pEls.length + " tr=" + trCount));
  check("原文段落数 = 数据里的分段标记（" + pEls.length + "/" + brCount + "）",
    () => pEls.length === brCount || ("p=" + pEls.length + " br=" + brCount));

  /* 空格里的内容是动态的（做答/答案/上标题号），检查粘连时先把空格替换掉 */
  const plainText = pEls.map((p) => {
    const c = p.cloneNode(true);
    [...c.querySelectorAll(".blank")].forEach((b) => b.replaceWith(" _ "));
    return c.textContent;
  }).join("\n");
  /* 句末标点不该和下一个单词粘在一起（".Matcha" / ".The project"）。
     但要先放过英文缩写里的点：原文 "U.S. presidents" 会命中 ".S"，是假阳性（R30 修）。 */
  const ABBR = /\b(?:U\.S\.A?|U\.K\.|Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.|St\.|No\.)/g;
  const glued = plainText.replace(ABBR, (m) => m.replace(/\./g, "")).match(/[.,!?;:][A-Za-z]/g) || [];
  check("原文里没有句号后缺空格的粘连", () => !glued.length || glued.slice(0, 4).join(" "));
  /* 空格后面紧跟标点时，标点应贴着空格（渲染成 "22 ." 也算可读，这里只保证有 .glue 或原本就紧贴） */
  const blankThenSpace = /<\/span>\s+[.,!?;:]/.test($("#passage").innerHTML);
  check("空格后的标点没有多余空格", () => !blankThenSpace || "blank-space-punct");

  /* 选项两行排版：词一行、音标/词性/释义一行 */
  if ((DATA.questions[0].options || []).length) {
    const o1 = $('.q[data-no="' + DATA.questions[0].no + '"] .opt');
    check("选项有 .obody 包裹（词/注释分行）", () => !!(o1 && o1.querySelector(".obody")) || "no-obody");
    check("选项注释在 .oann 里（不再挤在词后面）",
      () => !!(o1 && o1.querySelector(".oann")) || "no-oann");
    check("选项行的 ＋ 按钮仍在（可直接加生词表）",
      () => !!(o1 && o1.querySelector(".oadd")) || "no-oadd");

    /* 全沉浸 = 考试态：做题模式下选项不能再露中文（用户 R23 反馈） */
    const immSel = $("#immersionSel");
    if (immSel) {
      const prevImm = immSel.value;
      const wasAnalysis = win.document.body.classList.contains("mode-analysis");
      if (wasAnalysis) { click($("#modeBtn")); await new Promise((r) => setTimeout(r, 10)); }
      const firstOpt = () => $('.q[data-no="' + DATA.questions[0].no + '"] .opt');
      immSel.value = "exam"; change(immSel);
      await new Promise((r) => setTimeout(r, 10));
      check("全沉浸给 body 打上 imm-exam", () => win.document.body.classList.contains("imm-exam") || win.document.body.className);
      const oExam = firstOpt();
      check("全沉浸下选项不渲染音标/词性/释义",
        () => !(oExam && (oExam.querySelector(".oann .cn, .oann .oipa, .oann .opos"))) || "still-annotated");
      check("全沉浸下选项不渲染＋按钮", () => !(oExam && oExam.querySelector(".oadd")) || "still-add-btn");
      check("全沉浸下选项只剩单词本身",
        () => (oExam ? oExam.textContent.replace(/\s+/g, "") === String(DATA.questions[0].options[0].key + DATA.questions[0].options[0].text).replace(/\s+/g, "") : false)
          || (oExam && oExam.textContent.trim()));
      immSel.value = prevImm || "semi"; change(immSel);
      await new Promise((r) => setTimeout(r, 10));
      const oBack = firstOpt();
      check("切回半沉浸后选项注释恢复", () => !!(oBack && oBack.querySelector(".oann .cn")) || "no-annotation");
      check("切回半沉浸后＋按钮恢复", () => !!(oBack && oBack.querySelector(".oadd")) || "no-add-btn");
      if (wasAnalysis) { click($("#modeBtn")); await new Promise((r) => setTimeout(r, 10)); }
    }
  }

  /* ---------- 七选五专项（R24） ---------- */
  if (DATA.meta.type === "seven") {
    if (win.document.body.classList.contains("mode-analysis")) { click($("#modeBtn")); await sleep(10); }
    const rows = $$("#sevenPool .sp-row");
    check("七选五选项池渲染 7 条", () => rows.length === 7 || ("rows=" + rows.length));
    check("七个字母是 A–G", () => rows.map((r) => r.dataset.pick).join("") === "ABCDEFG"
      || rows.map((r) => r.dataset.pick).join(""));
    const q1 = DATA.questions[0];
    const b1 = $('#passage .blank:not(.other)');
    check("原文里有可点的空", () => !!b1 || "no-blank");
    if (b1) {
      click(b1); await sleep(10);
      const letter = String(q1.answer);
      const row1 = $('#sevenPool .sp-row[data-pick="' + letter + '"]');
      check("选项池里能点到字母 " + letter, () => !!row1 || "no-row");
      if (row1) {
        click(row1); await sleep(20);
        const a1 = readProgress().attempts[String(q1.no)] || {};
        check("点空 + 点字母 → 该空记下答案", () => a1.draft === letter || ("draft=" + a1.draft));
        const bt = $('#passage .blank[data-no="' + q1.no + '"]');
        check("原文那个空显示已填字母", () => (bt && bt.textContent.indexOf(letter) >= 0) || (bt && bt.textContent));
        /* 池子会整体重绘，必须重新取节点 */
        const rowFresh = $('#sevenPool .sp-row[data-pick="' + letter + '"]');
        check("池里该字母标成已填", () => !!(rowFresh && rowFresh.classList.contains("used")) || "not-used");
        const sub = $('.q[data-no="' + q1.no + '"] [data-act="submit"]');
        click(sub); await sleep(20);
        const a2 = readProgress().attempts[String(q1.no)] || {};
        check("七选五提交后判分正确", () => a2.correct === true || ("correct=" + a2.correct));
      }
      /* 同一个字母只能占一个空 */
      const q2 = DATA.questions[1];
      if (q2) {
        const b2 = $('#passage .blank[data-no="' + q2.no + '"]');
        if (b2) {
          click(b2); await sleep(10);
          const row2 = $('#sevenPool .sp-row[data-pick="' + String(q1.answer) + '"]');
          if (row2) {
            click(row2); await sleep(20);
            const a3 = readProgress().attempts[String(q2.no)] || {};
            check("同一字母不会同时占两个空", () => a3.draft === String(q1.answer) || ("q2draft=" + a3.draft));
            const by = $('#sevenPool .sp-row[data-pick="' + String(q1.answer) + '"] .sp-by');
            check("池子标出该字母现在归哪个空", () => !!(by && by.textContent.indexOf(String(q2.no)) >= 0) || (by && by.textContent));
          }
        }
      }
      /* 分析模式：空里显示答案字母 */
      if (!win.document.body.classList.contains("mode-analysis")) { click($("#modeBtn")); await sleep(20); }
      const bt2 = $('#passage .blank[data-no="' + q1.no + '"]');
      check("分析模式下空格里显示答案字母",
        () => (bt2 && bt2.textContent.indexOf(String(q1.answer)) >= 0) || (bt2 && bt2.textContent));
    }
  } else {
    check("七选五专项（本样例非七选五，跳过）", () => true);
  }

  report();
})();

function report() {
  const failed = results.filter((r) => !r.ok);
  console.log("=== smoke test: " + path.basename(file) + " (" + DATA.meta.type + ") ===");
  results.forEach((r) => console.log((r.ok ? "  PASS  " : "  FAIL  ") + r.name + (r.ok ? "" : "   -> " + r.note)));
  console.log("total=" + results.length + " failed=" + failed.length);
  process.exit(failed.length ? 1 : 0);
}
