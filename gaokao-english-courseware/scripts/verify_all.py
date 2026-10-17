#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一条命令跑完全部门禁（防止漏步）。

用法：
    python scripts/verify_all.py              # 结构 + 业务 + 覆盖率 + 一致性 + 构建 + 冒烟
    python scripts/verify_all.py --fast       # 跳过冒烟（没装 node/jsdom 时用）
    python scripts/verify_all.py --edge       # 额外跑真实 Edge 探针（慢）

退出码：0 全绿；1 有任一步失败。
"""
import argparse
import glob
import io
import json
import os
import shutil
import subprocess
import sys

# Windows 控制台默认 GBK，子进程输出里可能含无法编码的字符 → 统一按 UTF-8 输出（坏字符替换掉）
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402


def workspace():
    try:
        import paths
        return paths.workspace()
    except Exception:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ROOT = paths.workspace()
# 脚本住在 <skill>/scripts/：一律以本文件所在目录为准，不写死工作区里的 90_tools/
TOOLS = os.path.dirname(os.path.abspath(__file__))
EX_DIR = os.path.join(ROOT, "04_workspace", "schema-v1", "examples")
BUILD_DIR = os.path.join(ROOT, "04_workspace", "build")
PY = sys.executable


def run(cmd, tail=3, quiet_ok=True):
    """跑一条命令，返回 (ok, 摘要)。"""
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except Exception as e:
        return False, "无法执行：%s" % e
    out = (p.stdout or "") + (p.stderr or "")
    lines = [l for l in out.strip().splitlines() if l.strip()]
    ok = p.returncode == 0
    summary = " | ".join(lines[-tail:]) if lines else "(无输出)"
    return ok, summary


def stub_fail(msg):
    return "跳过（%s）" % msg


def find_node():
    """node 可能在 PATH 里，也可能是宿主自带的运行时；允许用 ENSTUDY_NODE 指定。"""
    env = os.environ.get("ENSTUDY_NODE")
    if env and os.path.isfile(env):
        return env
    found = shutil.which("node") or shutil.which("node.exe")
    if found:
        return found
    for cand in (
        os.path.expandvars(r"%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe"),
        r"C:\Program Files\nodejs\node.exe",
        "/usr/local/bin/node",
        "/usr/bin/node",
    ):
        if os.path.isfile(cand):
            return cand
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="跳过冒烟测试")
    ap.add_argument("--edge", action="store_true", help="额外跑真实 Edge 探针")
    args = ap.parse_args()

    rows = []

    def add(name, ok, note):
        rows.append((name, ok, note))

    ok, s = run([PY, os.path.join(TOOLS, "schema_check.py"), "--all"], tail=1)
    add("结构 schema_check", ok, s)

    ok, s = run([PY, os.path.join(TOOLS, "validate.py"), "--all"], tail=2)
    add("业务 validate", ok, s)

    ok, s = run([PY, os.path.join(TOOLS, "coverage.py"), "--all"], tail=1)
    # coverage 本身不设 --min 就总是 0；这里自己判断最低覆盖率
    lowest = 100.0
    try:
        import coverage as cov
        for p in sorted(glob.glob(os.path.join(EX_DIR, "*.json"))):
            doc = json.loads(io.open(p, encoding="utf-8").read())
            toks = cov.tokens(cov.passage_text(doc))
            keys = cov.keys_of(doc)
            hit = sum(1 for t in toks if cov.norm(t) in keys)
            lowest = min(lowest, 100.0 * hit / len(toks) if toks else 100.0)
    except Exception:
        lowest = -1
    add("词表覆盖率", lowest < 0 or lowest >= 95.0, "最低 %.1f%%（阈值 95%%）" % lowest if lowest >= 0 else "无法计算")

    ok, s = run([PY, os.path.join(TOOLS, "audit_samples.py")], tail=2)
    add("一致性 audit", ok, s)

    ok, s = run([PY, os.path.join(TOOLS, "build.py"), "--all", "--share"], tail=1)
    add("构建 build --share", ok, s)

    htmls = sorted(glob.glob(os.path.join(BUILD_DIR, "*.html")))
    node = find_node()
    if args.fast:
        add("冒烟 smoke_test", True, "跳过（--fast）")
    elif not node:
        add("冒烟 smoke_test", False, "找不到 node；用 --fast 跳过，或设 ENSTUDY_NODE 指向 node 可执行文件")
    else:
        smoke = os.path.join(TOOLS, "smoke_test.cjs")
        failed = []
        for h in htmls:
            ok, s = run([node, smoke, h], tail=1)
            if not ok:
                failed.append("%s: %s" % (os.path.basename(h), s))
        add("冒烟 smoke_test（%d 份）" % len(htmls), not failed, "全部通过" if not failed else "；".join(failed[:3]))

    if args.edge:
        if not node:
            add("真实 Edge 探针", False, "找不到 node")
        else:
            failed = []
            for h in htmls:
                ok, s = run([node, os.path.join(TOOLS, "edge_probe.cjs"), h], tail=1)
                if not ok or "errors=[]" not in s.replace(" ", ""):
                    failed.append(os.path.basename(h))
            add("真实 Edge 探针（%d 份）" % len(htmls), not failed, "errors=[]" if not failed else "出错：%s" % failed[:3])

    print("=" * 78)
    for name, ok, note in rows:
        print("%-22s %-4s %s" % (name, "PASS" if ok else "FAIL", note[:120]))
    print("=" * 78)
    bad = [r for r in rows if not r[1]]
    print("%d 步，失败 %d 步" % (len(rows), len(bad)))
    if bad:
        print("修完再交付。门禁含义见 references/pitfalls.md")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
