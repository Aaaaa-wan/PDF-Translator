#!/usr/bin/env python3
"""Utilities for canonical bilingual markdown used by en-cap-translator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple
import re

PLACEHOLDER = "TODO_TRANSLATE"
SUMMARY_PLACEHOLDER_EN = "TODO_SUMMARIZE"
SUMMARY_PLACEHOLDER_ZH = "待补充中文摘要"
DEPRECATED_PLACEHOLDER = "[ZH:"

FENCE_RE = re.compile(r"^\s*(```|~~~)")
MARKDOWN_TABLE_RE = re.compile(r"^\s*\|.*\|\s*$")
ASCII_TABLE_RE = re.compile(r"^\s*[+|].*[+|]\s*$")
CAPTION_RE = re.compile(r"^\s*(Figure|Fig\.|Table|Annex|Appendix)\b", re.IGNORECASE)
HEADER_FOOTER_RE = re.compile(r"^\s*(Page\s+\d+|Confidential|Draft)\b", re.IGNORECASE)
MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
UNORDERED_LIST_RE = re.compile(r"^([*+-])\s+(.+?)\s*$")
ORDERED_LIST_RE = re.compile(r"^(\d+\.)\s+(.+?)\s*$")
ALPHA_LIST_RE = re.compile(r"^([A-Za-z][\.\)])\s+(.+?)\s*$")
PAREN_LIST_RE = re.compile(r"^(\([0-9A-Za-z]+\))\s+(.+?)\s*$")
ANNEX_HEADING_RE = re.compile(r"^((?:Annex|Appendix)\s+[A-Z0-9]+)\s*(.*)$", re.IGNORECASE)
NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+?)\s*$")
MARKDOWN_IMAGE_RE = re.compile(r"^!\[(?P<alt>.*?)\]\((?P<target>.+)\)\s*$")
HTML_IMAGE_RE = re.compile(r"^\s*<img\b[^>]*>\s*$", re.IGNORECASE)
HTML_IMAGE_SRC_RE = re.compile(r'\bsrc=["\']([^"\']+)["\']', re.IGNORECASE)
HTML_IMAGE_ALT_RE = re.compile(r'\balt=["\']([^"\']*)["\']', re.IGNORECASE)


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    line_start: int
    line_end: int
    prefix: str = ""
    content: str = ""
    level: int = 0
    list_type: str = ""
    image_src: str = ""
    image_alt: str = ""


@dataclass(frozen=True)
class PairedBlock:
    kind: str
    english: Token
    chinese: Token


@dataclass(frozen=True)
class SingleBlock:
    kind: str
    token: Token


@dataclass(frozen=True)
class ValidationIssue:
    line: int
    message: str


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def count_cjk(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def count_latin(text: str) -> int:
    return len(re.findall(r"[A-Za-z]", text))


def dominant_language(text: str) -> str:
    cjk = count_cjk(text)
    latin = count_latin(text)
    if cjk == 0 and latin == 0:
        return "neutral"
    if cjk >= max(2, latin):
        return "zh"
    if latin > cjk:
        return "en"
    return "mixed"


def is_placeholder(text: str) -> bool:
    markers = (
        PLACEHOLDER,
        SUMMARY_PLACEHOLDER_EN,
        SUMMARY_PLACEHOLDER_ZH,
        DEPRECATED_PLACEHOLDER,
    )
    return any(marker in text for marker in markers)


def is_table_line(line: str) -> bool:
    stripped = line.rstrip()
    return bool(MARKDOWN_TABLE_RE.match(stripped) or ASCII_TABLE_RE.match(stripped))


def is_fence_line(line: str) -> bool:
    return bool(FENCE_RE.match(line.rstrip()))


def parse_markdown_image(line: str) -> tuple[str, str] | None:
    match = MARKDOWN_IMAGE_RE.match(line)
    if not match:
        return None

    alt = match.group("alt").strip()
    target = match.group("target").strip()
    if target.startswith("<") and ">" in target:
        src = target[1 : target.index(">")].strip()
        return (src, alt) if src else None

    target_match = re.match(r'(?P<src>\S+?)(?:\s+"[^"]*")?$', target)
    if not target_match:
        return None
    src = target_match.group("src").strip()
    return (src, alt) if src else None


def parse_html_image(line: str) -> tuple[str, str] | None:
    if not HTML_IMAGE_RE.match(line):
        return None
    src_match = HTML_IMAGE_SRC_RE.search(line)
    if not src_match:
        return None
    alt_match = HTML_IMAGE_ALT_RE.search(line)
    return src_match.group(1), alt_match.group(1) if alt_match else ""


def classify_line(line: str, line_no: int) -> Token:
    stripped = line.rstrip()

    image = parse_markdown_image(stripped) or parse_html_image(stripped)
    if image:
        src, alt = image
        return Token(
            kind="image",
            text=stripped,
            line_start=line_no,
            line_end=line_no,
            image_src=src,
            image_alt=alt,
        )

    md_heading = MD_HEADING_RE.match(stripped)
    if md_heading:
        hashes, content = md_heading.groups()
        return Token(
            kind="heading",
            text=f"{hashes} {content}",
            line_start=line_no,
            line_end=line_no,
            prefix=f"{hashes} ",
            content=content,
            level=len(hashes),
        )

    unordered = UNORDERED_LIST_RE.match(stripped)
    if unordered:
        marker, content = unordered.groups()
        return Token(
            kind="list_item",
            text=f"{marker} {content}",
            line_start=line_no,
            line_end=line_no,
            prefix=f"{marker} ",
            content=content,
            list_type="unordered",
        )

    ordered = ORDERED_LIST_RE.match(stripped)
    if ordered:
        marker, content = ordered.groups()
        return Token(
            kind="list_item",
            text=f"{marker} {content}",
            line_start=line_no,
            line_end=line_no,
            prefix=f"{marker} ",
            content=content,
            list_type="ordered",
        )

    alpha = ALPHA_LIST_RE.match(stripped)
    if alpha:
        marker, content = alpha.groups()
        return Token(
            kind="list_item",
            text=f"{marker} {content}",
            line_start=line_no,
            line_end=line_no,
            prefix=f"{marker} ",
            content=content,
            list_type="alpha",
        )

    paren = PAREN_LIST_RE.match(stripped)
    if paren:
        marker, content = paren.groups()
        return Token(
            kind="list_item",
            text=f"{marker} {content}",
            line_start=line_no,
            line_end=line_no,
            prefix=f"{marker} ",
            content=content,
            list_type="paren",
        )

    annex_heading = ANNEX_HEADING_RE.match(stripped)
    if annex_heading:
        prefix, tail = annex_heading.groups()
        content = tail.strip()
        text = prefix if not content else f"{prefix} {content}"
        return Token(
            kind="heading",
            text=text,
            line_start=line_no,
            line_end=line_no,
            prefix=prefix,
            content=content,
            level=1,
        )

    numbered_heading = NUMBERED_HEADING_RE.match(stripped)
    if numbered_heading and not ORDERED_LIST_RE.match(stripped):
        prefix, content = numbered_heading.groups()
        return Token(
            kind="heading",
            text=f"{prefix} {content}",
            line_start=line_no,
            line_end=line_no,
            prefix=f"{prefix} ",
            content=content,
            level=min(prefix.count(".") + 1, 6),
        )

    if CAPTION_RE.match(stripped) or HEADER_FOOTER_RE.match(stripped):
        return Token(
            kind="raw",
            text=stripped,
            line_start=line_no,
            line_end=line_no,
        )

    return Token(
        kind="paragraph",
        text=stripped,
        line_start=line_no,
        line_end=line_no,
        content=stripped,
    )


def _join_paragraph_lines(lines: Sequence[str]) -> str:
    sample = " ".join(lines)
    if dominant_language(sample) == "zh":
        return "".join(line.strip() for line in lines)
    return " ".join(line.strip() for line in lines)


def tokenize_text(text: str) -> List[Token]:
    tokens: List[Token] = []
    lines = text.splitlines()
    index = 0

    while index < len(lines):
        line_no = index + 1
        line = lines[index].rstrip("\n")
        stripped = line.rstrip()

        if not stripped:
            index += 1
            continue

        if is_fence_line(stripped):
            start = index
            fence = stripped[:3]
            block = [stripped]
            index += 1
            while index < len(lines):
                candidate = lines[index].rstrip()
                block.append(candidate)
                if candidate.startswith(fence):
                    index += 1
                    break
                index += 1
            tokens.append(
                Token(
                    kind="code_block",
                    text="\n".join(block),
                    line_start=start + 1,
                    line_end=index,
                )
            )
            continue

        if is_table_line(stripped):
            start = index
            table_lines = [stripped]
            index += 1
            while index < len(lines):
                candidate = lines[index].rstrip()
                if not candidate or not is_table_line(candidate):
                    break
                table_lines.append(candidate)
                index += 1
            tokens.append(
                Token(
                    kind="table",
                    text="\n".join(table_lines),
                    line_start=start + 1,
                    line_end=start + len(table_lines),
                )
            )
            continue

        classified = classify_line(stripped, line_no)
        if classified.kind != "paragraph":
            tokens.append(classified)
            index += 1
            continue

        start = index
        paragraph_lines = [stripped]
        paragraph_language = dominant_language(stripped)
        index += 1

        while index < len(lines):
            candidate = lines[index].rstrip()
            if not candidate:
                break
            if is_fence_line(candidate) or is_table_line(candidate):
                break
            classified_candidate = classify_line(candidate, index + 1)
            if classified_candidate.kind != "paragraph":
                break
            candidate_language = dominant_language(candidate)
            if paragraph_language in {"en", "zh"} and candidate_language in {"en", "zh"} and candidate_language != paragraph_language:
                break
            paragraph_lines.append(candidate)
            if paragraph_language == "neutral" and candidate_language in {"en", "zh"}:
                paragraph_language = candidate_language
            index += 1

        merged = _join_paragraph_lines(paragraph_lines)
        tokens.append(
            Token(
                kind="paragraph",
                text=merged,
                line_start=start + 1,
                line_end=start + len(paragraph_lines),
                content=merged,
            )
        )

    return tokens


def is_translatable(token: Token) -> bool:
    return token.kind in {"heading", "paragraph", "list_item"}


def can_pair(english: Token, chinese: Token) -> bool:
    if not (is_translatable(english) and is_translatable(chinese)):
        return False
    if english.kind != chinese.kind:
        return False
    if dominant_language(english.text) == "zh":
        return False
    if dominant_language(chinese.text) != "zh":
        return False
    if english.kind in {"heading", "list_item"} and english.prefix != chinese.prefix:
        return False
    return True


def pair_tokens(tokens: Sequence[Token]) -> Tuple[List[PairedBlock | SingleBlock], List[ValidationIssue]]:
    blocks: List[PairedBlock | SingleBlock] = []
    issues: List[ValidationIssue] = []
    index = 0

    while index < len(tokens):
        token = tokens[index]
        token_has_placeholder = is_placeholder(token.text)
        if token_has_placeholder:
            issues.append(ValidationIssue(token.line_start, "Remove placeholder content before delivery."))

        if not is_translatable(token):
            blocks.append(SingleBlock(kind=token.kind, token=token))
            index += 1
            continue

        if index + 1 < len(tokens) and can_pair(token, tokens[index + 1]):
            chinese = tokens[index + 1]
            if is_placeholder(chinese.text):
                issues.append(ValidationIssue(chinese.line_start, "Replace the translation placeholder with final Chinese text."))
            blocks.append(PairedBlock(kind=token.kind, english=token, chinese=chinese))
            index += 2
            continue

        issues.append(
            ValidationIssue(
                token.line_start,
                "Translatable English block is missing an immediately following Chinese translation.",
            )
        )
        blocks.append(SingleBlock(kind=token.kind, token=token))
        index += 1

    return blocks, issues


def validate_summary_block(blocks: Sequence[PairedBlock | SingleBlock], issues: List[ValidationIssue]) -> None:
    for block in blocks:
        if isinstance(block, PairedBlock):
            if block.kind != "paragraph":
                issues.append(
                    ValidationIssue(
                        block.english.line_start,
                        "The first translatable block must be a bilingual summary paragraph.",
                    )
                )
            return
    issues.append(ValidationIssue(1, "Add a bilingual summary paragraph before the main body."))


def validate_text(text: str) -> Tuple[List[PairedBlock | SingleBlock], List[ValidationIssue]]:
    blocks, issues = pair_tokens(tokenize_text(text))
    validate_summary_block(blocks, issues)
    return blocks, issues


def format_issue(issue: ValidationIssue) -> str:
    return f"line {issue.line}: {issue.message}"


def skeleton_placeholder(token: Token) -> str:
    if token.kind in {"heading", "list_item"}:
        return f"{token.prefix}{PLACEHOLDER}"
    return PLACEHOLDER


def build_skeleton(text: str) -> str:
    output: List[str] = [
        f"Document summary: {SUMMARY_PLACEHOLDER_EN}",
        SUMMARY_PLACEHOLDER_ZH,
        "",
    ]
    for token in tokenize_text(text):
        if is_translatable(token):
            output.append(token.text)
            output.append(skeleton_placeholder(token))
            output.append("")
        else:
            output.append(token.text)
            output.append("")
    while output and output[-1] == "":
        output.pop()
    return "\n".join(output) + "\n"


def parse_markdown_table(lines: Sequence[str]) -> List[List[str]] | None:
    rows: List[List[str]] = []
    for line in lines:
        stripped = line.strip()
        if not MARKDOWN_TABLE_RE.match(stripped):
            return None
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows or None


def load_validated_blocks(path: str | Path) -> List[PairedBlock | SingleBlock]:
    text = read_text(path)
    blocks, issues = validate_text(text)
    if issues:
        formatted = "\n".join(format_issue(issue) for issue in issues)
        raise ValueError(f"Input is not valid canonical bilingual markdown:\n{formatted}")
    return blocks
