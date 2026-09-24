#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""decl_validate.py —— 感知声明校验器（T-02，perception/0.2 / perception-fragment/0.2）。
【项目沉淀】通用工具
适用素体：无关
相关素材：声明 yaml/fragment
工具链　：Python 3 + PyYAML（离线）
可复用性：★★ 按 schema 复用
用途　　：感知声明校验器（perception/0.2）：声明 YAML → decl.json，并校验字段与引用。


用法：
    python3 decl_validate.py --in <声明.yaml> [--out <decl.json>] [--report json]
    python3 decl_validate.py --in <片段.decl.yaml>                  # 片段（按 schema 分派）
    python3 decl_validate.py --selftest [--mini-yaml]

依赖：PyYAML 可用则用（去掉 timestamp 隐式解析，保留 YAML 1.1 的 on/off/yes/no 布尔与裸数字）；
      否则退到本文件自带的 `_MiniYaml`（只覆盖声明用到的子集，见 README）。
      jsonschema 可用则用；不可用时 schema 层报 skipped 并只跑语义层（见 README「声明校验」）。

规格出处：schema/CONDITION_GRAMMAR.md（§1 EBNF、§2 语义、§3 姿势 id、§4 往返、§5 SEM-01…24、
§6 展开、§7 字段处置、§8 反例头注释与报错路径规范化）、schema/CHANGELOG.md、
schema/perception-0.2.schema.json。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA_DIR = HERE / "schema"
SCHEMA_PATH = SCHEMA_DIR / "perception-0.2.schema.json"
# 工作区根：.../开发工具/通用工具/审查/perception -> 上溯四级
WORKSPACE = HERE.parents[3]

SCHEMA_ID = "perception/0.2"
FRAGMENT_ID = "perception-fragment/0.2"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

# ---------------------------------------------------------------------------
# YAML 载入
# ---------------------------------------------------------------------------

try:  # pragma: no cover - 环境相关
    import yaml as _pyyaml
except Exception:  # pragma: no cover
    _pyyaml = None

_FORCE_MINI = False     # --mini-yaml 时强制走备用解析（用于自验）


class _MiniYamlError(Exception):
    pass


if _pyyaml is not None:

    class _DeclLoader(_pyyaml.SafeLoader):
        """SafeLoader：保留 YAML 1.1 布尔/裸数字，去掉 timestamp 隐式解析。"""

    # PyYAML 的隐式解析器表按首字符分组；逐组过滤掉 timestamp。
    for _ch, _res in list(_DeclLoader.yaml_implicit_resolvers.items()):
        _DeclLoader.yaml_implicit_resolvers[_ch] = [
            (tag, rx) for (tag, rx) in _res if tag != "tag:yaml.org,2002:timestamp"
        ]
    del _ch, _res

    def load_yaml_text(text, source="<string>"):
        """YAML 文本 -> Python 对象；时间戳按字符串载入。"""
        if _FORCE_MINI:
            return _MiniYaml().parse(text)
        try:
            return _pyyaml.load(text, Loader=_DeclLoader)
        except _pyyaml.YAMLError as exc:
            raise _MiniYamlError("YAML 解析失败：%s" % exc) from exc

else:  # pragma: no cover - 仅在无 PyYAML 时走这里

    def load_yaml_text(text, source="<string>"):
        return _MiniYaml().parse(text)


class _MiniYaml:  # pragma: no cover - 备用路径（无 PyYAML 时）
    """最小 YAML 子集解析：注释、块映射/序列、行内 flow、引号、YAML 1.1 标量。

    取舍：只覆盖声明/片段用到的写法（见 examples/）。不支持锚点、标签、多文档、
    多行标量（| / >）、复杂键。无 PyYAML 时应装上 PyYAML；这份备用解析在
    `--selftest` 里被强制走一遍以确保正反例都能读。
    """

    _BOOL = {"yes": True, "no": False, "true": True, "false": False,
             "on": True, "off": False}
    _NULL = {"", "~", "null", "Null", "NULL"}

    def parse(self, text):
        # 先做注释剥离；再把跨行的 flow（{[ 未闭合）合并成一行
        merged = []
        buf = None
        for raw in text.splitlines():
            line = self._strip_comment(raw)
            if buf is None:
                if line.strip() == "":
                    continue
                buf = line
            else:
                if line.strip() == "":
                    continue
                buf = buf.rstrip() + " " + line.strip()
            if self._balance(buf) <= 0:
                merged.append(buf)
                buf = None
        if buf is not None:
            merged.append(buf)
        self.lines = []
        for line in merged:
            if line.strip() == "":
                continue
            self.lines.append((len(line) - len(line.lstrip(" ")), line.strip()))
        self.i = 0
        return self._block(0)

    @staticmethod
    def _balance(s):
        depth = 0
        q = None
        for ch in s:
            if q:
                if ch == q:
                    q = None
                continue
            if ch in "\"'":
                q = ch
            elif ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
        return depth

    @staticmethod
    def _strip_comment(line):
        out, in_s, in_d, esc = [], False, False, False
        for ch in line:
            if in_d and esc:
                esc = False
                out.append(ch)
                continue
            if in_d and ch == "\\":
                esc = True
                out.append(ch)
                continue
            if ch == "'" and not in_d:
                in_s = not in_s
            elif ch == '"' and not in_s:
                in_d = not in_d
            elif ch == "#" and not in_s and not in_d:
                break
            out.append(ch)
        return "".join(out).rstrip()

    def _block(self, indent):
        if self.i >= len(self.lines):
            return None
        ind, body = self.lines[self.i]
        if ind < indent:
            return None
        if body == "-" or body.startswith("- "):
            return self._seq(ind)
        if body[0] in "{[\"'":
            self.i += 1
            return self._scalar(body)
        if ":" not in body:
            self.i += 1
            return self._scalar(body)
        return self._map(ind)

    def _seq(self, indent):
        items = []
        while self.i < len(self.lines):
            ind, body = self.lines[self.i]
            if ind < indent or not (body == "-" or body.startswith("- ")):
                break
            rest = body[1:].strip()
            self.i += 1
            if rest == "":
                items.append(self._block(indent + 2))
            elif ":" in rest and not rest.startswith(("{", "[", '"', "'")):
                # 行内 "- key: value"，把这一行当成缩进+2 的映射首行
                self.lines.insert(self.i, (indent + 2, rest))
                items.append(self._map(indent + 2))
            else:
                items.append(self._scalar(rest))
        return items

    def _map(self, indent):
        out = {}
        while self.i < len(self.lines):
            ind, body = self.lines[self.i]
            if ind < indent:
                break
            if ind > indent:
                raise _MiniYamlError("缩进异常：%r" % body)
            if body.startswith("- "):
                break
            key, _, rest = body.partition(":")
            key = self._scalar(key.strip())
            if rest.strip():
                out[key] = self._scalar(rest.strip())
                self.i += 1
            else:
                self.i += 1
                out[key] = self._block(indent + 2)
        return out

    def _scalar(self, s):
        if s == "":
            return None
        if s[0] in "{[":
            return self._flow(s)
        if s[0] in "\"'":
            if len(s) >= 2 and s[-1] == s[0]:
                body = s[1:-1]
                if s[0] == '"':
                    body = body.replace('\\"', '"').replace("\\\\", "\\")
                return body
            return s[1:]
        low = s.lower()
        if low in self._BOOL:
            return self._BOOL[low]
        if s in self._NULL:
            return None
        if re.fullmatch(r"-?[0-9]+", s):
            return int(s)
        if re.fullmatch(r"-?[0-9]+\.[0-9]+", s):
            return float(s)
        return s

    def _flow(self, s):
        # 极简 flow：[a, b] / {k: v, ...}，嵌套由递归处理；逗号切分尊重引号与括号
        s = s.strip()
        if s[0] == "[":
            inner = s[1:-1].strip()
            return [] if not inner else [self._scalar(x) for x in self._split_top(inner)]
        inner = s[1:-1].strip()
        d = {}
        if not inner:
            return d
        for part in self._split_top(inner):
            k, _, v = part.partition(":")
            d[self._scalar(k.strip())] = self._scalar(v.strip())
        return d

    @staticmethod
    def _split_top(s):
        parts, buf, depth, q, esc = [], [], 0, None, False
        for ch in s:
            if q:
                buf.append(ch)
                if esc:
                    esc = False
                elif q == '"' and ch == "\\":
                    esc = True
                elif ch == q:
                    q = None
                continue
            if ch in "\"'":
                q = ch
                buf.append(ch)
            elif ch in "[{":
                depth += 1
                buf.append(ch)
            elif ch in "]}":
                depth -= 1
                buf.append(ch)
            elif ch == "," and depth == 0:
                parts.append("".join(buf).strip())
                buf = []
            else:
                buf.append(ch)
        if "".join(buf).strip():
            parts.append("".join(buf).strip())
        return parts


# ---------------------------------------------------------------------------
# JSON Pointer / 报错路径规范化（GRAMMAR §8）
# ---------------------------------------------------------------------------

def json_pointer(segments):
    if not segments:
        return ""
    return "/" + "/".join(
        str(s).replace("~", "~0").replace("/", "~1") for s in segments
    )


def _leaf_errors(err):
    if getattr(err, "context", None):
        for sub in err.context:
            yield from _leaf_errors(sub)
    else:
        yield err


_NAME_RE = re.compile(r"'((?:[^'\\]|\\.)*)'")


def _additional_props(leaf):
    """additionalProperties 报错的多余键名：优先从父 schema 算，退到 message 解析。"""
    inst = leaf.instance
    parent = getattr(leaf, "parent", None)
    pschema = getattr(parent, "schema", None) if parent is not None else None
    if isinstance(inst, dict) and isinstance(pschema, dict):
        allowed = set(pschema.get("properties") or {})
        pats = list((pschema.get("patternProperties") or {}).keys())
        extra = [k for k in inst
                 if k not in allowed and not any(re.search(p, k) for p in pats)]
        if extra:
            return extra
    return _NAME_RE.findall(leaf.message or "")


def normalize_schema_errors(errors):
    """把 jsonschema iter_errors 的结果规范化成一组 JSON Pointer。"""
    paths = set()
    for err in errors:
        for leaf in _leaf_errors(err):
            segs = list(leaf.absolute_path)
            validator = getattr(leaf, "validator", None)
            if validator == "required":
                inst = leaf.instance
                for name in leaf.validator_value:
                    if not isinstance(inst, dict) or name not in inst:
                        paths.add(json_pointer(segs + [name]))
            elif validator == "additionalProperties":
                extras = _additional_props(leaf)
                if extras:
                    for name in extras:
                        paths.add(json_pointer(segs + [name]))
                else:
                    paths.add(json_pointer(segs))
            elif "propertyNames" in list(getattr(leaf, "schema_path", [])):
                key = leaf.instance if isinstance(leaf.instance, str) else None
                paths.add(json_pointer(segs + ([key] if key is not None else [])))
            else:
                paths.add(json_pointer(segs))
    return paths


# ---------------------------------------------------------------------------
# 条件表达式：词法 / 语法 / 求值（GRAMMAR §1、§2）
# ---------------------------------------------------------------------------

class CondError(Exception):
    def __init__(self, msg, pos=0):
        super().__init__(msg)
        self.pos = pos


_TOK_RE = re.compile(
    r"""
      (?P<ws>\s+)
    | (?P<slot>\#[0-9]+)
    | (?P<num>-?[0-9]+(?:\.[0-9]+)?)
    | (?P<str>"[^"\n]*")
    | (?P<op>!=|<=|>=|[()\[\]{},|&!=<>])
    | (?P<word>[^\s()\[\]{},|&!=<>":]+)
    """,
    re.VERBOSE,
)

_PART_REF_RE = re.compile(r"^(?:any\.[A-Za-z0-9_]+|[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*)$")
_IDENT_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_POSE_ID_RE = re.compile(
    r"^[A-Za-z0-9_\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+(?:@[0-9]+)?$"
)
_TAG_RE = re.compile(r"^[A-Za-z0-9_]+$")
_PARAM_RE = re.compile(r"^[A-Za-z0-9_/.$#+\-]+$")
_BARE_LABEL_RE = re.compile(r'^[^\s()\[\]{},|&!=<>":]+$')
_COMPONENTS = ("V1", "V2", "V3", "V4")


def _tokenize(text):
    toks = []
    pos = 0
    n = len(text)
    while pos < n:
        m = _TOK_RE.match(text, pos)
        if not m:
            raise CondError("无法识别的字符 %r" % text[pos], pos)
        kind = m.lastgroup
        val = m.group()
        if kind == "ws":
            pos = m.end()
            continue
        if kind == "str":
            val = val[1:-1]
        if kind == "word" and val.startswith("#"):
            raise CondError("非法的 # 记号", pos)
        toks.append((kind, val, pos))
        pos = m.end()
    toks.append(("eof", "", n))
    return toks


class _CondParser:
    def __init__(self, text):
        self.text = text
        self.toks = _tokenize(text)
        self.i = 0

    # -- 基础工具 ---------------------------------------------------------
    def peek(self):
        return self.toks[self.i]

    def kind(self):
        return self.toks[self.i][0]

    def val(self):
        return self.toks[self.i][1]

    def next(self):
        tok = self.toks[self.i]
        self.i += 1
        return tok

    def accept_op(self, *ops):
        if self.kind() == "op" and self.val() in ops:
            return self.next()[1]
        return None

    def expect_op(self, op):
        got = self.accept_op(op)
        if got is None:
            raise CondError("期望 %r，实际 %r" % (op, self.val()), self.toks[self.i][2])
        return got

    def expect_word(self, word):
        if self.kind() == "word" and self.val() == word:
            return self.next()
        raise CondError("期望 %r，实际 %r" % (word, self.val()), self.toks[self.i][2])

    # -- 语法 -------------------------------------------------------------
    def parse(self):
        node = self.disj()
        if self.kind() != "eof":
            raise CondError("多余的记号 %r" % self.val(), self.toks[self.i][2])
        return node

    def disj(self):
        parts = [self.conj()]
        while self.accept_op("|"):
            parts.append(self.conj())
        return parts[0] if len(parts) == 1 else ("or", tuple(parts))

    def conj(self):
        parts = [self.unary()]
        while self.accept_op("&"):
            parts.append(self.unary())
        return parts[0] if len(parts) == 1 else ("and", tuple(parts))

    def unary(self):
        if self.accept_op("!"):
            return ("not", self.unary())
        return self.primary()

    def primary(self):
        if self.accept_op("("):
            node = self.disj()
            self.expect_op(")")
            return node
        return self.atom()

    def atom(self):
        if self.kind() != "word":
            raise CondError("期望原子，实际 %r" % self.val(), self.toks[self.i][2])
        word = self.val()
        if word in ("true", "false"):
            self.next()
            return ("true",) if word == "true" else ("false",)
        if word == "vis":
            return self._vis()
        if word == "chain":
            return self._chain()
        if word == "slot":
            return self._slot()
        if word == "outfit":
            return self._outfit()
        if word == "ctl":
            return self._ctl()
        if word == "param":
            return self._param()
        if word == "pose_tag":
            return self._pose_tag()
        if word == "pose":
            return self._pose()
        if word.startswith("body."):
            return self._body()
        raise CondError("未知原子 %r" % word, self.toks[self.i][2])

    # -- 各原子 -----------------------------------------------------------
    def _part_ref(self):
        if self.kind() != "word" or not _PART_REF_RE.match(self.val()):
            raise CondError("期望部件引用，实际 %r" % self.val(), self.toks[self.i][2])
        return self.next()[1]

    def _ident(self):
        if self.kind() != "word" or not _IDENT_RE.match(self.val()):
            raise CondError("期望标识符，实际 %r" % self.val(), self.toks[self.i][2])
        return self.next()[1]

    def _label(self):
        if self.kind() == "str":
            return self.next()[1]
        if self.kind() == "word" and _BARE_LABEL_RE.match(self.val()):
            return self.next()[1]
        raise CondError("期望标签（像数字的标签要加引号），实际 %r" % self.val(),
                        self.toks[self.i][2])

    def _param_name(self):
        if self.kind() == "str":
            return self.next()[1]
        if self.kind() == "word" and _PARAM_RE.match(self.val()):
            return self.next()[1]
        raise CondError("期望参数名，实际 %r" % self.val(), self.toks[self.i][2])

    def _bit(self):
        if self.kind() == "num":
            v = self.val()
            if re.fullmatch(r"[01]", v):
                self.next()
                return int(v)
        raise CondError("期望 0/1，实际 %r" % self.val(), self.toks[self.i][2])

    def _pose_id(self):
        if self.kind() == "word" and _POSE_ID_RE.match(self.val()):
            return self.next()[1]
        raise CondError("期望姿势 id，实际 %r" % self.val(), self.toks[self.i][2])

    def _tag(self):
        if self.kind() == "word" and _TAG_RE.match(self.val()):
            return self.next()[1]
        raise CondError("期望 tag，实际 %r" % self.val(), self.toks[self.i][2])

    def _eq_op(self):
        op = self.accept_op("=", "!=")
        if op is None:
            raise CondError("期望 = 或 !=，实际 %r" % self.val(), self.toks[self.i][2])
        return op

    def _vis(self):
        self.expect_word("vis")
        self.expect_op("(")
        ref = self._part_ref()
        self.expect_op(")")
        comp = None
        if self.kind() == "word" and self.val().startswith("."):
            cand = self.val()[1:]
            if cand not in _COMPONENTS:
                raise CondError("非法的分量 %r" % self.val(), self.toks[self.i][2])
            comp = cand
            self.next()
        return ("vis", ref, comp)

    def _chain(self):
        self.expect_word("chain")
        self.expect_op("(")
        refs = [self._part_ref()]
        while self.accept_op(","):
            refs.append(self._part_ref())
        self.expect_op(")")
        return ("chain", tuple(refs))

    def _slot(self):
        self.expect_word("slot")
        self.expect_op("(")
        name = self._ident()
        self.expect_op(")")
        op = self._eq_op()
        bit = self._bit()
        return ("slot", name, op, bit)

    def _outfit(self):
        self.expect_word("outfit")
        if self.kind() == "word" and self.val() == "in":
            self.next()
            labels = self._label_set()
            return ("outfit", "in", tuple(labels))
        op = self._eq_op()
        return ("outfit", op, (self._label(),))

    def _label_set(self):
        self.expect_op("{")
        items = [self._label()]
        while self.accept_op(","):
            items.append(self._label())
        self.expect_op("}")
        return items

    def _ctl(self):
        self.expect_word("ctl")
        self.expect_op("(")
        name = self._ident()
        self.expect_op(")")
        if self.kind() == "word" and self.val() == "in":
            self.next()
            self.expect_op("{")
            vals = [self._ctl_value()]
            while self.accept_op(","):
                vals.append(self._ctl_value())
            self.expect_op("}")
            return ("ctl", name, "in", tuple(vals))
        op = self._eq_op()
        return ("ctl", name, op, (self._ctl_value(),))

    def _ctl_value(self):
        if self.kind() == "slot":
            tok = self.next()[1]
            return ("slot", int(tok[1:]))
        if self.kind() == "num" and re.fullmatch(r"[01]", self.val()):
            tok = self.next()[1]
            return ("bit", int(tok))
        if self.kind() == "str":
            return ("label", self.next()[1])
        if self.kind() == "word":
            return ("label", self.next()[1])
        raise CondError("期望控件取值，实际 %r" % self.val(), self.toks[self.i][2])

    def _param(self):
        self.expect_word("param")
        self.expect_op("(")
        name = self._param_name()
        self.expect_op(")")
        if self.kind() != "op" or self.val() not in ("=", "!=", "<=", ">=", "<", ">"):
            raise CondError("期望比较运算符，实际 %r" % self.val(), self.toks[self.i][2])
        op = self.next()[1]
        if self.kind() != "num":
            raise CondError("期望数值，实际 %r" % self.val(), self.toks[self.i][2])
        num = float(self.next()[1])
        return ("param", name, op, num)

    def _pose(self):
        self.expect_word("pose")
        if self.kind() == "word" and self.val() == "in":
            self.next()
            self.expect_op("{")
            ids = [self._pose_id()]
            while self.accept_op(","):
                ids.append(self._pose_id())
            self.expect_op("}")
            return ("pose", "in", tuple(ids))
        op = self._eq_op()
        return ("pose", op, (self._pose_id(),))

    def _pose_tag(self):
        self.expect_word("pose_tag")
        if self.kind() == "word" and self.val() == "in":
            self.next()
            self.expect_op("{")
            tags = [self._tag()]
            while self.accept_op(","):
                tags.append(self._tag())
            self.expect_op("}")
            return ("pose_tag", "in", tuple(tags))
        op = self._eq_op()
        return ("pose_tag", op, (self._tag(),))

    def _interval(self):
        lo_op = self.accept_op("[", "(")
        if lo_op is None:
            raise CondError("期望区间左括号，实际 %r" % self.val(), self.toks[self.i][2])
        lo_c = lo_op == "["
        if self.kind() != "num":
            raise CondError("期望区间端点，实际 %r" % self.val(), self.toks[self.i][2])
        lo = float(self.next()[1])
        self.expect_op(",")
        if self.kind() != "num":
            raise CondError("期望区间端点，实际 %r" % self.val(), self.toks[self.i][2])
        hi = float(self.next()[1])
        hi_op = self.accept_op("]", ")")
        if hi_op is None:
            raise CondError("期望区间右括号，实际 %r" % self.val(), self.toks[self.i][2])
        hi_c = hi_op == "]"
        return lo, hi, lo_c, hi_c

    def _body(self):
        word = self.val()
        self.next()
        axis = word[len("body."):]
        if not _IDENT_RE.match(axis):
            raise CondError("非法的体型轴 %r" % axis, self.toks[self.i][2])
        self.expect_word("in")
        lo, hi, lo_c, hi_c = self._interval()
        return ("body", axis, lo, hi, lo_c, hi_c)


def parse_cond(text):
    """解析条件字符串；返回 AST 或抛 CondError。"""
    if not isinstance(text, str) or text == "":
        raise CondError("空条件", 0)
    return _CondParser(text).parse()


# ---------------------------------------------------------------------------
# 往返序列（GRAMMAR §4）
# ---------------------------------------------------------------------------

class RoundtripError(Exception):
    pass


def parse_roundtrip(text):
    """解析一段往返序列，返回 [(param, [value, ...]), ...]。

    value = ("slot", i) | ("label", s) | ("num", v)
    """
    s = text
    i = 0
    n = len(s)
    out = []

    def skip_ws():
        nonlocal i
        while i < n and s[i] in " \t":
            i += 1

    def read_quoted():
        nonlocal i
        assert s[i] == '"'
        j = s.find('"', i + 1)
        if j < 0:
            raise RoundtripError("引号未闭合")
        val = s[i + 1:j]
        i = j + 1
        return val

    def read_param():
        nonlocal i
        if s[i] == '"':
            return read_quoted()
        j = i
        while j < n and s[j] not in ' \t:,"':
            if s.startswith("->", j):
                raise RoundtripError("参数名里出现 ->")
            j += 1
        if j == i:
            raise RoundtripError("缺参数名")
        val = s[i:j]
        i = j
        return val

    def read_value():
        nonlocal i
        if s[i] == "#":
            j = i + 1
            while j < n and s[j].isdigit():
                j += 1
            if j == i + 1:
                raise RoundtripError("槽号缺数字")
            val = ("slot", int(s[i + 1:j]))
            i = j
            return val
        if s[i] == '"':
            return ("label", read_quoted())
        j = i
        while j < n and s[j] not in ' \t,:"':
            if s.startswith("->", j) or s[j] == "→":
                break
            j += 1
        if j == i:
            raise RoundtripError("缺取值")
        raw = s[i:j]
        i = j
        if re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", raw):
            return ("num", float(raw))
        return ("label", raw)

    def read_arrow():
        nonlocal i
        if s.startswith("->", i):
            i += 2
            return True
        if i < n and s[i] == "→":
            i += 1
            return True
        return False

    while True:
        skip_ws()
        if i >= n:
            break
        param = read_param()
        skip_ws()
        if i >= n or s[i] != ":":
            raise RoundtripError("缺冒号")
        i += 1
        skip_ws()
        values = [read_value()]
        while True:
            skip_ws()
            if not read_arrow():
                break
            skip_ws()
            values.append(read_value())
        out.append((param, values))
        skip_ws()
        if i >= n:
            break
        if s[i] != ",":
            raise RoundtripError("缺逗号或序列结束")
        i += 1
    return out


# ---------------------------------------------------------------------------
# 姿势清单（GRAMMAR §3）
# ---------------------------------------------------------------------------

PROXY_POSES = (
    "proxy_afk", "proxy_backflip", "proxy_crouch_still", "proxy_crouch_walk_forward",
    "proxy_crouch_walk_right", "proxy_crouch_walk_right_135", "proxy_crouch_walk_right_45",
    "proxy_dance", "proxy_die", "proxy_empty", "proxy_eyes_die", "proxy_eyes_open",
    "proxy_eyes_shut", "proxy_fall_long", "proxy_fall_short", "proxy_hands_fist",
    "proxy_hands_gun", "proxy_hands_idle", "proxy_hands_idle2", "proxy_hands_open",
    "proxy_hands_peace", "proxy_hands_point", "proxy_hands_rock", "proxy_hands_thumbs_up",
    "proxy_idle", "proxy_idle2", "proxy_idle3", "proxy_ikpose", "proxy_land_quick",
    "proxy_landing", "proxy_low_crawl_forward", "proxy_low_crawl_idle",
    "proxy_low_crawl_right", "proxy_low_crawl_still", "proxy_mood_angry",
    "proxy_mood_happy", "proxy_mood_neutral", "proxy_mood_sad", "proxy_mood_surprised",
    "proxy_rotate90_left", "proxy_rotate90_right", "proxy_run_backward",
    "proxy_run_forward", "proxy_run_strafe_right", "proxy_run_strafe_right_135",
    "proxy_run_strafe_right_45", "proxy_seated_clap", "proxy_seated_disapprove",
    "proxy_seated_disbelief", "proxy_seated_drum", "proxy_seated_laugh",
    "proxy_seated_point", "proxy_seated_raise_hand", "proxy_seated_shake_fist",
    "proxy_shuffle_forward_lfoot", "proxy_shuffle_forward_rfoot", "proxy_shuffle_left",
    "proxy_shuffle_right", "proxy_sit", "proxy_sit2", "proxy_sit_down",
    "proxy_sit_getup", "proxy_sprint_forward", "proxy_stand_cheer", "proxy_stand_clap",
    "proxy_stand_point", "proxy_stand_sadkick", "proxy_stand_still",
    "proxy_stand_still2", "proxy_stand_still3", "proxy_stand_wave",
    "proxy_strafe_right", "proxy_strafe_right_135", "proxy_strafe_right_45",
    "proxy_supine_getup", "proxy_tpose", "proxy_turn_180", "proxy_walk_backward",
    "proxy_walk_forward",
)
PROXY_MULTIFRAME = ("landing", "hands_idle2", "empty", "rotate90_right")
GO_POSES = (
    "go_sit_crossed_leg", "go_w_sitting_up_low", "go_long_sitting",
    "go_sit_knees_apart_in", "go_laydown_side", "go_sleep_prone_low", "go_stand_wide",
)
GO_MOTIONS = ("go_jump_in_place", "go_knockback", "go_manual_afk_idle")
GM_EMOTES = (
    "C_emote_emote_1_laugh", "C_emote_emote_1_wave", "C_emote_emote_2_clap",
    "C_emote_emote_2_point", "C_emote_emote_3_point", "C_emote_emote_3_raise_hand",
    "C_emote_emote_4_cheer", "C_emote_emote_4_drum", "C_emote_emote_5_clap",
    "C_emote_emote_5_dance", "C_emote_emote_6_angry_fist", "C_emote_emote_6_backflip",
    "C_emote_emote_7_die", "C_emote_emote_7_disbelief", "C_emote_emote_8_disapprove",
    "C_emote_emote_8_sad",
)
# 库 B
_B_JOINTS = (
    ("hip_fb", True), ("hip_io", True), ("knee", True), ("shoulder_up", True),
    ("shoulder_fb", True), ("elbow", True), ("ankle", True), ("spine_fb", False),
)
_B_DOSES = (25, 50, 75, 100)
_B_COMBOS = (
    "combo_sit", "combo_deep_squat", "combo_kneel_sit",
    "combo_arms_crossed", "combo_arms_up", "combo_cross_legged",
)
_B_SWEEP = set()
for _jid, _sided in _B_JOINTS:
    if _sided:
        for _side in ("L", "R"):
            for _dose in _B_DOSES:
                _B_SWEEP.add("B_%s_%s_%d" % (_jid, _side, _dose))
    else:
        for _dose in _B_DOSES:
            _B_SWEEP.add("B_%s_C_%d" % (_jid, _dose))
_B_EXTREME = set()
for _jid, _sided in _B_JOINTS:
    if _sided:
        for _side in ("L", "R"):
            for _sign in ("m1", "p1"):
                _B_EXTREME.add("B_%s_%s_extreme_%s" % (_jid, _side, _sign))
    else:
        for _sign in ("m1", "p1"):
            _B_EXTREME.add("B_%s_C_extreme_%s" % (_jid, _sign))
del _jid, _sided, _side, _dose, _sign

POSE_TAGS = {
    "proxy", "library_a_pose", "gogoloco", "private", "cerp", "gesture_pose",
    "bearhug", "additive", "sweep", "extreme", "combo", "emote", "gesturemanager",
    "motion", "user", "extra", "dose_25", "dose_50", "dose_75", "dose_100",
    # 关节名
    "hip_fb", "hip_io", "knee", "shoulder_up", "shoulder_fb", "elbow", "ankle",
    "spine_fb",
    # 部位名
    "thigh", "shoulder", "elbow", "spine",
    # 组合名
    "combo_sit", "combo_deep_squat", "combo_kneel_sit", "combo_arms_crossed",
    "combo_arms_up", "combo_cross_legged",
}
POSE_TAGS.update({"thigh", "elbow"})

_KIND_VOCAB = {
    "outer", "top", "bottom", "onepiece", "underwear", "socks", "shoes", "gloves",
    "hat", "hair", "acc", "body_part",
}
_WRITER_VOCAB = {"gen", "vendor_sc", "vendor_clip", "vendor_fx", "driver",
                 "ours_legacy", "unknown"}
_LEVEL_VOCAB = {"high", "mid", "low", "unknown"}
_VRC_BUILTIN_PARAMS = {
    "IsLocal", "PreviewMode", "VRMode", "TrackingType", "Grounded", "Seated",
    "AFK", "InStation", "Upright", "GestureLeft", "GestureRight", "GestureLeftWeight",
    "GestureRightWeight", "Viseme", "Voice", "MuteSelf", "Earmuffs", "IsOnFriendsList",
    "IsAnimatorEnabled", "AvatarVersion", "ScaleModified", "ScaleFactor",
    "ScaleFactorInverse", "EyeHeightAsMeters", "EyeHeightAsPercent", "VelocityX",
    "VelocityY", "VelocityZ", "VelocityMagnitude", "AngularY",
    "VRCEmote", "VRCFaceBlendH", "VRCFaceBlendV",
}

_REGION_BONES = (
    "Hips", "LeftUpperLeg", "RightUpperLeg", "LeftLowerLeg", "RightLowerLeg",
    "LeftFoot", "RightFoot", "Spine", "Chest", "UpperChest", "Neck", "Head",
    "LeftShoulder", "RightShoulder", "LeftUpperArm", "RightUpperArm", "LeftLowerArm",
    "RightLowerArm", "LeftHand", "RightHand", "LeftToes", "RightToes", "LeftEye",
    "RightEye", "Jaw",
)
_FINGER_BONES = (
    "Thumb", "Index", "Middle", "Ring", "Little",
)
_FINGER_SEGS = ("Proximal", "Intermediate", "Distal")
for _f in _FINGER_BONES:
    for _s in _FINGER_SEGS:
        _REGION_BONES = _REGION_BONES + ("Left%s%s" % (_f, _s), "Right%s%s" % (_f, _s))
del _f, _s
LEFT_FINGERS = tuple("Left%s%s" % (f, s) for f in _FINGER_BONES for s in _FINGER_SEGS)
RIGHT_FINGERS = tuple("Right%s%s" % (f, s) for f in _FINGER_BONES for s in _FINGER_SEGS)
FOOT_CHILDREN = {"LeftFoot": ("LeftFoot.forefoot", "LeftFoot.arch", "LeftFoot.heel",
                              "LeftFoot.ankle"),
                 "RightFoot": ("RightFoot.forefoot", "RightFoot.arch", "RightFoot.heel",
                               "RightFoot.ankle")}


def region_leaves(region):
    if region in FOOT_CHILDREN:
        return list(FOOT_CHILDREN[region])
    if region == "LeftFingers":
        return list(LEFT_FINGERS)
    if region == "RightFingers":
        return list(RIGHT_FINGERS)
    return [region]


def region_leaves_set(regions):
    out = []
    for r in regions:
        out.extend(region_leaves(r))
    # 去重保序
    seen, res = set(), []
    for r in out:
        if r not in seen:
            seen.add(r)
            res.append(r)
    return res


def region_compact(leaves):
    """把叶子集合写回区域：整只脚的四个子部位都在时写回 LeftFoot/RightFoot。"""
    s = set(leaves)
    out = []
    used = set()
    for foot, children in FOOT_CHILDREN.items():
        if all(c in s for c in children):
            out.append(foot)
            used.update(children)
    for leaf in leaves:
        if leaf not in used and leaf not in out:
            out.append(leaf)
    return out


# ---------------------------------------------------------------------------
# 文档模型：includes 合并、展开状态、期望求值
# ---------------------------------------------------------------------------

SEM_ALL = ["SEM-%02d" % i for i in range(1, 25)]

_DEFAULT_GEO = {
    "closed": "inside",
    "tight": "no_pierce",
    "loose": "none",
    "cover": "no_poke",
    "opening": "opening_intact",
}


def load_yaml_file(path, base=None):
    p = Path(path)
    if not p.is_absolute():
        p = (Path(base) if base is not None else Path.cwd()) / p
    if not p.exists():
        raise FileNotFoundError(str(p))
    text = p.read_text(encoding="utf-8")
    return load_yaml_text(text, str(p))


class Finding:
    __slots__ = ("rule", "path", "message", "severity")

    def __init__(self, rule, path, message, severity="error"):
        self.rule = rule
        self.path = path
        self.message = message
        self.severity = severity

    def __repr__(self):
        return "Finding(%s, %s, %s)" % (self.rule, self.path, self.message)


class PartRec:
    __slots__ = ("obj", "id", "origin", "path_base", "inc_index", "local_index",
                 "generated_from")

    def __init__(self, obj, pid, origin, path_base, inc_index=None, local_index=None,
                 generated_from=None):
        self.obj = obj
        self.id = pid
        self.origin = origin
        self.path_base = path_base
        self.inc_index = inc_index
        self.local_index = local_index
        self.generated_from = generated_from


class DepRec:
    __slots__ = ("obj", "id", "origin", "path_base", "inc_index", "local_index",
                 "order", "generated_from")

    def __init__(self, obj, did, origin, path_base, inc_index=None, local_index=None,
                 generated_from=None):
        self.obj = obj
        self.id = did
        self.origin = origin
        self.path_base = path_base
        self.inc_index = inc_index
        self.local_index = local_index
        self.order = 0
        self.generated_from = generated_from


class IncludeRec:
    __slots__ = ("index", "as_", "mount", "outfit", "path", "doc", "valid", "error")

    def __init__(self, index, spec):
        self.index = index
        self.as_ = spec.get("as")
        self.mount = spec.get("mount")
        self.outfit = spec.get("outfit")
        self.path = spec.get("fragment")
        self.doc = None
        self.valid = False
        self.error = None


# -- 条件重写与序列化 --------------------------------------------------------

def rewrite_cond_refs(ast, as_):
    """把片段条件里的局部部件引用加上 `<as>.` 前缀（any.* 不动）。"""
    tag = ast[0]
    if tag == "vis":
        return ("vis", _prefix_ref(ast[1], as_), ast[2])
    if tag == "chain":
        return ("chain", tuple(_prefix_ref(r, as_) for r in ast[1]))
    if tag == "not":
        return ("not", rewrite_cond_refs(ast[1], as_))
    if tag in ("and", "or"):
        return (tag, tuple(rewrite_cond_refs(x, as_) for x in ast[1]))
    return ast


def _prefix_ref(ref, as_):
    if ref.startswith("any."):
        return ref
    return "%s.%s" % (as_, ref)


def format_cond(ast):
    tag = ast[0]
    if tag == "true":
        return "true"
    if tag == "false":
        return "false"
    if tag == "vis":
        s = "vis(%s)" % ast[1]
        if ast[2]:
            s += "." + ast[2]
        return s
    if tag == "chain":
        return "chain(%s)" % ", ".join(ast[1])
    if tag == "slot":
        return "slot(%s)%s%d" % (ast[1], ast[2], ast[3])
    if tag == "outfit":
        if ast[1] == "in":
            return "outfit in {%s}" % ", ".join(_fmt_label(x) for x in ast[2])
        return "outfit %s %s" % (ast[1], _fmt_label(ast[2][0]))
    if tag == "ctl":
        if ast[2] == "in":
            return "ctl(%s) in {%s}" % (ast[1], ", ".join(_fmt_ctl(v) for v in ast[3]))
        return "ctl(%s) %s %s" % (ast[1], ast[2], _fmt_ctl(ast[3][0]))
    if tag == "param":
        return "param(%s) %s %s" % (_fmt_param(ast[1]), ast[2], _fmt_num(ast[3]))
    if tag == "pose":
        vals = ", ".join(ast[2])
        if ast[1] == "in":
            return "pose in {%s}" % vals
        return "pose %s %s" % (ast[1], vals)
    if tag == "pose_tag":
        vals = ", ".join(ast[2])
        if ast[1] == "in":
            return "pose_tag in {%s}" % vals
        return "pose_tag %s %s" % (ast[1], vals)
    if tag == "body":
        lo = "[" if ast[3] else "("
        hi = "]" if ast[5] else ")"
        return "body.%s in %s%s, %s%s" % (ast[1], lo, _fmt_num(ast[2]), _fmt_num(ast[4]), hi)
    if tag == "not":
        return "!(%s)" % format_cond(ast[1])
    if tag == "and":
        return " & ".join("(%s)" % format_cond(x) for x in ast[1])
    if tag == "or":
        return " | ".join("(%s)" % format_cond(x) for x in ast[1])
    raise ValueError("未知条件节点 %r" % (tag,))


def _fmt_num(x):
    if float(x) == int(x):
        return str(int(x))
    return repr(float(x))


def _fmt_label(s):
    if re.fullmatch(r"[^\s()\[\]{},|&!=<>\":#][^\s()\[\]{},|&!=<>\":]*", s) and not \
            re.fullmatch(r"-?[0-9]+(\.[0-9]+)?", s):
        return s
    return '"%s"' % s


def _fmt_param(s):
    return _fmt_label(s)


def _fmt_ctl(v):
    if v[0] == "slot":
        return "#%d" % v[1]
    if v[0] == "bit":
        return str(v[1])
    return _fmt_label(v[1])


# -- 期望求值 ----------------------------------------------------------------

class EvalState:
    __slots__ = ("outfit_label", "slots", "ctl", "params", "body", "pose_id",
                 "pose_tags")

    def __init__(self):
        self.outfit_label = None
        self.slots = {}
        self.ctl = {}
        self.params = {}
        self.body = {}
        self.pose_id = None
        self.pose_tags = frozenset()

    def copy(self):
        st = EvalState()
        st.outfit_label = self.outfit_label
        st.slots = dict(self.slots)
        st.ctl = {k: dict(v) for k, v in self.ctl.items()}
        st.params = dict(self.params)
        st.body = dict(self.body)
        st.pose_id = self.pose_id
        st.pose_tags = self.pose_tags
        return st


def eval_cond(ast, st, E, parts_by_kind):
    tag = ast[0]
    if tag == "true":
        return True
    if tag == "false":
        return False
    if tag == "not":
        return not eval_cond(ast[1], st, E, parts_by_kind)
    if tag == "and":
        return all(eval_cond(x, st, E, parts_by_kind) for x in ast[1])
    if tag == "or":
        return any(eval_cond(x, st, E, parts_by_kind) for x in ast[1])
    if tag == "vis":
        ref = ast[1]
        if ref.startswith("any."):
            kind = ref[4:]
            return any(E.get(p, False) for p in parts_by_kind.get(kind, ()))
        return bool(E.get(ref, False))
    if tag == "chain":
        return any(_vis_ref(r, st, E, parts_by_kind) for r in ast[1])
    if tag == "slot":
        cur = st.slots.get(ast[1])
        if cur is None:
            return False
        ok = int(cur) == int(ast[3])
        return ok if ast[2] == "=" else not ok
    if tag == "outfit":
        ok = st.outfit_label in ast[2]
        return ok if ast[1] == "in" else (ok if ast[1] == "=" else not ok)
    if tag == "ctl":
        c = st.ctl.get(ast[1])
        if c is None:
            return False
        if ast[2] == "in":
            ok = any(_ctl_match(c, v) for v in ast[3])
        else:
            ok = _ctl_match(c, ast[3][0])
            if ast[2] == "!=":
                ok = not ok
        return ok
    if tag == "param":
        if ast[1] not in st.params:
            return False
        return _cmp(st.params[ast[1]], ast[2], ast[3])
    if tag == "pose":
        ok = st.pose_id in ast[2]
        return ok if ast[1] == "in" else (ok if ast[1] == "=" else not ok)
    if tag == "pose_tag":
        ok = bool(st.pose_tags & set(ast[2]))
        return ok if ast[1] == "in" else (ok if ast[1] == "=" else not ok)
    if tag == "body":
        v = st.body.get(ast[1])
        if v is None:
            return False
        lo_ok = v >= ast[2] if ast[3] else v > ast[2]
        hi_ok = v <= ast[4] if ast[5] else v < ast[4]
        return lo_ok and hi_ok
    raise ValueError("未知条件节点 %r" % (tag,))


def _vis_ref(ref, st, E, parts_by_kind):
    if ref.startswith("any."):
        kind = ref[4:]
        return any(E.get(p, False) for p in parts_by_kind.get(kind, ()))
    return bool(E.get(ref, False))


def _ctl_match(c, v):
    kind = v[0]
    if kind == "slot":
        return c.get("slot") == v[1]
    if kind == "bit":
        if c.get("kind") == "bool":
            return c.get("bit") == v[1]
        return c.get("slot") == v[1]
    return c.get("label") == v[1]


def _cmp(a, op, b):
    if op == "=":
        return a == b
    if op == "!=":
        return a != b
    if op == "<":
        return a < b
    if op == "<=":
        return a <= b
    if op == ">":
        return a > b
    if op == ">=":
        return a >= b
    return False


def cond_chain_atoms(ast):
    """返回 AST 里所有 chain 原子（含嵌套）。"""
    out = []
    stack = [ast]
    while stack:
        node = stack.pop()
        if node[0] == "chain":
            out.append(node)
        elif node[0] in ("and", "or"):
            stack.extend(node[1])
        elif node[0] == "not":
            stack.append(node[1])
    return out


def top_level_conjuncts(ast):
    return list(ast[1]) if ast[0] == "and" else [ast]


def cond_intervals(ast):
    """返回条件里所有 body 区间 (axis, lo, hi, lo_closed, hi_closed)。"""
    out = []
    stack = [ast]
    while stack:
        node = stack.pop()
        if node[0] == "body":
            out.append(node[1:])
        elif node[0] in ("and", "or"):
            stack.extend(node[1])
        elif node[0] == "not":
            stack.append(node[1])
    return out


def cond_param_atoms(ast):
    out = []
    stack = [ast]
    while stack:
        node = stack.pop()
        if node[0] == "param":
            out.append(node)
        elif node[0] in ("and", "or"):
            stack.extend(node[1])
        elif node[0] == "not":
            stack.append(node[1])
    return out


# -- 语义校验器 --------------------------------------------------------------

class SemanticValidator:
    def __init__(self, data, source, ctx, fragment_only=False, path_prefix=None):
        self.data = data
        self.source = source
        self.ctx = ctx
        self.fragment_only = fragment_only
        self.path_prefix = list(path_prefix or [])
        self.findings = []
        self.skips = {}
        self.notes = []
        self.id_dups = []
        self.parts_by_id = {}
        self.deps_by_id = {}
        self.parts = []          # PartRec 列表（合并后，id 唯一，声明覆盖片段）
        self.deps = []           # DepRec 列表（合并后）
        self.all_deps = []       # 含被 supersedes 取代的
        self.includes = []
        self.menu = data.get("menu") or {}
        self.geo_defaults = self._geo_defaults()
        self.superseded = set()
        self.superseded_by = {}
        self.generated_geo_ids = set()
        self.profile = ctx.get("profile")
        self.inventory = ctx.get("inventory")
        self.pose_library = ctx.get("pose_library")
        self.pose_ids = None
        self.pose_tags_by_id = None
        if self.pose_library:
            self._index_pose_library()
        self.avatar = data.get("avatar") or {}
        self._part_dims_cache = {}
        self._part_dims_inprog = set()
        self._ast_cache = {}
        self._pbk_cache = None

    # -- 小工具 -----------------------------------------------------------
    def add(self, rule, path, message, severity="error"):
        self.findings.append(Finding(rule, "".join(pointer_path(path)),
                                     message, severity))

    def add_skip(self, rule, reason):
        self.skips[rule] = reason

    def pfx(self, *segs):
        return self.path_prefix + list(segs)

    def rec_path(self, rec, *tail):
        base = rec.path_base if rec.path_base is not None else \
            ["deps", str(rec.order)]
        return list(base) + list(tail)

    def _geo_defaults(self):
        gd = self.data.get("geo_defaults")
        if gd is None:
            gd = {}
        elif gd is False:
            return {"_off": True}
        elif gd is True:
            gd = {}
        elif not isinstance(gd, dict):
            gd = {}
        out = dict(_DEFAULT_GEO)
        out.update(gd)
        return out

    def geo_on(self):
        return not self.geo_defaults.get("_off")

    def _index_pose_library(self):
        d = self.pose_library
        ids = {}
        tags = {}
        try:
            libs = d.get("libraries") or {}
            for arr in libs.values():
                for e in arr or []:
                    i = e.get("id")
                    if i is None:
                        continue
                    ids[i] = e
                    ids.setdefault(base_pose_id(i), e)
                    tags[i] = set(e.get("tags") or [])
                    tags.setdefault(base_pose_id(i), set(e.get("tags") or []))
        except AttributeError:
            self.pose_library = None
            return
        self.pose_ids = set(ids)
        self.pose_tags_by_id = tags

    # -- includes ---------------------------------------------------------
    def load_includes(self):
        specs = self.data.get("includes") or []
        seen_as = {}
        for i, spec in enumerate(specs):
            rec = IncludeRec(i, spec if isinstance(spec, dict) else {})
            self.includes.append(rec)
            if not isinstance(spec, dict):
                continue
            if rec.as_ in seen_as:
                self.add("SEM-18", self.pfx("includes", str(i), "as"),
                         "includes[].as 重复：%r" % rec.as_)
            seen_as[rec.as_] = i
            try:
                doc = load_yaml_file(rec.path, base=WORKSPACE)
            except Exception as exc:  # noqa: BLE001
                rec.error = "片段文件不可读：%s" % exc
                self.add("SEM-18", self.pfx("includes", str(i), "fragment"),
                         rec.error)
                continue
            if not isinstance(doc, dict):
                rec.error = "片段文件不是映射"
                self.add("SEM-18", self.pfx("includes", str(i), "fragment"), rec.error)
                continue
            rec.doc = doc
            # schema 层
            errs = schema_errors(doc, self.ctx.get("schema"))
            if errs is None:
                self.add_skip("SEM-18", "jsonschema 不可用，includes 片段只做结构核对")
            elif errs:
                rec.error = "片段不通过 perception-fragment/0.2 schema"
                self.add("SEM-18", self.pfx("includes", str(i), "fragment"), rec.error)
                continue
            # body 一致
            body_name = (self.avatar.get("profile") or "").split("@")[0]
            pkg = doc.get("package") or {}
            if pkg.get("body") != body_name:
                rec.error = ("片段 package.body（%s）与 avatar.profile 的素体（%s）不一致"
                             % (pkg.get("body"), body_name))
                self.add("SEM-18", self.pfx("includes", str(i), "fragment"), rec.error)
                continue
            # 片段依赖的 mesh 必须等于 avatar.body
            bad_mesh = None
            for j, dep in enumerate(doc.get("deps") or []):
                if not isinstance(dep, dict):
                    continue
                for tgt in _dep_targets(dep):
                    if tgt.get("mesh") is not None and tgt.get("mesh") != self.avatar.get("body"):
                        bad_mesh = ("dep#%d target.mesh=%r" % (j, tgt.get("mesh")))
                        break
                if bad_mesh:
                    break
                exp = dep.get("expect")
                if isinstance(exp, dict) and isinstance(exp.get("sync"), dict):
                    fm = (exp["sync"].get("from") or {}).get("mesh")
                    if fm is not None and fm != self.avatar.get("body"):
                        bad_mesh = "dep#%d sync.from.mesh=%r" % (j, fm)
                        break
            if bad_mesh:
                rec.error = "片段依赖的网格不是 avatar.body（%s）" % bad_mesh
                self.add("SEM-18", self.pfx("includes", str(i), "fragment"), rec.error)
                continue
            # 片段内的语义错：报成 /includes/<i>/fragment#<片段内路径>，该片段不合并，
            # 不另报 SEM-18（GRAMMAR §5 末段、§8）
            sub = SemanticValidator(
                doc, rec.path, self.ctx, fragment_only=True,
                path_prefix=self.pfx("includes", str(i), "fragment#"))
            sub.run()
            for f in sub.findings:
                self.findings.append(f)
            if any(f.severity == "error" for f in sub.findings):
                rec.error = "片段内部有语义错，不合并"
                continue
            rec.valid = True

    # -- 合并 -------------------------------------------------------------
    def merge(self):
        self.id_dups = []
        # 片段部件先入，声明再覆盖
        for rec in self.includes:
            if not rec.valid:
                continue
            local_seen = set()
            for j, part in enumerate(rec.doc.get("parts") or []):
                if not isinstance(part, dict):
                    continue
                local = part.get("id")
                if local is None:
                    continue
                if local in local_seen:
                    self.id_dups.append((
                        "part",
                        self.pfx("includes", str(rec.index), "fragment#",
                                 "parts", str(j), "id"),
                        "片段内部件 id 重复：%r" % local))
                local_seen.add(local)
                pid = "%s.%s" % (rec.as_, local)
                obj = dict(part)
                obj["id"] = pid
                if rec.outfit is not None:
                    obj["outfit"] = rec.outfit
                if "alt_of" in obj and isinstance(obj["alt_of"], str) and \
                        not obj["alt_of"].startswith("any."):
                    obj["alt_of"] = "%s.%s" % (rec.as_, obj["alt_of"])
                objs = []
                for o in obj.get("objects") or []:
                    o = dict(o)
                    if rec.mount:
                        o["path"] = "%s/%s" % (rec.mount, o.get("path"))
                    objs.append(o)
                obj["objects"] = objs
                self._put_part(PartRec(obj, pid, "fragment",
                                       self.pfx("includes", str(rec.index),
                                                "fragment#", "parts", str(j)),
                                       inc_index=rec.index, local_index=j))
            dep_seen = set()
            for j, dep in enumerate(rec.doc.get("deps") or []):
                if not isinstance(dep, dict):
                    continue
                local = dep.get("id")
                if local is None:
                    continue
                if local in dep_seen:
                    self.id_dups.append((
                        "dep",
                        self.pfx("includes", str(rec.index), "fragment#",
                                 "deps", str(j), "id"),
                        "片段内依赖 id 重复：%r" % local))
                dep_seen.add(local)
                did = "%s.%s" % (rec.as_, local)
                obj = _rewrite_fragment_dep(dep, rec.as_, did)
                self._put_dep(DepRec(obj, did, "fragment",
                                     self.pfx("includes", str(rec.index),
                                              "fragment#", "deps", str(j)),
                                     inc_index=rec.index, local_index=j))
        decl_part_seen = set()
        for i, part in enumerate(self.data.get("parts") or []):
            if not isinstance(part, dict):
                continue
            pid = part.get("id")
            if pid is None:
                continue
            if pid in decl_part_seen:
                self.id_dups.append(("part", self.pfx("parts", str(i), "id"),
                                     "parts[].id 重复：%r" % pid))
            decl_part_seen.add(pid)
            self._put_part(PartRec(dict(part), pid, "declared",
                                   self.pfx("parts", str(i))))
        decl_dep_seen = set()
        for i, dep in enumerate(self.data.get("deps") or []):
            if not isinstance(dep, dict):
                continue
            did = dep.get("id")
            if did is None:
                continue
            if did in decl_dep_seen:
                self.id_dups.append(("dep", self.pfx("deps", str(i), "id"),
                                     "deps[].id 重复：%r" % did))
            decl_dep_seen.add(did)
            self._put_dep(DepRec(dict(dep), did, "declared",
                                 self.pfx("deps", str(i))))

    def _put_part(self, rec):
        for k, prev in enumerate(self.parts):
            if prev.id == rec.id:
                if prev.origin == "fragment" and rec.origin == "declared":
                    self.parts[k] = rec
                elif prev.origin == "declared" and rec.origin == "fragment":
                    pass
                else:
                    self.parts[k] = rec
                self.parts_by_id[rec.id] = self.parts[k]
                return
        self.parts.append(rec)
        self.parts_by_id[rec.id] = rec

    def _put_dep(self, rec):
        for k, prev in enumerate(self.deps):
            if prev.id == rec.id:
                if prev.origin == "fragment" and rec.origin == "declared":
                    self.deps[k] = rec
                elif prev.origin == "declared" and rec.origin == "fragment":
                    pass
                else:
                    self.deps[k] = rec
                self.deps_by_id[rec.id] = self.deps[k]
                return
        self.deps.append(rec)
        self.deps_by_id[rec.id] = rec

    # -- 生成几何项 -------------------------------------------------------
    def compute_geo(self):
        """计算会生成的 geo id，并把未手写覆盖的生成项补进 deps。"""
        gd = self.geo_defaults
        exclude = set(gd.get("exclude") or [])
        gen = []
        for prec in list(self.parts):
            part = prec.obj
            pid = prec.id
            if pid in exclude:
                continue
            fit = part.get("fit")
            if fit == "none" or fit is None:
                continue
            covers = region_leaves_set(part.get("covers") or [])
            open_leaves = []
            for op in part.get("openings") or []:
                if isinstance(op, dict):
                    open_leaves.extend(region_leaves_set(op.get("region") or []))
            open_set = set(open_leaves)
            region = [x for x in covers if x not in open_set]
            if not covers:
                continue
            # 静态主项
            metric = None
            if fit == "closed":
                metric = gd.get("closed")
            elif fit == "tight":
                metric = gd.get("tight")
            elif fit == "loose":
                metric = gd.get("loose")
            if metric and metric != "none" and region:
                gen.append(("geo.%s" % pid, pid, "main", metric, region,
                            [x for x in (part.get("covers") or [])]))
            if part.get("openings") and gd.get("opening", "opening_intact") != "none":
                regions = []
                for op in part.get("openings") or []:
                    if isinstance(op, dict):
                        regions.extend(op.get("region") or [])
                gen.append(("geo.%s.opening" % pid, pid, "opening",
                            "opening_intact", regions, []))
            if gd.get("cover", "no_poke") != "none" and covers:
                if region:
                    gen.append(("geo.%s.poke" % pid, pid, "poke", "no_poke", region, []))
        self.generated_geo_ids = {g[0] for g in gen}
        for gid, pid, kind, metric, region, _ in gen:
            if gid in self.deps_by_id:
                continue
            obj = _make_geo_dep(gid, pid, kind, metric, region)
            rec = DepRec(obj, gid, "geo_default", None, generated_from=pid)
            self.deps.append(rec)
            self.deps_by_id[gid] = rec
        # order
        for i, rec in enumerate(self.deps):
            rec.order = i

    # -- supersedes -------------------------------------------------------
    def compute_supersedes(self):
        ids = set(self.deps_by_id)
        for rec in self.deps:
            dep = rec.obj
            supers = dep.get("supersedes")
            if not supers:
                continue
            for k, sid in enumerate(supers):
                if not isinstance(sid, str):
                    continue
                if sid == rec.id:
                    self.add("SEM-24", self.rec_path(rec, "supersedes", str(k)),
                             "supersedes 不能取代自己")
                    continue
                if sid not in ids:
                    self.add("SEM-24", self.rec_path(rec, "supersedes", str(k)),
                             "supersedes 引用不存在的依赖 %r" % sid)
                    continue
                self.superseded.add(sid)
                self.superseded_by.setdefault(sid, []).append(rec.id)
        # 成环：报在环里边里 order 最大的那条（A↔B 报后一条）
        edge = {}
        for rec in self.deps:
            for sid in rec.obj.get("supersedes") or []:
                if isinstance(sid, str) and sid in ids:
                    edge.setdefault(rec.id, []).append(sid)
        seen_edges = set()
        for rec in self.deps:
            for k, sid in enumerate(rec.obj.get("supersedes") or []):
                if not isinstance(sid, str) or sid == rec.id or sid not in ids:
                    continue
                if rec.id in (self.deps_by_id[sid].obj.get("supersedes") or []):
                    later = rec if rec.order > self.deps_by_id[sid].order else None
                    if later is rec and (rec.id, sid) not in seen_edges:
                        seen_edges.add((rec.id, sid))
                        self.add("SEM-24", self.rec_path(rec, "supersedes", str(k)),
                                 "supersedes 成环：%s ↔ %s" % (rec.id, sid))

    # -- 工具：目标、部件 -------------------------------------------------
    def part(self, pid):
        return self.parts_by_id.get(pid)

    def part_smr_meshes(self, pid):
        rec = self.parts_by_id.get(pid)
        if not rec:
            return []
        out = []
        for o in rec.obj.get("objects") or []:
            if isinstance(o, dict) and o.get("renderer") == "smr" and o.get("path"):
                out.append(o["path"])
        return out

    def all_smr_paths(self):
        out = set()
        for rec in self.parts:
            for m in self.part_smr_meshes(rec.id):
                out.add(m)
        return out

    def parts_by_kind(self):
        if getattr(self, "_pbk_cache", None) is None:
            d = {}
            for rec in self.parts:
                d.setdefault(rec.obj.get("kind"), []).append(rec.id)
            self._pbk_cache = d
        return self._pbk_cache

    # -- 条件字段枚举 -----------------------------------------------------
    def dep_cond_fields(self, rec):
        dep = rec.obj
        out = []
        if "when" in dep:
            out.append((["when"], dep["when"]))
        for i, c in enumerate(dep.get("cases") or []):
            if isinstance(c, dict) and "when" in c:
                out.append((["cases", str(i), "when"], c["when"]))
        for rel, outcome in dep_outcomes(dep):
            if isinstance(outcome, dict) and isinstance(outcome.get("variant"), dict):
                for j, opt in enumerate(outcome["variant"].get("options") or []):
                    if isinstance(opt, dict) and "when" in opt:
                        out.append((rel + ["variant", "options", str(j), "when"],
                                    opt["when"]))
        return out

    # -- 状态空间 ---------------------------------------------------------
    def dim_for_param(self, param):
        outfit = self.menu.get("outfit") or {}
        if param == outfit.get("param"):
            return "outfit"
        for name, c in (self.menu.get("slots") or {}).items():
            if isinstance(c, dict) and c.get("param") == param:
                return "slot:" + name
        for name, c in (self.menu.get("controls") or {}).items():
            if isinstance(c, dict) and c.get("param") == param:
                return "ctl:" + name
        for name, ax in (self.data.get("body_axes") or {}).items():
            if isinstance(ax, dict) and ax.get("param") == param:
                return "axis:" + name
        return "param:" + param

    def build_dim_values(self):
        vals = {}
        outfit = self.menu.get("outfit") or {}
        labels = outfit.get("labels") or []
        typ = outfit.get("type")
        if labels:
            vals["outfit"] = list(labels)
        else:
            vals["outfit"] = [None]
        for name, c in (self.menu.get("slots") or {}).items():
            vals["slot:" + name] = [0, 1]
        for name, c in (self.menu.get("controls") or {}).items():
            t = c.get("type")
            labels = c.get("labels") or []
            if t == "bool":
                vals["ctl:" + name] = [{"kind": "bool", "bit": b} for b in (0, 1)]
            elif t == "int":
                vals["ctl:" + name] = [
                    {"kind": "int", "label": lab, "slot": i, "bit": i, "raw": i}
                    for i, lab in enumerate(labels)]
            elif t == "float_slots":
                n = len(labels)
                vals["ctl:" + name] = [
                    {"kind": "float_slots", "label": lab, "slot": i, "bit": i,
                     "raw": (i / n if n else 0.0)} for i, lab in enumerate(labels)]
            else:  # float
                vals["ctl:" + name] = [{"kind": "float", "raw": 0.0}]
        for name, ax in (self.data.get("body_axes") or {}).items():
            vals["axis:" + name] = [0.0]
        # 条件常数
        consts = {}
        for rec in self.deps:
            for rel, text in self.dep_cond_fields(rec):
                ast = self._safe_parse(text)
                if ast is None:
                    continue
                for pa in cond_param_atoms(ast):
                    dk = self.dim_for_param(pa[1])
                    consts.setdefault(dk, []).append(pa[3])
                for iv in cond_intervals(ast):
                    consts.setdefault("axis:" + iv[0], []).extend([iv[1], iv[2]])
        for w in self.data.get("waivers") or []:
            if isinstance(w, dict) and "states" in w:
                ast = self._safe_parse(w["states"])
                if ast is not None:
                    for pa in cond_param_atoms(ast):
                        consts.setdefault(self.dim_for_param(pa[1]), []).append(pa[3])
                    for iv in cond_intervals(ast):
                        consts.setdefault("axis:" + iv[0], []).extend([iv[1], iv[2]])
        # 连续维：即使条件里没出现，也要按 §6.1 取样（空常数缺省 {0,0.5,1}）
        for name, c in (self.menu.get("controls") or {}).items():
            if c.get("type") == "float":
                cs = list(consts.get("ctl:" + name, []))
                vals["ctl:" + name] = [
                    {"kind": "float", "raw": v} for v in samples_for(cs)]
        for name, ax in (self.data.get("body_axes") or {}).items():
            samples = ax.get("samples") if isinstance(ax, dict) else None
            allc = list(consts.get("axis:" + name, [])) + list(samples or [])
            vals["axis:" + name] = samples_for(allc)
        # 用常数重算其余连续维
        for dk, cs in consts.items():
            if dk.startswith("param:"):
                vals[dk] = samples_for(cs)
        # 姿势维
        if self._needs_pose_dim():
            vals["pose"] = self._pose_reps()
        self.dim_values = vals
        return vals

    def _safe_parse(self, text):
        if text is None:
            return None
        cached = self._ast_cache.get(text)
        if cached is not None:
            return cached
        try:
            ast = parse_cond(text)
        except CondError:
            ast = None
        if ast is not None:
            self._ast_cache[text] = ast
        return ast

    def _needs_pose_dim(self):
        for rec in self.deps:
            for rel, text in self.dep_cond_fields(rec):
                ast = self._safe_parse(text)
                if ast is not None and _has_pose_atom(ast):
                    return True
        return False

    def _pose_universe(self):
        if self.pose_ids:
            out = []
            seen = set()
            lib = self.pose_library.get("libraries") or {}
            for arr in lib.values():
                for e in arr or []:
                    i = e.get("id")
                    if i and i not in seen:
                        seen.add(i)
                        out.append((i, frozenset(e.get("tags") or [])))
            return out
        out = []
        for i in PROXY_POSES:
            tags = {"proxy"}
            if i in ("proxy_stand_still", "proxy_tpose", "proxy_crouch_still",
                     "proxy_low_crawl_still", "proxy_sit", "proxy_sit2", "proxy_afk",
                     "proxy_walk_forward", "proxy_run_forward", "proxy_sprint_forward",
                     "proxy_crouch_walk_forward", "proxy_low_crawl_forward",
                     "proxy_stand_wave", "proxy_stand_cheer", "proxy_seated_raise_hand"):
                tags.add("library_a_pose")
            out.append((i, frozenset(tags)))
        for i in GO_POSES:
            out.append((i, frozenset({"gogoloco", "library_a_pose"})))
        for i in sorted(_B_SWEEP):
            joint = i.split("_")[1] + ("_" + i.split("_")[2] if i.count("_") >= 3
                                       and i.split("_")[2] in ("L", "R", "C") else "")
            out.append((i, frozenset({"sweep", "dose_100"})))
        for i in _B_COMBOS:
            out.append(("B_" + i, frozenset({"combo"})))
        for i in sorted(_B_EXTREME):
            out.append((i, frozenset({"sweep", "extreme"})))
        for i in GM_EMOTES:
            out.append((i, frozenset({"emote", "gesturemanager"})))
        for i in GO_MOTIONS:
            out.append(("C_" + i, frozenset({"gogoloco", "motion"})))
        return out

    def _pose_reps(self):
        atoms = []
        for rec in self.deps:
            for rel, text in self.dep_cond_fields(rec):
                ast = self._safe_parse(text)
                if ast is not None:
                    atoms.extend(_pose_atoms(ast))
        # 去重
        uniq = []
        for a in atoms:
            if a not in uniq:
                uniq.append(a)
        reps = {}
        for pid, tags in self._pose_universe():
            vec = tuple(_pose_atom_truth(a, pid, tags) for a in uniq)
            if vec not in reps:
                reps[vec] = (pid, tags)
        return list(reps.values())

    def _default_state(self):
        st = EvalState()
        outfit = self.menu.get("outfit") or {}
        labels = outfit.get("labels") or []
        dflt = outfit.get("default", 0)
        idx = _slot_index_of_default(outfit, dflt)
        if labels:
            st.outfit_label = labels[idx]
            st.params[outfit.get("param")] = _raw_of_slot(outfit, idx)
        for name, c in (self.menu.get("slots") or {}).items():
            st.slots[name] = 1 if float(c.get("default", 0)) >= 0.5 else 0
            st.params[c.get("param")] = st.slots[name]
        for name, c in (self.menu.get("controls") or {}).items():
            labels = c.get("labels") or []
            t = c.get("type")
            if t in ("int", "float_slots") and labels:
                idx = _slot_index_of_default(c, c.get("default", 0))
                st.ctl[name] = {"kind": t, "label": labels[idx], "slot": idx,
                                "bit": idx}
                st.params[c.get("param")] = _raw_of_slot(c, idx)
            elif t == "bool":
                b = 1 if float(c.get("default", 0)) >= 0.5 else 0
                st.ctl[name] = {"kind": "bool", "bit": b}
                st.params[c.get("param")] = b
            else:
                v = float(c.get("default", 0) or 0)
                st.ctl[name] = {"kind": "float", "raw": v}
                st.params[c.get("param")] = v
        for name, ax in (self.data.get("body_axes") or {}).items():
            st.body[name] = 0.0
            if isinstance(ax, dict) and ax.get("param"):
                st.params[ax["param"]] = 0.0
        for dk in getattr(self, "dim_values", {}):
            if dk.startswith("param:"):
                st.params[dk[6:]] = 0.0
        st.pose_id = None
        st.pose_tags = frozenset()
        return st

    def apply_dim(self, st, dk, val):
        if dk == "outfit":
            st.outfit_label = val
            outfit = self.menu.get("outfit") or {}
            labels = outfit.get("labels") or []
            if val in labels:
                st.params[outfit.get("param")] = _raw_of_slot(outfit, labels.index(val))
        elif dk.startswith("slot:"):
            name = dk[5:]
            st.slots[name] = int(val)
            c = (self.menu.get("slots") or {}).get(name) or {}
            if c.get("param"):
                st.params[c["param"]] = int(val)
        elif dk.startswith("ctl:"):
            name = dk[4:]
            c = (self.menu.get("controls") or {}).get(name) or {}
            st.ctl[name] = val
            if c.get("param"):
                st.params[c["param"]] = val.get("raw")
        elif dk.startswith("axis:"):
            name = dk[5:]
            st.body[name] = val
            ax = (self.data.get("body_axes") or {}).get(name) or {}
            if ax.get("param"):
                st.params[ax["param"]] = val
        elif dk.startswith("param:"):
            st.params[dk[6:]] = val
        elif dk == "pose":
            st.pose_id, st.pose_tags = val

    def states_for(self, dims):
        dims = [d for d in dims if d in getattr(self, "dim_values", {})]
        base = self._default_state()
        if not dims:
            yield base
            return
        lists = [self.dim_values[d] for d in dims]
        import itertools
        for combo in itertools.product(*lists):
            st = base.copy()
            for d, v in zip(dims, combo):
                self.apply_dim(st, d, v)
            yield st

    # -- 期望可见性 E -----------------------------------------------------
    def compute_E(self, st, deps):
        E = {}
        pbk = self.parts_by_kind()
        for rec in self.parts:
            E[rec.id] = self._base_visible(rec.obj, st)
        for rec in deps:
            tgt = rec.obj.get("target")
            if not isinstance(tgt, dict) or "part" not in tgt:
                continue
            if "key" in tgt or "keys" in tgt or "submesh" in tgt:
                continue
            pid = tgt["part"]
            if pid not in E:
                continue
            out = self.eval_dep(rec, st, E, pbk)
            if isinstance(out, dict):
                if out.get("hidden") is True:
                    E[pid] = False
                elif out.get("shown") is True:
                    E[pid] = True
        return E

    def _base_visible(self, part, st):
        if part.get("alt_of"):
            return False
        outfit = part.get("outfit")
        if outfit:
            labels = outfit if isinstance(outfit, list) else [outfit]
            if st.outfit_label not in labels:
                return False
        slot = part.get("slot")
        if slot:
            if int(st.slots.get(slot, 0)) != 1:
                return False
        tog = part.get("toggle")
        if isinstance(tog, dict):
            c = st.ctl.get(tog.get("control"))
            if c is None:
                return False
            shown = tog.get("shown_at")
            vals = shown if isinstance(shown, list) else [shown]
            hit = False
            for v in vals:
                if isinstance(v, int) and not isinstance(v, bool):
                    if c.get("kind") == "bool" and c.get("bit") == v:
                        hit = True
                else:
                    if c.get("label") == v:
                        hit = True
            if not hit:
                return False
        return True

    def eval_dep(self, rec, st, E, pbk):
        dep = rec.obj
        else_out = dep.get("else")
        if else_out is None:
            else_out = "dont_care" if rec.origin == "fragment" else "baseline"
        when = dep.get("when")
        ast = self._safe_parse(when) if when is not None else ("true",)
        if ast is None:
            return else_out
        if not eval_cond(ast, st, E, pbk):
            return else_out
        if "expect_by_leader" in dep:
            leader = self._leader_of(ast, st, E, pbk)
            if leader is None:
                return else_out
            ebl = dep.get("expect_by_leader") or {}
            return ebl.get(leader, else_out)
        if "cases" in dep:
            for c in dep.get("cases") or []:
                if not isinstance(c, dict):
                    continue
                cast = self._safe_parse(c.get("when"))
                if cast is not None and eval_cond(cast, st, E, pbk):
                    return c.get("expect", else_out)
            return else_out
        if "expect" in dep:
            return dep["expect"]
        return else_out

    def _leader_of(self, ast, st, E, pbk):
        for item in top_level_conjuncts(ast):
            if item[0] == "chain":
                for ref in item[1]:
                    if _vis_ref(ref, st, E, pbk):
                        return ref
                return None
        return None

    # -- 维依赖分析 -------------------------------------------------------
    def part_dims(self, pid):
        if pid in self._part_dims_cache:
            return self._part_dims_cache[pid]
        if pid in self._part_dims_inprog:
            return set()
        self._part_dims_inprog.add(pid)
        dims = set()
        if pid.startswith("any."):
            kind = pid[4:]
            for p in self.parts_by_kind().get(kind, ()):
                dims |= self.part_dims(p)
        else:
            rec = self.parts_by_id.get(pid)
            if rec:
                part = rec.obj
                if part.get("outfit"):
                    dims.add("outfit")
                if part.get("slot"):
                    dims.add("slot:" + part["slot"])
                tog = part.get("toggle")
                if isinstance(tog, dict) and tog.get("control"):
                    dims.add("ctl:" + tog["control"])
                for dep in self.deps:
                    tgt = dep.obj.get("target")
                    if isinstance(tgt, dict) and tgt.get("part") == pid and \
                            "key" not in tgt and "keys" not in tgt and \
                            "submesh" not in tgt:
                        dims |= self.dep_activity_dims(dep)
        self._part_dims_inprog.discard(pid)
        self._part_dims_cache[pid] = dims
        return dims

    def cond_dims(self, ast):
        if ast is None:
            return set()
        tag = ast[0]
        if tag in ("true", "false"):
            return set()
        if tag in ("vis", "chain"):
            dims = set()
            refs = ast[1] if tag == "chain" else (ast[1],)
            for r in refs:
                dims |= self.part_dims(r)
            return dims
        if tag == "slot":
            return {"slot:" + ast[1]}
        if tag == "outfit":
            return {"outfit"}
        if tag == "ctl":
            return {"ctl:" + ast[1]}
        if tag == "param":
            return {self.dim_for_param(ast[1])}
        if tag in ("pose", "pose_tag"):
            return {"pose"}
        if tag == "body":
            return {"axis:" + ast[1]}
        if tag == "not":
            return self.cond_dims(ast[1])
        if tag in ("and", "or"):
            dims = set()
            for x in ast[1]:
                dims |= self.cond_dims(x)
            return dims
        return set()

    def dep_activity_dims(self, rec):
        dims = set()
        for rel, text in self.dep_cond_fields(rec):
            dims |= self.cond_dims(self._safe_parse(text))
        return dims

    # -- 入口 -------------------------------------------------------------
    def run(self):
        if self.fragment_only:
            self._merge_fragment_only()
            self.compute_supersedes_fragment()
            # 片段单独校验只跑片段内能判的规则（GRAMMAR §5 末段）
            for fn in (self.check_sem01, self.check_sem02_03, self.check_sem04,
                       self.check_sem05, self.check_sem06, self.check_sem09,
                       self.check_sem10, self.check_sem11, self.check_sem13,
                       self.check_sem19):
                fn()
            return self
        self.load_includes()
        self.merge()
        self.compute_geo()
        self.compute_supersedes()
        self.build_dim_values()
        self.check_sem01()
        self.check_sem02_03()
        self.check_sem04()
        self.check_sem05()
        self.check_sem06()
        self.check_sem07()
        self.check_sem08()
        self.check_sem09()
        self.check_sem10()
        self.check_sem11()
        self.check_sem12()
        self.check_sem13()
        self.check_sem14()
        self.check_sem15()
        self.check_sem16()
        self.check_sem17()
        self.check_sem18()
        self.check_sem19()
        self.check_sem20()
        self.check_sem21()
        self.check_sem22()
        self.check_sem23()
        self.check_sem24()
        return self

    def _merge_fragment_only(self):
        for i, part in enumerate(self.data.get("parts") or []):
            if isinstance(part, dict) and part.get("id") is not None:
                self._put_part(PartRec(dict(part), part["id"], "fragment",
                                       self.pfx("parts", str(i)), local_index=i))
        for i, dep in enumerate(self.data.get("deps") or []):
            if isinstance(dep, dict) and dep.get("id") is not None:
                self._put_dep(DepRec(dict(dep), dep["id"], "fragment",
                                     self.pfx("deps", str(i)), local_index=i))
        for i, rec in enumerate(self.deps):
            rec.order = i

    def compute_supersedes_fragment(self):
        ids = set(self.deps_by_id)
        for rec in self.deps:
            for k, sid in enumerate(rec.obj.get("supersedes") or []):
                if sid == rec.id:
                    self.add("SEM-24", self.rec_path(rec, "supersedes", str(k)),
                             "supersedes 不能取代自己")
                elif sid not in ids:
                    self.add("SEM-24", self.rec_path(rec, "supersedes", str(k)),
                             "supersedes 引用不存在的依赖 %r" % sid)
                else:
                    self.superseded.add(sid)
                    self.superseded_by.setdefault(sid, []).append(rec.id)

    # ===================================================================
    # SEM 规则
    # ===================================================================
    def iter_conditions(self):
        for rec in self.deps:
            for rel, text in self.dep_cond_fields(rec):
                yield ("dep", rec, rel, text)
        for i, w in enumerate(self.data.get("waivers") or []):
            if isinstance(w, dict) and "states" in w:
                yield ("waiver", i, None, w["states"])

    def check_sem01(self):
        # 部件/依赖 id 唯一（重复信息在 merge 阶段记录）
        for kind, path, msg in getattr(self, "id_dups", []):
            self.add("SEM-01", path, msg)
        if self.fragment_only:
            return
        # 手写 geo. 开头的 dep id 必须恰好是某个会生成的 id
        for rec in self.deps:
            if rec.origin != "declared":
                continue
            if not rec.id.startswith("geo."):
                continue
            if rec.id not in self.generated_geo_ids:
                self.add("SEM-01", self.rec_path(rec, "id"),
                         "手写 geo. 开头的 id 不是任何会生成的几何项：%s" % rec.id)

    def _check_part_ref(self, ref, path, fragment_mode):
        if ref.startswith("any."):
            kind = ref[4:]
            if kind not in _KIND_VOCAB:
                self.add("SEM-03", path, "any.<kind> 的 kind 不在词表：%r" % kind)
                return False
            return True
        if ref not in self.parts_by_id:
            self.add("SEM-03", path, "条件引用不存在的部件：%r" % ref)
            return False
        return True

    def _check_pose_ref(self, pid, path, rule="SEM-03"):
        base = base_pose_id(pid)
        frame = None
        if "@" in pid:
            try:
                frame = int(pid.rsplit("@", 1)[1])
            except ValueError:
                self.add(rule, path, "姿势帧号非法：%r" % pid)
                return
            if frame > 5:
                self.add(rule, path, "姿势帧号 > 5：%r" % pid)
                return
        if self.pose_ids is not None:
            if pid in self.pose_ids or base in self.pose_ids:
                return
            self.add(rule, path, "姿势 id 不在姿势库：%r" % pid)
            return
        if base.startswith("proxy_"):
            if base not in PROXY_POSES:
                self.add(rule, path, "proxy 姿势 id 不在 SDK 清单：%r" % base)
            elif frame is not None and base[len("proxy_"):] not in PROXY_MULTIFRAME:
                self.add(rule, path, "该 proxy 不是多帧 clip，不能带 @：%r" % pid)
        elif base.startswith("go_"):
            if base not in GO_POSES:
                self.add(rule, path, "go_ 姿势 id 不在 GoGo 清单：%r" % base)
        elif base.startswith("B_"):
            if base not in _B_SWEEP and base not in _B_EXTREME and \
                    base not in ("B_" + c for c in _B_COMBOS):
                self.add(rule, path, "库 B 姿势 id 不在内置清单：%r" % base)
        elif base.startswith("C_emote_"):
            if base not in GM_EMOTES:
                self.add(rule, path, "GM 表情 id 不在清单：%r" % base)
        elif base.startswith("C_go_"):
            if base not in ("C_" + m for m in GO_MOTIONS):
                self.add(rule, path, "GoGo 动作 id 不在清单：%r" % base)
        elif base.startswith("C_extra_"):
            self.add(rule, path, "C_extra_ 离线查不了（只出警告）", severity="warning")
        else:
            self.add(rule, path, "工程私有姿势离线查不了（只出警告）", severity="warning")

    def _check_pose_tag(self, tag, path, rule="SEM-03"):
        if tag not in POSE_TAGS:
            self.add(rule, path, "pose_tag 不在 tag 词表：%r" % tag)

    def _param_universe(self):
        uni = set(_VRC_BUILTIN_PARAMS)
        outfit = self.menu.get("outfit") or {}
        if outfit.get("param"):
            uni.add(outfit["param"])
        for c in (self.menu.get("slots") or {}).values():
            if isinstance(c, dict) and c.get("param"):
                uni.add(c["param"])
        for c in (self.menu.get("controls") or {}).values():
            if isinstance(c, dict) and c.get("param"):
                uni.add(c["param"])
        for ax in (self.data.get("body_axes") or {}).values():
            if isinstance(ax, dict) and ax.get("param"):
                uni.add(ax["param"])
        return uni

    def _check_cond_refs(self, ast, path, fragment_mode):
        tag = ast[0]
        if tag in ("and", "or"):
            for x in ast[1]:
                self._check_cond_refs(x, path, fragment_mode)
            return
        if tag == "not":
            self._check_cond_refs(ast[1], path, fragment_mode)
            return
        if tag in ("true", "false"):
            return
        if fragment_mode and tag not in ("vis", "chain", "pose", "pose_tag"):
            self.add("SEM-03", path,
                     "片段里的条件只许 vis/chain/pose/pose_tag/true/false（出现 %s）" % tag)
            return
        if tag == "vis":
            self._check_part_ref(ast[1], path, fragment_mode)
        elif tag == "chain":
            for r in ast[1]:
                self._check_part_ref(r, path, fragment_mode)
        elif tag == "slot":
            if ast[1] not in (self.menu.get("slots") or {}):
                self.add("SEM-03", path, "slot() 引用不存在的部位开关：%r" % ast[1])
        elif tag == "outfit":
            labels = set((self.menu.get("outfit") or {}).get("labels") or [])
            for lab in ast[2]:
                if lab not in labels:
                    self.add("SEM-03", path, "outfit 标签不在 menu.outfit.labels：%r" % lab)
        elif tag == "ctl":
            c = (self.menu.get("controls") or {}).get(ast[1])
            if c is None:
                self.add("SEM-03", path, "ctl() 引用不存在的控件：%r" % ast[1])
            elif c.get("type") == "float":
                self.add("SEM-03", path, "float 控件不能用 ctl()：%r" % ast[1])
            else:
                labs = c.get("labels") or []
                n = len(labs)
                for v in ast[3]:
                    if v[0] == "slot":
                        if not (0 <= v[1] < n):
                            self.add("SEM-03", path, "ctl() 槽号超出范围：#%d" % v[1])
                    elif v[0] == "bit":
                        if c.get("type") == "bool":
                            pass
                        elif not (0 <= v[1] < n):
                            self.add("SEM-03", path, "ctl() 取值超出范围：%r" % (v[1],))
                    else:
                        if v[1] not in labs:
                            self.add("SEM-03", path,
                                     "ctl() 的值不是该控件的标签：%r" % v[1])
        elif tag == "param":
            if ast[1] not in self._param_universe():
                self.add("SEM-03", path,
                         "param() 既不是菜单参数也不是内置参数：%r" % ast[1])
        elif tag == "pose":
            for pid in ast[2]:
                self._check_pose_ref(pid, path)
        elif tag == "pose_tag":
            for t in ast[2]:
                self._check_pose_tag(t, path)
        elif tag == "body":
            if ast[1] not in (self.data.get("body_axes") or {}):
                self.add("SEM-03", path, "body.<轴> 未在 body_axes 定义：%r" % ast[1])

    def check_sem02_03(self):
        for kind, rec, rel, text in self.iter_conditions():
            if kind == "dep":
                path = self.rec_path(rec, *rel)
            else:
                path = self.pfx("waivers", str(rec), "states")
            try:
                ast = parse_cond(text)
            except CondError as exc:
                self.add("SEM-02", path, "条件语法错：%s" % exc)
                continue
            # SEM-02：chain ≥ 2 成员
            for ch in cond_chain_atoms(ast):
                if len(ch[1]) < 2:
                    self.add("SEM-02", path, "chain 至少两个成员（EBNF）")
            self._check_cond_refs(ast, path, self.fragment_only)

    def check_sem04(self):
        for rec in self.deps:
            pm = self._safe_parse(rec.obj.get("when")) if rec.obj.get("when") else None
            if pm is not None:
                for ch in cond_chain_atoms(pm):
                    members = list(ch[1])
                    if len(members) != len(set(members)):
                        self.add("SEM-04", self.rec_path(rec, "when"), "chain 成员重复")
            if "expect_by_leader" not in rec.obj:
                continue
            if pm is None:
                self.add("SEM-04", self.rec_path(rec, "when"),
                         "用 expect_by_leader 时必须写 when: chain(...)")
                continue
            chains = [c for c in top_level_conjuncts(pm) if c[0] == "chain"]
            if len(chains) != 1:
                self.add("SEM-04", self.rec_path(rec, "when"),
                         "expect_by_leader 的 chain 必须是 when 的顶层合取项（恰一个）")
                continue
            members = list(chains[0][1])
            keys = list((rec.obj.get("expect_by_leader") or {}).keys())
            for m in members:
                if m not in keys:
                    self.add("SEM-04", self.rec_path(rec, "expect_by_leader"),
                             "expect_by_leader 缺 chain 成员：%s" % m)
            for k in keys:
                if k not in members:
                    self.add("SEM-04", self.rec_path(rec, "expect_by_leader", k),
                             "expect_by_leader 的键不是 chain 成员：%s" % k)

    def _target_path(self, rec, tgt_index):
        if tgt_index is None:
            return self.rec_path(rec, "target")
        return self.rec_path(rec, "targets", str(tgt_index))

    def check_sem05(self):
        body = self.avatar.get("body")
        smr_paths = self.all_smr_paths()
        for rec in self.deps:
            targets = []
            if isinstance(rec.obj.get("target"), dict):
                targets.append((None, rec.obj["target"]))
            for j, t in enumerate(rec.obj.get("targets") or []):
                if isinstance(t, dict):
                    targets.append((j, t))
            for j, tgt in targets:
                base = self._target_path(rec, j)
                if "part" in tgt:
                    if tgt["part"] not in self.parts_by_id:
                        self.add("SEM-05", base + ["part"],
                                 "target.part 不存在：%r" % tgt["part"])
                    elif ("key" in tgt or "keys" in tgt) and \
                            not self.part_smr_meshes(tgt["part"]):
                        self.add("SEM-05", base + ["part"],
                                 "带 key 的部件没有 smr 物体：%r" % tgt["part"])
                if "mesh" in tgt and not self.fragment_only:
                    m = tgt["mesh"]
                    if m != body and m not in smr_paths:
                        self.add("SEM-05", base + ["mesh"],
                                 "target.mesh 既不是 avatar.body 也不是任何部件的 smr 物体：%r" % m)
            # sync.from.mesh
            for rel, outcome in dep_outcomes(rec.obj):
                if isinstance(outcome, dict) and isinstance(outcome.get("sync"), dict):
                    fm = (outcome["sync"].get("from") or {}).get("mesh")
                    if fm is not None and not self.fragment_only and \
                            fm != body and fm not in smr_paths:
                        self.add("SEM-05", self.rec_path(rec, *(rel + ["sync", "from", "mesh"])),
                                 "sync.from.mesh 不是 smr 网格：%r" % fm)
        # body_axes
        for name, ax in (self.data.get("body_axes") or {}).items():
            if isinstance(ax, dict) and isinstance(ax.get("key"), dict):
                m = ax["key"].get("mesh")
                if m is not None and not self.fragment_only and \
                        m != body and m not in smr_paths:
                    self.add("SEM-05", self.pfx("body_axes", name, "key", "mesh"),
                             "body_axes.%s.key.mesh 不是 smr 网格：%r" % (name, m))

    def _outcome_kind(self, outcome):
        if not isinstance(outcome, dict):
            return None
        for k in ("value", "range", "values", "not_written", "sync", "hidden", "shown",
                  "deleted", "variant", "geo", "grab", "no_writer_other_than", "pending",
                  "class"):
            if k in outcome:
                return k
        return None

    def _check_outcome_shape(self, rec, rel, outcome, base_path):
        kind = self._outcome_kind(outcome)
        if kind is None or kind == "pending":
            return
        targets = []
        if isinstance(rec.obj.get("target"), dict):
            targets.append(rec.obj["target"])
        for t in rec.obj.get("targets") or []:
            if isinstance(t, dict):
                targets.append(t)
        has_part = lambda t: "part" in t
        has_keys = lambda t: ("key" in t or "keys" in t)
        has_submesh = lambda t: "submesh" in t
        bad = False
        msg = ""
        for t in targets:
            if kind in ("hidden", "shown", "variant", "geo"):
                if not has_part(t) or has_keys(t) or has_submesh(t):
                    bad = True
                    msg = "%s 要 {part} 且不带键与 submesh" % kind
            elif kind == "grab":
                if not has_part(t) or has_keys(t):
                    bad = True
                    msg = "grab 要 {part} 或 {part, submesh}，不带键"
            elif kind == "values":
                if has_keys(t):
                    bad = True
                    msg = "values 时 target 不带 key/keys"
            else:  # value/range/class/not_written/sync/deleted/no_writer_other_than
                if not has_keys(t):
                    bad = True
                    msg = "%s 要带 key 或 keys" % kind
            if has_submesh(t) and kind != "grab":
                bad = True
                msg = "{part, submesh} 只配 grab"
            if bad:
                break
        if bad:
            self.add("SEM-06", self.rec_path(rec, *rel), msg)

    def check_sem06(self):
        for rec in self.deps:
            for rel, outcome in dep_outcomes(rec.obj):
                self._check_outcome_shape(rec, rel, outcome, None)

    def _profile_keys(self):
        if not isinstance(self.profile, dict):
            return None
        keys = set()
        kc = self.profile.get("key_classes") or {}
        if isinstance(kc, dict):
            for cls, group in kc.items():
                if isinstance(group, dict):
                    keys.update(group.keys())
        for grp in ("baseline", "key_baseline", "keys"):
            d = self.profile.get(grp)
            if isinstance(d, dict):
                keys.update(d.keys())
        return keys

    def _profile_all_keys(self):
        """档案全量键表 `all_keys:`（任务 AQ）。是 list 才认（空表也算给了键表，
        代表身体确实没有键）；缺字段或非 list 返回 None（走旧的 key_classes 警告口径）。"""
        if not isinstance(self.profile, dict):
            return None
        v = self.profile.get("all_keys")
        if isinstance(v, list):
            return [k for k in v if isinstance(k, str)]
        return None

    def _profile_baseline(self, key):
        if not isinstance(self.profile, dict):
            return None
        for grp in ("baseline", "key_baseline"):
            d = self.profile.get(grp)
            if isinstance(d, dict) and key in d:
                v = d[key]
                if isinstance(v, (int, float)):
                    return float(v)
                if isinstance(v, dict) and isinstance(v.get("value"), (int, float)):
                    return float(v["value"])
        return None

    def _body_key_refs(self):
        """声明里目标 mesh（或 part 解析到的第一个 SMR 路径）等于身体网格的键引用。
        产出 (rec, target_index, 路径尾, 键名)；`check_sem07` 与 selftest 共用。"""
        body = self.avatar.get("body")
        for rec in self.deps:
            targets = []
            if isinstance(rec.obj.get("target"), dict):
                targets.append((None, rec.obj["target"]))
            for j, t in enumerate(rec.obj.get("targets") or []):
                if isinstance(t, dict):
                    targets.append((j, t))
            for j, tgt in targets:
                m = tgt.get("mesh")
                if m is None and tgt.get("part"):
                    meshes = self.part_smr_meshes(tgt["part"])
                    m = meshes[0] if meshes else None
                if m != body:
                    continue
                if "key" in tgt:
                    yield rec, j, ["key"], tgt["key"]
                for i, k in enumerate(tgt.get("keys") or []):
                    yield rec, j, ["keys", str(i)], k

    def check_sem07(self):
        all_keys = self._profile_all_keys()
        keys = set(all_keys) if all_keys is not None else self._profile_keys()
        if keys is None:
            self.add_skip("SEM-07", "未提供素体档案（--profile），身体键存在性未核")
            return
        # 有 all_keys：它是身体网格全量键表，键不存在 → error（key_classes 只用于分类）；
        # 没有 all_keys：维持旧口径，只出 warning（档案还没有 schema，见 CHANGELOG 遗留 2）。
        strict = all_keys is not None
        for rec, j, sub, k in self._body_key_refs():
            if k in keys:
                continue
            if strict:
                self.add("SEM-07", self._target_path(rec, j) + sub,
                         "身体键不在素体档案 all_keys 里：%r（档案已给全量键表，视为不存在）" % k)
            else:
                self.add("SEM-07", self._target_path(rec, j) + sub,
                         "身体键不在素体档案里（降为警告）：%r" % k,
                         severity="warning")

    def check_sem08(self):
        if self.fragment_only:
            return
        menu = self.menu
        for rec in self.parts:
            part = rec.obj
            outfit = part.get("outfit")
            if outfit:
                labels = set((menu.get("outfit") or {}).get("labels") or [])
                for lab in (outfit if isinstance(outfit, list) else [outfit]):
                    if lab not in labels:
                        self.add("SEM-08", self.rec_path(rec, "outfit"),
                                 "parts[].outfit 标签不在 menu.outfit.labels：%r" % lab)
            slot = part.get("slot")
            if slot and slot not in (menu.get("slots") or {}):
                self.add("SEM-08", self.rec_path(rec, "slot"),
                         "parts[].slot 不在 menu.slots：%r" % slot)
            tog = part.get("toggle")
            if isinstance(tog, dict):
                cname = tog.get("control")
                c = (menu.get("controls") or {}).get(cname)
                if c is None:
                    self.add("SEM-08", self.rec_path(rec, "toggle", "control"),
                             "toggle.control 不在 menu.controls：%r" % cname)
                else:
                    if c.get("type") == "float":
                        self.add("SEM-08", self.rec_path(rec, "toggle", "control"),
                                 "toggle.control 不能是 float 控件：%r" % cname)
                    labs = c.get("labels") or []
                    shown = tog.get("shown_at")
                    vals = shown if isinstance(shown, list) else [shown]
                    bad = []
                    for v in vals:
                        if isinstance(v, bool):
                            v = int(v)
                        if c.get("type") == "bool":
                            if not (isinstance(v, int) and v in (0, 1)):
                                bad.append(v)
                        else:
                            # int/float_slots：shown_at 必须是标签；裸 0/1 是给 bool 的
                            if isinstance(v, int) and not isinstance(v, bool):
                                bad.append(v)
                            elif v not in labs:
                                bad.append(v)
                    if bad:
                        self.add("SEM-08", self.rec_path(rec, "toggle", "shown_at"),
                                 "toggle.shown_at 不是该控件的标签：%r" % (bad,))

    def check_sem09(self):
        for rec in self.parts:
            part = rec.obj
            alt = part.get("alt_of")
            if not alt:
                continue
            main = self.parts_by_id.get(alt)
            if main is None:
                self.add("SEM-09", self.rec_path(rec, "alt_of"),
                         "alt_of 指向不存在的部件：%r" % alt)
                continue
            if main.obj.get("alt_of"):
                self.add("SEM-09", self.rec_path(rec, "alt_of"),
                         "alt_of 指向的部件自身也是备选件：%r" % alt)
            if part.get("outfit") and main.obj.get("outfit"):
                a = part["outfit"] if isinstance(part["outfit"], list) else [part["outfit"]]
                b = main.obj["outfit"] if isinstance(main.obj["outfit"], list) else [main.obj["outfit"]]
                if set(a) != set(b):
                    self.add("SEM-09", self.rec_path(rec, "outfit"),
                             "备选件 outfit 与主件不同")

    def check_sem10(self):
        for rec in self.deps:
            for rel, outcome in dep_outcomes(rec.obj):
                if not isinstance(outcome, dict) or not isinstance(outcome.get("variant"), dict):
                    continue
                var = outcome["variant"]
                tgt = rec.obj.get("target")
                if not isinstance(tgt, dict) or "part" not in tgt:
                    continue
                target = tgt["part"]
                group = {target}
                for pr in self.parts:
                    if pr.obj.get("alt_of") == target:
                        group.add(pr.id)
                if len(group) < 2:
                    self.add("SEM-10", self.rec_path(rec, *(rel + ["variant"])),
                             "变体组少于 2 件")
                for j, opt in enumerate(var.get("options") or []):
                    if not isinstance(opt, dict):
                        continue
                    use = opt.get("use")
                    if use not in group:
                        self.add("SEM-10",
                                 self.rec_path(rec, *(rel + ["variant", "options", str(j), "use"])),
                                 "variant.options[].use 不在变体组：%r" % use)

    def check_sem11(self):
        seen = {}
        for rec in self.parts:
            for j, o in enumerate(rec.obj.get("objects") or []):
                if not isinstance(o, dict):
                    continue
                key = (o.get("path"), o.get("submesh"))
                if key in seen:
                    self.add("SEM-11", self.rec_path(rec, "objects", str(j), "path"),
                             "同一物体属于两个部件：%r" % (key[0],))
                else:
                    seen[key] = rec.id

    def check_sem12(self):
        if self.inventory is None:
            self.add_skip("SEM-12", "未提供 T-05 盘点（--inventory），物体与材质槽未核")
            return
        renderers = {}
        try:
            for av in self.inventory.get("avatars") or []:
                for r in av.get("renderers") or []:
                    if isinstance(r, dict) and r.get("path"):
                        renderers[r["path"]] = r
        except AttributeError:
            renderers = {}
        if not renderers:
            self.add_skip("SEM-12", "inventory.json 里没有 renderers，无法核对")
            return
        want_type = {"smr": "SkinnedMeshRenderer", "mesh": "MeshRenderer"}
        for rec in self.parts:
            for j, o in enumerate(rec.obj.get("objects") or []):
                if not isinstance(o, dict):
                    continue
                r = renderers.get(o.get("path"))
                if r is None:
                    self.add("SEM-12", self.rec_path(rec, "objects", str(j), "renderer"),
                             "objects[].path 不在盘点里：%r（降为警告）" % o.get("path"),
                             severity="warning")
                    continue
                if r.get("type") != want_type.get(o.get("renderer")):
                    self.add("SEM-12", self.rec_path(rec, "objects", str(j), "renderer"),
                             "渲染器类型与盘点不一致：声明 %s / 盘点 %s"
                             % (o.get("renderer"), r.get("type")))
                sm = o.get("submesh")
                if sm is not None:
                    n = len(r.get("material_slots") or []) or r.get("submesh_count") or 0
                    if n and sm >= n:
                        self.add("SEM-12", self.rec_path(rec, "objects", str(j), "submesh"),
                                 "submesh 不小于材质槽数：%d / %d" % (sm, n))
        for rec in self.deps:
            targets = []
            if isinstance(rec.obj.get("target"), dict):
                targets.append((None, rec.obj["target"]))
            for j, t in enumerate(rec.obj.get("targets") or []):
                if isinstance(t, dict):
                    targets.append((j, t))
            for j, tgt in targets:
                sm = tgt.get("submesh")
                if sm is None or not tgt.get("part"):
                    continue
                counts = []
                for p in self.part_smr_meshes(tgt["part"]):
                    r = renderers.get(p)
                    if r:
                        counts.append(len(r.get("material_slots") or [])
                                      or r.get("submesh_count") or 0)
                if counts and sm >= min(counts):
                    self.add("SEM-12", self._target_path(rec, j) + ["submesh"],
                             "target.submesh 不小于材质槽数：%d / %d" % (sm, min(counts)))

    def check_sem13(self):
        for kind, rec, rel, text in self.iter_conditions():
            if kind == "dep":
                path = self.rec_path(rec, *rel)
            else:
                path = self.pfx("waivers", str(rec), "states")
            ast = self._safe_parse(text)
            if ast is None:
                continue
            for axis, lo, hi, _lc, _hc in cond_intervals(ast):
                if lo > hi:
                    self.add("SEM-13", path, "条件区间 lo > hi")
        for rec in self.deps:
            for rel, outcome in dep_outcomes(rec.obj):
                if not isinstance(outcome, dict):
                    continue
                if isinstance(outcome.get("range"), list) and len(outcome["range"]) == 2:
                    if outcome["range"][0] > outcome["range"][1]:
                        self.add("SEM-13", self.rec_path(rec, *(rel + ["range"])),
                                 "range 的 lo > hi")
                if isinstance(outcome.get("deleted"), dict):
                    d = outcome["deleted"]
                    if "min_ratio" in d and "max_ratio" in d and d["min_ratio"] > d["max_ratio"]:
                        self.add("SEM-13",
                                 self.rec_path(rec, *(rel + ["deleted", "min_ratio"])),
                                 "deleted min_ratio > max_ratio")
                sync = outcome.get("sync")
                if isinstance(sync, dict) and isinstance(sync.get("map"), list):
                    srcs = [p[0] for p in sync["map"] if isinstance(p, (list, tuple)) and p]
                    if any(b <= a for a, b in zip(srcs, srcs[1:])):
                        self.add("SEM-13", self.rec_path(rec, *(rel + ["sync", "map"])),
                                 "sync.map 的源值必须严格升序")

    def check_sem14(self):
        def check_ctrl(ctrl, path):
            t = ctrl.get("type")
            labels = ctrl.get("labels") or []
            d = ctrl.get("default")
            if d is None:
                return
            if t == "float_slots":
                n = len(labels)
                if n == 0:
                    return
                if not any(abs(float(d) - i / n) <= 1e-6 for i in range(n)):
                    self.add("SEM-14", path, "float_slots 的 default 不在任何 i/n 上")
            elif t == "int":
                if not (isinstance(d, int) and not isinstance(d, bool)
                        and 0 <= d < len(labels)):
                    self.add("SEM-14", path, "int 的 default 不在 0…n−1 上")
            elif t == "float":
                if not (0.0 <= float(d) <= 1.0):
                    self.add("SEM-14", path, "float 的 default 不在 [0,1]")
            elif t == "bool":
                if d not in (0, 1):
                    self.add("SEM-14", path, "bool 的 default 不是 0/1")

        outfit = self.menu.get("outfit")
        if isinstance(outfit, dict):
            check_ctrl(outfit, self.pfx("menu", "outfit", "default"))
        for name, c in (self.menu.get("slots") or {}).items():
            if isinstance(c, dict):
                check_ctrl(c, self.pfx("menu", "slots", name, "default"))
        for name, c in (self.menu.get("controls") or {}).items():
            if isinstance(c, dict):
                check_ctrl(c, self.pfx("menu", "controls", name, "default"))

    def _find_control_by_param(self, param):
        outfit = self.menu.get("outfit") or {}
        if outfit.get("param") == param:
            return outfit, "outfit"
        for name, c in (self.menu.get("slots") or {}).items():
            if isinstance(c, dict) and c.get("param") == param:
                return c, "slot:" + name
        for name, c in (self.menu.get("controls") or {}).items():
            if isinstance(c, dict) and c.get("param") == param:
                return c, "ctl:" + name
        return None, None

    def check_sem15(self):
        for rec in self.deps:
            for i, seg in enumerate(rec.obj.get("roundtrip") or []):
                path = self.rec_path(rec, "roundtrip", str(i))
                if not isinstance(seg, str):
                    self.add("SEM-15", path, "往返段不是字符串")
                    continue
                try:
                    parsed = parse_roundtrip(seg)
                except RoundtripError as exc:
                    self.add("SEM-15", path, "往返语法错：%s" % exc)
                    continue
                for param, values in parsed:
                    ctrl, _ = self._find_control_by_param(param)
                    if ctrl is None:
                        self.add("SEM-15", path, "往返参数不在 menu 里：%r" % param)
                        continue
                    t = ctrl.get("type")
                    labels = ctrl.get("labels") or []
                    n = len(labels)
                    for v in values:
                        if t == "bool":
                            if v[0] != "num" or float(v[1]) not in (0.0, 1.0):
                                self.add("SEM-15", path, "bool 控件只许 0/1：%r" % (v,))
                        elif t in ("int", "float_slots"):
                            if v[0] == "num":
                                self.add("SEM-15", path,
                                         "int/float_slots 不许写裸数（写标签或 #i）：%r" % (v,))
                            elif v[0] == "slot":
                                if not (0 <= v[1] < n):
                                    self.add("SEM-15", path, "往返槽号超出档数：#%d" % v[1])
                            else:
                                if v[1] not in labels:
                                    self.add("SEM-15", path,
                                             "往返标签不在该控件 labels：%r" % v[1])
                        elif t == "float":
                            if v[0] != "num" or not (0.0 <= float(v[1]) <= 1.0):
                                self.add("SEM-15", path, "float 控件只许 [0,1] 内的数：%r" % (v,))

    def check_sem16(self):
        for i, w in enumerate(self.data.get("waivers") or []):
            if not isinstance(w, dict):
                continue
            if "dep" in w:
                did = w["dep"]
                if did not in self.deps_by_id:
                    self.add("SEM-16", self.pfx("waivers", str(i), "dep"),
                             "豁免指向不存在的 dep：%r" % did)
                elif did in self.superseded:
                    self.add("SEM-16", self.pfx("waivers", str(i), "dep"),
                             "被 supersedes 取代的依赖不能再豁免：%r" % did)
            if "rule" in w:
                for j, pid in enumerate(w.get("parts") or []):
                    if pid not in self.parts_by_id:
                        self.add("SEM-16", self.pfx("waivers", str(i), "parts", str(j)),
                                 "rule 豁免的部件不存在：%r" % pid)

    def check_sem17(self):
        if self.fragment_only:
            return
        gd = self.data.get("geo_defaults")
        if not isinstance(gd, dict):
            return
        for i, pid in enumerate(gd.get("exclude") or []):
            if pid not in self.parts_by_id:
                self.add("SEM-17", self.pfx("geo_defaults", "exclude", str(i)),
                         "geo_defaults.exclude 里的部件不存在：%r" % pid)

    def check_sem18(self):
        # 已在 load_includes 中报错
        return

    def check_sem19(self):
        for rec in self.deps:
            dep = rec.obj
            if dep.get("human"):
                continue
            need = False
            for rel, outcome in dep_outcomes(dep):
                if rel[0] == "expect":
                    continue  # schema 管
                if isinstance(outcome, dict) and outcome.get("pending") is True:
                    need = True
            if need:
                self.add("SEM-19", self.rec_path(rec, "human"),
                         "cases/else/expect_by_leader 里用 pending 时 dep 必须有 human")

    def check_sem20(self):
        seen = {}
        outfit = self.menu.get("outfit") or {}
        if outfit.get("param") is not None:
            seen[outfit["param"]] = self.pfx("menu", "outfit", "param")
        for name, c in (self.menu.get("slots") or {}).items():
            if not isinstance(c, dict) or c.get("param") is None:
                continue
            p = c["param"]
            path = self.pfx("menu", "slots", name, "param")
            if p in seen:
                self.add("SEM-20", path, "menu 里两个控件用了同一个参数：%r" % p)
            else:
                seen[p] = path
        for name, c in (self.menu.get("controls") or {}).items():
            if not isinstance(c, dict) or c.get("param") is None:
                continue
            p = c["param"]
            path = self.pfx("menu", "controls", name, "param")
            if p in seen:
                self.add("SEM-20", path, "menu 里两个控件用了同一个参数：%r" % p)
            else:
                seen[p] = path

    def check_sem21(self):
        if not self.geo_on():
            return
        for rec in self.parts:
            part = rec.obj
            if part.get("fit") in ("closed", "tight") and not (part.get("covers") or []):
                self.add("SEM-21", self.rec_path(rec, "covers"),
                         "fit 为 closed/tight 且 covers 为空（不生成几何项）",
                         severity="warning")

    # -- SEM-22 期望冲突 --------------------------------------------------
    def _group_deps(self):
        """按 (mesh,key) 找出有 ≥2 个 dep 可能写入的键。"""
        groups = {}
        for rec in self.deps:
            if rec.id in self.superseded:
                continue
            keys = set()
            for rel, outcome in dep_outcomes(rec.obj):
                for mk in self._entry_keys(rec, outcome):
                    keys.add(mk)
            for mk in keys:
                groups.setdefault(mk, []).append(rec)
        return {k: v for k, v in groups.items() if len(v) >= 2}

    def _entry_keys(self, rec, outcome):
        out = []
        targets = _dep_targets(rec.obj)
        for tgt in targets:
            meshes = []
            if tgt.get("mesh"):
                meshes.append(tgt["mesh"])
            elif tgt.get("part"):
                meshes.extend(self.part_smr_meshes(tgt["part"]))
            if not meshes:
                continue
            keys = []
            if isinstance(outcome, dict):
                if isinstance(outcome.get("values"), dict):
                    keys.extend(outcome["values"].keys())
                elif "value" in outcome or "range" in outcome or "class" in outcome:
                    if "key" in tgt:
                        keys.append(tgt["key"])
                    keys.extend(tgt.get("keys") or [])
            elif outcome == "baseline":
                if "key" in tgt:
                    keys.append(tgt["key"])
                keys.extend(tgt.get("keys") or [])
            for m in meshes:
                for k in keys:
                    out.append((m, k))
        return out

    def _numeric_of(self, rec, outcome, key):
        if isinstance(outcome, dict):
            tol = outcome.get("tol", 0.5)
            if "value" in outcome:
                v = float(outcome["value"])
                return (v - tol, v + tol)
            if isinstance(outcome.get("range"), list) and len(outcome["range"]) == 2:
                return (float(outcome["range"][0]), float(outcome["range"][1]))
            if isinstance(outcome.get("values"), dict) and key[1] in outcome["values"]:
                v = float(outcome["values"][key[1]])
                return (v - tol, v + tol)
            return None
        if outcome == "baseline":
            b = self._profile_baseline(key[1])
            if b is None:
                return None
            return (b - 0.5, b + 0.5)
        return None

    def _class_of(self, outcome):
        if isinstance(outcome, dict):
            return outcome.get("class")
        return None

    def _sem22_pairwise(self, act):
        for i in range(len(act)):
            for j in range(i + 1, len(act)):
                a, b = act[i], act[j]
                if a[0] is b[0]:
                    continue
                why = None
                if a[1] is not None and b[1] is not None:
                    if a[1][1] < b[1][0] - 1e-9 or b[1][1] < a[1][0] - 1e-9:
                        why = ("取值不相容：%r vs %r" % (a[1], b[1]))
                if a[2] and b[2] and a[2] != b[2]:
                    why = "键类别不同：%r vs %r" % (a[2], b[2])
                if why:
                    later = a[0] if a[0].order > b[0].order else b[0]
                    return (later, why)
        return None

    def _sem22_scan(self, groups, dims):
        """在给定维集合上枚举，返回 {key: (later_rec, why)}（每个键首个冲突）。"""
        pbk = self.parts_by_kind()
        found = {}
        keys = list(groups)
        for st in self.states_for(dims):
            E = self.compute_E(st, self.deps)
            for key in keys:
                if key in found:
                    continue
                act = []
                for rec in groups[key]:
                    outcome = self.eval_dep(rec, st, E, pbk)
                    num = self._numeric_of(rec, outcome, key)
                    cls = self._class_of(outcome)
                    if num is not None or cls is not None:
                        act.append((rec, num, cls))
                hit = self._sem22_pairwise(act)
                if hit:
                    found[key] = hit
            if len(found) == len(keys):
                break
        return found

    def check_sem22(self):
        """期望冲突：按 §6.1 枚举状态（维太大时才退到按组维，见 README）。"""
        groups = self._group_deps()
        if not groups:
            return
        all_dims = sorted(self.dim_values)
        total = 1
        for d in all_dims:
            total *= max(len(self.dim_values[d]), 1)
        if total <= 500000:
            found = self._sem22_scan(groups, all_dims)
        else:
            found = {}
            for key in sorted(groups, key=lambda k: str(k)):
                dims = set()
                for rec in groups[key]:
                    dims |= self.dep_activity_dims(rec)
                f = self._sem22_scan({key: groups[key]}, sorted(dims))
                if key in f:
                    found[key] = f[key]
        for key in sorted(found, key=lambda k: str(k)):
            rec, why = found[key]
            if rec.path_base is not None:
                path = self.rec_path(rec, "id")
            else:
                path = self.pfx("deps", str(rec.order), "id")
            self.add("SEM-22", path, "期望冲突：%s（网格 %s 键 %s）"
                     % (why, key[0], key[1]))

    def _check_pose_selector(self, sel, path, rule):
        if not isinstance(sel, str):
            return
        if sel.startswith("tag:"):
            self._check_pose_tag(sel[4:], path, rule)
        else:
            self._check_pose_ref(sel, path, rule)

    def check_sem23(self):
        for rec in self.parts:
            scope = rec.obj.get("pose_scope")
            if not isinstance(scope, dict):
                continue
            for grp in ("include", "exclude"):
                for j, sel in enumerate(scope.get(grp) or []):
                    self._check_pose_selector(
                        sel, self.rec_path(rec, "pose_scope", grp, str(j)), "SEM-23")
        for i, w in enumerate(self.data.get("waivers") or []):
            if not isinstance(w, dict) or "pose" not in w:
                continue
            pose = w["pose"]
            if isinstance(pose, list):
                for j, sel in enumerate(pose):
                    self._check_pose_selector(
                        sel, self.pfx("waivers", str(i), "pose", str(j)), "SEM-23")
            else:
                self._check_pose_selector(pose, self.pfx("waivers", str(i), "pose"),
                                          "SEM-23")

    def check_sem24(self):
        # 存在性/自取代/成环已在 compute_supersedes 里报
        return

    # -- 展开（decl.json） -------------------------------------------------
    def expand(self):
        if self.fragment_only:
            out = {"schema": FRAGMENT_ID}
            if "package" in self.data:
                out["package"] = _deep(self.data["package"])
            if "note" in self.data:
                out["note"] = self.data["note"]
            out["parts"] = [_expand_part(p) for p in
                            sorted(self.parts, key=lambda r: r.id)]
            out["deps"] = [_expand_dep(r, self) for r in
                           sorted(self.deps, key=lambda r: r.id)]
            return out
        out = {}
        for k, v in self.data.items():
            if k in ("includes", "parts", "deps"):
                continue
            out[k] = _deep(v)
        out["includes"] = []
        for rec in self.includes:
            if not rec.valid:
                continue
            spec = {"fragment": rec.path, "mount": rec.mount, "as": rec.as_}
            if rec.outfit is not None:
                spec["outfit"] = _deep(rec.outfit)
            out["includes"].append(spec)
        out["parts"] = [_expand_part(p) for p in sorted(self.parts, key=lambda r: r.id)]
        deps = []
        for rec in sorted(self.deps, key=lambda r: r.id):
            d = _expand_dep(rec, self)
            if rec.id in self.superseded:
                d["superseded_by"] = list(self.superseded_by.get(rec.id) or [])
            deps.append(d)
        out["deps"] = deps
        # 缺省写实
        if "geo_defaults" not in out or out["geo_defaults"] is True:
            out["geo_defaults"] = {k: v for k, v in _DEFAULT_GEO.items()}
        elif isinstance(out.get("geo_defaults"), dict):
            gd = dict(_DEFAULT_GEO)
            gd.update(out["geo_defaults"])
            out["geo_defaults"] = gd
        if "poses" not in out:
            out["poses"] = {"libraries": ["A", "B", "C"]}
        if "render" not in out:
            out["render"] = {"grab_point_min": 3050}
        if "roundtrip_default" not in out:
            out["roundtrip_default"] = {"history_k": 2,
                                        "templates": ["slot_1_0_1", "slot_0_1_0",
                                                      "outfit_A_B_A"]}
        return out


def _deep(v):
    return json.loads(json.dumps(v, ensure_ascii=False))


def _expand_part(rec):
    obj = _deep(rec.obj)
    obj["origin"] = rec.origin
    if rec.generated_from:
        obj["generated_from"] = rec.generated_from
    return obj


def _expand_dep(rec, validator):
    obj = _deep(rec.obj)
    if "when" not in obj:
        obj["when"] = "true"
    if "else" not in obj:
        obj["else"] = "dont_care" if rec.origin == "fragment" else "baseline"
    for rel, outcome in dep_outcomes(obj):
        if isinstance(outcome, dict):
            if ("value" in outcome or "values" in outcome) and "tol" not in outcome:
                outcome["tol"] = 0.5
    obj["origin"] = rec.origin
    if rec.generated_from:
        obj["generated_from"] = rec.generated_from
    if isinstance(obj.get("roundtrip"), list) and not obj["roundtrip"]:
        obj.pop("roundtrip", None)
    # 排序对象键无意义（json.dumps sort_keys 处理）
    return obj


def pointer_path(segs):
    return json_pointer(segs)


def base_pose_id(pid):
    return pid.split("@")[0]


def _slot_index_of_default(ctrl, dflt):
    labels = ctrl.get("labels") or []
    t = ctrl.get("type")
    if t == "int":
        try:
            v = int(dflt)
        except (TypeError, ValueError):
            return 0
        return min(max(v, 0), max(len(labels) - 1, 0))
    try:
        v = float(dflt)
    except (TypeError, ValueError):
        return 0
    n = len(labels)
    if n == 0:
        return 0
    return min(max(int(round(v * n)), 0), n - 1)


def _raw_of_slot(ctrl, idx):
    t = ctrl.get("type")
    if t == "int":
        return idx
    labels = ctrl.get("labels") or []
    n = len(labels)
    return (idx / n) if n else 0.0


def samples_for(constants, lo=0.0, hi=1.0):
    cs = sorted({float(c) for c in constants})
    if not cs:
        return [0.0, 0.5, 1.0]
    out = set()
    for c in cs:
        out.add(min(max(c, lo), hi))
    for a, b in zip(cs, cs[1:]):
        out.add(min(max((a + b) / 2.0, lo), hi))
    out.add(min(max(cs[0] - 1.0, lo), hi))
    out.add(min(max(cs[-1] + 1.0, lo), hi))
    return sorted(out)


def _has_pose_atom(ast):
    return bool(_pose_atoms(ast))


def _pose_atoms(ast):
    out = []
    stack = [ast]
    while stack:
        node = stack.pop()
        if node[0] in ("pose", "pose_tag"):
            out.append(node)
        elif node[0] in ("and", "or"):
            stack.extend(node[1])
        elif node[0] == "not":
            stack.append(node[1])
    return out


def _pose_atom_truth(atom, pid, tags):
    base = base_pose_id(pid)
    if atom[0] == "pose":
        ok = base in atom[2]
    else:
        ok = bool(tags & set(atom[2]))
    if atom[1] == "in":
        return ok
    return ok if atom[1] == "=" else not ok


def _dep_targets(dep):
    out = []
    if isinstance(dep.get("target"), dict):
        out.append(dep["target"])
    for t in dep.get("targets") or []:
        if isinstance(t, dict):
            out.append(t)
    return out


def dep_outcomes(dep):
    out = []
    if "expect" in dep:
        out.append((["expect"], dep["expect"]))
    for i, c in enumerate(dep.get("cases") or []):
        if isinstance(c, dict) and "expect" in c:
            out.append((["cases", str(i), "expect"], c["expect"]))
    if "expect_by_leader" in dep:
        for k, v in (dep.get("expect_by_leader") or {}).items():
            out.append((["expect_by_leader", k], v))
    if "else" in dep:
        out.append((["else"], dep["else"]))
    return out


def _rewrite_fragment_dep(dep, as_, did):
    obj = json.loads(json.dumps(dep, ensure_ascii=False))
    obj["id"] = did
    if "when" in obj:
        ast = None
        try:
            ast = parse_cond(obj["when"])
        except CondError:
            ast = None
        if ast is not None:
            obj["when"] = format_cond(rewrite_cond_refs(ast, as_))
    for i, c in enumerate(obj.get("cases") or []):
        if isinstance(c, dict) and "when" in c:
            try:
                ast = parse_cond(c["when"])
                c["when"] = format_cond(rewrite_cond_refs(ast, as_))
            except CondError:
                pass
    for rel, outcome in dep_outcomes(obj):
        if isinstance(outcome, dict) and isinstance(outcome.get("variant"), dict):
            for opt in outcome["variant"].get("options") or []:
                if isinstance(opt, dict) and "use" in opt and not opt["use"].startswith("any."):
                    opt["use"] = "%s.%s" % (as_, opt["use"])
    for tgt in _dep_targets(obj):
        if tgt.get("part") and not tgt["part"].startswith("any."):
            tgt["part"] = "%s.%s" % (as_, tgt["part"])
    if isinstance(obj.get("expect_by_leader"), dict):
        obj["expect_by_leader"] = {
            ("%s.%s" % (as_, k) if not k.startswith("any.") else k): v
            for k, v in obj["expect_by_leader"].items()
        }
    if "else" not in obj:
        obj["else"] = "dont_care"
    return obj


def _make_geo_dep(gid, pid, kind, metric, region):
    if kind == "main":
        expect = {"geo": {metric: {"region": region_compact(region)}}}
    elif kind == "opening":
        expect = {"geo": {"opening_intact": {"region": region_compact(region)}}}
    else:
        expect = {"geo": {"no_poke": {"region": region_compact(region)}}}
    return {
        "id": gid,
        "kind": "D1",
        "target": {"part": pid},
        "expect": expect,
        "when": "true",
        "else": "dont_care",
        "writer": ["gen"],
        "source": ["推断 geo_defaults 生成（CONDITION_GRAMMAR §6 第 2 步）"],
        "confidence": {"writer": "high", "correct": "high"},
    }


# ---------------------------------------------------------------------------
# schema / 上下文 / 单文档校验
# ---------------------------------------------------------------------------

_SCHEMA_CACHE = {}


def load_schema():
    if "schema" not in _SCHEMA_CACHE:
        try:
            schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        except Exception:
            _SCHEMA_CACHE["schema"] = None
            _SCHEMA_CACHE["validator"] = None
            return None, None
        validator = None
        try:
            from jsonschema import Draft202012Validator
            Draft202012Validator.check_schema(schema)
            validator = Draft202012Validator(schema)
        except Exception:
            validator = None
        _SCHEMA_CACHE["schema"] = schema
        _SCHEMA_CACHE["validator"] = validator
    return _SCHEMA_CACHE["schema"], _SCHEMA_CACHE["validator"]


def schema_errors(doc, schema_tuple):
    """返回规范化路径集合；jsonschema 不可用时返回 None（表示降级）。"""
    if schema_tuple is None:
        schema_tuple = load_schema()
    if isinstance(schema_tuple, tuple):
        _schema, validator = schema_tuple
    else:
        _schema, validator = None, None
    if validator is None:
        return None
    try:
        return normalize_schema_errors(validator.iter_errors(doc))
    except Exception:
        return None


def discover_pose_library(project):
    if not project:
        return None
    cand = WORKSPACE / project / "_感知" / "out" / "pose_library.json"
    if cand.exists():
        try:
            return json.loads(cand.read_text(encoding="utf-8"))
        except Exception:
            return None
    base = WORKSPACE
    if not base.exists():
        return None
    for p in sorted(base.glob("*/_感知/out/pose_library.json")):
        if project in p.parents[2].name:
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return None
    return None


def build_ctx(profile_path=None, inventory_path=None, pose_library_path=None,
              project=None):
    schema_tuple = load_schema()
    ctx = {"schema": schema_tuple, "profile": None, "inventory": None,
           "pose_library": None, "profile_path": profile_path,
           "inventory_path": inventory_path}
    if profile_path:
        try:
            ctx["profile"] = load_yaml_file(profile_path)
        except Exception as exc:  # noqa: BLE001
            ctx["profile_error"] = str(exc)
    if inventory_path:
        try:
            ctx["inventory"] = json.loads(
                Path(inventory_path).read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            try:
                ctx["inventory"] = load_yaml_file(inventory_path)
            except Exception:
                ctx["inventory_error"] = str(exc)
    if pose_library_path:
        try:
            ctx["pose_library"] = json.loads(
                Path(pose_library_path).read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            try:
                ctx["pose_library"] = load_yaml_file(pose_library_path)
            except Exception:
                ctx["pose_library_error"] = str(exc)
    else:
        ctx["pose_library"] = discover_pose_library(project)
    return ctx


class Result:
    __slots__ = ("source", "schema_ok", "schema_paths", "findings", "skips",
                 "validator", "decl", "fragment")

    def __init__(self):
        self.source = None
        self.schema_ok = True
        self.schema_paths = set()
        self.findings = []
        self.skips = {}
        self.validator = None
        self.decl = None
        self.fragment = False

    @property
    def errors(self):
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self):
        return [f for f in self.findings if f.severity == "warning"]


def validate_document(data, source, ctx):
    result = Result()
    result.source = source
    result.fragment = isinstance(data, dict) and data.get("schema") == FRAGMENT_ID
    errs = schema_errors(data, ctx.get("schema"))
    if errs is None:
        result.schema_ok = None
        result.schema_paths = set()
    else:
        result.schema_ok = not errs
        result.schema_paths = errs
    if errs:  # schema 不过的文档不跑语义层（GRAMMAR §8）
        return result
    sv = SemanticValidator(data, source, ctx, fragment_only=result.fragment)
    sv.run()
    result.validator = sv
    result.findings = sv.findings
    result.skips = sv.skips
    return result


def decl_bytes(sv):
    obj = sv.expand()
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      indent=2).encode("utf-8")


# ---------------------------------------------------------------------------
# 反例头注释 / selftest
# ---------------------------------------------------------------------------

_HEADER_RULE = "# rule:"
_HEADER_LAYER = "# layer:"
_HEADER_PATH = "# expect_error_path:"


def parse_header(text):
    rule = layer = exp = None
    for ln in text.splitlines()[:6]:
        if ln.startswith(_HEADER_RULE):
            rule = ln[len(_HEADER_RULE):].strip()
        elif ln.startswith(_HEADER_LAYER):
            layer = ln[len(_HEADER_LAYER):].strip()
        elif ln.startswith(_HEADER_PATH):
            exp = ln[len(_HEADER_PATH):].strip()
    sem = None
    if rule:
        m = re.search(r"SEM-\d+", rule)
        if m:
            sem = m.group(0)
    return rule, layer, exp, sem


def _project_of(data):
    if not isinstance(data, dict):
        return None
    av = data.get("avatar")
    if isinstance(av, dict):
        return av.get("project")
    return None


# --- SEM-07 / all_keys 专项自验（任务 AQ）---------------------------------
# 复用 examples/ok/features_misc.yaml（含 includes 与身体键依赖），只换注入的 profile：
#   反例  all_keys=[]           → 身体键全部报 SEM-07 error（不再是 warning）
#   正例  all_keys=声明引用的键 → 0 错
#   反例2 all_keys=少一个键     → 清一色 SEM-07 error，且不误伤其它规则
def _sem07_probe(ok_dir, profile):
    path = ok_dir / "features_misc.yaml"
    text = path.read_text(encoding="utf-8")
    data = load_yaml_text(text, str(path))
    ctx = build_ctx(project=_project_of(data))
    ctx["profile"] = profile
    return validate_document(data, str(path), ctx)


def _selftest_sem07_all_keys(ok_dir):
    fails = []
    probe_profile = {"body": "Body_b", "mesh": "Body_b", "all_keys": []}
    r0 = _sem07_probe(ok_dir, probe_profile)
    if r0.schema_ok is not True:
        return ["SEM-07/all_keys：features_misc schema 未通过"]
    errs = r0.errors
    if not errs or {f.rule for f in errs} != {"SEM-07"}:
        return ["SEM-07/all_keys 反例1：all_keys=[] 应清一色 SEM-07 错，实为 %s"
                % sorted({f.rule for f in errs})]
    if any(f.severity != "error" for f in errs):
        return ["SEM-07/all_keys 反例1：有 all_keys 时缺失键应是 error，混进了 warning"]

    refs = list(r0.validator._body_key_refs())
    ref_keys = sorted({t[3] for t in refs})
    if not ref_keys:
        return ["SEM-07/all_keys：features_misc 没有身体键引用，专项自验失去意义"]

    r1 = _sem07_probe(ok_dir, {"body": "Body_b", "mesh": "Body_b", "all_keys": ref_keys})
    if r1.errors:
        fails.append("SEM-07/all_keys 正例：all_keys 列全 %d 键后应 0 错，实为 %s"
                     % (len(ref_keys),
                        [(f.rule, f.path) for f in r1.errors[:5]]))

    dropped = ref_keys[0]
    r2 = _sem07_probe(ok_dir, {"body": "Body_b", "mesh": "Body_b",
                               "all_keys": [k for k in ref_keys if k != dropped]})
    errs2 = r2.errors
    if not errs2 or {f.rule for f in errs2} != {"SEM-07"}:
        fails.append("SEM-07/all_keys 反例2：少一个键应清一色 SEM-07 错，实为 %s"
                     % sorted({f.rule for f in errs2}))
    elif any(f.severity != "error" for f in errs2):
        fails.append("SEM-07/all_keys 反例2：缺失键应是 error")
    elif dropped not in " ".join(f.message for f in errs2):
        fails.append("SEM-07/all_keys 反例2：报错未点名缺失键 %r" % dropped)

    # 没有 all_keys 时维持旧口径：只 warning、不 error（回归保护）
    r3 = _sem07_probe(ok_dir, {"body": "Body_b", "mesh": "Body_b",
                               "key_classes": {"other": {}}})
    if r3.errors:
        fails.append("SEM-07/旧口径回归：无 all_keys 时不应有 error，实为 %s"
                     % [(f.rule, f.path) for f in r3.errors[:5]])
    n_sem07_warn = sum(1 for f in r3.warnings if f.rule == "SEM-07")
    if n_sem07_warn == 0:
        fails.append("SEM-07/旧口径回归：无 all_keys 且键不在 key_classes 时应出 warning")
    return fails


def run_selftest(mini_yaml=False, verbose=False):
    global _FORCE_MINI
    if mini_yaml:
        _FORCE_MINI = True
    ok_dir = HERE / "examples" / "ok"
    bad_dir = HERE / "examples" / "bad"
    fails = []
    ok_fails = []
    bad_fails = []
    n_ok = n_bad = 0
    for path in sorted(ok_dir.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        data = load_yaml_text(text, str(path))
        ctx = build_ctx(project=_project_of(data))
        r = validate_document(data, str(path), ctx)
        n_ok += 1
        if r.schema_ok is not True:
            ok_fails.append("%s: schema 未通过（%s）" % (path.name, sorted(r.schema_paths)))
            continue
        if r.errors:
            ok_fails.append("%s: 语义层有 %d 个错：%s"
                         % (path.name, len(r.errors),
                            [(f.rule, f.path) for f in r.errors[:5]]))
            continue
        try:
            b1 = decl_bytes(SemanticValidator(
                load_yaml_text(text, str(path)), str(path), ctx,
                fragment_only=r.fragment).run())
            b2 = decl_bytes(SemanticValidator(
                load_yaml_text(text, str(path)), str(path), ctx,
                fragment_only=r.fragment).run())
        except Exception as exc:  # noqa: BLE001
            ok_fails.append("%s: 展开失败：%s" % (path.name, exc))
            continue
        if b1 != b2:
            ok_fails.append("%s: 两次展开字节不一致" % path.name)
    for path in sorted(bad_dir.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        header_rule, layer, exp, sem = parse_header(text)
        try:
            data = load_yaml_text(text, str(path))
        except Exception as exc:  # noqa: BLE001
            bad_fails.append("%s: YAML 载入失败：%s" % (path.name, exc))
            continue
        ctx = build_ctx(project=_project_of(data))
        r = validate_document(data, str(path), ctx)
        n_bad += 1
        if layer == "schema":
            if r.schema_ok is None:
                bad_fails.append("%s: jsonschema 不可用，无法自验 schema 层" % path.name)
                continue
            if r.schema_ok:
                bad_fails.append("%s: schema 本应被拒但通过了" % path.name)
                continue
            if exp and exp not in r.schema_paths:
                bad_fails.append("%s: 期望路径 %s 不在 %s"
                             % (path.name, exp, sorted(r.schema_paths)))
            continue
        if r.schema_ok is not True:
            bad_fails.append("%s: schema 本应通过却被拒（%s）"
                         % (path.name, sorted(r.schema_paths)))
            continue
        rules = {f.rule for f in r.errors}
        expected = {sem} if sem else set()
        if rules != expected:
            bad_fails.append("%s: 命中规则 %s，期望 %s（%s）"
                         % (path.name, sorted(rules), sorted(expected),
                            [(f.rule, f.path) for f in r.errors[:5]]))
            continue
        if exp and exp not in {f.path for f in r.errors}:
            bad_fails.append("%s: 期望路径 %s 不在 %s"
                         % (path.name, exp, sorted({f.path for f in r.errors})))
    fails = ok_fails + bad_fails + _selftest_sem07_all_keys(ok_dir)
    print("ok files: %d  ok failures: %d   bad files: %d  bad mismatches: %d"
          % (n_ok, len(ok_fails), n_bad, len(bad_fails)))
    if fails:
        print("FAIL:")
        for f in fails:
            print("  " + f)
        return 1
    print("ALL PASS")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_report(r, stream=sys.stdout, as_json=False):
    if as_json:
        obj = {
            "source": r.source,
            "schema": ("ok" if r.schema_ok else
                       ("skipped" if r.schema_ok is None else "fail")),
            "schema_paths": sorted(r.schema_paths),
            "errors": [{"rule": f.rule, "path": f.path, "message": f.message}
                       for f in r.errors],
            "warnings": [{"rule": f.rule, "path": f.path, "message": f.message}
                         for f in r.warnings],
            "skipped": r.skips,
        }
        stream.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
        return
    stream.write("file: %s\n" % r.source)
    if r.schema_ok is None:
        stream.write("schema: SKIPPED（jsonschema 不可用）\n")
    elif r.schema_ok:
        stream.write("schema: OK\n")
    else:
        stream.write("schema: FAIL\n")
        for p in sorted(r.schema_paths):
            stream.write("  %s\n" % p)
    if r.schema_ok is not True:
        return
    if r.errors:
        stream.write("semantic: FAIL（%d 个错）\n" % len(r.errors))
    else:
        stream.write("semantic: OK（%d 个警告）\n" % len(r.warnings))
    for f in r.findings:
        stream.write("  [%s] %s %s\n" % (f.severity, f.rule, f.path))
        if f.message:
            stream.write("        %s\n" % f.message)
    if r.skips:
        stream.write("skipped: %s\n" % ", ".join(
            "%s（%s）" % (k, v) for k, v in sorted(r.skips.items())))


def _sha256(blob):
    import hashlib
    return hashlib.sha256(blob).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="感知声明校验器（perception/0.2，T-02）")
    ap.add_argument("--in", dest="inp", help="要校验的 YAML（声明或片段）")
    ap.add_argument("--out", dest="out", help="输出确定性排序的 decl.json")
    ap.add_argument("--selftest", action="store_true",
                    help="跑 examples/ok 与 examples/bad")
    ap.add_argument("--mini-yaml", action="store_true",
                    help="强制使用自带最小 YAML 解析（自验备用路径）")
    ap.add_argument("--profile", help="素体档案 YAML（SEM-07）")
    ap.add_argument("--inventory", help="T-05 盘点 inventory.json（SEM-12）")
    ap.add_argument("--pose-library", help="姿势库 pose_library.json")
    ap.add_argument("--report", choices=("text", "json"), default="text")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    if args.mini_yaml:
        global _FORCE_MINI
        _FORCE_MINI = True

    if args.selftest:
        return run_selftest(mini_yaml=args.mini_yaml)

    if not args.inp:
        ap.error("需要 --in 或 --selftest")

    try:
        data = load_yaml_file(args.inp)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("载入失败：%s\n" % exc)
        return EXIT_USAGE

    ctx = build_ctx(args.profile, args.inventory, args.pose_library,
                    project=_project_of(data))
    r = validate_document(data, str(args.inp), ctx)
    if not args.quiet:
        _print_report(r, as_json=(args.report == "json"))

    if args.out:
        if r.schema_ok is not True:
            sys.stderr.write("schema 未通过，不写 decl.json\n")
        elif r.validator is None:
            sys.stderr.write("语义层未运行，不写 decl.json\n")
        else:
            blob = decl_bytes(r.validator)
            Path(args.out).write_bytes(blob)
            if not args.quiet:
                sys.stdout.write("decl.json -> %s（%d 字节 sha256=%s）\n"
                                 % (args.out, len(blob), _sha256(blob)))

    if r.schema_ok is not True:
        return EXIT_FAIL
    return EXIT_FAIL if r.errors else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())


