#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""词索引去重（大小写重名归并）。

为什么需要：模板里 `WORD_INDEX[k.toLowerCase()] = ...`（tpl-student.html:322-323），
所以 `Danielle Lenoue` 与 `danielle lenoue` 会互相覆盖 —— 谁在后面谁生效，
结果是"词条信息随机变简/变全"，且词表看起来有重复。

规则（幂等）：
  1. 按小写分组；组内多于 1 条 → 只保留**信息最全**的一条（非空字段多者优先），
     平手时保留**首字母大写**的那条（专有名词）。
  2. 同时处理 examples/*.json 与 overlays/*.words.json / *.analysis.json，
     否则重跑 apply_overlay.py 会把重名再合并回来。

用法：
    python scripts/fix_wordindex.py --check   # 只报不写
    python scripts/fix_wordindex.py           # 修复
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
EX_DIR = os.path.join(ROOT, "04_workspace", "schema-v1", "examples")
OV_DIR = os.path.join(ROOT, "04_workspace", "schema-v1", "overlays")


def richness(v):
    return sum(1 for f in ("ipa", "pos", "cn", "eg", "base") if str((v or {}).get(f) or "").strip())


def dedupe(idx):
    """返回 (新索引, 丢弃的键列表)。保持原顺序中的保留者位置。"""
    keep, groups = {}, {}
    for k in idx:
        groups.setdefault(k.lower(), []).append(k)
    drop = []
    for low, keys in groups.items():
        if len(keys) == 1:
            keep[keys[0]] = idx[keys[0]]
            continue
        winner = sorted(keys, key=lambda k: (-richness(idx[k]), 0 if k[:1].isupper() else 1, len(k)))[0]
        keep[winner] = idx[winner]
        drop.extend([k for k in keys if k != winner])
    # 按首选顺序重排：保留原 JSON 顺序
    ordered = {}
    for k in idx:
        if k in keep and k not in ordered:
            ordered[k] = keep[k]
    return ordered, drop


def fix_file(path, check):
    doc = json.loads(io.open(path, encoding="utf-8").read())
    changed, dropped = False, []
    if "passage" in doc or "wordIndex" in doc:
        holder = doc["passage"] if "wordIndex" in (doc.get("passage") or {}) else doc
        idx = holder.get("wordIndex") or {}
        if idx:
            new, drop = dedupe(idx)
            if drop:
                dropped, changed = drop, True
                if not check:
                    holder["wordIndex"] = new
    if changed and not check:
        io.open(path, "w", encoding="utf-8", newline="\n").write(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    return changed, dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    targets = (sorted(glob.glob(os.path.join(EX_DIR, "*.json")))
               + sorted(glob.glob(os.path.join(OV_DIR, "*.words.json")))
               + sorted(glob.glob(os.path.join(OV_DIR, "*.analysis.json"))))
    dirty = 0
    for p in targets:
        changed, drop = fix_file(p, args.check)
        if changed:
            dirty += 1
            print("%-34s %s dropped=%d %s" % (os.path.basename(p),
                                             "WOULD-FIX" if args.check else "FIXED",
                                             len(drop),
                                             ",".join(k.encode("ascii", "replace").decode() for k in drop)))
    print("files touched: %d %s" % (dirty, "(check only)" if args.check else ""))
    return 1 if (args.check and dirty) else 0


if __name__ == "__main__":
    sys.exit(main())
