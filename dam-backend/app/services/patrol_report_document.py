"""Editable DOCX renderer for the daily patrol report."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import (
    WD_ALIGN_PARAGRAPH,
    WD_TAB_ALIGNMENT,
    WD_TAB_LEADER,
)
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor


BLUE = "0B4F8A"
BLUE_LIGHT = "EAF2F8"
TEXT = "243447"
MUTED = "64748B"
RULE = "D9E2EC"
HIGH = "C62828"
HIGH_BG = "FDECEC"
MEDIUM = "D97706"
MEDIUM_BG = "FFF4E5"
LOW = "356A9A"
LOW_BG = "EAF2F8"
GREEN = "1B7F4B"

SANS = "Noto Sans CJK SC"
SERIF = "Noto Serif CJK SC"

RISK_STYLE = {
    "HIGH": ("高风险", HIGH, HIGH_BG),
    "MEDIUM": ("中风险", MEDIUM, MEDIUM_BG),
    "LOW": ("低风险", LOW, LOW_BG),
}


def _font(run, *, name=SANS, size=9, color=TEXT, bold=False):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    run.bold = bold


def _text(paragraph, text, **kwargs):
    run = paragraph.add_run(str(text))
    _font(run, **kwargs)
    return run


def _paragraph(paragraph, *, align=None, before=0, after=0, line=1.15):
    if align is not None:
        paragraph.alignment = align
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    fmt.line_spacing = line


def _shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def _margins(cell, top=90, start=100, bottom=90, end=100):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for name, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{name}"))
        if node is None:
            node = OxmlElement(f"w:{name}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def _border(cell, **edges):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge_name, attrs in edges.items():
        edge = borders.find(qn(f"w:{edge_name}"))
        if edge is None:
            edge = OxmlElement(f"w:{edge_name}")
            borders.append(edge)
        for key, value in attrs.items():
            edge.set(qn(f"w:{key}"), str(value))


def _clear_borders(table):
    for row in table.rows:
        for cell in row.cells:
            none = {"val": "nil"}
            _border(cell, top=none, bottom=none, start=none, end=none)


def _crop_picture(paragraph, image_path, *, width, height, crop):
    inline = paragraph.add_run().add_picture(str(image_path), width=width, height=height)
    blip_fill = inline._inline.graphic.graphicData.pic.blipFill
    src_rect = OxmlElement("a:srcRect")
    for key in ("l", "t", "r", "b"):
        src_rect.set(key, str(int(crop.get(key, 0))))
    blip_fill.insert(1, src_rect)


def _field(paragraph, instruction):
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for node in (begin, instr, separate, text, end):
        run._r.append(node)
    _font(run, size=8, color=MUTED)


def _page_number_start(section, start=1):
    pg_num = section._sectPr.find(qn("w:pgNumType"))
    if pg_num is None:
        pg_num = OxmlElement("w:pgNumType")
        section._sectPr.append(pg_num)
    pg_num.set(qn("w:start"), str(start))


def _page(section):
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Mm(19)
    section.bottom_margin = Mm(17)
    section.left_margin = Mm(20)
    section.right_margin = Mm(20)
    section.header_distance = Mm(7)
    section.footer_distance = Mm(8)


def _header(section, board_image, report_date):
    header = section.header
    header.is_linked_to_previous = False
    table = header.add_table(rows=1, cols=2, width=Mm(170))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _clear_borders(table)
    left = table.cell(0, 0).paragraphs[0]
    _crop_picture(
        left,
        board_image,
        width=Mm(33),
        height=Mm(13.5),
        crop={"l": 1900, "t": 4700, "r": 85600, "b": 86800},
    )
    right = table.cell(0, 1).paragraphs[0]
    _paragraph(right, align=WD_ALIGN_PARAGRAPH.RIGHT, before=2)
    _text(right, "大藤峡空地联动每日巡检报告", size=8, color=MUTED)
    _text(right, f"   {report_date}", size=8, color=BLUE, bold=True)
    for cell in table.rows[0].cells:
        _border(cell, bottom={"val": "single", "sz": "8", "color": BLUE})


def _footer(section, report_date, numbered=True):
    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0]
    _paragraph(p, align=WD_ALIGN_PARAGRAPH.CENTER)
    _text(p, f"每日巡检报告 · {report_date}", size=7.5, color=MUTED)
    if numbered:
        _text(p, "    ·    ", size=7.5, color=RULE)
        _field(p, "PAGE")


def _section_title(document, number, title, color=BLUE):
    p = document.add_paragraph()
    _paragraph(p, after=5)
    _text(p, f"{number:02d}", name=SERIF, size=17, color=color)
    _text(p, f"  {title}", name=SERIF, size=17, color=color, bold=True)
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for key, value in (("val", "single"), ("sz", "14"), ("color", color), ("space", "5")):
        bottom.set(qn(f"w:{key}"), value)
    p_bdr.append(bottom)
    p._p.get_or_add_pPr().append(p_bdr)


def _cover(document, context, board_image):
    section = document.sections[0]
    _page(section)
    section.different_first_page_header_footer = True
    section.top_margin = Mm(13)
    section.bottom_margin = Mm(12)

    logo = document.add_paragraph()
    _paragraph(logo, align=WD_ALIGN_PARAGRAPH.LEFT, after=25)
    _crop_picture(
        logo,
        board_image,
        width=Mm(52),
        height=Mm(21.3),
        crop={"l": 1900, "t": 4700, "r": 85600, "b": 86800},
    )
    title = document.add_paragraph()
    _paragraph(title, align=WD_ALIGN_PARAGRAPH.CENTER, after=18)
    _text(title, "大藤峡空地联动每日巡检报告", name=SERIF, size=25, color=BLUE, bold=True)

    photo = document.add_paragraph()
    _paragraph(photo, align=WD_ALIGN_PARAGRAPH.CENTER, after=13)
    _crop_picture(
        photo,
        board_image,
        width=Mm(166),
        height=Mm(142.5),
        crop={"l": 780, "t": 33860, "r": 74300, "b": 28800},
    )
    date = document.add_paragraph()
    _paragraph(date, align=WD_ALIGN_PARAGRAPH.CENTER, after=5)
    _text(date, context["report_date_cn"], name=SERIF, size=16, color=BLUE, bold=True)
    code = document.add_paragraph()
    _paragraph(code, align=WD_ALIGN_PARAGRAPH.CENTER)
    _text(code, f"文档编号：DX-XJRB-{context['report_date_compact']}", size=8.5, color=MUTED)


def _contents(document, context, board_image):
    document.add_page_break()
    _header(document.sections[0], board_image, context["report_date"])
    _footer(document.sections[0], context["report_date"], numbered=False)
    p = document.add_paragraph()
    _paragraph(p, after=23)
    _text(p, "目录", name=SERIF, size=20, color=BLUE, bold=True)
    items = [
        ("01", "当日风险统计", "1"),
        ("02", "高风险事件", "2"),
        ("03", "中风险事件", "3"),
        ("04", "低风险事件", "4"),
    ]
    for number, title, page in items:
        row = document.add_paragraph()
        _paragraph(row, after=15)
        tabs = row.paragraph_format.tab_stops
        tabs.add_tab_stop(Mm(18), WD_TAB_ALIGNMENT.LEFT)
        tabs.add_tab_stop(Mm(168), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        _text(row, number, name=SERIF, size=12, color=BLUE, bold=True)
        _text(row, f"\t{title}\t", name=SERIF, size=11.5, color=TEXT)
        _text(row, page, name=SERIF, size=11.5, color=BLUE)


def _start_body(document, context, board_image):
    section = document.add_section(WD_SECTION.NEW_PAGE)
    _page(section)
    section.different_first_page_header_footer = False
    _page_number_start(section, 1)
    _header(section, board_image, context["report_date"])
    _footer(section, context["report_date"])


def _summary(document, context):
    stats = context["stats"]
    _section_title(document, 1, "当日风险统计")
    p = document.add_paragraph()
    _paragraph(p, after=8, line=1.35)
    if stats["total_events"]:
        _text(p, "当日共记录 ", size=10)
        _text(p, stats["total_events"], size=11, color=BLUE, bold=True)
        _text(
            p,
            f" 起风险事件：高风险 {stats['high_count']} 起、中风险 {stats['medium_count']} 起、低风险 {stats['low_count']} 起；"
            f"已闭环 {stats['closed_count']} 起，待跟进 {stats['open_count']} 起。",
            size=10,
        )
    else:
        _text(p, "当日未记录风险事件。", size=10, color=GREEN, bold=True)

    metrics = [
        ("事件总数", stats["total_events"], BLUE, BLUE_LIGHT),
        ("高风险", stats["high_count"], HIGH, HIGH_BG),
        ("中风险", stats["medium_count"], MEDIUM, MEDIUM_BG),
        ("低风险", stats["low_count"], LOW, LOW_BG),
        ("已闭环", stats["closed_count"], GREEN, "EAF6EF"),
        ("待跟进", stats["open_count"], MUTED, "F2F4F7"),
    ]
    table = document.add_table(rows=2, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for index, (label, value, color, bg) in enumerate(metrics):
        cell = table.cell(index // 3, index % 3)
        _shade(cell, bg)
        _margins(cell, top=150, bottom=150, start=150, end=150)
        p1 = cell.paragraphs[0]
        _paragraph(p1, align=WD_ALIGN_PARAGRAPH.CENTER)
        _text(p1, value, name=SERIF, size=20, color=color, bold=True)
        p2 = cell.add_paragraph()
        _paragraph(p2, align=WD_ALIGN_PARAGRAPH.CENTER)
        _text(p2, label, size=8.5)

    h = document.add_paragraph()
    _paragraph(h, before=11, after=4)
    _text(h, "事件来源", name=SERIF, size=12, color=BLUE, bold=True)
    source = document.add_table(rows=3, cols=3)
    source.style = "Table Grid"
    source_data = [
        ("来源", "事件数（起）", "占比"),
        ("传感器事件", stats["sensor_count"], stats["sensor_rate"]),
        ("视觉检测事件", stats["camera_count"], stats["camera_rate"]),
    ]
    for row_index, values in enumerate(source_data):
        for col_index, value in enumerate(values):
            cell = source.cell(row_index, col_index)
            _margins(cell)
            if row_index == 0:
                _shade(cell, BLUE_LIGHT)
            p = cell.paragraphs[0]
            _paragraph(p, align=WD_ALIGN_PARAGRAPH.CENTER)
            _text(p, value, size=8.5, color=BLUE if row_index == 0 else TEXT, bold=row_index == 0)

    h2 = document.add_paragraph()
    _paragraph(h2, before=10, after=4)
    _text(h2, "当日结论", name=SERIF, size=12, color=BLUE, bold=True)
    box = document.add_table(rows=1, cols=1)
    cell = box.cell(0, 0)
    _shade(cell, BLUE_LIGHT)
    _margins(cell, top=150, bottom=150, start=170, end=170)
    _border(cell, start={"val": "single", "sz": "22", "color": BLUE})
    _text(cell.paragraphs[0], context["conclusion"], size=9.5, color=BLUE, bold=True)


def _event_block(document, event, risk_key):
    risk_label, color, bg = RISK_STYLE[risk_key]
    table = document.add_table(rows=5, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for row in table.rows:
        for cell in row.cells:
            _margins(cell)
            _border(cell, bottom={"val": "single", "sz": "5", "color": RULE})
    head = table.cell(0, 0).merge(table.cell(0, 2))
    _shade(head, bg)
    _text(head.paragraphs[0], event["event_name"], name=SERIF, size=11.5, color=color, bold=True)
    _text(head.paragraphs[0], f"    {event['instance_no']}", size=8, color=MUTED)
    badge = table.cell(0, 3)
    _shade(badge, bg)
    badge.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _text(badge.paragraphs[0], risk_label, size=9, color=color, bold=True)

    pairs = [
        ("发生时间", event["occur_time"], "来源 / 位置", f"{event['source_label']} · {event['location']}"),
        ("关键观测", event["key_observation"], "当前状态", event["result_label"]),
        ("处置情况", event["handling_summary"], "完成时间", event["completed_at"]),
        ("事件摘要", event["summary"], "", ""),
    ]
    for row_index, values in enumerate(pairs, 1):
        if row_index == 4:
            table.cell(row_index, 1).merge(table.cell(row_index, 3))
        columns = range(2) if row_index == 4 else range(4)
        for col_index in columns:
            value = values[col_index]
            cell = table.cell(row_index, col_index)
            if col_index in (0, 2) and value:
                _shade(cell, "F7F9FB")
            _text(
                cell.paragraphs[0],
                value or "—",
                size=8.2,
                color=MUTED if col_index in (0, 2) else (GREEN if value == "已闭环" else TEXT),
                bold=col_index in (0, 2) or value == "已闭环",
            )

    images = event.get("evidence_images") or []
    if images:
        label = document.add_paragraph()
        _paragraph(label, before=5, after=3)
        _text(label, "图像佐证", size=9, color=color, bold=True)
        for index, evidence in enumerate(images[:2], 1):
            p = document.add_paragraph()
            _paragraph(p, align=WD_ALIGN_PARAGRAPH.CENTER, after=2)
            p.add_run().add_picture(io.BytesIO(evidence["content"]), width=Mm(145))
            caption = document.add_paragraph()
            _paragraph(caption, align=WD_ALIGN_PARAGRAPH.CENTER, after=5)
            description = evidence.get("description") or f"事件图像 {index}"
            captured_at = evidence.get("captured_at") or ""
            _text(caption, f"{description}{' · ' + captured_at if captured_at else ''}", size=7.5, color=MUTED)
    elif event["source_type"] == "camera":
        p = document.add_paragraph()
        _paragraph(p, before=4, after=5)
        _text(p, "图像佐证：无可用图像", size=8, color=MUTED)
    document.add_paragraph().paragraph_format.space_after = Pt(2)


def _risk_page(document, context, number, risk_key):
    document.add_page_break()
    label, color, _ = RISK_STYLE[risk_key]
    _section_title(document, number, f"{label}事件", color=color)
    events = context["events_by_risk"][risk_key]
    if not events:
        p = document.add_paragraph()
        _paragraph(p, before=8)
        _text(p, f"当日无{label}事件。", size=10, color=GREEN, bold=True)
        return
    for event in events:
        _event_block(document, event, risk_key)


def render_daily_report_docx(context: dict[str, Any], board_image: Path) -> bytes:
    if not board_image.is_file():
        raise FileNotFoundError(f"report cover asset is missing: {board_image}")
    document = Document()
    normal = document.styles["Normal"]
    normal.font.name = SANS
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), SANS)
    normal.font.size = Pt(9)
    document.core_properties.title = f"每日巡检报告{context['report_date']}"
    document.core_properties.subject = "传感器事件与视觉检测事件每日汇总"
    document.core_properties.author = "box_system"

    _cover(document, context, board_image)
    _contents(document, context, board_image)
    _start_body(document, context, board_image)
    _summary(document, context)
    _risk_page(document, context, 2, "HIGH")
    _risk_page(document, context, 3, "MEDIUM")
    _risk_page(document, context, 4, "LOW")

    output = io.BytesIO()
    document.save(output)
    return output.getvalue()
