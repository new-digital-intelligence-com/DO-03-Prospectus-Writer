#!/usr/bin/env python3
"""Fill a token-based .docx template, pruning dropped slots and whole sections.

    fill_docx.py TEMPLATE VALUES.json OUTPUT
        [--drop-slots TOKEN,TOKEN] [--drop-sections "Heading","Heading"] [--list-tokens]

The .docx sibling of fill_template.py, and it belongs to the archetype rather than
any pack: "produce from a template" is not "produce a PowerPoint".

Two differences from the pptx filler, both forced by the format:

1. **Pruning is structural, not geometric.** A Word document has no shapes laid out
   in columns, so there is no band to delete. A dropped slot's whole paragraph goes;
   if that paragraph was the only text in a table row, the row goes with it. Clearing
   the text alone leaves an empty bullet, an empty row, or a heading with nothing
   under it — all of which reach the reader.

2. **Sections are named by their heading, not numbered.** `--drop-sections` takes
   heading *text* and removes that heading plus everything beneath it until the next
   heading of the same or higher outline level. Ordinals were tried in the pptx
   filler and put the group-to-position mapping in the operator's head instead of in
   the config (DO-23 eval finding F6); heading text keeps it in the config.

Tokens split across runs are handled: Word routinely breaks {{FOO}} into three
<w:t> elements after a spell-check pass, so a naive per-element replace silently
misses them and the token survives into the delivered file.

Exits non-zero if any token survives anywhere — body, headers or footers. That is
QA check 1, not a warning.
"""
import argparse, json, re, shutil, sys, zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from defusedxml import minidom

TOKEN_RE = re.compile(r'\{\{([A-Z0-9_]+)\}\}')

# Every part whose text the reader can see. Headers and footers matter: a prospectus
# template carries the offering name and the version label up there, and a token left
# in a footer appears on every single page.
TEXT_PARTS = ('word/document.xml',)
TEXT_GLOBS = ('word/header*.xml', 'word/footer*.xml', 'word/footnotes.xml',
              'word/endnotes.xml')


def unpack(src: Path, work: Path) -> None:
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    with zipfile.ZipFile(src) as z:
        z.extractall(work)


def text_parts(work: Path):
    out = [work / p for p in TEXT_PARTS if (work / p).exists()]
    for g in TEXT_GLOBS:
        out += sorted((work / 'word').glob(g.split('/', 1)[1]))
    return out


def para_text(p) -> str:
    return ''.join(t.firstChild.nodeValue or ''
                   for t in p.getElementsByTagName('w:t') if t.firstChild)


def outline_level(p):
    """Heading depth of a paragraph, or None when it is body text.

    Word records this two ways and templates use both: a named style
    (`w:pStyle val="Heading2"`) or an explicit outline level
    (`w:outlineLvl val="1"`). Reading only pStyle misses documents built from a
    theme, which is most client templates.
    """
    for pr in p.getElementsByTagName('w:pPr'):
        for lvl in pr.getElementsByTagName('w:outlineLvl'):
            v = lvl.getAttribute('w:val')
            if v.isdigit():
                return int(v) + 1
        for st in pr.getElementsByTagName('w:pStyle'):
            m = re.fullmatch(r'(?:Heading|heading)\s*(\d)', st.getAttribute('w:val') or '')
            if m:
                return int(m.group(1))
    return None


def paragraphs(part: Path):
    dom = minidom.parseString(part.read_text(encoding='utf-8'))
    return dom, dom.getElementsByTagName('w:p')


def list_tokens(work: Path) -> dict:
    found = {}
    for part in text_parts(work):
        for t in TOKEN_RE.findall(part.read_text(encoding='utf-8')):
            found.setdefault(t, []).append(part.name)
    return found


def row_of(p):
    """The w:tr ancestor of a paragraph, if it sits in a table."""
    n = p.parentNode
    while n is not None and getattr(n, 'tagName', None) != 'w:tr':
        n = n.parentNode
    return n


def row_is_empty_but(tr, doomed) -> bool:
    """True when every paragraph in this row is among those being deleted.

    A three-column spec table whose middle cell held a dropped slot must keep the
    row — the other two cells still say something. A row whose every cell is going
    is an empty row, and an empty row is visible.
    """
    ps = tr.getElementsByTagName('w:p')
    return bool(ps) and all(p in doomed for p in ps if para_text(p).strip())


def drop_empty_tables(dom) -> int:
    """Remove any w:tbl left with no rows.

    Deleting the rows of a table does not delete the table. A `<w:tbl>` with zero
    `<w:tr>` children is invalid against the OOXML schema, and Word responds by
    offering to repair the file — which is what the reader sees instead of the
    document. Found while verifying the first DO-03 fill: dropping the "Service
    tiers" section removed all four rows and left the shell behind.
    """
    n = 0
    for tbl in list(dom.getElementsByTagName('w:tbl')):
        if not tbl.getElementsByTagName('w:tr') and tbl.parentNode is not None:
            tbl.parentNode.removeChild(tbl)
            n += 1
    return n


def prune_slots(part: Path, tokens: set) -> int:
    if not tokens:
        return 0
    dom, ps = paragraphs(part)
    pat = re.compile('|'.join(re.escape('{{%s}}' % t) for t in sorted(tokens)))
    doomed = [p for p in ps if pat.search(para_text(p))]
    if not doomed:
        return 0
    dset = set(doomed)
    rows, kill = set(), []
    for p in doomed:
        tr = row_of(p)
        if tr is not None and row_is_empty_but(tr, dset):
            rows.add(tr)
        else:
            kill.append(p)
    n = 0
    for tr in rows:
        tr.parentNode.removeChild(tr)
        n += 1
    for p in kill:
        # A row already removed takes its paragraphs with it; removing them again
        # raises. Checking parentNode is cheaper than tracking descendants.
        if p.parentNode is not None:
            p.parentNode.removeChild(p)
            n += 1
    n += drop_empty_tables(dom)
    part.write_text(dom.toxml(), encoding='utf-8')
    return n


def drop_sections(part: Path, headings: set) -> int:
    """Delete each named heading and its subtree, matched on normalised text."""
    if not headings:
        return 0
    want = {re.sub(r'\s+', ' ', h).strip().casefold() for h in headings}
    dom, ps = paragraphs(part)
    doomed, i = [], 0
    while i < len(ps):
        p = ps[i]
        lvl = outline_level(p)
        txt = re.sub(r'\s+', ' ', para_text(p)).strip().casefold()
        if lvl is not None and txt in want:
            doomed.append(p)
            j = i + 1
            while j < len(ps):
                nxt = outline_level(ps[j])
                if nxt is not None and nxt <= lvl:
                    break        # next heading of same or higher rank ends the section
                doomed.append(ps[j])
                j += 1
            i = j
            continue
        i += 1
    if not doomed:
        return 0
    dset = set(doomed)
    rows = {tr for tr in (row_of(p) for p in doomed)
            if tr is not None and row_is_empty_but(tr, dset)}
    for tr in rows:
        tr.parentNode.removeChild(tr)
    for p in doomed:
        if p.parentNode is not None:
            p.parentNode.removeChild(p)
    n = len(doomed) + drop_empty_tables(dom)
    part.write_text(dom.toxml(), encoding='utf-8')
    return n


def fill_part(part: Path, values: dict) -> None:
    """Substitute tokens, handling the ones Word has split across runs.

    Pass 1 replaces tokens that sit whole inside one <w:t>, which preserves every
    run's own formatting. Pass 2 only touches paragraphs where a token is still
    matched after joining the runs: there the joined text is written into the first
    <w:t> and the rest are emptied, which costs mid-paragraph formatting in that
    one paragraph. Doing pass 2 unconditionally would flatten bold and links
    throughout the document.
    """
    dom, ps = paragraphs(part)
    def sub(s: str) -> str:
        return TOKEN_RE.sub(lambda m: escape(str(values.get(m.group(1), m.group(0)))), s)

    for t in dom.getElementsByTagName('w:t'):
        if t.firstChild and t.firstChild.nodeValue:
            t.firstChild.nodeValue = sub(t.firstChild.nodeValue)

    for p in ps:
        ts = [t for t in p.getElementsByTagName('w:t') if t.firstChild]
        if len(ts) < 2:
            continue
        joined = ''.join(t.firstChild.nodeValue or '' for t in ts)
        if not TOKEN_RE.search(joined):
            continue
        filled = sub(joined)
        if filled == joined:
            continue                    # token has no value — leave it for QA to catch
        ts[0].firstChild.nodeValue = filled
        # xml:space must be preserved or Word trims the leading space of a run that
        # now begins with one.
        ts[0].setAttribute('xml:space', 'preserve')
        for t in ts[1:]:
            t.firstChild.nodeValue = ''
    part.write_text(dom.toxml(), encoding='utf-8')


def repack(work: Path, out: Path) -> None:
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(work.rglob('*')):
            if f.is_file():
                z.write(f, f.relative_to(work).as_posix())


def survivors(out: Path) -> dict:
    found = {}
    with zipfile.ZipFile(out) as z:
        for n in z.namelist():
            if not n.startswith('word/') or not n.endswith('.xml'):
                continue
            for t in TOKEN_RE.findall(z.read(n).decode('utf-8', 'replace')):
                found.setdefault(t, []).append(n)
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('template')
    ap.add_argument('values', nargs='?')
    ap.add_argument('output', nargs='?')
    ap.add_argument('--drop-slots', default='')
    ap.add_argument('--drop-sections', default='')
    ap.add_argument('--list-tokens', action='store_true')
    a = ap.parse_args()

    src = Path(a.template)
    work = Path('.fill_docx_work')
    unpack(src, work)

    if a.list_tokens:
        print(json.dumps({k: sorted(set(v)) for k, v in list_tokens(work).items()},
                         indent=2, sort_keys=True))
        shutil.rmtree(work)
        return

    if not a.values or not a.output:
        sys.exit('VALUES.json and OUTPUT are required unless --list-tokens is given')

    values = json.loads(Path(a.values).read_text(encoding='utf-8'))
    slots = {t.strip().strip('{}') for t in a.drop_slots.split(',') if t.strip()}
    sections = [s.strip().strip('"') for s in a.drop_sections.split(',') if s.strip()]

    n_sec = n_slot = 0
    for part in text_parts(work):
        n_sec += drop_sections(part, set(sections))
    for part in text_parts(work):
        n_slot += prune_slots(part, slots)
    for part in text_parts(work):
        fill_part(part, values)

    out = Path(a.output)
    repack(work, out)
    shutil.rmtree(work)

    left = survivors(out)
    print(json.dumps({
        'output': str(out),
        'paragraphs_dropped_by_section': n_sec,
        'paragraphs_or_rows_dropped_by_slot': n_slot,
        'values_supplied': len(values),
        'tokens_surviving': {k: sorted(set(v)) for k, v in left.items()},
    }, indent=2, sort_keys=True))

    if left:
        sys.exit(f'{len(left)} token(s) survived into {out}: '
                 f'{", ".join(sorted(left))} — supply a value or drop the slot')


if __name__ == '__main__':
    main()
