#!/usr/bin/env python3
"""Fill a token-based .pptx template, pruning dropped slots and slides.

    fill_template.py TEMPLATE VALUES.json OUTPUT
        [--drop-slots TOKEN,TOKEN] [--drop-slides N,N] [--list-tokens]

Belongs to the produce-from-template archetype. Offering-agnostic: it knows about
tokens, shapes and columns, never about any particular employee.

Pruning rule — why it is geometric and not textual: clearing a dropped slot's text
leaves its container, its rule and its background panel on the page. So the script
finds the column band occupied by the dropped slots' own shapes, then deletes every
shape whose horizontal extent lies at least OVERLAP inside that band. A full-width
title or footnote overlaps only slightly and survives; the card behind the slot does
not.

Exits non-zero if any token survives — that is QA check 1, not a warning.
"""
import argparse, json, re, shutil, subprocess, sys, zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from defusedxml import minidom

TOKEN_RE = re.compile(r'\{\{([A-Z0-9_]+)\}\}')
OVERLAP = 0.80          # fraction of a shape that must sit inside the band to be pruned


def unpack(src: Path, work: Path) -> None:
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    with zipfile.ZipFile(src) as z:
        z.extractall(work)


def slides(work: Path):
    return sorted((work / 'ppt/slides').glob('slide*.xml'),
                  key=lambda p: int(re.search(r'(\d+)', p.name).group(1)))


def list_tokens(work: Path) -> dict:
    found = {}
    for s in slides(work):
        for t in TOKEN_RE.findall(s.read_text(encoding='utf-8')):
            found.setdefault(t, []).append(s.name)
    return found


def extent(sp):
    """(x, x+cx) in EMU for a shape, or None when it has no explicit geometry."""
    off = sp.getElementsByTagName('a:off')
    ext = sp.getElementsByTagName('a:ext')
    if not off or not ext:
        return None
    x = int(off[0].getAttribute('x') or 0)
    cx = int(ext[0].getAttribute('cx') or 0)
    return x, x + cx


def prune_slots(path: Path, tokens: set) -> int:
    doc = minidom.parse(str(path))
    shapes = list(doc.getElementsByTagName('p:sp'))

    carriers = [sp for sp in shapes
                if any('{{%s}}' % t in sp.toxml() for t in tokens)]
    if not carriers:
        return 0

    bands = [e for e in (extent(sp) for sp in carriers) if e]
    if not bands:
        return 0
    lo, hi = min(b[0] for b in bands), max(b[1] for b in bands)

    removed = 0
    for sp in shapes:
        e = extent(sp)
        if not e:
            continue
        width = e[1] - e[0]
        if width <= 0:
            continue
        inside = max(0, min(e[1], hi) - max(e[0], lo))
        if inside / width >= OVERLAP:
            sp.parentNode.removeChild(sp)
            removed += 1
    path.write_text(doc.toxml(), encoding='utf-8')
    return removed


def dependents(work: Path, slide: Path) -> list:
    """Parts a slide owns outright — its notes slide and that notes slide's rels.

    A slide is not a single file. Deleting only slideN.xml leaves notesSlideN.xml
    behind, still pointing at a part that no longer exists: a broken relationship
    and an unreferenced part, which is what makes a deck open as 'repaired'.
    """
    out = []
    r = slide.parent / '_rels' / (slide.name + '.rels')
    if not r.exists():
        return out
    for rel in minidom.parse(str(r)).getElementsByTagName('Relationship'):
        if not rel.getAttribute('Type').endswith('/notesSlide'):
            continue
        n = (slide.parent / rel.getAttribute('Target')).resolve()
        out.append(n)
        nr = n.parent / '_rels' / (n.name + '.rels')
        if nr.exists():
            out.append(nr)
    return out


def strip_content_types(work: Path, deleted: list) -> None:
    """Drop [Content_Types].xml Overrides for parts that no longer exist."""
    ct = work / '[Content_Types].xml'
    names = {'/' + p.relative_to(work).as_posix() for p in deleted}
    doc = minidom.parse(str(ct))
    for node in list(doc.getElementsByTagName('Override')):
        if node.getAttribute('PartName') in names:
            node.parentNode.removeChild(node)
    ct.write_text(doc.toxml(), encoding='utf-8')


def drop_slides(work: Path, numbers: set) -> int:
    """Remove slides from the presentation by ordinal position (1-based)."""
    if not numbers:
        return 0
    pres = work / 'ppt/presentation.xml'
    rels = work / 'ppt/_rels/presentation.xml.rels'
    doc = minidom.parse(str(pres))
    rdoc = minidom.parse(str(rels))

    lst = doc.getElementsByTagName('p:sldIdLst')[0]
    ids = [n for n in lst.childNodes if getattr(n, 'tagName', '') == 'p:sldId']
    rid_by_target = {}
    for rel in rdoc.getElementsByTagName('Relationship'):
        rid_by_target[rel.getAttribute('Id')] = rel.getAttribute('Target')

    removed, deleted = 0, []
    for pos, node in enumerate(ids, start=1):
        if pos not in numbers:
            continue
        rid = node.getAttribute('r:id')
        target = rid_by_target.get(rid, '')
        lst.removeChild(node)
        for rel in list(rdoc.getElementsByTagName('Relationship')):
            if rel.getAttribute('Id') == rid:
                rel.parentNode.removeChild(rel)
        if target:
            f = (work / 'ppt' / target).resolve()
            for p in dependents(work, f) + [f, f.parent / '_rels' / (f.name + '.rels')]:
                if p.exists():
                    p.unlink()
                    deleted.append(p)
        removed += 1

    pres.write_text(doc.toxml(), encoding='utf-8')
    rels.write_text(rdoc.toxml(), encoding='utf-8')
    strip_content_types(work, deleted)
    return removed


def fill(work: Path, values: dict) -> None:
    for s in slides(work):
        t = s.read_text(encoding='utf-8')
        for k, v in values.items():
            t = t.replace('{{%s}}' % k, escape(str(v)))
        s.write_text(t, encoding='utf-8')


def repack(work: Path, out: Path) -> None:
    if out.exists():
        out.unlink()
    subprocess.run(['zip', '-Xrq', str(out.resolve()), '.'], cwd=work, check=True)


def survivors(out: Path):
    left = []
    with zipfile.ZipFile(out) as z:
        for nm in z.namelist():
            if nm.endswith('.xml'):
                for m in TOKEN_RE.findall(z.read(nm).decode('utf-8', 'ignore')):
                    left.append((nm, m))
    return left


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('template'); ap.add_argument('values', nargs='?')
    ap.add_argument('output', nargs='?')
    ap.add_argument('--drop-slots', default='')
    ap.add_argument('--drop-slides', default='')
    ap.add_argument('--list-tokens', action='store_true')
    ap.add_argument('--work', default='_fill_work')
    a = ap.parse_args()

    work = Path(a.work)
    unpack(Path(a.template), work)

    if a.list_tokens:
        for t, where in sorted(list_tokens(work).items()):
            print(f'{t:28s} {",".join(where)}')
        return

    if not a.values or not a.output:
        ap.error('VALUES.json and OUTPUT are required unless --list-tokens')

    values = json.loads(Path(a.values).read_text(encoding='utf-8'))
    dropped_slides = {int(n) for n in a.drop_slides.split(',') if n.strip()}
    dropped_slots = {t.strip() for t in a.drop_slots.split(',') if t.strip()}

    n_sl = drop_slides(work, dropped_slides)
    n_sh = 0
    if dropped_slots:
        for s in slides(work):
            n_sh += prune_slots(s, dropped_slots)

    fill(work, values)
    out = Path(a.output)
    repack(work, out)

    left = survivors(out)
    print(json.dumps({
        'output': str(out),
        'slides_dropped': n_sl,
        'shapes_pruned': n_sh,
        'slots_filled': len(values),
        'surviving_tokens': [f'{n}:{t}' for n, t in left],
    }, indent=2))
    sys.exit(1 if left else 0)


if __name__ == '__main__':
    main()
