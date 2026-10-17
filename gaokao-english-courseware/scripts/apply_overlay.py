#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 overlays/<docId>.analysis.json 里的「逐句对照」与「全篇词表」合并进 examples/<docId>.json。

overlay 结构（由生成期产出，见 02_docs/08-双模式设计（做题·分析）.md §4）：
    { "sentencePairs": [ {"id":"s1","en":"...","zh":"..."} ], "wordIndex": { "word": {"ipa","pos","cn","eg"} } }

合并结果写入 passage.sentencePairs 与 passage.wordIndex，并把 schemaVersion 升到 SCHEMA_VERSION（当前 1.3）。
幂等：同一 overlay 连跑两次结果一致。

用法：
    python scripts/apply_overlay.py --all
    python scripts/apply_overlay.py 04_workspace/schema-v1/examples/grammar-smartcity.json
    python scripts/apply_overlay.py --all --check     # 只检查是否需要合并
"""
import argparse
import glob
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402
ROOT = paths.workspace()
SCHEMA_VERSION = "1.3"
EX_DIR = os.path.join(ROOT, "04_workspace", "schema-v1", "examples")
OV_DIR = os.path.join(ROOT, "04_workspace", "schema-v1", "overlays")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fix_wordindex import dedupe  # noqa: E402  大小写重名归并（模板按小写建索引，重名会互相覆盖）


def apply_one(path, check=False):
    doc = json.loads(io.open(path, encoding="utf-8").read())
    doc_id = (doc.get("meta") or {}).get("docId")
    ov_path = os.path.join(OV_DIR, doc_id + ".analysis.json")
    words_path = os.path.join(OV_DIR, doc_id + ".words.json")
    fill_path = os.path.join(OV_DIR, doc_id + ".fill.json")
    if not os.path.isfile(ov_path) and not os.path.isfile(words_path) and not os.path.isfile(fill_path):
        return "no-overlay", 0, 0, False
    pairs, words = [], {}
    if os.path.isfile(ov_path):
        ov = json.loads(io.open(ov_path, encoding="utf-8").read())
        pairs = ov.get("sentencePairs") or []
        words = ov.get("wordIndex") or {}
    passage = doc.setdefault("passage", {})
    changed = False
    if pairs and passage.get("sentencePairs") != pairs:
        passage["sentencePairs"] = pairs
        changed = True
    # 全量词索引（<docId>.words.json）优先：与 analysis 里的词表取并集
    if os.path.isfile(words_path):
        extra = (json.loads(io.open(words_path, encoding="utf-8").read()) or {}).get("wordIndex") or {}
        if extra:
            merged = dict(words)
            merged.update(extra)
            words = merged
    # 大小写重名归并（Danielle Lenoue / danielle lenoue 会让模板的 key.toLowerCase() 互相覆盖）
    # 必须在比较之前做，否则每次跑都会"看似有变化"，破坏幂等
    if words:
        words, _drop = dedupe(words)
    # 补词表（<docId>.fill.json，R25）：优先级最高，专门用来"把漏掉的词补进索引"
    # 期望值必须在"是否需要写"的比较之前算完，否则文件里已有的 fill 词不在期望值里，
    # --check 会永远报 merged（status 与退出码失真，R30 修）：
    #   · 有 analysis/words overlay：期望值 = overlay 词表 ∪ fill
    #   · 只有 fill（阅读这类词表直接写在主数据里）：期望值 = 现有索引 ∪ fill
    fill_words = {}
    if os.path.isfile(fill_path):
        fill_words = (json.loads(io.open(fill_path, encoding="utf-8").read()) or {}).get("wordIndex") or {}
    if fill_words:
        expected = dict(words if words else (passage.get("wordIndex") or {}))
        expected.update(fill_words)
        expected, _drop = dedupe(expected)
    else:
        expected = words
    if expected and passage.get("wordIndex") != expected:
        passage["wordIndex"] = expected
        changed = True
    words = expected or {}
    # 选项注释（<docId>.options.json）：给每个选项补 音标/词性/原型（原有语境释义 cn 优先保留）
    opts_path = os.path.join(OV_DIR, doc_id + ".options.json")
    if os.path.isfile(opts_path):
        om = (json.loads(io.open(opts_path, encoding="utf-8").read()) or {}).get("options") or {}
        for q in doc.get("questions") or []:
            for o in q.get("options") or []:
                info = om.get(str(o.get("text", "")).strip().lower())
                if not info:
                    continue
                for f in ("ipa", "pos", "base"):
                    if info.get(f) and o.get(f) != info[f]:
                        o[f] = info[f]
                        changed = True
                if not o.get("cn") and info.get("cn"):
                    o["cn"] = info["cn"]
                    changed = True
    if changed and doc.get("schemaVersion") != SCHEMA_VERSION:
        doc["schemaVersion"] = SCHEMA_VERSION
    if changed and not check:
        io.open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    return ("merged" if changed else "ok"), len(pairs), len(words), changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    targets = args.files or (sorted(glob.glob(os.path.join(EX_DIR, "*.json"))) if args.all else [])
    if not targets:
        print("no input; use --all or pass json paths")
        return 1
    dirty = 0
    for p in targets:
        status, npairs, nwords, changed = apply_one(p, args.check)
        if changed:
            dirty += 1
        print("%-30s %-10s sentences=%d words=%d" % (os.path.basename(p), status, npairs, nwords))
    return 1 if (args.check and dirty) else 0


if __name__ == "__main__":
    sys.exit(main())
