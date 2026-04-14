#!/usr/bin/env python3
"""Render canonical bilingual markdown to DOCX without third-party dependencies."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import struct
from urllib.parse import urlparse
from xml.sax.saxutils import escape
import zipfile

from _bilingual_markdown import PairedBlock, SingleBlock, load_validated_blocks, parse_markdown_table

WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CORE_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NAMESPACE = "http://purl.org/dc/elements/1.1/"
DCTERMS_NAMESPACE = "http://purl.org/dc/terms/"
XSI_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"
EXTENDED_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
CONTENT_TYPES_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/content-types"
WP_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/picture"
IMAGE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
MAX_IMAGE_WIDTH_EMU = 5_760_000


@dataclass(frozen=True)
class ImageAsset:
    rel_id: str
    target: str
    archive_name: str
    content_type: str
    data: bytes
    cx: int
    cy: int
    name: str
    alt: str


def xml_text(text: str) -> str:
    return escape(text)


def xml_attr(text: str) -> str:
    return escape(text, {'"': "&quot;"})


def paragraph(
    text: str,
    *,
    style: str = "Normal",
    italic: bool = False,
    bold: bool = False,
    color: str | None = None,
    code: bool = False,
    font_size: int = 22,
    align: str | None = None,
    spacing_before: int | None = None,
    spacing_after: int | None = None,
    indent_left: int | None = None,
    hanging: int | None = None,
    keep_next: bool = False,
    page_break_before: bool = False,
    shading_fill: str | None = None,
    border_left_color: str | None = None,
    border_left_size: int = 18,
) -> str:
    props = [f'<w:pStyle w:val="{style}"/>']
    if align:
        props.append(f'<w:jc w:val="{align}"/>')
    if spacing_before is not None or spacing_after is not None:
        before = f' w:before="{spacing_before}"' if spacing_before is not None else ""
        after = f' w:after="{spacing_after}"' if spacing_after is not None else ""
        props.append(f"<w:spacing{before}{after}/>")
    if indent_left is not None or hanging is not None:
        left = f' w:left="{indent_left}"' if indent_left is not None else ""
        hanging_attr = f' w:hanging="{hanging}"' if hanging is not None else ""
        props.append(f"<w:ind{left}{hanging_attr}/>")
    if keep_next:
        props.append("<w:keepNext/>")
    if page_break_before:
        props.append("<w:pageBreakBefore/>")
    if shading_fill:
        props.append(f'<w:shd w:val="clear" w:fill="{shading_fill}"/>')
    if border_left_color:
        props.append(
            "<w:pBdr>"
            f'<w:left w:val="single" w:sz="{border_left_size}" w:space="12" w:color="{border_left_color}"/>'
            "</w:pBdr>"
        )
    run_props = [
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="SimSun"/>',
        f'<w:sz w:val="{font_size}"/>',
    ]
    if italic:
        run_props.append("<w:i/>")
    if bold:
        run_props.append("<w:b/>")
    if color:
        run_props.append(f'<w:color w:val="{color}"/>')
    if code:
        run_props = [
            '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="Consolas"/>',
            '<w:sz w:val="20"/>',
        ]
    return (
        "<w:p>"
        f"<w:pPr>{''.join(props)}</w:pPr>"
        "<w:r>"
        f"<w:rPr>{''.join(run_props)}</w:rPr>"
        f'<w:t xml:space="preserve">{xml_text(text)}</w:t>'
        "</w:r>"
        "</w:p>"
    )


def page_break_paragraph() -> str:
    return "<w:p><w:r><w:br w:type=\"page\"/></w:r></w:p>"


def looks_numeric(cell: str) -> bool:
    return bool(re.fullmatch(r"[0-9.,%<>=/()\- ]+", cell.strip()))


def column_widths(rows: list[list[str]], total_width: int = 9000) -> list[int]:
    col_count = max(len(row) for row in rows)
    weights: list[int] = []
    for index in range(col_count):
        max_len = max(len(row[index]) if index < len(row) else 0 for row in rows)
        weights.append(max(max_len, 8))
    weight_sum = sum(weights)
    widths = [max(1100, int(total_width * weight / weight_sum)) for weight in weights]
    diff = total_width - sum(widths)
    widths[-1] += diff
    return widths


def table_cell_xml(
    text: str,
    *,
    width: int,
    header: bool,
    align: str = "left",
    font_size: int = 20,
) -> str:
    shading = '<w:shd w:val="clear" w:fill="EEF3F7"/>' if header else ""
    bold = "<w:b/>" if header else ""
    return (
        "<w:tc>"
        "<w:tcPr>"
        f'<w:tcW w:w="{width}" w:type="dxa"/>'
        '<w:vAlign w:val="center"/>'
        f"{shading}"
        "</w:tcPr>"
        "<w:p>"
        f'<w:pPr><w:jc w:val="{align}"/></w:pPr>'
        "<w:r><w:rPr>"
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="SimSun"/>'
        f'<w:sz w:val="{font_size}"/>'
        f"{bold}"
        "</w:rPr>"
        f'<w:t xml:space="preserve">{xml_text(text)}</w:t>'
        "</w:r></w:p>"
        "</w:tc>"
    )


def table_xml(rows: list[list[str]]) -> str:
    grid_cols = max(len(row) for row in rows)
    widths = column_widths(rows)
    compact = grid_cols >= 5 or any(len(cell) > 40 for row in rows for cell in row)
    font_size = 18 if compact else 20
    grid = "".join(f'<w:gridCol w:w="{widths[index]}"/>' for index in range(grid_cols))
    parts = [
        "<w:tbl>",
        "<w:tblPr>"
        '<w:tblW w:w="9000" w:type="dxa"/>'
        '<w:jc w:val="center"/>'
        '<w:tblLayout w:type="fixed"/>'
        "<w:tblBorders>"
        '<w:top w:val="single" w:sz="8" w:space="0" w:color="808080"/>'
        '<w:left w:val="single" w:sz="8" w:space="0" w:color="808080"/>'
        '<w:bottom w:val="single" w:sz="8" w:space="0" w:color="808080"/>'
        '<w:right w:val="single" w:sz="8" w:space="0" w:color="808080"/>'
        '<w:insideH w:val="single" w:sz="8" w:space="0" w:color="B0B0B0"/>'
        '<w:insideV w:val="single" w:sz="8" w:space="0" w:color="B0B0B0"/>'
        "</w:tblBorders>"
        "</w:tblPr>",
        f"<w:tblGrid>{grid}</w:tblGrid>",
    ]
    for row_index, row in enumerate(rows):
        header_row = row_index == 0
        row_prefix = "<w:tr>"
        if header_row:
            row_prefix = '<w:tr><w:trPr><w:tblHeader/></w:trPr>'
        parts.append(row_prefix)
        padded_row = row + [""] * (grid_cols - len(row))
        for col_index, cell in enumerate(padded_row):
            align = "center" if looks_numeric(cell) else "left"
            parts.append(
                table_cell_xml(
                    cell,
                    width=widths[col_index],
                    header=header_row,
                    align=align,
                    font_size=font_size,
                )
            )
        parts.append("</w:tr>")
    parts.append("</w:tbl>")
    return "".join(parts)


def heading_style(level: int) -> str:
    return f"Heading{min(max(level, 1), 6)}"


def is_external_reference(src: str) -> bool:
    return urlparse(src).scheme in {"http", "https", "data"}


def resolve_image_path(src: str, input_path: str) -> Path | None:
    if not src or is_external_reference(src):
        return None
    candidate = Path(src)
    if not candidate.is_absolute():
        candidate = Path(input_path).resolve().parent / candidate
    return candidate if candidate.exists() else None


def detect_image_type(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    mapping = {
        ".png": ("png", "image/png"),
        ".jpg": ("jpeg", "image/jpeg"),
        ".jpeg": ("jpeg", "image/jpeg"),
        ".gif": ("gif", "image/gif"),
        ".bmp": ("bmp", "image/bmp"),
    }
    if suffix not in mapping:
        raise ValueError(f"Unsupported image format: {path.suffix}")
    return mapping[suffix]


def png_dimensions(data: bytes) -> tuple[int, int]:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Invalid PNG file")
    return struct.unpack(">II", data[16:24])


def gif_dimensions(data: bytes) -> tuple[int, int]:
    if data[:6] not in {b"GIF87a", b"GIF89a"}:
        raise ValueError("Invalid GIF file")
    return struct.unpack("<HH", data[6:10])


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("Invalid JPEG file")
    index = 2
    sof_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    while index < len(data):
        while index < len(data) and data[index] != 0xFF:
            index += 1
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(data):
            break
        segment_length = struct.unpack(">H", data[index : index + 2])[0]
        if marker in sof_markers:
            if index + 7 > len(data):
                break
            height, width = struct.unpack(">HH", data[index + 3 : index + 7])
            return width, height
        index += segment_length
    raise ValueError("Could not determine JPEG dimensions")


def image_dimensions(path: Path, data: bytes) -> tuple[int, int]:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return png_dimensions(data)
    if suffix in {".jpg", ".jpeg"}:
        return jpeg_dimensions(data)
    if suffix == ".gif":
        return gif_dimensions(data)
    if suffix == ".bmp" and len(data) >= 26:
        width, height = struct.unpack("<II", data[18:26])
        return width, height
    return (800, 600)


def scale_image(width_px: int, height_px: int) -> tuple[int, int]:
    width_px = max(width_px, 1)
    height_px = max(height_px, 1)
    cx = int(width_px * 9525)
    cy = int(height_px * 9525)
    if cx > MAX_IMAGE_WIDTH_EMU:
        scale = MAX_IMAGE_WIDTH_EMU / cx
        cx = int(cx * scale)
        cy = int(cy * scale)
    return cx, cy


def build_image_asset(block: SingleBlock, input_path: str, image_index: int) -> ImageAsset | None:
    image_path = resolve_image_path(block.token.image_src, input_path)
    if image_path is None:
        return None

    extension, content_type = detect_image_type(image_path)
    data = image_path.read_bytes()
    width_px, height_px = image_dimensions(image_path, data)
    cx, cy = scale_image(width_px, height_px)
    file_name = f"image{image_index}.{extension}"
    rel_id = f"rIdImage{image_index}"
    return ImageAsset(
        rel_id=rel_id,
        target=f"media/{file_name}",
        archive_name=f"word/media/{file_name}",
        content_type=content_type,
        data=data,
        cx=cx,
        cy=cy,
        name=file_name,
        alt=block.token.image_alt or image_path.name,
    )


def image_xml(asset: ImageAsset, docpr_id: int) -> str:
    name = xml_attr(asset.name)
    alt = xml_attr(asset.alt)
    return (
        "<w:p>"
        '<w:pPr><w:jc w:val="center"/><w:spacing w:before="120" w:after="160"/></w:pPr>'
        "<w:r><w:drawing>"
        '<wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{asset.cx}" cy="{asset.cy}"/>'
        f'<wp:docPr id="{docpr_id}" name="{name}" descr="{alt}"/>'
        "<wp:cNvGraphicFramePr>"
        '<a:graphicFrameLocks noChangeAspect="1"/>'
        "</wp:cNvGraphicFramePr>"
        "<a:graphic>"
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        "<pic:pic>"
        "<pic:nvPicPr>"
        f'<pic:cNvPr id="0" name="{name}" descr="{alt}"/>'
        "<pic:cNvPicPr/>"
        "</pic:nvPicPr>"
        "<pic:blipFill>"
        f'<a:blip r:embed="{asset.rel_id}"/>'
        "<a:stretch><a:fillRect/></a:stretch>"
        "</pic:blipFill>"
        "<pic:spPr>"
        f'<a:xfrm><a:off x="0" y="0"/><a:ext cx="{asset.cx}" cy="{asset.cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        "</pic:spPr>"
        "</pic:pic>"
        "</a:graphicData>"
        "</a:graphic>"
        "</wp:inline>"
        "</w:drawing></w:r></w:p>"
    )


def is_major_section_heading(text: str, level: int, seen_major_sections: int) -> bool:
    if level == 1:
        return seen_major_sections > 0
    if level != 2:
        return False
    if seen_major_sections == 0:
        return True
    stripped = text.strip()
    return stripped.isupper() or stripped.upper().startswith("APPENDIX") or bool(re.match(r"^\d", stripped))


def build_document_xml(
    blocks: list[PairedBlock | SingleBlock],
    input_path: str,
    title: str | None,
) -> tuple[str, list[ImageAsset]]:
    body: list[str] = []
    images: list[ImageAsset] = []
    image_index = 1
    docpr_id = 1
    summary_rendered = False
    title_rendered = False
    preface_metadata_mode = False
    metadata_lines = 0
    seen_major_sections = 0

    for block in blocks:
        if isinstance(block, PairedBlock):
            if block.kind == "heading":
                style = heading_style(block.english.level)
                en_text = block.english.content or block.english.text
                zh_text = block.chinese.content or block.chinese.text
                if block.english.level == 1 and not title_rendered:
                    body.append(
                        paragraph(
                            en_text,
                            style="Title",
                            align="center",
                            spacing_before=120,
                            spacing_after=40,
                            font_size=32,
                            bold=True,
                            keep_next=True,
                        )
                    )
                    body.append(
                        paragraph(
                            zh_text,
                            style="Title",
                            align="center",
                            spacing_after=220,
                            font_size=28,
                            italic=True,
                            color="0F4C81",
                        )
                    )
                    title_rendered = True
                    preface_metadata_mode = True
                    metadata_lines = 0
                    continue

                page_break = is_major_section_heading(en_text, block.english.level, seen_major_sections)
                if page_break:
                    seen_major_sections += 1
                if block.english.level >= 2:
                    preface_metadata_mode = False
                body.append(
                    paragraph(
                        en_text,
                        style=style,
                        spacing_before=240 if block.english.level <= 2 else 160,
                        spacing_after=20,
                        keep_next=True,
                        page_break_before=page_break,
                    )
                )
                body.append(
                    paragraph(
                        zh_text,
                        style=style,
                        italic=True,
                        color="0F4C81",
                        spacing_after=140,
                    )
                )
            elif block.kind == "list_item":
                body.append(
                    paragraph(
                        block.english.text,
                        spacing_after=20,
                        indent_left=720,
                        hanging=360,
                    )
                )
                body.append(
                    paragraph(
                        block.chinese.text,
                        italic=True,
                        color="0F4C81",
                        spacing_after=80,
                        indent_left=720,
                        hanging=360,
                    )
                )
            else:
                if not summary_rendered:
                    body.append(
                        paragraph(
                            block.english.text,
                            spacing_before=40,
                            spacing_after=20,
                            shading_fill="F4F8FB",
                            border_left_color="18344F",
                            keep_next=True,
                        )
                    )
                    body.append(
                        paragraph(
                            block.chinese.text,
                            italic=True,
                            color="0F4C81",
                            spacing_after=200,
                            shading_fill="F4F8FB",
                            border_left_color="18344F",
                        )
                    )
                    summary_rendered = True
                elif preface_metadata_mode and metadata_lines < 2:
                    body.append(
                        paragraph(
                            block.english.text,
                            align="center",
                            color="666666",
                            font_size=20,
                            spacing_after=20,
                        )
                    )
                    body.append(
                        paragraph(
                            block.chinese.text,
                            align="center",
                            color="666666",
                            italic=True,
                            font_size=20,
                            spacing_after=120,
                        )
                    )
                    metadata_lines += 1
                else:
                    body.append(paragraph(block.english.text, spacing_after=20))
                    body.append(
                        paragraph(
                            block.chinese.text,
                            italic=True,
                            color="0F4C81",
                            spacing_after=120,
                        )
                    )
            continue

        if block.kind == "table":
            body.append(paragraph("", spacing_after=40))
            rows = parse_markdown_table(block.token.text.splitlines())
            if rows:
                body.append(table_xml(rows))
            else:
                for line in block.token.text.splitlines():
                    body.append(paragraph(line, code=True))
            body.append(paragraph("", spacing_after=60))
            continue

        if block.kind == "image":
            asset = build_image_asset(block, input_path, image_index)
            if asset is None:
                fallback = block.token.image_src or block.token.text
                body.append(paragraph(f"[Missing image: {fallback}]"))
            else:
                body.append(image_xml(asset, docpr_id))
                images.append(asset)
                image_index += 1
                docpr_id += 1
            continue

        if block.kind == "code_block":
            for line in block.token.text.splitlines():
                body.append(paragraph(line, code=True))
            continue

        raw_text = block.token.text.strip()
        if raw_text.lower().startswith(("figure", "fig.", "table")):
            body.append(
                paragraph(
                    raw_text,
                    align="center",
                    italic=True,
                    color="666666",
                    font_size=18,
                    spacing_before=40,
                    spacing_after=120,
                )
            )
        else:
            body.append(paragraph(raw_text, spacing_after=80))

    body.append(
        '<w:sectPr>'
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/>'
        "</w:sectPr>"
    )

    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{WORD_NAMESPACE}" xmlns:r="{DOC_REL_NAMESPACE}" xmlns:wp="{WP_NAMESPACE}" xmlns:a="{A_NAMESPACE}" xmlns:pic="{PIC_NAMESPACE}">'
        f"<w:body>{''.join(body)}</w:body>"
        "</w:document>"
    )
    return xml, images


def styles_xml() -> str:
    heading_styles = []
    for level in range(1, 7):
        size = 32 - (level - 1) * 2
        heading_styles.append(
            f'<w:style w:type="paragraph" w:styleId="Heading{level}">'
            f'<w:name w:val="heading {level}"/>'
            "<w:qFormat/>"
            "<w:rPr>"
            '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="SimHei"/>'
            f'<w:sz w:val="{size}"/>'
            "<w:b/>"
            "</w:rPr>"
            "</w:style>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:styles xmlns:w="{WORD_NAMESPACE}">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
        '<w:name w:val="Normal"/>'
        "<w:qFormat/>"
        "<w:rPr>"
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="SimSun"/>'
        '<w:sz w:val="22"/>'
        "</w:rPr>"
        "</w:style>"
        '<w:style w:type="paragraph" w:styleId="Title">'
        '<w:name w:val="Title"/>'
        "<w:qFormat/>"
        "<w:pPr><w:jc w:val=\"center\"/></w:pPr>"
        "<w:rPr>"
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="SimHei"/>'
        '<w:sz w:val="32"/>'
        "<w:b/>"
        "</w:rPr>"
        "</w:style>"
        f"{''.join(heading_styles)}"
        "</w:styles>"
    )


def content_types_xml(images: list[ImageAsset]) -> str:
    image_defaults = {
        "image/png": '<Default Extension="png" ContentType="image/png"/>',
        "image/jpeg": '<Default Extension="jpeg" ContentType="image/jpeg"/><Default Extension="jpg" ContentType="image/jpeg"/>',
        "image/gif": '<Default Extension="gif" ContentType="image/gif"/>',
        "image/bmp": '<Default Extension="bmp" ContentType="image/bmp"/>',
    }
    defaults = "".join(
        image_defaults[mime_type]
        for mime_type in sorted({asset.content_type for asset in images})
        if mime_type in image_defaults
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Types xmlns="{CONTENT_TYPES_NAMESPACE}">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f"{defaults}"
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        "</Types>"
    )


def package_relationships_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{REL_NAMESPACE}">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def document_relationships_xml(images: list[ImageAsset]) -> str:
    relationships = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    ]
    for asset in images:
        relationships.append(
            f'<Relationship Id="{asset.rel_id}" Type="{IMAGE_REL_TYPE}" Target="{asset.target}"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{REL_NAMESPACE}">'
        f"{''.join(relationships)}"
        "</Relationships>"
    )


def core_properties_xml(title: str | None) -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    safe_title = xml_text(title or "Bilingual Translation")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<cp:coreProperties xmlns:cp="{CORE_NAMESPACE}" xmlns:dc="{DC_NAMESPACE}" xmlns:dcterms="{DCTERMS_NAMESPACE}" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="{XSI_NAMESPACE}">'
        f"<dc:title>{safe_title}</dc:title>"
        "<dc:creator>en-cap-translator</dc:creator>"
        "<cp:lastModifiedBy>en-cap-translator</cp:lastModifiedBy>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>'
        "</cp:coreProperties>"
    )


def app_properties_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Properties xmlns="{EXTENDED_NAMESPACE}" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>en-cap-translator</Application>"
        "</Properties>"
    )


def write_docx(
    output_path: str,
    blocks: list[PairedBlock | SingleBlock],
    input_path: str,
    title: str | None,
) -> None:
    document_xml, images = build_document_xml(blocks, input_path, title)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml(images))
        archive.writestr("_rels/.rels", package_relationships_xml())
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/styles.xml", styles_xml())
        archive.writestr("word/_rels/document.xml.rels", document_relationships_xml(images))
        archive.writestr("docProps/core.xml", core_properties_xml(title))
        archive.writestr("docProps/app.xml", app_properties_xml())
        for asset in images:
            archive.writestr(asset.archive_name, asset.data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render canonical bilingual markdown to DOCX.")
    parser.add_argument("input", help="Validated bilingual markdown file.")
    parser.add_argument("output", help="Output DOCX file.")
    parser.add_argument("--title", default=None, help="Optional document title.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    blocks = load_validated_blocks(args.input)
    output = Path(args.output)
    write_docx(str(output), blocks, args.input, args.title)
    print(f"Wrote DOCX to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
