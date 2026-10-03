#!/usr/bin/env python3
"""
ghyaml.py -- a RESTRICTED YAML loader for GitHub Actions workflows, written because
PyYAML is not installed on this host.

THE RULE THIS FILE EXISTS TO UPHOLD
    A parser that meets something it does not understand must return UNVERIFIABLE.
    It must never return a confident answer it did not actually compute.

canfail.py -- Lane CI's instrument, which is good and I am not forking it -- does
`import yaml` and `sys.exit("needs PyYAML")` when the module is absent. On this box
that is what happens: the tool does not run at all. The danger is not the exit code,
it is the *driver around it*: a harness that shells out, sees a non-zero exit, and
records "0 findings", has just reported clean on an instrument that never executed.
That is the same defect as the CI workflow that always passes, wearing a Python
process's clothes.

So this loader returns `(value, problems)`. `problems` non-empty => the caller MUST
surface the file as unverifiable. Silence is not an option the caller is given.

SUPPORTED (the GH Actions subset, which is all these files actually use)
    block mappings          key: value
    nested mappings         indentation
    block sequences         - item      - key: value  (+ continuation lines)
    block scalars           |   |-   >   >-   (and  |+ )
    flow sequences         [a, b, c]   (single line only)
    scalars                 plain / 'single' / "double"
    booleans, null, ints    true false null ~ 123
    comments                '#' at line start or after whitespace, outside quotes

DELIBERATELY UNSUPPORTED -- each of these raises into `problems`, never a guess
    anchors & aliases      &anchor  *alias
    flow mappings          {a: 1}          (indistinguishable from a plain scalar
                                               for our purposes; refuse rather than
                                               half-understand)
    multi-line flow        [a,\n b]
    tab indentation
    explicit indentation indicators   |2
    complex keys           ? key
    tags                   !!str
    multiple documents      ---   (we take the first and say so)
"""
from __future__ import annotations

import re
from typing import Any

__all__ = ["load", "LoadProblem", "Unverifiable"]


class Unverifiable(Exception):
    """Raised inside the parser; always converted into a `problems` entry."""


class LoadProblem:
    __slots__ = ("line", "message")

    def __init__(self, line: int, message: str):
        self.line = line
        self.message = message

    def __str__(self) -> str:
        return f"line {self.line}: {self.message}"

    def as_dict(self) -> dict:
        return {"line": self.line, "message": self.message}


UNSUPPORTED = (
    (re.compile(r"(?<![\w\"'])&\w[\w-]*"), "YAML anchor (&name)"),
    (re.compile(r"(?<![\w\"'])\*\w[\w-]*"), "YAML alias (*name)"),
    (re.compile(r":\s*\{"), "flow mapping ({...})"),
    (re.compile(r"(?<![\w\"'])\?\s"), "complex key (? ...)"),
    (re.compile(r"(?<![\w\"'])!!?\w[\w:/-]*\s"), "explicit tag (!!str)"),
    (re.compile(r"[\|&>][+-]?[1-9]"), "explicit indentation indicator (|2)"),
)


# ── tokenising ────────────────────────────────────────────────────────────────────

class Line:
    __slots__ = ("no", "indent", "text", "raw")

    def __init__(self, no: int, raw: str):
        self.no = no
        self.raw = raw
        s = raw.rstrip("\n").rstrip()
        stripped = s.lstrip(" ")
        self.indent = len(s) - len(stripped)
        self.text = stripped

    def __repr__(self) -> str:      # pragma: no cover - debugging aid
        return f"Line({self.no}, ind={self.indent}, {self.text!r})"


def _strip_comment(s: str, problems: list) -> str:
    """Remove an unquoted trailing comment. A '#' inside quotes is data."""
    out, quote, i = [], None, 0
    while i < len(s):
        ch = s[i]
        if quote:
            out.append(ch)
            if ch == quote:
                if quote == "'" and i + 1 < len(s) and s[i + 1] == "'":
                    out.append(s[i + 1])
                    i += 2
                    continue
                quote = None
            elif quote == '"' and ch == "\\" and i + 1 < len(s):
                out.append(s[i + 1])
                i += 2
                continue
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "#" and (i == 0 or s[i - 1] in " \t"):
            break
        out.append(ch)
        i += 1
    if quote:
        problems.append(LoadProblem(0, "unterminated quote"))
    return "".join(out).rstrip()


def _scan(text: str, problems: list) -> list[Line]:
    lines: list[Line] = []
    for no, raw in enumerate(text.splitlines(), 1):
        if raw.startswith("﻿"):
            raw = raw[1:]
        lead = raw.lstrip(" ")
        if lead.startswith("#"):
            continue
        if not lead.strip():
            continue
        if raw.startswith("\t") or re.match(r"^ *\t", raw):
            problems.append(LoadProblem(no, "tab used for indentation"))
            continue
        body = _strip_comment(raw, problems)
        if not body.strip():
            continue
        ln = Line(no, body)
        if ln.text != body.strip():
            ln.indent = len(body) - len(body.lstrip(" "))
            ln.text = body.strip()
        lines.append(ln)
    return lines


def _check_unsupported(ln: Line, problems: list) -> None:
    for pat, label in UNSUPPORTED:
        if pat.search(ln.text):
            problems.append(LoadProblem(ln.no, f"unsupported construct: {label}"))
            return
    if "\t" in ln.text:
        problems.append(LoadProblem(ln.no, "tab inside a value"))


# ── scalars ──────────────────────────────────────────────────────────────────────

_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(\d+\.\d*|\.\d+)([eE][+-]?\d+)?$")


def _scalar(tok: str, ln: Line, problems: list) -> Any:
    tok = tok.strip()
    if not tok:
        return None
    if tok[0] == "'" and tok[-1] == "'" and len(tok) >= 2:
        return tok[1:-1].replace("''", "'")
    if tok[0] == '"' and tok[-1] == '"' and len(tok) >= 2:
        body = tok[1:-1]
        body = re.sub(r"\\(.)", r"\1", body)
        return body.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
    if tok.startswith("[") and tok.endswith("]"):
        inner = tok[1:-1].strip()
        if not inner:
            return []
        return [_scalar(p, ln, problems) for p in _split_flow(inner)]
    if tok in ("null", "Null", "NULL", "~"):
        return None
    if tok in ("true", "True", "TRUE"):
        return True
    if tok in ("false", "False", "FALSE"):
        return False
    if _INT_RE.match(tok):
        return int(tok)
    if _FLOAT_RE.match(tok):
        return float(tok)
    return tok


def _split_flow(s: str) -> list[str]:
    parts, buf, quote, depth = [], [], None, 0
    for ch in s:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
            buf.append(ch)
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())
    return [p for p in parts if p != ""]


_KEY_RE = re.compile(r"""^(?P<key>"(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^:]+?)\s*:(?=\s|$)""")


def _split_key(text: str, ln: Line, problems: list) -> tuple[str, str] | None:
    m = _KEY_RE.match(text)
    if not m:
        if text.endswith(":"):
            problems.append(LoadProblem(ln.no, f"malformed mapping line: {text[:40]!r}"))
        return None
    return m.group("key").strip(), text[m.end():].strip()


def _read_block_scalar(ln: Line, style: str, chomp: str, all_lines: list[Line],
                       idx: int, problems: list) -> tuple[str, int]:
    """Collect the indented block that follows. Returns (text, next_index)."""
    body: list[str] = []
    j = idx + 1
    base = None
    while j < len(all_lines):
        nxt = all_lines[j]
        if nxt.indent <= ln.indent:
            break
        if base is None:
            base = nxt.indent
        body.append(" " * max(0, nxt.indent - base) + nxt.text)
        j += 1
    if style == "|":
        text = "\n".join(body)
        text = text + "\n" if body else ""
    else:                                    # folded
        text = ""
        for k, b in enumerate(body):
            if k and b.strip() and not b.startswith(" ") and body[k - 1].strip():
                text += " " + b.strip()
            else:
                text += ("\n" if k else "") + b
        if body:
            text += "\n"
    if chomp == "-":
        text = text.rstrip("\n")
    return text, j


def _parse_block(all_lines: list[Line], i: int, indent: int,
                 problems: list) -> tuple[Any, int]:
    if i >= len(all_lines):
        return None, i
    ln = all_lines[i]
    if ln.text.startswith("- ") or ln.text == "-":
        return _parse_seq(all_lines, i, indent, problems)
    return _parse_map(all_lines, i, indent, problems)


def _parse_map(all_lines: list[Line], i: int, indent: int,
               problems: list) -> tuple[dict, int]:
    out: dict[str, Any] = {}
    while i < len(all_lines):
        ln = all_lines[i]
        if ln.indent < indent:
            break
        if ln.indent > indent:
            problems.append(LoadProblem(ln.no, "unexpected indentation in mapping"))
            i += 1
            continue
        if ln.text.startswith("- "):
            break
        kv = _split_key(ln.text, ln, problems)
        if kv is None:
            problems.append(LoadProblem(ln.no, f"not a key: {ln.text[:40]!r}"))
            i += 1
            continue
        key, rest = kv
        _check_unsupported(ln, problems)
        key = _scalar(key, ln, problems) if key[:1] in "'\"" else key

        m = re.match(r"^([|>])([+-]?)\s*$", rest)
        if m:
            text, i = _read_block_scalar(ln, m.group(1), m.group(2), all_lines, i, problems)
            out[key] = text
            continue
        if rest == "":
            i += 1
            if i < len(all_lines) and all_lines[i].indent > indent:
                val, i = _parse_block(all_lines, i, all_lines[i].indent, problems)
                out[key] = val
            else:
                out[key] = None
            continue
        out[key] = _scalar(rest, ln, problems)
        i += 1
    return out, i


def _parse_seq(all_lines: list[Line], i: int, indent: int,
               problems: list) -> tuple[list, int]:
    out: list[Any] = []
    while i < len(all_lines):
        ln = all_lines[i]
        if ln.indent < indent:
            break
        if ln.indent > indent:
            problems.append(LoadProblem(ln.no, "unexpected indentation in sequence"))
            i += 1
            continue
        if not (ln.text.startswith("- ") or ln.text == "-"):
            break
        _check_unsupported(ln, problems)
        item = ln.text[1:].strip()
        # the content after "- " starts a nested block whose indent is
        # indent + 2 (or wherever it really begins); handle inline maps
        if item == "":
            i += 1
            if i < len(all_lines) and all_lines[i].indent > indent:
                val, i = _parse_block(all_lines, i, all_lines[i].indent, problems)
                out.append(val)
            else:
                out.append(None)
            continue
        kv = _split_key(item, ln, problems)
        if kv is not None:
            key, rest = kv
            child_indent = ln.indent + 2 + (len(item) - len(item.lstrip(" ")))
            synthetic = Line(ln.no, " " * child_indent + item)
            sub, i2 = _parse_map([synthetic] + all_lines[i + 1:], 0, child_indent, problems)
            out.append(sub)
            i = i2
            continue
        m = re.match(r"^([|>])([+-]?)\s*$", item)
        if m:
            text, i = _read_block_scalar(ln, m.group(1), m.group(2), all_lines, i, problems)
            out.append(text)
            continue
        out.append(_scalar(item, ln, problems))
        i += 1
    return out, i


# ── entry point ──────────────────────────────────────────────────────────────────

def load(text: str) -> tuple[Any, list[LoadProblem]]:
    """Parse `text`. Returns (value, problems).

    `problems` is the contract: a non-empty list means the value is NOT trustworthy
    and the caller must report the file as unverifiable. Empty list + non-dict
    return also means unverifiable -- the caller checks that too.
    """
    problems: list[LoadProblem] = []
    if not isinstance(text, str) or not text.strip():
        return None, [LoadProblem(0, "empty document")]

    raw_doc_count = len(re.findall(r"(?m)^---\s*$", text))
    if raw_doc_count > 1:
        problems.append(LoadProblem(0, f"multi-document stream ({raw_doc_count} docs); "
                                       "only the first is parsed"))

    lines = _scan(text, problems)
    if not lines:
        return None, [LoadProblem(0, "no content outside comments")]
    for ln in lines:
        _check_unsupported(ln, problems)

    value, i = _parse_block(lines, 0, lines[0].indent, problems)
    if i < len(lines):
        problems.append(LoadProblem(lines[i].no,
                                    f"trailing content not consumed: {lines[i].text[:40]!r}"))
    return value, problems
