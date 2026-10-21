"""
Export collection entries to a printable PDF in the style of a 5e book page: parchment-coloured pages, two
columns, dark red headings with a gold rule, and monster stat blocks in a tan box.

``export_pdf(path, entries, options)`` takes the entries a collection page has ticked (spells, feats, species,
backgrounds, equipment, magic items, monsters) and writes the PDF with reportlab, using the PDF's built-in
Times fonts so nothing has to be bundled. Description markup is the app's own (``# headings``, ``**bold**``,
``*italic*``, list lines, ``| tables |`` and ``[[links]]``, which print as their text).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Tuple

PARCHMENT = "#EEE5CE"
HEADING = "#58180D"
RULE = "#C9AD6A"
STAT_BOX = "#FDF1DC"
STAT_RULE = "#9C2B1B"
TABLE_STRIPE = "#E0E5C1"


def available() -> bool:
    """Whether reportlab (which writes the PDF) is installed."""
    try:
        import reportlab  # noqa: F401
        return True
    except ImportError:
        return False


@dataclass
class ExportOptions:
    title: str = "Spellbook Export"
    columns: int = 2
    parchment: bool = True
    page_size: str = "Letter"            # or "A4"
    page_numbers: bool = True


@dataclass
class Block:
    """One entry, ready to print."""
    title: str
    subtitle: str = ""                   # italic line under the title ("Level 3 Evocation")
    stats: List[Tuple[str, str]] = field(default_factory=list)      # ("Casting Time", "Action")
    body: str = ""                       # markup
    monster: Optional[object] = None     # a monster prints as a stat block


# --------------------------------------------------------------------------- #
# Entries -> blocks
# --------------------------------------------------------------------------- #

def block_for(entry) -> Block:
    """The printable form of one collection entry (dispatches on its class name)."""
    kind = type(entry).__name__
    name = getattr(entry, "name", "")
    if kind == "Spell":
        stats = [("Casting Time", entry.display_casting_time()), ("Range", entry.display_range()),
                 ("Components", entry.components), ("Duration", entry.display_duration())]
        classes = entry.display_classes() if hasattr(entry, "display_classes") else ""
        subtitle = entry.display_level() + (f" ({classes})" if classes else "")
        return Block(name, subtitle, stats, entry.display_description())
    if kind == "Feat":
        subtitle = (entry.type + " Feat") if entry.type else "Feat"
        stats = [("Prerequisite", entry.prereq)] if entry.prereq else []
        return Block(name, subtitle, stats, entry.description)
    if kind in ("MagicItem", "Equipment"):
        if kind == "MagicItem":
            rarity = getattr(entry.rarity, "value", str(entry.rarity))
            subtitle = f"{entry.type}, {rarity}"
            if entry.requires_attunement:
                req = entry.attunement_requirement
                subtitle += f" (requires attunement{' ' + req if req else ''})"
        else:
            subtitle = entry.type
        stats = []
        if entry.cost:
            stats.append(("Cost", entry.cost))
        if entry.weight:
            stats.append(("Weight", entry.display_weight()))
        props = ", ".join(p.get("name", "") + (f" ({p['value']})" if p.get("value") else "")
                          for p in (entry.properties or []) if isinstance(p, dict) and p.get("name"))
        if props:
            stats.append(("Properties", props))
        return Block(name, subtitle, stats, entry.description)
    if kind == "Lineage":
        stats = [("Creature Type", entry.creature_type), ("Size", entry.size), ("Speed", f"{entry.speed} feet")]
        body = entry.description
        for t in entry.traits:
            body += f"\n\n***{t.name}.*** {t.description}"
        return Block(name, "Species", stats, body.strip())
    if kind == "Background":
        stats = []
        for label, values in (("Ability Scores", entry.ability_scores), ("Feat", entry.feats),
                              ("Skill Proficiencies", entry.skills), ("Tool Proficiencies", entry.other_proficiencies)):
            if values:
                stats.append((label, ", ".join(values)))
        if entry.equipment:
            stats.append(("Equipment", entry.equipment))
        body = entry.description
        for f in entry.features:
            body += f"\n\n***{f.name}.*** {f.description}"
        return Block(name, "Background", stats, body.strip())
    if kind == "Monster":
        return Block(name, entry.get_type_line(), monster=entry)
    if kind == "CharacterClassDefinition":
        stats = [("Primary Ability", entry.primary_ability), ("Hit Die", entry.hit_die),
                 ("Saving Throws", ", ".join(entry.saving_throw_proficiencies)),
                 ("Skills", f"Choose {entry.skill_proficiency_choices}: " + ", ".join(entry.skill_proficiency_options)
                  if entry.skill_proficiency_options else ""),
                 ("Weapons", ", ".join(entry.weapon_proficiencies)), ("Armor", ", ".join(entry.armor_proficiencies)),
                 ("Tools", ", ".join(entry.tool_proficiencies))]
        body = entry.description or ""
        for level in sorted(entry.levels):
            for ability in entry.levels[level].abilities:
                if not getattr(ability, "is_subclass_feature", False):
                    body += f"\n\n### Level {level}: {ability.title}\n\n{ability.description}"
        return Block(name, "Class", [(k, v) for k, v in stats if v], body.strip())
    if kind == "SubclassDefinition":
        body = entry.description or ""
        for feature in sorted(entry.features, key=lambda f: f.level):
            body += f"\n\n### Level {feature.level}: {feature.title}\n\n{feature.description}"
        return Block(name, f"{entry.parent_class} Subclass", [], body.strip())
    if kind == "RulePage":
        return Block(name, entry.category, [], entry.description)
    # anything else with a name and a description
    return Block(name, "", [], getattr(entry, "description", ""))


# --------------------------------------------------------------------------- #
# Markup -> reportlab
# --------------------------------------------------------------------------- #

_LINK = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+))?\]\]")


def inline(text: str) -> str:
    """One line of markup as reportlab paragraph XML."""
    def link(m):
        shown = m.group(2) or m.group(1).split(":", 1)[-1].split("#")[-1]
        return shown
    text = _LINK.sub(link, text or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(?:p|div|span)[^>]*>", "", text, flags=re.IGNORECASE)
    text = html.escape(html.unescape(text), quote=False)
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)
    text = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])", r"<i>\1</i>", text)
    return text.replace("\n", "<br/>")


_LIST = re.compile(r"^(\s*)(?:•|[-*]|\d+\.)\s+(.*)$")
_HEAD = re.compile(r"^(#{1,4})\s+(.+?)\s*$")


def body_flowables(markup: str, styles) -> list:
    """Paragraphs, headings, lists and tables from a description."""
    from reportlab.platypus import Paragraph
    out = []
    lines = (markup or "").replace("\r\n", "\n").split("\n")
    i = 0
    para: List[str] = []

    def flush():
        if para:
            out.append(Paragraph(inline(" ".join(para)), styles["body"]))
            para.clear()

    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            flush()
            i += 1
            continue
        if line.lstrip().startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                out.append(_table(rows, styles))
            continue
        m = _HEAD.match(line)
        if m:
            flush()
            level = len(m.group(1))
            out.append(Paragraph(inline(m.group(2)), styles["h3" if level <= 2 else "h4"]))
            i += 1
            continue
        m = _LIST.match(line)
        if m:
            flush()
            out.append(Paragraph(inline(m.group(2)), styles["bullet"], bulletText="•"))
            i += 1
            continue
        if line.lstrip().startswith("---") and set(line.strip()) == {"-"}:
            flush()
            i += 1
            continue
        para.append(line.strip())
        i += 1
    flush()
    return out


def _table(rows: List[List[str]], styles):
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle
    width = max(len(r) for r in rows)
    data = []
    for n, r in enumerate(rows):
        r = r + [""] * (width - len(r))
        style = styles["cell_head"] if n == 0 else styles["cell"]
        data.append([Paragraph(inline(c), style) for c in r])
    # every column is at least as wide as its longest word; the rest of the width goes by how much text it holds
    from reportlab.pdfbase.pdfmetrics import stringWidth
    total = styles.get("_width", 240.0)
    pad = 6.5

    def plain(t):
        return re.sub(r"[*_`]|\[\[[^:\]]*:|\]\]", "", t)

    cols = [[plain(r[c]) for r in rows if c < len(r)] for c in range(width)]
    least = [max((stringWidth(w, "Times-Bold", 8.5) for t in col for w in t.split()), default=0) + pad
             for col in cols]
    weight = [max((min(len(t), 60) for t in col), default=1) + 2 for col in cols]
    spare = max(0.0, total - sum(least))
    weight = [w ** 1.5 for w in weight]          # favour the wordy columns
    widths = [lo + spare * w / sum(weight) for lo, w in zip(least, weight)]
    if sum(widths) > total:                  # too many columns for the page: shrink them all alike
        widths = [w * total / sum(widths) for w in widths]
    table = Table(data, colWidths=widths, hAlign="LEFT", repeatRows=1)
    commands = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]
    for n in range(1, len(data)):
        if n % 2:
            commands.append(("BACKGROUND", (0, n), (-1, n), colors.HexColor(TABLE_STRIPE)))
    table.setStyle(TableStyle(commands))
    return table


# --------------------------------------------------------------------------- #
# Styles and pages
# --------------------------------------------------------------------------- #

def make_styles():
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    red = colors.HexColor(HEADING)
    base = ParagraphStyle("body", fontName="Times-Roman", fontSize=9.5, leading=11.6, spaceAfter=4,
                          textColor=colors.black)
    return {
        "doc_title": ParagraphStyle("doc_title", parent=base, fontName="Times-Bold", fontSize=26, leading=30,
                                    textColor=red, spaceAfter=10),
        "title": ParagraphStyle("title", parent=base, fontName="Times-Bold", fontSize=15, leading=17,
                                textColor=red, spaceBefore=8, spaceAfter=0),
        "subtitle": ParagraphStyle("subtitle", parent=base, fontName="Times-Italic", fontSize=9.5, spaceAfter=3),
        "stat": ParagraphStyle("stat", parent=base, spaceAfter=0, leftIndent=0),
        "body": base,
        "bullet": ParagraphStyle("bullet", parent=base, leftIndent=10, bulletIndent=2, spaceAfter=2),
        "h3": ParagraphStyle("h3", parent=base, fontName="Times-Bold", fontSize=11.5, leading=13, textColor=red,
                             spaceBefore=4, spaceAfter=2),
        "h4": ParagraphStyle("h4", parent=base, fontName="Times-BoldItalic", fontSize=10, leading=12,
                             spaceBefore=2, spaceAfter=1),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8.5, leading=10, spaceAfter=0),
        "cell_head": ParagraphStyle("cell_head", parent=base, fontName="Times-Bold", fontSize=8.5, leading=10,
                                    spaceAfter=0),
        "sb_name": ParagraphStyle("sb_name", parent=base, fontName="Times-Bold", fontSize=14, leading=16,
                                  textColor=red, spaceAfter=0),
        "sb_line": ParagraphStyle("sb_line", parent=base, fontSize=9, leading=10.8, spaceAfter=0,
                                  textColor=red),
        "sb_body": ParagraphStyle("sb_body", parent=base, fontSize=9, leading=10.8, spaceAfter=3),
        "sb_head": ParagraphStyle("sb_head", parent=base, fontName="Times-Bold", fontSize=11, leading=13,
                                  textColor=red, spaceBefore=4, spaceAfter=2),
    }


def rule(color: str, thickness: float = 1.2, space: float = 3):
    from reportlab.lib import colors
    from reportlab.platypus.flowables import HRFlowable
    return HRFlowable(width="100%", thickness=thickness, color=colors.HexColor(color), spaceBefore=1,
                      spaceAfter=space)


def entry_flowables(block: Block, styles) -> list:
    from reportlab.platypus import KeepTogether, Paragraph
    if block.monster is not None:
        return [monster_flowable(block.monster, styles)]
    head = [Paragraph(inline(block.title), styles["title"]), rule(RULE, 1.4, 2)]
    if block.subtitle:
        head.append(Paragraph(inline(block.subtitle), styles["subtitle"]))
    for label, value in block.stats:
        head.append(Paragraph(f"<b>{html.escape(label)}:</b> {inline(value)}", styles["stat"]))
    if block.stats:
        head.append(Paragraph("", styles["body"]))
    body = body_flowables(block.body, styles)
    return [KeepTogether(head + body[:1])] + body[1:]


def _mod(score: int) -> str:
    m = (score - 10) // 2
    return f"+{m}" if m >= 0 else str(m)


def monster_flowable(monster, styles):
    """A monster's stat block: a tan box with red rules."""
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle
    from character_sheet import AbilityScore
    s = styles
    parts = [Paragraph(inline(monster.name), s["sb_name"]),
             Paragraph(f"<i>{html.escape(monster.get_type_line())}</i>", s["sb_body"]), rule(STAT_RULE, 1.6, 3)]

    def line(label, value):
        if value:
            parts.append(Paragraph(f"<b>{label}</b> {inline(str(value))}", s["sb_line"]))

    line("Armor Class", monster.display_ac())
    if getattr(monster, "show_initiative", True):
        line("Initiative", monster.display_initiative())
    line("Hit Points", monster.display_hp())
    line("Speed", monster.display_speed())
    parts.append(rule(STAT_RULE, 1.6, 3))
    abilities = list(AbilityScore)
    head, vals = [], []
    for a in abilities:
        score = monster.ability_scores.get(a)
        head.append(Paragraph(f"<b>{AbilityScore.short_name(a).upper()}</b>", s["cell_head"]))
        vals.append(Paragraph(f"{score} ({_mod(score)})", s["cell"]))
    grid = Table([head, vals], hAlign="CENTER")
    grid.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("LEFTPADDING", (0, 0), (-1, -1), 1),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 1), ("TOPPADDING", (0, 0), (-1, -1), 0),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    parts.append(grid)
    parts.append(rule(STAT_RULE, 1.6, 3))
    line("Skills", monster.display_skills())
    line("Vulnerabilities", monster.display_vulnerabilities())
    line("Resistances", monster.display_resistances())
    line("Immunities", monster.display_immunities())
    line("Gear", monster.display_gear())
    line("Senses", monster.display_senses())
    line("Languages", monster.display_languages())
    line("CR", monster.display_cr().removeprefix("CR ").strip())
    parts.append(rule(STAT_RULE, 1.6, 3))
    sections = [("", monster.traits), ("Actions", monster.actions), ("Bonus Actions", monster.bonus_actions),
                ("Reactions", monster.reactions), ("Legendary Actions", monster.legendary_actions),
                ("Lair Actions", getattr(monster, "lair_actions", []))]
    for heading, features in sections:
        if not features:
            continue
        if heading:
            parts.append(Paragraph(heading, s["sb_head"]))
            parts.append(rule(STAT_RULE, 0.8, 2))
            if heading == "Legendary Actions":
                intro = monster.get_legendary_intro()
                if intro:
                    parts.append(Paragraph(inline(intro), s["sb_body"]))
        for f in features:
            text = (f.description or "").replace("\n\n", "\n")
            parts.append(Paragraph(f"<b><i>{html.escape(f.name)}.</i></b> {inline(text)}", s["sb_body"]))
    box = Table([[p] for p in parts], colWidths=None, hAlign="LEFT")
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(STAT_BOX)),
                             ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                             ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                             ("TOPPADDING", (0, 0), (-1, 0), 5), ("BOTTOMPADDING", (0, -1), (-1, -1), 5),
                             ("LINEABOVE", (0, 0), (-1, 0), 3, colors.HexColor("#E69A28")),
                             ("LINEBELOW", (0, -1), (-1, -1), 3, colors.HexColor("#E69A28"))]))
    return box


def export_pdf(path: str, entries: Iterable, options: Optional[ExportOptions] = None) -> int:
    """Write the entries to a PDF at ``path``. Returns how many were written."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, LETTER
    from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer

    options = options or ExportOptions()
    blocks = [block_for(e) for e in entries]
    page = A4 if options.page_size.upper() == "A4" else LETTER
    margin, gap = 46, 18
    columns = 2 if options.columns >= 2 else 1
    width, height = page
    col_w = (width - 2 * margin - gap * (columns - 1)) / columns
    frames = [Frame(margin + i * (col_w + gap), margin, col_w, height - 2 * margin, id=f"c{i}",
                    leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0) for i in range(columns)]

    def decorate(canvas, doc):
        canvas.saveState()
        if options.parchment:
            canvas.setFillColor(colors.HexColor(PARCHMENT))
            canvas.rect(0, 0, width, height, stroke=0, fill=1)
        if options.page_numbers:
            canvas.setFont("Times-Roman", 9)
            canvas.setFillColor(colors.HexColor(HEADING))
            canvas.drawCentredString(width / 2, margin / 2, str(doc.page))
        if columns == 2:
            canvas.setStrokeColor(colors.HexColor(RULE))
            canvas.setLineWidth(0.4)
            canvas.line(width / 2, margin, width / 2, height - margin)
        canvas.restoreState()

    doc = BaseDocTemplate(path, pagesize=page, title=options.title, author="Spellbook",
                          leftMargin=margin, rightMargin=margin, topMargin=margin, bottomMargin=margin)
    doc.addPageTemplates([PageTemplate(id="page", frames=frames, onPage=decorate)])
    styles = make_styles()
    styles["_width"] = col_w
    story = []
    if options.title:
        story += [Paragraph(inline(options.title), styles["doc_title"]), rule(RULE, 2, 6)]
    for block in blocks:
        story += entry_flowables(block, styles)
        story.append(Spacer(1, 6))
    doc.build(story)
    return len(blocks)
