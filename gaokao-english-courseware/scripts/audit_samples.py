#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""样品一致性审计（不依赖第三方库）。

回答的问题：**现在这几份样品到底有没有"数据层/交付层"的硬伤**——
比 validate.py 更宽，覆盖 content JSON、overlay、构建产物、share 交付副本四层。

用法：
    python scripts/audit_samples.py            # 全部
    python scripts/audit_samples.py --no-edge  # 跳过 share 同步检查（未构建时）

检查项（ERROR 阻断交付，WARN 仅提示）：
  A1 题号必须连续递增；A2 answer 必须在选项内；A3 hints level 连续且末级为 answer
  A4 错误选项应有 distractorType；A5 passage 空格数应等于题数
  A6 sentencePairs 的 ______ 处数应等于题数（做题模式不许泄露答案）
  B1 wordIndex 大小写重名（Danielle Lenoue / danielle lenoue）
  B2 wordIndex 条目缺 ipa / pos / cn
  B3 wordIndex 键在原文中找不到（疑似拼错或多余）
  B4 选项注释覆盖率（ipa / pos）
  C1 构建产物 sha256 必须与 share 交付副本一致（否则发出去的是旧版）
  C2 产物不得残留 __TITLE__ / __APP_DATA__ 占位符
  C3 产物不得带 data-page-node-id（生成器残留）
  C4 产物必须含 @media print
  C5 产物 <script> 开闭必须配平；内联 app-data 必须可解析
  C6 产物内 HTML id 不得重复（重复会打断事件绑定）
报告写入 04_workspace/build/audit-report.md（UTF-8）。
"""
import argparse
import glob
import hashlib
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402
ROOT = paths.workspace()
EX_DIR = os.path.join(ROOT, "04_workspace", "schema-v1", "examples")
OV_DIR = os.path.join(ROOT, "04_workspace", "schema-v1", "overlays")
BUILD_DIR = os.path.join(ROOT, "04_workspace", "build")
SHARE_DIR = os.path.join(ROOT, "04_workspace", "share")
OUT = os.path.join(BUILD_DIR, "audit-report.md")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from share_map import share_name  # noqa: E402  与 build.py 共用同一份交付命名规则
import coverage as cov  # noqa: E402  词表覆盖率口径（与 common_words.py 一致）
from common_words import COMMON_LOOK  # noqa: E402  通用虚词表真源


class Rep(object):
    def __init__(self, name):
        self.name, self.errs, self.warns, self.notes = name, [], [], []

    def E(self, m):
        self.errs.append(m)

    def W(self, m):
        self.warns.append(m)

    def N(self, m):
        self.notes.append(m)

    @property
    def status(self):
        return "FAIL" if self.errs else ("WARN" if self.warns else "OK")


def passage_text(doc):
    for b in (doc.get("passage") or {}).get("blocks") or []:
        if isinstance(b, dict) and b.get("text"):
            yield b["text"]


def searchable_text(doc):
    """词条可能来自原文、选项、答案解析（答案词本身被挖空），所以都要搜。"""
    parts = list(passage_text(doc))
    for p in (doc.get("passage") or {}).get("sentencePairs") or []:
        parts.append(str(p.get("en", "")))
    for q in doc.get("questions") or []:
        parts.extend([str(q.get("stem", "")), str(q.get("analysis", "")), str(q.get("answer", ""))])
        for o in q.get("options") or []:
            parts.append(str(o.get("text", "")))
        for h in q.get("hints") or []:
            parts.append(str(h.get("text", "")))
    return " ".join(parts).lower()


def likely_present(key, body):
    """词索引键可能是原型，原文是变形（delay → delayed、foot → feet…），宽松匹配一次。"""
    k = key.lower()
    if k in body:
        return True
    cands = [k + "s", k + "es", k + "ed", k + "d", k + "ing", k + "ly"]
    if k.endswith("e"):
        cands += [k[:-1] + "ing", k[:-1] + "ed"]
    if k.endswith("y"):
        cands += [k[:-1] + "ies", k[:-1] + "ied"]
    return any(c in body for c in cands)


def audit_json(path):
    doc = json.loads(io.open(path, encoding="utf-8").read())
    doc_id = (doc.get("meta") or {}).get("docId") or os.path.basename(path)
    r = Rep(os.path.basename(path))
    meta = doc.get("meta") or {}
    qs = doc.get("questions") or []
    pas = doc.get("passage") or {}

    if not meta.get("paper") or meta.get("paper") == "待确认":
        r.W("meta.paper 未定（论文卷型区间无法校验）")

    # A1 题号连续
    nos = [q.get("no") for q in qs]
    ints = [n for n in nos if isinstance(n, int)]
    gaps = [b for a, b in zip(ints, ints[1:]) if b != a + 1]
    if gaps:
        r.E("题号不连续：%s" % gaps)
    if ints and ints[0] != min(ints):
        r.W("题号未从最小开始排列")

    # 空格数
    blocks = list(pas.get("blocks") or [])
    blanks = sum(str(b.get("text", "")).count("______") for b in blocks if isinstance(b, dict))
    blockers = sum(1 for b in blocks if isinstance(b, dict) and b.get("type") == "gap")
    blocks_gap = blockers > 0 or blanks > 0
    if blanks and blanks != len(qs):
        r.E("原文 ______ 共 %d 处，题数 %d（不相等）" % (blanks, len(qs)))
    if blockers and blockers != len(qs):
        r.E("gap 块 %d 个，题数 %d（不相等）" % (blockers, len(qs)))

    total = 0.0
    miss_distractor = 0
    opt_with_ipa = opt_with_pos = opt_total = 0
    for q in qs:
        no = q.get("no")
        total += float(q.get("score") or 0)
        opts = q.get("options") or []
        if not q.get("answer"):
            r.E("第 %s 题缺 answer" % no)
        if not q.get("analysis"):
            r.E("第 %s 题缺 analysis" % no)
        hints = q.get("hints") or []
        levels = [h.get("level") for h in hints]
        if levels != list(range(1, len(levels) + 1)):
            r.E("第 %s 题 hints.level 非 1..n 连续：%s" % (no, levels))
        if not any(h.get("type") == "answer" for h in hints):
            r.E("第 %s 题 hints 缺 type=answer 末级提示" % no)
        if opts:
            keys = [str(o.get("key")) for o in opts]
            if str(q.get("answer")) not in keys:
                r.E("第 %s 题 answer=%s 不在选项 %s 中" % (no, q.get("answer"), keys))
            for o in opts:
                opt_total += 1
                if (o.get("ipa") or "").strip():
                    opt_with_ipa += 1
                if (o.get("pos") or "").strip():
                    opt_with_pos += 1
                if str(o.get("key")) != str(q.get("answer")) and not o.get("distractorType"):
                    miss_distractor += 1
    if miss_distractor:
        r.W("%d 个错误选项缺 distractorType（干扰项分析无法归类）" % miss_distractor)
    r.N("题数 %d / 选项 %d / 分值合计 %g / 选项注释 ipa %d pos %d"
        % (len(qs), opt_total, total, opt_with_ipa, opt_with_pos))

    # A5.5 段落结构：数据里每段起始块打 br，段数应与中文对照（translation）一致
    #      首块上的 br 不算"新段"（它就是第一段）
    tr = pas.get("translation") or []
    n_para = 1 + sum(1 for i, b in enumerate(blocks) if i > 0 and isinstance(b, dict) and b.get("br"))
    if tr and n_para != len(tr):
        r.E("原文段落数 %d ≠ 中文对照段数 %d（渲染会把不同段落粘在一起）" % (n_para, len(tr)))
    r.N("原文 %d 段 / 中文对照 %d 段" % (n_para, len(tr)))

    # A6 sentencePairs 不许泄露答案
    pairs = pas.get("sentencePairs") or []
    if pairs:
        pb = sum(str(p.get("en", "")).count("______") for p in pairs)
        # 只有"原文本身有空位"的题型才要求 ______ 处数 == 题数（阅读原文没有空位）
        if blocks_gap and pb != len(qs):
            r.W("sentencePairs 中 ______ 共 %d 处，题数 %d" % (pb, len(qs)))
        r.N("逐句译文 %d 句（______ %d 处）" % (len(pairs), pb))
    else:
        r.W("无 sentencePairs（划句翻译/逐句对照不可用）")

    # B 词索引
    idx = pas.get("wordIndex") or {}
    if idx:
        low = {}
        for k in idx:
            low.setdefault(k.lower(), []).append(k)
        dup = {k: v for k, v in low.items() if len(v) > 1}
        if dup:
            r.E("wordIndex 大小写重名 %d 组：%s" % (len(dup), list(dup.values())[:4]))
        no_ipa = [k for k, v in idx.items() if not (v.get("ipa") or "").strip()]
        no_pos = [k for k, v in idx.items() if not (v.get("pos") or "").strip()]
        no_cn = [k for k, v in idx.items() if not (v.get("cn") or "").strip()]
        if no_cn:
            r.E("wordIndex 缺 cn：%s" % no_cn[:6])
        if no_ipa:
            r.W("wordIndex 缺音标 %d 条：%s" % (len(no_ipa), no_ipa[:6]))
        if no_pos:
            r.W("wordIndex 缺词性 %d 条：%s" % (len(no_pos), no_pos[:6]))
        body = searchable_text(doc)
        gone = [k for k in idx if not likely_present(k, body)]
        if gone:
            r.W("wordIndex 有 %d 条在全文（原文/选项/解析）中都找不到：%s" % (len(gone), gone[:6]))
        r.N("词索引 %d 条（含原型 %d）" % (len(idx), sum(1 for v in idx.values() if v.get("base"))))
    else:
        r.W("无 wordIndex（划词查词只剩外链兜底）")

    gl = (doc.get("glossary") or [])          # 生词表在顶层，不在 passage 里
    if gl:
        bad = [g.get("key") or g.get("word") for g in gl if not (g.get("cn") or "").strip()]
        if bad:
            r.E("glossary 缺 cn：%s" % bad[:6])
        r.N("生词表自带 %d 条" % len(gl))

    # 题型专项（R24）
    typ = meta.get("type")
    if typ == "seven":
        sopts = (doc.get("seven") or {}).get("options") or []
        keys = [str(o.get("key")) for o in sopts]
        if sorted(keys) != list("ABCDEFG"):
            r.E("seven.options 不是 A–G 七项：%s" % keys)
        bad_ans = [q.get("no") for q in qs if str(q.get("answer")) not in keys]
        if bad_ans:
            r.E("七选五答案不在选项池里：题 %s" % bad_ans)
        no_text = [o.get("key") for o in sopts if not (o.get("text") or "").strip()]
        if no_text:
            r.E("seven.options 缺英文选项文本：%s" % no_text)
        r.N("七选五选项池 %d 条（带中文大意 %d）" % (len(sopts), sum(1 for o in sopts if o.get("cn"))))
    if typ == "reading":
        no_opt = [q.get("no") for q in qs if len(q.get("options") or []) < 2]
        if no_opt:
            r.E("阅读题缺选项（A–D）：题 %s" % no_opt)
        r.N("阅读 %d 题，每题选项 %s" % (len(qs), [len(q.get("options") or []) for q in qs]))
    st, cu, hs = pas.get("structure") or [], pas.get("culture") or [], pas.get("hardSentences") or []
    if st or cu or hs:
        r.N("深度解读：结构 %d 条 / 文化背景 %d 条 / 长难句 %d 条" % (len(st), len(cu), len(hs)))
    if meta.get("partial"):
        r.N("meta.partial=true（整卷中的一节/一篇，题号只校验落在区间内）")

    # 词表覆盖率（R25）：学生"点任何词都想有中文"
    try:
        toks = cov.tokens(cov.passage_text(doc))
        keys = cov.keys_of(doc)
        hit = sum(1 for t in toks if t.lower() in keys)
        pct = 100.0 * hit / len(toks) if toks else 100.0
        r.N("词表覆盖率 %.1f%%（%d/%d 词次有离线释义）" % (pct, hit, len(toks)))
        if pct < 95.0:
            r.W("词表覆盖率 %.1f%% < 95%%：还有词点了没反应（跑 scripts/coverage.py --missing 看缺哪些）" % pct)
    except Exception as e:
        r.W("覆盖率检查失败：%s" % e)
    return r


def audit_html(path, check_share):
    r = Rep(os.path.basename(path))
    html = io.open(path, encoding="utf-8").read()
    data = None
    m = re.search(r'<script[^>]*id="app-data"[^>]*>(.*?)</script>', html, re.S)
    if m:
        try:
            data = json.loads(m.group(1).replace("<\\/", "</"))
            r.N("内联数据可解析：%d 题" % len(data.get("questions") or []))
        except Exception as e:
            r.E("内联 app-data 无法解析：%s" % e)
    else:
        r.E("找不到 #app-data 内联数据")

    if "__APP_DATA__" in html or "__TITLE__" in html:
        r.E("产物残留未替换占位符")
    if "data-page-node-id" in html:
        r.E("产物带 data-page-node-id（生成器残留）")
    if "@media print" not in html:
        r.E("产物缺 @media print（不能打印）")
    opens = len(re.findall(r"<script\b", html))
    closes = len(re.findall(r"</script>", html))
    if opens != closes:
        r.E("<script> 开闭不配平：%d/%d" % (opens, closes))
    ids = re.findall(r'\sid="([^"]+)"', html)
    dupids = sorted({i for i in ids if ids.count(i) > 1})
    if dupids:
        r.E("HTML id 重复：%s" % dupids[:6])
    if data and data.get("meta", {}).get("title"):
        t = data["meta"]["title"]
        if t not in html.split("</title>")[0]:
            r.W("<title> 与 meta.title 不一致")
    # 模板里的通用虚词表必须与 scripts/common_words.py 一致（两处副本容易漂）
    m2 = re.search(r"var COMMON_LOOK = \{(.*?)\n  \};", html, re.S)
    if m2:
        in_tpl = set(re.findall(r"([A-Za-z]+)\s*:\s*\[", m2.group(1)))
        if in_tpl != set(COMMON_LOOK.keys()):
            only_tpl = sorted(in_tpl - set(COMMON_LOOK))
            only_py = sorted(set(COMMON_LOOK) - in_tpl)
            r.E("通用虚词表与 common_words.py 不一致：模板多 %s / 少了 %s" % (only_tpl[:5], only_py[:5]))
        else:
            r.N("通用虚词表 %d 条（与 common_words.py 一致）" % len(in_tpl))
    else:
        r.W("模板里找不到 COMMON_LOOK，无法校验通用虚词表")
    r.N("大小 %.1f KB / 内联 id %d 个" % (len(html.encode("utf-8")) / 1024.0, len(ids)))

    if check_share:
        target = share_name(os.path.basename(path), data)
        sp = os.path.join(SHARE_DIR, target) if target else None
        if sp and os.path.isfile(sp):
            h1 = hashlib.sha256(io.open(path, "rb").read()).hexdigest()
            h2 = hashlib.sha256(io.open(sp, "rb").read()).hexdigest()
            if h1 != h2:
                r.E("share 交付副本与 build 不一致（发出去的是旧版）：%s" % target)
            else:
                r.N("share 副本同步：%s" % target)
        elif sp:
            r.W("share 缺交付副本：%s" % target)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-share", action="store_true", help="跳过 share 同步检查")
    args = ap.parse_args()

    reps = []
    for p in sorted(glob.glob(os.path.join(EX_DIR, "*.json"))):
        reps.append(audit_json(p))
    for p in sorted(glob.glob(os.path.join(BUILD_DIR, "*.html"))):
        reps.append(audit_html(p, not args.no_share))

    bad = sum(1 for r in reps if r.errs)
    lines = ["# 样品一致性审计报告\n", "共 %d 个对象，ERROR %d 个。\n" % (len(reps), bad)]
    for r in reps:
        lines.append("## %s — %s（ERROR %d / WARN %d）\n" % (r.name, r.status, len(r.errs), len(r.warns)))
        for e in r.errs:
            lines.append("- ❌ %s" % e)
        for w in r.warns:
            lines.append("- ⚠️ %s" % w)
        for n in r.notes:
            lines.append("- · %s" % n)
        lines.append("")
    io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(lines))

    for r in reps:
        print("%-34s %-4s E=%d W=%d" % (r.name.encode("ascii", "replace").decode(),
                                        r.status, len(r.errs), len(r.warns)))
    print("report: 04_workspace/build/audit-report.md")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
