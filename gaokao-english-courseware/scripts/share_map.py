#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建产物 → share 交付副本 的命名映射（build.py 与 audit_samples.py 共用，唯一真源）。

命名规则：
  1) SHARE_MAP 里登记过的，用它（固定交付名，适合成套卷子的一致性命名）；
  2) 没登记的，按 `meta.title` 自动命名，文件名里 Windows 不允许的字符会被去掉；
  3) 标题也空就用 docId。

为什么不再要求"每加一篇都改这个文件"：R22 那次手工 copy 忘了同步，导致发出去的
样例3/样例4 还是旧版（build 与 share 的 sha256 不一致）；现在映射是函数算出来的，
build 和 audit 走同一条规则，漏登记也不会静默不同步。
"""
import os
import re

SHARE_MAP = {
    "grammar-smartcity.html": "样例1-语法填空-智慧城市.html",
    "cloze-2023-n1.html": "样例2-完形填空-2023新高考I卷.html",
    "cloze-hideseek.html": "样例3-完形填空-藏猫猫（21-35）.html",
    "grammar-matcha.html": "样例4-语法填空-抹茶Matcha（36-45）.html",
    "reading-wildcamp.html": "样例5-阅读理解-Wild Nature Camp（21-23）.html",
    "seven-futureletter.html": "样例6-七选五-给未来的自己写一封信（36-40）.html",
    "reading-wangshuzhen.html": "样例7-阅读理解-Wang Shuzhen（24-27）.html",
}

# Windows / macOS 都不接受的文件名字符
_BAD_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]')
# 中文标题里常用的断句符：换成空格，别让文件名里出现"。"（读起来像断句错误）
_SEPARATORS = re.compile(r"[。；，、：！？]")


def _clean(name):
    s = _SEPARATORS.sub(" ", name or "")
    s = _BAD_CHARS.sub("", s.strip())
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s[:72]


def share_name(built_name, doc=None):
    """交付副本文件名。built_name 是 build/ 下的文件名（docId.html）。"""
    if built_name in SHARE_MAP:
        return SHARE_MAP[built_name]
    meta = (doc or {}).get("meta") or {}
    stem = _clean(meta.get("title")) or _clean(os.path.splitext(built_name)[0]) or "doc"
    return stem + ".html"
