---
name: gaokao-english-courseware
description: Use when turning 高考英语 exam material into a student self-study single-file HTML courseware — 阅读理解、七选五、完形填空、语法填空，含作答判分、四级提示、全量划词查词、中文对照、学习档案、打印样式。也用于初始化新工作区、生成 schema 合法的数据骨架、给已有课件补词表/补译文/修排版，或一条命令跑全部门禁（schema/validate/coverage/audit/build/smoke）并交付。
license: MIT
metadata:
  version: "1.1.0"
  data-model: schema-v1.3
  language: zh-CN
---

# 高考英语自学课件流水线

把一份卷子（试卷照片 / PDF / 原件 HTML / docx）变成**单文件、零依赖、双击可用**的学生课件。

**两条铁律**

1. **数据是唯一真源**：`04_workspace/schema-v1/examples/<docId>.json`；HTML 只是可随时重生成的产物。
2. **学习档案存浏览器**（localStorage），重新生成课件不覆盖学生记录。

## 什么时候用

- 新做一篇课件：阅读理解 / 七选五 / 完形填空 / 语法填空。
- 给已有课件补东西：词表覆盖率不够、分段粘成一段、排版糟、答案要复核。
- 换机器 / 换卷子目录，要搭同样的工作区。
- 交付前跑门禁、打快照。

**不适用**：听力、短文改错、应用文、读后续写（见文末能力边界）。

## 输入 → 输出

| 输入 | 输出 |
|---|---|
| 试卷照片 / PDF / docx / 原件 HTML | `04_workspace/build/<docId>.html`（单文件，`file://` 双击可用） |
| 已抽好的内容 JSON | `04_workspace/share/<友好名>.html`（交付副本，命名在 `scripts/share_map.py`） |
| 一句话需求（"把这篇阅读做成课件"） | 上二者 + 门禁报告（`build/validate-report.md`、`build/audit-report.md`） |

课件里学生能做的：作答与即时判分、四级提示阶梯、全量划词查词（音标/词性/中文/例句）、逐句中英对照、长难句拆解、文化背景、交卷报告、错题本、生词本、掌握度统计、打印。

## 工作区

```
01_source/                      素材（只读，永不修改）
04_workspace/schema-v1/
  schema.json                   数据模型真源（v1.3）
  examples/<docId>.json         内容数据（唯一真源）
  overlays/<docId>.*.json       词索引 / 选项注释 / 逐句译文 / 补词表
04_workspace/build|share/       产物与交付副本
```

- 空目录起手：`<python> scripts/init_workspace.py <目录>`（建目录 + 从 `assets/schema-v1.3.json` 装 schema）。
- **工作区解析**：`scripts/paths.py` 按 `ENSTUDY_ROOT` → 从 cwd 向上找含 `04_workspace/schema-v1` 的目录 → cwd。不确定就先跑它。
- 工作区没有 `schema.json` 或模板时，脚本会回退到本 skill 自带的 `assets/` 与 `templates/`，**新工作区不用先复制一堆东西**。

## 六步

0. **（新工作区才做）** `scripts/init_workspace.py <目录>`
1. **抽取**（人和 AI 一起读原件）：原文分段、题干、选项、答案、解析、结构、文化背景、长难句、词汇。答案必须有来源；AI 推定的要在 `meta.source` 写"待核对"。
2. **起骨架** `scripts/new_doc.py --doc-id … --type … --nos 24-27 --title …`，然后往里填内容。字段看 `references/schema.md`，形状抄 `references/example-reading.json` / `example-seven.json`。
3. **补词表** `scripts/coverage.py <docId>.json --missing` 看缺哪些词 → 写 `overlays/<docId>.fill.json`（键 = 原文词面）。
4. **合并** `scripts/apply_overlay.py --all`（幂等；`--check` 只查不写）。
5. **门禁**一条命令全跑：
   ```
   <python> scripts/verify_all.py          # schema → validate → coverage → audit → build --share → smoke
   <python> scripts/verify_all.py --fast   # 没装 node/jsdom 时跳过冒烟
   <python> scripts/verify_all.py --edge   # 追加真实 Edge 探针（慢）
   ```
6. **交付**：`04_workspace/share/` 里的 HTML 直接给学生；要回滚就整目录快照到 `99_backups/`。

环境变量：`ENSTUDY_ROOT`（工作区根）、`NODE_PATH`（指向有 jsdom 的 `node_modules`）、`ENSTUDY_NODE`（指定 node 可执行文件）。

## 写内容的四个规范文件（写完自查）

| 要写什么 | 看哪 |
|---|---|
| 提示阶梯（4 级） | `references/hints.md`：每级该给到哪、句模板、6 种错法 |
| 干扰项类型 | `references/distractors.md`：11 个枚举、判定问句、`why` 的唯一标准 |
| 考点标签 | `references/tags.md`：7 个一级能力、`能力/考点` 写法、旧标签迁移 |
| 卷型与题号区间 | `references/paper-spec.md` |

一题一题过，先保证 `answer` / `analysis` / 四级 `hints` 齐；有选项的题再补 `distractorType` + `why`。

## 三条最容易踩的坑

- **忘打 `br` 分段标记**：碎块数据会整篇粘成一段；`audit_samples.py` 报"段落数 ≠ 对照段数"。
- **改了数据没重跑 `build --share`**：发出去还是旧版；`audit` 判 ERROR。
- **冒烟缺 jsdom**：设 `NODE_PATH`，否则 `Cannot find module 'jsdom'`。

其余 12 条见 `references/pitfalls.md`。

## 能力边界（别对外承诺没有的东西）

| 有 | 没有（别声称） |
|---|---|
| 四类题型：reading / seven / cloze / grammar | 听力、短文改错、应用文、读后续写 |
| 学生版（`meta.mode=student`） | 教师版批量揭示 / 投屏（`mode=teacher` 只是占位，无专门 UI） |
| 七选五"点空 + 点字母" | 七选五**拖拽** |
| 每篇独立 HTML、交卷报告、错题本、生词本、掌握度 | **整卷合集视图**（同一套卷的多篇不合并统计） |
| 打印样式（含 `@media print`） | 教师版"答案解析版"单独排版 |

## 自检

```
<python> scripts/selftest.py      # 6 项：必需文件 / frontmatter / 脚本语法 / 示例合 schema / 模板占位符 / 真构建
```

## 参考

| 文件 | 内容 |
|---|---|
| `references/schema.md` | 每个字段怎么写、什么时候用、常见错法 |
| `references/pipeline.md` | 六步细节、命令速查、扩展新题型（听力/写作）的方法 |
| `references/hints.md` | 4 级提示的写法与反例 |
| `references/distractors.md` | 干扰项 11 类判定与 `why` 写法 |
| `references/tags.md` | 考点标签库（掌握度聚合口径） |
| `references/pitfalls.md` | 12 个真踩过的坑 |
| `references/paper-spec.md` | 四类卷题号/分值/时长 + 校验区间 |
| `references/example-reading.json` / `example-seven.json` | 标准数据形状（截短版，直接抄） |
| `templates/tpl-student.html` | 学生版模板（构建时注入数据） |
| `assets/schema-v1.3.json` | schema 副本（新工作区由 `init_workspace.py` 装进去） |
