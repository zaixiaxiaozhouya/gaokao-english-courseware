# 数据字段怎么写（schema v1.3）

> 真源是 `04_workspace/schema-v1/schema.json`；本文是给人看的说明。
> 结构由 `scripts/schema_check.py` 校验（未知字段直接报错），业务规则由 `scripts/validate.py` 校验。

## 顶层

| 字段 | 必填 | 说明 |
|---|---|---|
| `schemaVersion` | ✅ | 写 `"1.3"` |
| `meta` | ✅ | 见下 |
| `passage` | ✅ | 原文、译文、词表、深度解读 |
| `questions` | ✅ | 至少 1 题 |
| `glossary` | | 生词表（学生版默认显示、画蓝色实线）。建议每篇 5–8 个核心词；留空时生词表为空、冒烟会自动跳过相关断言 |
| `seven` | 七选五必填 | A–G 七个选项 |
| `review` | | 题后回顾块 `[{title, lines[]}]` |
| `_provenance` | | 生成来源记录（过渡期保留） |

顶层不允许出现别的键。

## meta

| 字段 | 必填 | 取值/说明 |
|---|---|---|
| `docId` | ✅ | 小写 kebab：`reading-wildcamp`。持久化键 `enstudy:<docId>:progress` |
| `type` | ✅ | `reading` / `seven` / `cloze` / `grammar`（+ 预留 listening / correction / writing-*） |
| `title` `subtitle` | ✅ / | 页面标题与副标题 |
| `generatedAt` | ✅ | `2026-10-17T15:00:00+08:00` |
| `source` | | 素材出处；**答案靠 AI 推定时必须写"待核对"** |
| `paper` | | `新课标I卷` / `新课标II卷` / `全国甲卷` / `全国乙卷` / `其他` / `待确认`。写具体卷型后 `validate` 才会卡题号区间与分值 |
| `section` `version` `mode` | | `mode` 只有 `student` / `teacher` |
| `partial` | | `true` = 整卷里只做一节（如阅读 A 篇 21–23）：只校验题号"落在区间内" |

## passage

| 字段 | 说明 |
|---|---|
| `blocks[]` | 原文块。`{"type":"p","text":…}` 文本块；`{"type":"gap","no":21,"cue":""}` 空位；**每个新段首块加 `"br":true`**。**只有这两种 type**（早期数据里的 `w` 块已废弃） |
| `translation[]` | 逐段中文；**条数 = 段落数 = 1 + br 数（首块不算）** |
| `sentencePairs[]` | `{id:"s1", en, zh}`。原文有空位的题型（语法/完形/七选五）`en` **必须保留 `______`**，处数=题数；阅读理解原文没空位，写正常句子 |
| `wordIndex{}` | 键=**原文出现的词面**，值 `{ipa, pos, cn, eg?, base?}`。虚词不用写（模板有 124 条通用虚词兜底）。键不许只差大小写 |
| `structure[]` `culture[]` | 文章结构 / 文化背景（分析模式显示） |
| `hardSentences[]` | `{en, zh?, note?}` 长难句 |
| `genre` `topic` `wordCount` | 可选元信息 |
| `paragraphs[]` | 逐段元信息 `{id, label?, role?, summary?}`（**不是段数**） |

## questions[]

| 字段 | 说明 |
|---|---|
| `no` `score` | 题号、分值（阅读 2.5、七选五 2.5、完形 1、语法 1.5） |
| `stem` | 题干。多空同句时本题只留自己的一个空，其余写 `〔52〕`（模板渲染成「（第52题）」） |
| `answer` | 选择题=选项 key；填空=答案本身（多解用 `/`）；七选五=单个大写字母 |
| `analysis` | 解析（必填）：定位 + 为什么对 + 干扰项为什么错 |
| `hints[]` | **必须 4 级**，`type` 依次 `point` → `evidence` → `eliminate` → `answer` |
| `options[]` | `{key, text, ipa?, pos?, cn?, distractorType?, why?}`；**错误选项必须写 `distractorType`** |
| `kind` `role` `points` `difficulty` `evidence` `tip` `blankIndex` | 可选；`blankIndex` 用在多空同句 |

`distractorType` 取值：`无中生有` `张冠李戴` `偷换概念` `以偏概全` `因果倒置` `时序错误` `程度失当` `正话反说` `语义不符` `逻辑相反` `词汇搭配不当`。

## seven（只有七选五）

```jsonc
"seven": { "options": [
  { "key":"A", "text":"…", "cn":"中文大意", "role":"正确项", "inference":"为什么能放某空" }
  // 正好 A–G 七条
]}
```

七选五的 `questions[]` **不要再放 `options`**。

## glossary[]

`{key, word, ipa, pos, cn}`：学生自己的"必背词"，会画蓝色实线并自动朗读按钮。

## 三种 overlay（不进主数据，由 apply_overlay 合并）

| 文件 | 用途 |
|---|---|
| `<docId>.words.json` | 大批词索引（`{"wordIndex":{…}}`），与主数据取并集 |
| `<docId>.options.json` | 完形/阅读选项的音标·词性·原型（按选项文本小写匹配） |
| `<docId>.analysis.json` | 逐句译文 + 词表 |
| `<docId>.fill.json` | **补词表**，最后合并、优先级最高（补覆盖率用） |

合并顺序固定，跑 `apply_overlay.py --all` 后必须再跑一次 `--check` 确认 `ok`（幂等）。
