# 流水线细节与命令速查

## 0. 环境

```powershell
$py   = "<提供 python 的可执行文件>"
$node = "<提供 node 的可执行文件>"
$env:NODE_PATH = "<提供 jsdom 的 node_modules 目录>"   # 冒烟/探针必须先设
$env:ENSTUDY_ROOT = "<工作区根目录>"                    # 脚本不在工作区里跑时用
```

先确认脚本认的是哪个工作区：`& $py scripts/paths.py`。

## 1. 抽取

- **老师课件 HTML**：DOM 里通常是"外壳 + N 组 `<section class="view">`"（题目讲解 / 文章结构 / 文化背景 / 长难句 / 词汇表）。逐组抽，别丢结构/文化/长难句三块。
- **试卷照片 / PDF**：OCR 后必须逐句核对拼写与标点（尤其引号、连字符、专有名词）。
- **答案**：优先用原件/官方答案。只能靠语境推定就在 `meta.source` 写明"待核对"，并在交付说明里标出来。

## 2. 写数据

```powershell
& $py scripts/validate.py 04_workspace/schema-v1/examples/<docId>.json   # 边写边验，直到 PASS
```

一题一题过，先保证 `answer` / `analysis` / `hints`（4 级）齐；有选项的题补 `distractorType` + `why`。

## 3. 补词表（决定"点了有没有中文"）

```powershell
& $py scripts/coverage.py 04_workspace/schema-v1/examples/<docId>.json --missing
```

按输出把缺的词写进 `overlays/<docId>.fill.json`：

```jsonc
{ "docId": "<docId>", "wordIndex": {
  "camp":         {"ipa":"/kæmp/","pos":"n.","cn":"营地；营","eg":"the Wild Nature Camp"},
  "participants": {"ipa":"/pɑːˈtɪsɪpənts/","pos":"n.","cn":"参与者（复数）","base":"participant"}
}}
```

要点：键=原文词面；`ipa`/`pos`/`cn` 都不能空；变形词写 `base`；虚词不用写。

## 4. 合并

```powershell
& $py scripts/apply_overlay.py --all
& $py scripts/apply_overlay.py --all --check      # 必须输出 ok
```

## 5. 门禁（顺序照跑）

```powershell
& $py   scripts/schema_check.py --all        # 结构（未知字段/类型/枚举）
& $py   scripts/validate.py --all            # 业务规则
& $py   scripts/coverage.py --all            # 覆盖率（<95% 会提示缺词）
& $py   scripts/audit_samples.py             # 一致性 + share 同步
& $py   scripts/build.py --all --share       # 构建产物 + 交付副本
& $node scripts/smoke_test.cjs 04_workspace/build/<docId>.html
& $node scripts/edge_probe.cjs 04_workspace/build/<docId>.html   # 交付前建议跑（真实 Edge）
```

`build.py --all --share` 连跑两次，`built … sha=` 必须一致（幂等）。

## 6. 交付

`04_workspace/share/` 里的 HTML 就是发给学生的成品。交付名规则在 `scripts/share_map.py`：登记过的用固定名（适合成套卷子统一命名），没登记的按 `meta.title` 自动命名（Windows 不允许的字符会被去掉）。`build.py` 与 `audit_samples.py` 共用 `share_name()`，所以不会出现"build 换了名字、audit 还在查旧名"。

## 扩展一个新题型（听力 / 短文改错 / 写作）

1. 在 `schema.json` 的 `meta.type` 枚举里加值，并为该题型加必要的结构（如 `listening.items[]`、`writing.rubric[]`）。
2. `validate.py` 的 `RANGES` 里补题号区间与分值（见 `references/paper-spec.md`）。
3. `templates/tpl-student.html` 里按 `DATA.meta.type` 加渲染分支（参考七选五的 `isSeven()` + 选项池）。
4. `smoke_test.cjs` 补该题型的断言分支。
5. 写一份样例数据 → 跑门禁 → 交付。

## 目录与命名

- 数据：`examples/<docId>.json`，`docId` 小写 kebab（`reading-wildcamp`、`seven-futureletter`、`cloze-2023-n1`、`grammar-matcha`）。
- overlay：`overlays/<docId>.{words,options,analysis,fill}.json`。
- 产物：`build/<docId>.html`（自动）；交付副本名在 `share_map.py`。
