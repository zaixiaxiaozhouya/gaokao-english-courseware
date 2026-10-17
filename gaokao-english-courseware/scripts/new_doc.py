#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成一份符合 schema v1.3 的**内容骨架**，把"写数据"变成填空题。

用法：
    python scripts/new_doc.py --doc-id reading-xxx --type reading \
        --title "阅读理解 C 篇 · …" --nos 28-31 --score 2.5 --partial

    python scripts/new_doc.py --doc-id seven-xxx --type seven --title "七选五 · …" --nos 36-40
    python scripts/new_doc.py --doc-id cloze-xxx --type cloze --title "完形填空 · …" --nos 41-55 --score 1
    python scripts/new_doc.py --doc-id grammar-xxx --type grammar --title "语法填空 · …" --nos 56-65 --score 1.5

产出的骨架**故意通不过 validate**（answer 写 TBD、覆盖率 0），填完才会变绿——这是"待办清单"。
已存在则拒绝覆盖，除非 --force。
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402


def workspace():
    try:
        import paths
        return paths.workspace()
    except Exception:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ROOT = paths.workspace()
EX_DIR = os.path.join(ROOT, "04_workspace", "schema-v1", "examples")

SECTION = {"reading": "阅读理解", "seven": "七选五", "cloze": "完形填空", "grammar": "语法填空"}
KIND = {"reading": "choice", "seven": "seven", "cloze": "cloze", "grammar": "gap"}
N_OPTIONS = {"reading": 4, "cloze": 4}
KEYS = ["A", "B", "C", "D", "E", "F", "G"]


def parse_nos(spec):
    out = []
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def build(doc_id, typ, title, subtitle, source, paper, score, nos, partial):
    if typ == "reading":
        # 阅读理解原文本身没有空位：一段一个 p 块，段落之间用 br 分段。
        # （只有七选五 / 完形 / 语法填空才有 gap 块）
        blocks = [
            {"type": "p", "text": "TODO：第 1 段原文", "br": True},
            {"type": "p", "text": "TODO：第 2 段原文（段数按原文来，多退少补）", "br": True},
        ]
        translation = ["TODO：第 1 段中文", "TODO：第 2 段中文"]
    else:
        blocks = [
            {"type": "p", "text": "TODO：把第 1 段原文粘在这里，段末保留一个空格 ", "br": True},
        ]
        for i, no in enumerate(nos):
            blocks.append({"type": "gap", "no": no, "cue": ""})
            blocks.append({"type": "p", "text": " TODO：第 %d 空后面的原文（新段落时给这个块加 br）" % no,
                           "br": (i == 0)})
        translation = ["TODO：第 1 段中文"]

    questions = []
    for i, no in enumerate(nos):
        q = {
            "no": no,
            "score": score,
            "stem": "TODO：第 %d 空所在句子（用 ______ 标出空位）" % no if typ == "grammar"
                    else "TODO：第 %d 题题干（英文原文）" % no,
            "answer": "TBD",
            "analysis": "TODO：定位第 N 段「原句」→ 为什么答案对 → 每个干扰项错在哪",
            "hints": [
                {"level": 1, "type": "point", "text": "TODO：考点方向（只给题型/能力，不给位置）"},
                {"level": 2, "type": "evidence", "text": "TODO：第 N 段「半句原文」——为什么这句是题眼"},
                {"level": 3, "type": "eliminate", "text": "TODO：A 项…；B 项…；D 项…"},
                {"level": 4, "type": "answer", "text": "TODO：答案 X ＋ 一句定位 ＋ 一句总结"},
            ],
            "kind": KIND[typ],
        }
        if typ == "seven":
            q["role"] = "TODO：这个空在段落里的作用（小标题/举例/承接…）"
        else:
            n = N_OPTIONS.get(typ, 0)
            if n:
                q["options"] = [
                    {"key": KEYS[k], "text": "TODO：选项 %s" % KEYS[k], "cn": "", "distractorType": ""}
                    for k in range(n)
                ]
        questions.append(q)

    doc = {
        "schemaVersion": "1.3",
        "meta": {
            "docId": doc_id,
            "type": typ,
            "mode": "student",
            "title": title,
            "subtitle": subtitle or "%s（%s，%d 题）" % (SECTION[typ], nos[0] if len(nos) == 1 else "%d–%d" % (nos[0], nos[-1]), len(nos)),
            "source": source,
            "paper": paper,
            "section": SECTION[typ],
            "generatedAt": "",
            "version": "v0.1",
        },
        "passage": {
            "blocks": blocks,
            "translation": translation,
            "translationMode": "paragraph",
            "sentencePairs": [],
            "wordIndex": {},
            "structure": [],
            "culture": [],
            "hardSentences": [],
        },
        "glossary": [],
        "questions": questions,
    }
    if partial:
        doc["meta"]["partial"] = True
    if typ == "seven":
        doc["seven"] = {"options": [{"key": KEYS[i], "text": "TODO：选项 %s" % KEYS[i], "cn": "", "role": ""} for i in range(7)]}
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc-id", required=True)
    ap.add_argument("--type", required=True, choices=["reading", "seven", "cloze", "grammar"])
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--source", default="TODO：素材出处（原创/改编/AI 推定时写『待核对』）")
    ap.add_argument("--paper", default="待确认")
    ap.add_argument("--score", type=float, default=None)
    ap.add_argument("--nos", required=True, help="题号，如 24-27 或 24,25,26,27")
    ap.add_argument("--partial", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    nos = parse_nos(args.nos)
    if not nos:
        print("--nos 解析失败")
        return 2
    default_score = {"reading": 2.5, "seven": 2.5, "cloze": 1.0, "grammar": 1.5}[args.type]
    score = args.score if args.score is not None else default_score

    path = os.path.join(EX_DIR, args.doc_id + ".json")
    if os.path.isfile(path) and not args.force:
        print("已存在：%s（要覆盖加 --force）" % path)
        return 1
    os.makedirs(EX_DIR, exist_ok=True)

    import datetime
    doc = build(args.doc_id, args.type, args.title, args.subtitle, args.source, args.paper,
                score, nos, args.partial)
    doc["meta"]["generatedAt"] = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()
    io.open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")

    print("骨架已生成：%s" % path)
    print("题号 %s，%d 题，每题 %s 分" % (nos, len(nos), score))
    print("")
    print("接下来（按顺序）：")
    if args.type == "reading":
        print("  1. 填 passage.blocks：一段一个 {type:p}，新段首块加 \"br\": true（阅读原文没有空位）")
    else:
        print("  1. 填 passage.blocks：每段一块 {type:p}，**新段首块加 \"br\": true**；空位用 {type:gap,no:N}")
    print("  2. 填 passage.translation：条数必须 = 段落数（1 + br 数，首块不算）")
    print("  3. 填 questions：answer 从 TBD 改成真答案；每题 4 级 hints；错误选项写 distractorType + why")
    if args.type == "seven":
        print("  4. 填 seven.options（A–G 七条的英文与中文大意）")
    print("  5. 填 passage.wordIndex（或写 overlays/%s.fill.json），然后：" % args.doc_id)
    print("     python scripts/coverage.py 04_workspace/schema-v1/examples/%s.json --missing" % args.doc_id)
    print("  6. 填 glossary（5–8 个核心生词，学生版会画蓝色实线；留空则生词表为空）")
    print("  7. 跑门禁：python scripts/verify_all.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
