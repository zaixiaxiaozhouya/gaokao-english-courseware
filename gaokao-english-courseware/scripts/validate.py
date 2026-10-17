#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容 JSON 门禁校验（不依赖第三方库）。

用法：
    python scripts/validate.py --all
    python scripts/validate.py 04_workspace/schema-v1/examples/cloze-2023-n1.json

检查项（ERROR 阻断，WARN 提示）：
  E1 必备字段：schemaVersion / meta.{docId,type,title} / passage.blocks / questions
  E2 题号唯一且升序；同卷型题号区间校验（见 references/paper-spec.md）
  E3 每题必须有 answer / analysis / hints（且 hints 从 level 1 连续递增）
  E4 选择题：≥2 个选项，answer 必须是某个选项 key；错误选项缺 distractorType 记 WARN
  E5 填空题：hints 的 level 4（answer 型）必须存在
  W1 v1.1 应有 passage.translation（学生版需要中文对照）
  W2 分值合计与该 section 的期望值比对（仅提示）
报告同时写入 04_workspace/build/validate-report.md（UTF-8）。
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
OUT_DIR = os.path.join(ROOT, "04_workspace", "build")
SCHEMA_PATH = os.path.join(ROOT, "04_workspace", "schema-v1", "schema.json")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schema_check import Checker  # noqa: E402  结构校验（schema v1.3 是真源）

try:
    SCHEMA_CHECKER = Checker(json.loads(io.open(SCHEMA_PATH, encoding="utf-8").read()))
except Exception as _e:      # schema 坏了要立刻暴露，不要静默跳过
    SCHEMA_CHECKER = None
    print("!! schema.json 读取失败：%s" % _e)

# 题号区间与分值：来源 references/paper-spec.md
RANGES = {
    ("新课标I卷", "grammar"): (56, 65, 15.0),
    ("新课标II卷", "grammar"): (56, 65, 15.0),
    ("全国甲卷", "grammar"): (61, 70, 15.0),
    ("全国乙卷", "grammar"): (61, 70, 15.0),
    ("新课标I卷", "cloze"): (41, 55, 15.0),
    ("新课标II卷", "cloze"): (41, 55, 15.0),
    ("全国甲卷", "cloze"): (41, 60, 30.0),
    ("全国乙卷", "cloze"): (41, 60, 30.0),
    ("新课标I卷", "seven"): (36, 40, 12.5),
    ("新课标II卷", "seven"): (36, 40, 12.5),
    ("全国甲卷", "seven"): (36, 40, 10.0),
    ("全国乙卷", "seven"): (36, 40, 10.0),
    # 阅读理解第一节（R24 补）：题号区间四类卷都是 21–35；新课标 2.5 分/题，老全国卷 2 分/题
    # （见 references/paper-spec.md:31 与 :51，老卷 21–35 是 30 分，36–40 归七选五）
    ("新课标I卷", "reading"): (21, 35, 37.5),
    ("新课标II卷", "reading"): (21, 35, 37.5),
    ("全国甲卷", "reading"): (21, 35, 30.0),
    ("全国乙卷", "reading"): (21, 35, 30.0),
}


def validate(doc, path):
    errs, warns = [], []

    def E(msg): errs.append(msg)

    def W(msg): warns.append(msg)

    if not doc.get("schemaVersion"):
        E("缺 schemaVersion")
    meta = doc.get("meta") or {}
    for k in ("docId", "type", "title"):
        if not meta.get(k):
            E("meta.%s 缺失" % k)
    if str(doc.get("schemaVersion", "")).startswith("1.1") and not (doc.get("passage") or {}).get("translation"):
        W("v1.1 但没有 passage.translation（学生版中文对照会缺失）")
    if not (doc.get("passage") or {}).get("blocks"):
        E("passage.blocks 缺失")

    qs = doc.get("questions") or []
    if not qs:
        E("questions 为空")
    # v1.2：逐句对照与全篇词表（学生版划词/划句的离线来源）
    pas = doc.get("passage") or {}
    pairs = pas.get("sentencePairs") or []
    if pairs:
        ids = [p.get("id") for p in pairs]
        if len(set(ids)) != len(ids):
            E("passage.sentencePairs 的 id 有重复")
        for p in pairs:
            if not (p.get("en") or "").strip() or not (p.get("zh") or "").strip():
                E("passage.sentencePairs 存在空的 en/zh（id=%s）" % p.get("id"))
            if str(p.get("zh", "")).strip().endswith("。"):
                continue
        blanks = sum(str(p.get("en", "")).count("______") for p in pairs)
        # 只有"原文本身有空位"的题型（语法填空/完形/七选五）才要求逐句里的 ______ 处数 == 题数；
        # 阅读理解原文没有空位，句子里本来就不该有 ______（R24）
        has_gap = any((b or {}).get("type") == "gap" for b in (pas.get("blocks") or []))
        if has_gap and blanks != len(qs):
            W("sentencePairs 中 ______ 共 %d 处，与题数 %d 不一致（可能切句方式不同）" % (blanks, len(qs)))
    idx = pas.get("wordIndex") or {}
    if idx:
        miss = [k for k, v in idx.items() if not (v.get("cn") or "").strip()]
        if miss:
            E("passage.wordIndex 以下词条缺 cn：%s" % miss[:8])
        noipa = [k for k, v in idx.items() if not (v.get("ipa") or "").strip()]
        if noipa:
            W("passage.wordIndex 以下词条缺音标：%s" % noipa[:8])
    nos = [q.get("no") for q in qs]
    if len(set(nos)) != len(nos):
        E("题号有重复：%s" % nos)
    if nos != sorted(nos):
        E("题号未升序：%s" % nos)

    paper, typ = meta.get("paper"), meta.get("type")
    if (paper, typ) in RANGES:
        lo, hi, expect = RANGES[(paper, typ)]
        got = sorted(n for n in nos if isinstance(n, int))
        partial = bool(meta.get("partial"))
        if got and not partial and (got[0] != lo or got[-1] != hi):
            E("题号区间应为 %d–%d，实际 %s–%s" % (lo, hi, got[0], got[-1]))
        if got and partial:
            # 单篇/单节抽出来做的内容（例如只做阅读 A 篇 21–23）：只校验落在区间内
            if got[0] < lo or got[-1] > hi:
                E("partial 内容的题号 %s–%s 超出该题型区间 %d–%d" % (got[0], got[-1], lo, hi))
        total = sum(float(q.get("score") or 0) for q in qs)
        if total and not partial and abs(total - expect) > 0.01:
            W("分值合计 %.1f，与该 section 期望 %.1f 不一致" % (total, expect))
    else:
        W("卷型/题型组合 (%s, %s) 不在 paper-spec 校验表内，跳过题号与分值校验" % (paper, typ))

    # 七选五（R24）：选项池在 doc.seven.options，必须正好 A–G，且每题答案必须落在池里
    if typ == "seven":
        sopts = (doc.get("seven") or {}).get("options") or []
        keys = [str(o.get("key")) for o in sopts]
        if sorted(keys) != list("ABCDEFG"):
            E("seven.options 必须是 A–G 七项，实际 %s" % (keys,))
        for q in qs:
            if str(q.get("answer")) not in keys:
                E("第 %s 题 answer=%s 不在 seven.options 的键里" % (q.get("no"), q.get("answer")))
            if not (q.get("analysis") or "").strip():
                E("第 %s 题缺 analysis（七选五每题都要给为什么对/为什么错）" % q.get("no"))

    for q in qs:
        no = q.get("no")
        if not q.get("answer"):
            E("第 %s 题缺 answer" % no)
        if not q.get("analysis"):
            E("第 %s 题缺 analysis" % no)
        hints = q.get("hints") or []
        if not hints:
            E("第 %s 题缺 hints（学生版必须有分级提示）" % no)
        else:
            levels = [h.get("level") for h in hints]
            if levels != list(range(1, len(levels) + 1)):
                E("第 %s 题 hints.level 必须是 1..n 连续，实际 %s" % (no, levels))
            if not any(h.get("type") == "answer" for h in hints):
                E("第 %s 题 hints 缺少 type=answer 的最终级" % no)
        opts = q.get("options")
        if opts:
            if len(opts) < 2:
                E("第 %s 题选项少于 2 个" % no)
            keys = [o.get("key") for o in opts]
            if str(q.get("answer")) not in [str(k) for k in keys]:
                E("第 %s 题 answer=%s 不在选项 %s 中" % (no, q.get("answer"), keys))
            missing = [k for o, k in zip(opts, keys) if str(k) != str(q.get("answer")) and not o.get("distractorType")]
            if missing:
                W("第 %s 题以下错误选项缺 distractorType：%s" % (no, missing))
    return errs, warns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    targets = args.files or (sorted(glob.glob(os.path.join(EX_DIR, "*.json"))) if args.all else [])
    if not targets:
        print("no input; use --all or pass json paths")
        return 1

    report, bad = [], 0
    for p in targets:
        doc = json.loads(io.open(p, encoding="utf-8").read())
        # 先过 schema（结构：字段名/类型/枚举/必填），再过业务规则
        s_errs = []
        if SCHEMA_CHECKER is None:
            s_errs = ["schema.json 不可用，结构校验被跳过"]
        else:
            SCHEMA_CHECKER.check(doc, SCHEMA_CHECKER.root, "$", s_errs)
        errs, warns = validate(doc, p)
        errs = s_errs + errs
        name = os.path.basename(p)
        status = "PASS" if not errs else "FAIL"
        if errs:
            bad += 1
        print("%-30s %-4s errors=%d warnings=%d" % (name, status, len(errs), len(warns)))
        report.append("## %s — %s\n" % (name, status))
        for e in errs:
            report.append("- ❌ %s" % e)
        for w in warns:
            report.append("- ⚠️ %s" % w)
        if not errs and not warns:
            report.append("- 无问题")
        report.append("")
    os.makedirs(OUT_DIR, exist_ok=True)
    io.open(os.path.join(OUT_DIR, "validate-report.md"), "w", encoding="utf-8").write(
        "# 内容 JSON 校验报告\n\n共 %d 个文件，失败 %d 个。\n\n%s" % (len(targets), bad, "\n".join(report)))
    print("report: 04_workspace/build/validate-report.md")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
