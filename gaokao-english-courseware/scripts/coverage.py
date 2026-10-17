#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""词表覆盖率检查：原文里到底有多少词"点得到、有中文"。

回答的问题：学生读原文时，还有哪些词是"点了没反应 / 点了只有外链"的。

用法：
    python scripts/coverage.py --all
    python scripts/coverage.py 04_workspace/schema-v1/examples/reading-wildcamp.json
    python scripts/coverage.py --all --missing reading-wildcamp   # 只打印缺失词表

口径：
  · 统计范围 = 原文 blocks 的文本（学生真正在正文里点到的词），可选 --with-stems 把题干与选项也算进来
  · 一个词算"有覆盖"，当且仅当 wordIndex 或 glossary 里存在同名的键（不区分大小写）
  · 另外单列"能靠原型推断"的（变形词，索引里有原形 base）——这部分点了能出卡片，但不是直接命中
"""
import argparse
import glob
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402
ROOT = paths.workspace()
EX_DIR = os.path.join(ROOT, "04_workspace", "schema-v1", "examples")
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'\u2019-]*")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common_words import COMMON_LOOK  # noqa: E402  通用虚词表（模板里 COMMON_LOOK 的副本）

STOP = set(COMMON_LOOK.keys())


def passage_text(doc):
    out = []
    for b in (doc.get("passage") or {}).get("blocks") or []:
        if isinstance(b, dict) and b.get("text"):
            out.append(b["text"])
    return " ".join(out)


def extra_text(doc):
    out = []
    for q in doc.get("questions") or []:
        out.append(str(q.get("stem") or ""))
        for o in q.get("options") or []:
            out.append(str(o.get("text") or ""))
    for s in (doc.get("seven") or {}).get("options") or []:
        out.append(str(s.get("text") or ""))
    return " ".join(out)


def norm(w):
    """键/词统一口径：小写 + 弯撇号转 ASCII（模板里也是这么归一后匹配的）。"""
    return str(w or "").lower().replace("\u2018", "'").replace("\u2019", "'")


def keys_of(doc):
    keys = set()
    for k in ((doc.get("passage") or {}).get("wordIndex") or {}):
        keys.add(norm(k))
    for g in doc.get("glossary") or []:
        for f in ("key", "word"):
            if g.get(f):
                keys.add(norm(g[f]))
    keys |= set(COMMON_LOOK.keys())     # 模板里通用虚词也会命中
    return keys


def bases_of(doc):
    bases = set()
    for v in ((doc.get("passage") or {}).get("wordIndex") or {}).values():
        if isinstance(v, dict) and v.get("base"):
            bases.add(str(v["base"]).lower())
    return bases


def tokens(text):
    out = []
    for m in TOKEN_RE.finditer(text):
        w = m.group(0)
        if w.endswith("'s") or w.endswith("\u2019s"):
            w = w[:-2]
        out.append(w)
    return out


def report(path, show_missing=False, with_stems=False):
    doc = json.loads(io.open(path, encoding="utf-8").read())
    text = passage_text(doc) + (" " + extra_text(doc) if with_stems else "")
    toks = tokens(text)
    keys, bases = keys_of(doc), bases_of(doc)
    uniq = {}
    for t in toks:
        low = norm(t)
        uniq[low] = uniq.get(low, 0) + 1
    total = len(toks)
    hit = [t for t in toks if norm(t) in keys]
    miss = {k: v for k, v in uniq.items() if k not in keys}
    miss_content = {k: v for k, v in miss.items() if k not in STOP}
    lem = [k for k in miss if k in bases]
    pct = 100.0 * len(hit) / total if total else 0.0
    note = []
    note.append("%-30s tokens=%-4d 覆盖 %5.1f%% (%d/%d)  唯一词=%-3d 缺=%-3d (实词缺 %d)"
                % (os.path.basename(path), total, pct, len(hit), total, len(uniq), len(miss), len(miss_content)))
    note.append("  索引键 %d / 生词表 %d / 缺词中能靠原型推断的 %d"
                % (len(keys), len(doc.get("glossary") or []), len(lem)))
    if show_missing:
        top = sorted(miss_content.items(), key=lambda kv: (-kv[1], kv[0]))
        note.append("  缺失实词（按频次）：" + ", ".join("%s×%d" % (k, v) for k, v in top[:80]))
    for line in note:
        print(line)
    return pct, miss_content


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--with-stems", action="store_true", help="把题干与选项也算进覆盖率")
    ap.add_argument("--missing", action="store_true", help="打印缺失词表")
    ap.add_argument("--min", type=float, default=0.0, help="低于该覆盖率则 exit 1（门禁用）")
    args = ap.parse_args()
    targets = args.files or (sorted(glob.glob(os.path.join(EX_DIR, "*.json"))) if args.all else [])
    if not targets:
        print("no input; use --all or pass json paths")
        return 1
    worst = 100.0
    for p in targets:
        pct, _ = report(p, args.missing, args.with_stems)
        worst = min(worst, pct)
    if args.min and worst < args.min:
        print("FAIL: 最低覆盖率 %.1f%% < %.1f%%" % (worst, args.min))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
