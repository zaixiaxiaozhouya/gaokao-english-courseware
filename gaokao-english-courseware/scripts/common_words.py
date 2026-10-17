#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用虚词表（唯一真源）。

为什么要有：学生"点任何一个词"都希望有反应。虚词（the/and/of/to…）也进查词索引，
但**不参与正文划线**（否则整篇都是虚线，没法看）。
模板里的 `COMMON_LOOK` 是这份清单的副本（模板必须自包含、单文件零依赖），
`audit_samples.py` 会检查两边是否一致。

改动流程：改这里 → 同步改 templates/tpl-student.html 的 COMMON_LOOK → 跑 audit。
"""

# key: (词性, 中文)
COMMON_LOOK = {
    "a": ("art.", "一个（泛指）"), "an": ("art.", "一个（元音前）"), "the": ("art.", "这／那（特指）"),
    "and": ("conj.", "和；而且"), "or": ("conj.", "或者"), "but": ("conj.", "但是"), "so": ("conj.", "所以；如此"),
    "if": ("conj.", "如果"), "because": ("conj.", "因为"), "than": ("conj.", "比"), "then": ("adv.", "然后；那时"),
    "as": ("conj.", "当……时；作为；像"), "while": ("conj.", "当……时；然而"), "although": ("conj.", "虽然"),
    "of": ("prep.", "……的"), "to": ("prep.", "到；向（不定式符号）"), "in": ("prep.", "在……里"), "on": ("prep.", "在……上"),
    "at": ("prep.", "在（某点／某时）"), "for": ("prep.", "为了；给"), "from": ("prep.", "从"), "by": ("prep.", "通过；被；在……旁"),
    "with": ("prep.", "和；带有"), "without": ("prep.", "没有"), "about": ("prep.", "关于；大约"), "into": ("prep.", "进入"),
    "over": ("prep.", "在……之上；超过"), "under": ("prep.", "在……之下"), "during": ("prep.", "在……期间"),
    "after": ("prep.", "在……之后"), "before": ("prep.", "在……之前"), "through": ("prep.", "穿过；通过"),
    "across": ("prep.", "穿过；横过"), "like": ("prep.", "像"), "according": ("adv.", "根据（according to）"),
    "is": ("v.", "是（be 的第三人称单数）"), "are": ("v.", "是（be 的复数）"), "am": ("v.", "是（be 的第一人称）"),
    "was": ("v.", "是（be 的过去式单数）"), "were": ("v.", "是（be 的过去式复数）"), "be": ("v.", "是；成为"),
    "been": ("v.", "be 的过去分词"), "being": ("v.", "be 的现在分词"), "do": ("v.", "做；助动词"),
    "does": ("v.", "做（第三人称单数）"), "did": ("v.", "做（过去式）"), "have": ("v.", "有；助动词"),
    "has": ("v.", "有（第三人称单数）"), "had": ("v.", "有（过去式）"), "can": ("modal", "能够"),
    "could": ("modal", "能够（过去式／委婉）"), "may": ("modal", "可以；可能"), "might": ("modal", "可能"),
    "must": ("modal", "必须"), "shall": ("modal", "将"), "should": ("modal", "应该"), "will": ("modal", "将会"),
    "would": ("modal", "会（过去将来／委婉）"), "it": ("pron.", "它"), "its": ("pron.", "它的"),
    "they": ("pron.", "他们"), "them": ("pron.", "他们（宾格）"), "their": ("pron.", "他们的"), "theirs": ("pron.", "他们的（名词性）"),
    "he": ("pron.", "他"), "him": ("pron.", "他（宾格）"), "his": ("pron.", "他的"), "she": ("pron.", "她"),
    "her": ("pron.", "她／她的"), "we": ("pron.", "我们"), "us": ("pron.", "我们（宾格）"), "our": ("pron.", "我们的"),
    "you": ("pron.", "你／你们"), "your": ("pron.", "你的／你们的"), "i": ("pron.", "我"), "me": ("pron.", "我（宾格）"),
    "my": ("pron.", "我的"), "this": ("pron.", "这个"), "that": ("pron.", "那个"), "these": ("pron.", "这些"), "those": ("pron.", "那些"),
    "there": ("adv.", "那里；（there be）有"), "here": ("adv.", "这里"), "not": ("adv.", "不"), "no": ("adv.", "不；没有"),
    "any": ("det.", "任何"), "some": ("det.", "一些"), "all": ("det.", "全部"), "each": ("det.", "每个"), "every": ("det.", "每一个"),
    "more": ("adv.", "更多"), "most": ("adv.", "最；大多数"), "very": ("adv.", "非常"), "too": ("adv.", "太；也"),
    "just": ("adv.", "只是；刚"), "only": ("adv.", "只有"), "also": ("adv.", "也"), "such": ("det.", "这样的"),
    "who": ("pron.", "谁（引导定语从句）"), "whom": ("pron.", "谁（宾格）"), "whose": ("pron.", "谁的"),
    "what": ("pron.", "什么"), "which": ("pron.", "哪一个（引导定语从句）"), "when": ("conj.", "当……时"),
    "where": ("adv.", "在哪里"), "why": ("adv.", "为什么"), "how": ("adv.", "如何"), "once": ("adv.", "一旦；曾经"),
    "one": ("num.", "一；一个"), "other": ("det.", "别的"), "others": ("pron.", "其他人"), "another": ("det.", "另一个"),
    "own": ("adj.", "自己的"), "same": ("adj.", "相同的"), "both": ("det.", "两者都"), "either": ("det.", "任一"),
    "neither": ("det.", "两者都不"), "out": ("adv.", "向外"), "up": ("adv.", "向上"), "down": ("adv.", "向下"),
    "off": ("adv.", "离开；关掉"), "back": ("adv.", "回；向后"), "still": ("adv.", "仍然"), "even": ("adv.", "甚至"),
}
