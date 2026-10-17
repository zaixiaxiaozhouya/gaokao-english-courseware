#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在一个空目录里初始化"可跑流水线"的工作区骨架。

用法：
    python scripts/init_workspace.py <目标目录>          # 在目标目录里建 04_workspace/...
    python scripts/init_workspace.py                    # 用当前目录

会创建（已存在则跳过，不覆盖任何已有文件）：
    04_workspace/schema-v1/schema.json      ← 从 skill 的 assets/ 复制（如果工作区里没有）
    04_workspace/schema-v1/examples/        空目录
    04_workspace/schema-v1/overlays/        空目录
    04_workspace/build/  04_workspace/share/  空目录
    01_source/                              空目录（素材放这里，只读）
    99_backups/                             空目录（快照放这里）

不复制模板：build.py 会自动回退到 skill 自带的 templates/tpl-student.html。
"""
import io
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)


def find_skill_asset(name):
    for cand in (os.path.join(SKILL_DIR, "assets", name),
                 os.path.join(HERE, "..", "03_skill", "assets", name)):
        if os.path.isfile(cand):
            return cand
    return None


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    target = os.path.abspath(target)
    os.makedirs(target, exist_ok=True)
    made, skipped = [], []

    dirs = ["01_source", "99_backups", "04_workspace/schema-v1/examples",
            "04_workspace/schema-v1/overlays", "04_workspace/build", "04_workspace/share"]
    for d in dirs:
        p = os.path.join(target, d.replace("/", os.sep))
        if os.path.isdir(p):
            skipped.append(d)
        else:
            os.makedirs(p, exist_ok=True)
            made.append(d)

    schema_dst = os.path.join(target, "04_workspace", "schema-v1", "schema.json")
    if os.path.isfile(schema_dst):
        skipped.append("04_workspace/schema-v1/schema.json")
    else:
        src = find_skill_asset("schema-v1.3.json")
        if not src:
            print("!! 找不到 skill 里的 assets/schema-v1.3.json，schema 没装")
            return 1
        shutil.copyfile(src, schema_dst)
        made.append("04_workspace/schema-v1/schema.json（schema v1.3）")

    print("工作区：%s" % target)
    if made:
        print("已创建：")
        for m in made:
            print("  + " + m)
    if skipped:
        print("已存在（跳过）：" + ", ".join(skipped))
    print("")
    print("下一步：")
    print("  1. 把素材放进 01_source/（只读，不要改）")
    print("  2. python scripts/new_doc.py --doc-id <id> --type <reading|seven|cloze|grammar> --nos 24-27 --title ...")
    print("  3. 填完数据后：python scripts/verify_all.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
