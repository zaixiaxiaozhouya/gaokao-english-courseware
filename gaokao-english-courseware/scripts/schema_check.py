#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""零依赖的 JSON Schema 子集校验器（本项目专用）。

为什么不用 jsonschema 库：项目硬约束是"生成物零外部依赖、脚本只用标准库"。
这里只实现本项目 schema 用到的那一小撮关键字：

    type / required / properties / additionalProperties / items
    enum / const / pattern / minLength
    minimum / maximum / exclusiveMinimum
    minItems / maxItems / oneOf / $ref(#/$defs/...)

用法：
    python scripts/schema_check.py <doc.json> [...]
    python scripts/schema_check.py --all
    python scripts/schema_check.py --all --quiet      # 只打印失败项

退出码：0 全部通过；1 有结构错误；2 用法/schema 自身读取失败。
"""
import argparse
import glob
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402
ROOT = paths.workspace()
SCHEMA = os.path.join(ROOT, "04_workspace", "schema-v1", "schema.json")
if not os.path.isfile(SCHEMA):
    for _cand in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "schema-v1.3.json"),
                  os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "03_skill", "assets", "schema-v1.3.json")):
        if os.path.isfile(_cand):
            SCHEMA = os.path.abspath(_cand)
            break
EX_DIR = os.path.join(ROOT, "04_workspace", "schema-v1", "examples")

TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


class Checker(object):
    def __init__(self, schema):
        self.root = schema

    def resolve(self, node):
        """处理 $ref: #/$defs/X（只支持本地 defs）。"""
        seen = 0
        while isinstance(node, dict) and "$ref" in node:
            ref = node["$ref"]
            if not ref.startswith("#/"):
                raise ValueError("不支持的 $ref: %s" % ref)
            cur = self.root
            for part in ref[2:].split("/"):
                cur = cur[part]
            node = cur
            seen += 1
            if seen > 20:
                raise ValueError("$ref 循环")
        return node

    def check(self, value, schema, path, errs):
        schema = self.resolve(schema)
        if not isinstance(schema, dict):
            return

        if "oneOf" in schema:
            ok = 0
            first = None
            for sub in schema["oneOf"]:
                sub_errs = []
                self.check(value, sub, path, sub_errs)
                if not sub_errs:
                    ok += 1
                elif first is None:
                    first = sub_errs
            if ok == 0:
                errs.extend(first or ["%s: 不匹配任何 oneOf 分支" % path])
            return

        if "const" in schema and value != schema["const"]:
            errs.append("%s: 应为 %r，实际 %r" % (path, schema["const"], value))
        if "enum" in schema and value not in schema["enum"]:
            errs.append("%s: 值 %r 不在枚举 %s 内" % (path, value, schema["enum"]))

        t = schema.get("type")
        if t:
            want = TYPES.get(t)
            if want and not isinstance(value, want):
                # bool 是 int 的子类，单独挡掉
                if not (t in ("number", "integer") and isinstance(value, bool)):
                    errs.append("%s: 类型应为 %s，实际 %s" % (path, t, type(value).__name__))
                    return

        if isinstance(value, str):
            if "minLength" in schema and len(value) < schema["minLength"]:
                errs.append("%s: 长度 < %d" % (path, schema["minLength"]))
            if "pattern" in schema and not re.search(schema["pattern"], value):
                errs.append("%s: 不匹配 pattern %s（值=%r）" % (path, schema["pattern"], value[:40]))

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                errs.append("%s: 应 >= %s，实际 %s" % (path, schema["minimum"], value))
            if "maximum" in schema and value > schema["maximum"]:
                errs.append("%s: 应 <= %s，实际 %s" % (path, schema["maximum"], value))
            if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
                errs.append("%s: 应 > %s，实际 %s" % (path, schema["exclusiveMinimum"], value))

        if isinstance(value, list):
            if "minItems" in schema and len(value) < schema["minItems"]:
                errs.append("%s: 元素数 %d < %d" % (path, len(value), schema["minItems"]))
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                errs.append("%s: 元素数 %d > %d" % (path, len(value), schema["maxItems"]))
            item_schema = schema.get("items")
            if item_schema:
                for i, v in enumerate(value):
                    self.check(v, item_schema, "%s[%d]" % (path, i), errs)

        if isinstance(value, dict):
            props = schema.get("properties") or {}
            for k in schema.get("required") or []:
                if k not in value:
                    errs.append("%s.%s: 缺必填字段" % (path, k))
            ap = schema.get("additionalProperties", True)
            for k, v in value.items():
                if k in props:
                    self.check(v, props[k], "%s.%s" % (path, k), errs)
                elif ap is False:
                    errs.append("%s.%s: schema 未声明该字段（additionalProperties=false）" % (path, k))
                elif isinstance(ap, dict):
                    self.check(v, ap, "%s.%s" % (path, k), errs)


def check_file(path, checker, quiet=False):
    try:
        doc = json.loads(io.open(path, encoding="utf-8").read())
    except Exception as e:
        print("%-30s LOAD-FAIL %s" % (os.path.basename(path), e))
        return 1
    errs = []
    checker.check(doc, checker.root, "$", errs)
    name = os.path.basename(path)
    if errs:
        print("%-30s FAIL errors=%d" % (name, len(errs)))
        for e in errs[:25]:
            print("    - " + e)
        if len(errs) > 25:
            print("    … 还有 %d 条" % (len(errs) - 25))
        return 1
    if not quiet:
        print("%-30s PASS" % name)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--schema", default=SCHEMA)
    args = ap.parse_args()
    try:
        schema = json.loads(io.open(args.schema, encoding="utf-8").read())
    except Exception as e:
        print("schema 读取失败：%s" % e)
        return 2
    checker = Checker(schema)
    targets = args.files or (sorted(glob.glob(os.path.join(EX_DIR, "*.json"))) if args.all else [])
    if not targets:
        print("no input; use --all or pass json paths")
        return 2
    bad = 0
    for p in targets:
        bad += check_file(p, checker, args.quiet)
    print("schema=%s | %d 个文件，失败 %d 个" % (os.path.basename(args.schema), len(targets), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
