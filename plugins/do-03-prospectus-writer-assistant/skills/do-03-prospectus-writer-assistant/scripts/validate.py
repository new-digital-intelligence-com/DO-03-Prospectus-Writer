#!/usr/bin/env python3
"""Structural validation of a produced OOXML file. Works for .docx, .pptx, .xlsx.

    validate.py OUTPUT [--original TEMPLATE]

QA check 3 of the archetype named this script for weeks before it existed: every
bundle built on produce-from-template shipped a SKILL.md instructing the model to
run `validate.py`, and there was no such file. So the check was skipped, or
improvised, on every run.

What it actually checks — all four are failure modes seen in real builds:

1. **The zip opens and every part is readable.** A repack that wrote a directory
   entry as a file, or truncated on a full disk, fails here.
2. **Every XML part parses.** Editing a DOM and calling toxml() can emit invalid
   XML if a node was detached mid-tree.
3. **Every [Content_Types].xml Override points at a part that exists**, and every
   part that needs an Override has one. This is the check that catches the orphaned
   notesSlide: delete slide3.xml, leave its Override, and PowerPoint offers to
   repair the file.
4. **Every internal relationship Target resolves.** A dangling r:id is how a
   dropped part announces itself to the reader — as a repair prompt, not an error.

With --original it also reports the part inventory difference. Parts missing from
the output are expected when sections or slides were dropped; parts *added* are
not, and are printed as a warning because nothing in the fill step should create a
part.

Exits non-zero when any of the four checks fails. Inventory differences alone never
fail the run — dropping content is the archetype's job.
"""
import argparse, posixpath, sys, zipfile
from collections import defaultdict

from defusedxml import minidom

CT = '[Content_Types].xml'

# Parts that must carry an Override in [Content_Types].xml. A Default by extension
# covers media and rels; these carry a specific content type and Word/PowerPoint
# will not open the file if one is missing.
NEEDS_OVERRIDE = (
    'word/document.xml', 'word/styles.xml',
    'xl/workbook.xml',
    'ppt/presentation.xml',
)


def rels_of(name: str) -> str:
    d, b = posixpath.split(name)
    return posixpath.join(d, '_rels', b + '.rels')


def check(out: str, original: str | None) -> int:
    errors, warnings = [], []

    try:
        z = zipfile.ZipFile(out)
    except Exception as e:
        print(f'FAIL  not a readable zip: {e}')
        return 1

    with z:
        names = set(z.namelist())
        bad = z.testzip()
        if bad:
            errors.append(f'corrupt part: {bad}')

        # 2 — every XML part parses
        doms = {}
        for n in sorted(names):
            if not (n.endswith('.xml') or n.endswith('.rels')):
                continue
            try:
                doms[n] = minidom.parseString(z.read(n).decode('utf-8', 'replace'))
            except Exception as e:
                errors.append(f'{n} is not well-formed XML: {e}')

        # 3 — content types
        if CT not in names:
            errors.append(f'{CT} is missing — the file cannot open')
        elif CT in doms:
            overrides = {o.getAttribute('PartName').lstrip('/')
                         for o in doms[CT].getElementsByTagName('Override')}
            for o in sorted(overrides):
                if o not in names:
                    errors.append(f'{CT} declares an Override for {o}, '
                                  f'which is not in the file (orphaned Override)')
            for need in NEEDS_OVERRIDE:
                if need in names and need not in overrides:
                    errors.append(f'{need} exists but has no Override in {CT}')

        # 4 — relationship targets
        for n, dom in sorted(doms.items()):
            if not n.endswith('.rels'):
                continue
            base = posixpath.dirname(posixpath.dirname(n))
            for rel in dom.getElementsByTagName('Relationship'):
                if rel.getAttribute('TargetMode') == 'External':
                    continue
                tgt = rel.getAttribute('Target')
                if not tgt or tgt.startswith('#'):
                    continue
                resolved = posixpath.normpath(posixpath.join(base, tgt)).lstrip('/')
                if resolved not in names:
                    errors.append(f'{n}: relationship {rel.getAttribute("Id")} '
                                  f'targets {resolved}, which is not in the file')

        # 5 — format-specific structures that are schema-invalid but zip-valid.
        # A w:tbl with no w:tr survives every check above and still makes Word offer
        # to repair the file. Found on the first DO-03 fill, where dropping a section
        # removed all of a table's rows and left the shell.
        if 'word/document.xml' in doms:
            for part in [n for n in sorted(doms) if n.startswith('word/')
                         and n.endswith('.xml')]:
                for tbl in doms[part].getElementsByTagName('w:tbl'):
                    if not tbl.getElementsByTagName('w:tr'):
                        errors.append(f'{part}: a table has no rows — invalid OOXML, '
                                      f'Word will offer to repair the file')
        if 'ppt/presentation.xml' in doms:
            for part in [n for n in sorted(doms) if n.startswith('ppt/slides/slide')]:
                if not doms[part].getElementsByTagName('p:sp') and \
                   not doms[part].getElementsByTagName('p:pic') and \
                   not doms[part].getElementsByTagName('p:graphicFrame'):
                    warnings.append(f'{part} has no shapes — a blank slide is still a '
                                    f'page the reader turns')

    if original:
        try:
            with zipfile.ZipFile(original) as zo:
                onames = set(zo.namelist())
        except Exception as e:
            warnings.append(f'could not read --original: {e}')
        else:
            gone = sorted(onames - names)
            added = sorted(names - onames)
            if gone:
                print(f'INFO  {len(gone)} part(s) removed vs the template '
                      f'(expected when content was dropped):')
                for g in gone:
                    print(f'        - {g}')
            for a in added:
                warnings.append(f'part not present in the template: {a}')

    for w in warnings:
        print(f'WARN  {w}')
    for e in errors:
        print(f'FAIL  {e}')

    if errors:
        print(f'\n{len(errors)} structural error(s) — do not deliver this file.')
        return 1
    print(f'OK    {out}: {len(names)} parts, structure valid'
          + (f', {len(warnings)} warning(s)' if warnings else ''))
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('output')
    ap.add_argument('--original', default=None)
    a = ap.parse_args()
    sys.exit(check(a.output, a.original))


if __name__ == '__main__':
    main()
