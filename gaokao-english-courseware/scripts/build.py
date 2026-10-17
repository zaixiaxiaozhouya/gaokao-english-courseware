#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把内容 JSON 注入模板，生成单文件学生版 HTML。

用法：
    python scripts/build.py --all
    python scripts/build.py --all --share      # 同时刷新 share/ 下的交付副本（按 share_map.py 命名）
    python scripts/build.py 04_workspace/schema-v1/examples/grammar-smartcity.json

约定：
- 模板：templates/tpl-student.html，占位符 `__TITLE__` 与 `__APP_DATA__`
- 产物：04_workspace/build/<docId>.html（单文件、零外部依赖、file:// 可直接打开）
- 幂等：同一输入连跑两次，产物字节一致（JSON 里 `</` 会被转义成 `<\\/` 以防提前闭合 script）
"""
import argparse
import glob
import hashlib
import io
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from share_map import SHARE_MAP, share_name  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402
ROOT = paths.workspace()
# 模板优先用 skill 自带的（脚本在 <skill>/scripts/，模板在 <skill>/templates/）；
# 老工作区里如果还有 03_skill/templates/，才回退过去。
TPL = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "tpl-student.html"))
if not os.path.isfile(TPL):
    TPL = os.path.join(ROOT, "03_skill", "templates", "tpl-student.html")
EX_DIR = os.path.join(ROOT, "04_workspace", "schema-v1", "examples")
OUT_DIR = os.path.join(ROOT, "04_workspace", "build")
SHARE_DIR = os.path.join(ROOT, "04_workspace", "share")


def build_one(json_path):
    doc = json.loads(io.open(json_path, encoding="utf-8").read())
    tpl = io.open(TPL, encoding="utf-8").read()
    title = (doc.get("meta") or {}).get("title") or "英语练习"
    payload = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    # 关键：JSON 里的 "</" 必须转义成 "<\/"，否则会提前闭合 <script>；JSON 规范允许 \/ 转义
    payload = payload.replace("</", "<\\/")
    html = tpl.replace("__TITLE__", title).replace("__APP_DATA__", payload)
    out = os.path.join(OUT_DIR, (doc.get("meta") or {}).get("docId", "doc") + ".html")
    os.makedirs(OUT_DIR, exist_ok=True)
    io.open(out, "w", encoding="utf-8", newline="\n").write(html)
    return out, len(html), doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="内容 JSON 路径")
    ap.add_argument("--all", action="store_true", help="构建 examples/ 下全部 JSON")
    ap.add_argument("--share", action="store_true", help="同时刷新 share/ 交付副本（防止发出去的是旧版）")
    args = ap.parse_args()

    targets = args.files or (sorted(glob.glob(os.path.join(EX_DIR, "*.json"))) if args.all else [])
    if not targets:
        print("no input; use --all or pass json paths")
        return 1

    for p in targets:
        out, size, doc = build_one(p)
        name = os.path.basename(out)
        # 打印 ASCII 安全信息，避免控制台编码干扰
        print("built %-28s %7d chars  sha=%s" % (name, size, hashlib.sha256(io.open(out, "rb").read()).hexdigest()[:12]))
        if args.share:
            # 登记过就用固定名；没登记按 meta.title 自动命名（不再要求每篇改 share_map.py）
            friendly = share_name(name, doc)
            os.makedirs(SHARE_DIR, exist_ok=True)
            shutil.copyfile(out, os.path.join(SHARE_DIR, friendly))
            how = "登记名" if name in SHARE_MAP else "按标题"
            print("       -> share/%s（%s）" % (friendly, how))
    return 0


if __name__ == "__main__":
    sys.exit(main())
