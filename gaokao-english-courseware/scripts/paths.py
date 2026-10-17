#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工作区根目录解析（skill 里所有脚本都通过它找 01_source / 04_workspace）。

顺序：
    1) 环境变量 ENSTUDY_ROOT
    2) 从当前工作目录向上找"含 04_workspace/schema-v1 的目录"
    3) 从本脚本所在目录向上找（同一规则）
    4) 都没有 → 当前工作目录
"""
import os


def _has_workspace(path):
    return os.path.isdir(os.path.join(path, "04_workspace", "schema-v1"))


def _walk_up(start):
    cur = os.path.abspath(start)
    while True:
        if _has_workspace(cur):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def workspace():
    env = os.environ.get("ENSTUDY_ROOT")
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    found = _walk_up(os.getcwd()) or _walk_up(os.path.dirname(os.path.abspath(__file__)))
    return found or os.getcwd()


if __name__ == "__main__":
    print(workspace())
