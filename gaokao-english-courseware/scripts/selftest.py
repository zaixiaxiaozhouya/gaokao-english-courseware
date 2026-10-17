#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skill 自检：确认这个 skill 包"自己"是好的（不依赖任何工作区）。

检查：
  S1 必需文件齐全（SKILL.md / references / scripts / templates / assets）
  S2 SKILL.md 有合法 frontmatter（name 为 kebab-case，description 非空）
  S3 所有 .py 脚本能编译（语法）
  S4 随包的示例数据能用 assets 里的 schema 通过校验
  S5 模板含占位符 `__TITLE__` / `__APP_DATA__` 与 `@media print`
  S6 用示例数据真的构建一次（输出到临时目录）并做产物结构检查

用法：python scripts/selftest.py      # 退出码 0 = 全绿
"""
import io
import json
import os
import py_compile
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def find_skill_dir():
    """定位 skill 目录：<skill>/scripts/selftest.py 或老布局的 <项目>/scripts/selftest.py + 03_skill/。"""
    cands = [
        os.path.dirname(HERE),                              # <skill>/scripts -> <skill>
        os.path.join(os.path.dirname(HERE), "03_skill"),    # <项目>/scripts -> <项目>/03_skill
        os.path.join(HERE, "..", "..", "03_skill"),
    ]
    for c in cands:
        c = os.path.abspath(c)
        if os.path.isfile(os.path.join(c, "SKILL.md")):
            return c
    return os.path.abspath(cands[0])


SKILL = find_skill_dir()
rows = []


def ok(name, good, note=""):
    rows.append((name, bool(good), note))


def main():
    # S1 必需文件（README.md 是仓库文档，不算 skill 的运行时依赖：单独安装 skill 时不会有它）
    need = ["SKILL.md", "templates/tpl-student.html", "assets/schema-v1.3.json",
            "references/schema.md", "references/pipeline.md", "references/pitfalls.md",
            "scripts/schema_check.py", "scripts/validate.py", "scripts/coverage.py",
            "scripts/build.py", "scripts/smoke_test.cjs", "scripts/paths.py"]
    missing = [n for n in need if not os.path.isfile(os.path.join(SKILL, n.replace("/", os.sep)))]
    ok("S1 必需文件齐全", not missing, "缺：" + ", ".join(missing) if missing else "%d 项" % len(need))

    # S2 frontmatter
    txt = io.open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8").read()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", txt, re.S)
    fm = m.group(1) if m else ""
    name = re.search(r"^name:\s*(\S+)\s*$", fm, re.M)
    desc = re.search(r"^description:\s*(.+)$", fm, re.M)
    good = bool(name and re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name.group(1)) and desc and len(desc.group(1).strip()) > 20)
    ok("S2 SKILL.md frontmatter", good,
       "name=%s, description %d 字" % (name.group(1) if name else "?", len(desc.group(1)) if desc else 0))

    # S3 脚本可编译
    bad = []
    for fn in sorted(os.listdir(HERE)):
        if not fn.endswith(".py"):
            continue
        try:
            py_compile.compile(os.path.join(HERE, fn), doraise=True)
        except Exception as e:
            bad.append("%s: %s" % (fn, e))
    ok("S3 脚本语法", not bad, "；".join(bad[:3]) if bad else "%d 个 .py" % len([f for f in os.listdir(HERE) if f.endswith(".py")]))

    # S4 示例数据 + schema
    sys.path.insert(0, HERE)
    try:
        from schema_check import Checker
        schema = json.loads(io.open(os.path.join(SKILL, "assets", "schema-v1.3.json"), encoding="utf-8").read())
        checker = Checker(schema)
        errs_all = []
        for fn in ("example-reading.json", "example-seven.json"):
            p = os.path.join(SKILL, "references", fn)
            doc = json.loads(io.open(p, encoding="utf-8").read())
            e = []
            checker.check(doc, checker.root, "$", e)
            if e:
                errs_all.append("%s: %s" % (fn, e[:2]))
        ok("S4 示例数据合 schema", not errs_all, "；".join(errs_all) if errs_all else "2 份示例")
    except Exception as exc:
        ok("S4 示例数据合 schema", False, str(exc)[:100])

    # S5 模板
    tpl = io.open(os.path.join(SKILL, "templates", "tpl-student.html"), encoding="utf-8").read()
    ok("S5 模板占位符与打印样式", "__TITLE__" in tpl and "__APP_DATA__" in tpl and "@media print" in tpl,
       "%d KB" % (len(tpl.encode("utf-8")) // 1024))

    # S6 真构建一次
    try:
        sys.path.insert(0, HERE)
        import importlib
        build = importlib.import_module("build")
        build.TPL = os.path.join(SKILL, "templates", "tpl-student.html")
        doc = json.loads(io.open(os.path.join(SKILL, "references", "example-reading.json"), encoding="utf-8").read())
        tmp = tempfile.mkdtemp(prefix="enstudy-selftest-")
        out = os.path.join(tmp, "selftest.html")
        payload = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        html = tpl.replace("__TITLE__", doc["meta"]["title"]).replace("__APP_DATA__", payload)
        io.open(out, "w", encoding="utf-8", newline="\n").write(html)
        problems = []
        if "__APP_DATA__" in html or "__TITLE__" in html:
            problems.append("占位符没替换")
        if "data-page-node-id" in html:
            problems.append("带生成器残留")
        if not re.search(r'id="app-data"', html):
            problems.append("缺 #app-data")
        ids = re.findall(r'\sid="([^"]+)"', html)
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            problems.append("id 重复 %s" % dup[:3])
        ok("S6 用示例数据真构建", not problems, "；".join(problems) if problems else "%d KB" % (len(html) // 1024))
    except Exception as exc:
        ok("S6 用示例数据真构建", False, str(exc)[:120])

    print("=" * 72)
    for name, good, note in rows:
        print("%-26s %-4s %s" % (name, "PASS" if good else "FAIL", note))
    print("=" * 72)
    bad = [r for r in rows if not r[1]]
    print("%s｜%d 项，失败 %d" % (SKILL, len(rows), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
