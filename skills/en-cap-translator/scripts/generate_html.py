#!/usr/bin/env python3
"""Render canonical bilingual markdown to print-ready HTML."""

from __future__ import annotations

import argparse
import base64
import mimetypes
from html import escape
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from _bilingual_markdown import PairedBlock, SingleBlock, load_validated_blocks, parse_markdown_table


CSS = """
body {
  font-family: "Times New Roman", "Noto Serif SC", serif;
  font-size: 11pt;
  line-height: 1.65;
  color: #222;
  margin: 0 auto;
  max-width: 900px;
  padding: 28px 32px 56px;
}

header {
  margin-bottom: 24px;
  padding-bottom: 12px;
  border-bottom: 2px solid #18344f;
}

header h1 {
  margin: 0;
  font-size: 20pt;
  color: #18344f;
}

.en {
  color: #111;
}

.zh {
  color: #0f4c81;
  font-style: italic;
  margin-top: 3px;
}

.heading-pair,
.bilingual-block,
.summary-block,
.table-block,
.image-block,
.verbatim {
  margin-top: 10px;
}

.heading-pair .en,
.heading-pair .zh,
.bilingual-block p,
.summary-block p {
  margin: 0;
}

.heading-pair .zh {
  margin-top: 4px;
}

.summary-block {
  background: #f4f8fb;
  border-left: 4px solid #18344f;
  border-radius: 4px;
  padding: 12px 14px;
}

.summary-block .zh {
  margin-top: 6px;
}

.bilingual-list {
  list-style: none;
  margin: 8px 0 12px;
  padding: 0;
}

.bilingual-list li + li {
  margin-top: 8px;
}

.verbatim,
pre {
  white-space: pre-wrap;
  background: #f7f8fa;
  border: 1px solid #d9e0e7;
  border-radius: 6px;
  padding: 10px 12px;
}

.image-block {
  text-align: center;
}

.image-block img {
  max-width: 100%;
  height: auto;
  display: inline-block;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin: 14px 0;
  font-size: 10.5pt;
}

th,
td {
  border: 1px solid #c6d0da;
  padding: 7px 8px;
  vertical-align: top;
  text-align: left;
}

th {
  background: #eef3f7;
}

@page {
  size: A4;
  margin: 18mm;
}
"""


def heading_tag(level: int) -> str:
    return f"h{min(max(level, 1), 6)}"


def is_external_reference(src: str) -> bool:
    return urlparse(src).scheme in {"http", "https", "data"}


def inline_image_src(src: str, input_path: str) -> str | None:
    if is_external_reference(src):
        return src

    candidate = Path(src)
    if not candidate.is_absolute():
        candidate = Path(input_path).resolve().parent / candidate
    if not candidate.exists():
        return None

    mime_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(candidate.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def render_heading(block: PairedBlock) -> str:
    tag = heading_tag(block.english.level)
    en_text = block.english.content or block.english.text
    zh_text = block.chinese.content or block.chinese.text
    return (
        f'<section class="heading-pair"><{tag} class="en">{escape(en_text)}</{tag}>'
        f'<{tag} class="zh">{escape(zh_text)}</{tag}></section>'
    )


def render_paragraph(block: PairedBlock, *, summary: bool = False) -> str:
    class_name = "summary-block" if summary else "bilingual-block"
    return (
        f'<section class="{class_name}">'
        f'<p class="en">{escape(block.english.text)}</p>'
        f'<p class="zh">{escape(block.chinese.text)}</p>'
        "</section>"
    )


def render_list(blocks: List[PairedBlock | SingleBlock], start: int) -> tuple[str, int]:
    lines = ['<ul class="bilingual-list">']
    index = start
    while index < len(blocks):
        block = blocks[index]
        if not isinstance(block, PairedBlock) or block.kind != "list_item":
            break
        lines.append("<li>")
        lines.append(f'<div class="en">{escape(block.english.text)}</div>')
        lines.append(f'<div class="zh">{escape(block.chinese.text)}</div>')
        lines.append("</li>")
        index += 1
    lines.append("</ul>")
    return "".join(lines), index


def render_table(block: SingleBlock) -> str:
    rows = parse_markdown_table(block.token.text.splitlines())
    if not rows:
        return f'<pre class="verbatim">{escape(block.token.text)}</pre>'

    html = ['<section class="table-block"><table>']
    header = rows[0]
    html.append("<thead><tr>")
    for cell in header:
        html.append(f"<th>{escape(cell)}</th>")
    html.append("</tr></thead>")

    if len(rows) > 1:
        html.append("<tbody>")
        for row in rows[1:]:
            html.append("<tr>")
            for cell in row:
                html.append(f"<td>{escape(cell)}</td>")
            html.append("</tr>")
        html.append("</tbody>")

    html.append("</table></section>")
    return "".join(html)


def render_image(block: SingleBlock, input_path: str) -> str:
    src = inline_image_src(block.token.image_src, input_path)
    alt = block.token.image_alt or Path(block.token.image_src).name or "image"
    if src is None:
        return f'<p class="verbatim">[Missing image: {escape(block.token.image_src)}]</p>'
    return (
        '<section class="image-block">'
        f'<img src="{escape(src, quote=True)}" alt="{escape(alt, quote=True)}">'
        "</section>"
    )


def render_single(block: SingleBlock, input_path: str) -> str:
    if block.kind == "table":
        return render_table(block)
    if block.kind == "image":
        return render_image(block, input_path)
    if block.kind == "code_block":
        return f'<pre>{escape(block.token.text)}</pre>'
    return f'<p class="verbatim">{escape(block.token.text)}</p>'


def render_document(blocks: List[PairedBlock | SingleBlock], input_path: str, title: str | None) -> str:
    body: List[str] = []
    index = 0
    summary_rendered = False

    while index < len(blocks):
        block = blocks[index]
        if isinstance(block, SingleBlock):
            body.append(render_single(block, input_path))
            index += 1
            continue

        if block.kind == "list_item":
            html, next_index = render_list(blocks, index)
            body.append(html)
            index = next_index
            continue

        if block.kind == "heading":
            body.append(render_heading(block))
        else:
            body.append(render_paragraph(block, summary=not summary_rendered))
            summary_rendered = True
        index += 1

    title_html = ""
    if title:
        title_html = f"<header><h1>{escape(title)}</h1></header>"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title or 'Bilingual Translation')}</title>
  <style>{CSS}</style>
</head>
<body>
  {title_html}
  {''.join(body)}
</body>
</html>
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render canonical bilingual markdown to HTML.")
    parser.add_argument("input", help="Validated bilingual markdown file.")
    parser.add_argument("output", help="Output HTML file.")
    parser.add_argument("--title", default=None, help="Optional document title.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    blocks = load_validated_blocks(args.input)
    html = render_document(blocks, args.input, args.title)
    Path(args.output).write_text(html, encoding="utf-8")
    print(f"Wrote HTML to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
