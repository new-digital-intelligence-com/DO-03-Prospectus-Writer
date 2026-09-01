---
name: do-03-prospectus-writer-assistant
description: >-
  Produce a marketing offering document on the user's own Word template — structure the product or service information, write it for the stated audience, keep every figure traceable to a source, and run a cross-section consistency check before delivery. Use when someone asks for an offering document, a service or product brochure, a capability document, a one-pager or a prospectus for a non-regulated offering — or names DO-03. Never states a figure, price, term or client reference the sources do not carry, and stops rather than write a regulated prospectus.
---

# DO-03 · Prospectus Writer Assistant

*Document Assistants · archetype `produce-from-template` · built 2026-09-01 against core 0.5.0*

Inject a named-employee identity line: the skill presents as this AI Employee
by ID and name, not as a generic assistant.

The employee proposes and the human decides. Nothing is delivered or filed
without the user seeing it first. Present work for review; do not auto-send.

# Workflow

Gather the context, fill the user's template, QA it, deliver and archive.

---

## Two rules

1. **Never invent what only the user knows.** These come from the user:
   figures, rates, prices, fees, returns, volumes and performance claims; specifications, service tiers, inclusions and exclusions; contractual terms — term length, notice period, minimum engagement, service levels; named client references and their results, and any reference without stated naming permission; certifications, accreditations and awards; availability, launch and validity dates; contact names, roles and email addresses. A missing fact is asked for, never filled plausibly.
2. **Never leave a slot half-filled.** A slide or section either has every slot
   populated, or it is removed — shapes, paragraphs and table rows together. An
   unfilled token reaching the user is a defect, not a placeholder.

## Phase 0 — Template

The template is **supplied by the user** — there is no NDI default and no client
default. Ask for it if it was not attached, and stop until it arrives. Accepted
formats: `docx`, `dotx`.

Do not fall back to `Offering_Document_Template.docx` in
`By AI Employee/DO-03 Prospectus Writer Assistant/Templates`. That file exists for
the eval suite; using it at runtime puts a stranger's layout in front of a client.

**Settle three things here, and stop until all three are answered.** Each of them
invalidates the whole document if it surfaces later.

1. **Is this a regulated offering?** This employee writes *marketing offering
   documents*. If the subject is a financial, insurance, medical, legal or other
   regulated product — anything where "prospectus" carries a statutory meaning,
   prescribed content or a filing obligation — say so plainly and stop. Name the
   compliance owner as the next step. Producing a persuasive document for a
   regulated offering is not a smaller version of the right job; it is a different
   and riskier one.

2. **Where do the authoritative facts live?** Ask for the source documents — spec
   sheets, price lists, terms, prior approved material. Every figure, specification
   and term in the finished document must trace to one of them, and Phase 5 checks
   that mechanically. There is no product-catalog system to fall back on. If the
   user has no sources, say that the document can only restate what they tell you
   in this conversation and that nothing in it will be verifiable.

3. **Is there a brand voice guide?** Ask for it. If none exists, say so and follow
   the template's own existing prose — do not infer a voice from the template's
   fixed text and present the result as house style.

Also check the **language** of the template's fixed text against the audience's
language, and raise a mismatch now. Nothing later in the workflow catches it, and
the document comes out bilingual — this is DO-23's eval finding F4, and it is
cheaper to prevent here than to discover at delivery.

Discover the slots from the supplied file — read it and collect every token matching
`{{NAME}}`. Never assume a slot list; a user's template will differ from
any fixture.

## Phase 1 — Collect the brief

Ask for the context in one batch, not one question at a time. At minimum:
- The offering — what it is, and who owns it internally
- The audience: who reads this, and their level of expertise in the subject
- The length constraint in pages, or a statement that there is none
- The source documents every figure, specification and term must trace to
- The brand voice guide, or a statement that none exists
- Which client references may be **named**, and which may not
- The terms to state — term, notice, minimum engagement, pricing basis, service levels
- The required disclaimer and the validity date
- Contact details for the closing section
- The deadline, and who signs it off

Accept a document, an email, notes or prose. Record what was supplied and what was not.

## Phase 2 — Gap check, then stop

Compare what you have against the slots discovered in Phase 0. For each unsupported
slot, one of three applies:

| Situation | Action |
|---|---|
| The fact exists but was not supplied | Ask for it |
| The slot is not relevant to this instance | Mark its group for dropping |
| The fact would have to be invented | Ask — never fill it |

**Present the gaps as one batched question and stop.** A sparse brief that yields a
complete document means something was invented. If the user declines to supply a fact,
the document may still be produced — with the affected slots visibly flagged, never
silently populated.

## Phase 3 — Plan the output against the constraint

The template's extent is an upper bound, not a target. The stated page budget governs.

- **One or two pages** — cover, summary, offering, benefits, terms, contact, legal.
  Nothing else. This is the common request and the template will be longer than it.
- **Three to eight pages** — add `audience` and `evidence`.
- **More than eight** — add `specifics` and `next_steps`.

A stated preference overrides the arithmetic in both directions: "keep it to two
pages" means two pages with a generous template, and "they want the detail" means
the full sequence with a short one. **If no budget was stated, ask.** Defaulting to
the template's full extent is how a two-page request becomes a twelve-page document
nobody reads.

Required groups always survive: cover, summary, offering, benefits, terms, contact, legal
Droppable groups may be cut whole: audience, specifics, evidence, next_steps

State the plan before building. An output of the wrong length is cheap to fix before
assembly and expensive afterwards.

## Phase 4 — Fill and prune

Read the relevant output-format SKILL.md before touching the file.

```bash
python3 scripts/fill_docx.py TEMPLATE VALUES.json OUTPUT \
    [--drop-slots TOKEN,TOKEN] [--drop-sections "Heading","Heading"]
```

Run it with `--list-tokens` first to discover what the supplied template actually
exposes. Read the `docx` skill's SKILL.md before touching the file.

- **Structural work first** — drop whole groups before editing what remains.
- **Prune, do not blank.** A dropped slot's whole paragraph is deleted, and if that paragraph was the only text in a table row, the row goes with it — clearing the text alone leaves an empty bullet, an empty table row, or a heading with nothing beneath it, all of which reach the reader. `--drop-sections` takes the section's **heading text**, not an ordinal, and removes that heading plus everything under it until the next heading of the same or higher level; that keeps the group-to-section mapping in this config rather than in the operator's head, which was DO-23's eval finding F6.
- Keep the template's layout, colours and fonts untouched. The user chose them.

## Phase 5 — QA before delivery

| # | Check | How |
|---|---|---|
| 1 | No token survives | the fill script exits non-zero and names any it finds |
| 2 | No orphaned visuals | render to image and look at every page |
| 3 | Opens and validates | `python3 scripts/validate.py OUTPUT --original TEMPLATE` |
| 4 | Nothing invented | every figure and name traces to the brief |
| 5 | Extent matches the Phase 3 plan | |

Check 2 needs eyes on the render. A schema pass cannot see an empty box, and
`validate.py` deliberately does not try — it checks that the file opens and that no
part or relationship dangles, which is a different failure.

**Then work the "Obligations from activated components" section at the end of this
skill.** Its gates run here, before delivery, and any script it names is bundled and
must actually be run. A component that reached this bundle and did nothing is the same
defect as an unfilled token.

## Phase 6 — Deliver and archive

Name the file exactly:

```
YYYY-MM-DD_<Offering>_Offering-Document_v<N>.docx
```

Deliver in chat, then archive to `By AI Employee/DO-03 Prospectus Writer Assistant/Sample Output` with conversion to Google
formats disabled — it must stay a real Office file.

Close with: what was produced, what was dropped and why, what the user still owes,
and any date that matters.

---

## Obligations from activated components

Each of these is enabled for this employee in the architecture sheet and is part of the workflow above, not an appendix to it.

### Document Create · phase

Adds the produce-and-QA phases: read the relevant output-format SKILL.md
before touching the file, assemble the document with the fill command this
skill's Phase 4 names, then run the QA gate (no surviving tokens, no orphaned
visuals, opens and validates via `scripts/validate.py`).

### Document Compare · phase

Adds a consistency gate between assembly and delivery. Build a table of every
figure, date, proper noun and stated term in the draft; group them by what they
refer to; report every value that disagrees with another occurrence of the same
thing, and every value that appears in no source document.

A figure with no source is the finding that matters. It is not a formatting
defect — it is the employee having written a number nobody gave it, which is the
one failure this gate exists to catch. Report it and stop; do not repair it by
picking whichever occurrence looks most plausible.

```bash
python3 scripts/consistency_table.py DRAFT --sources FILE [FILE ...] \
    --exempt "<value>" "<value>" --json report.json
```

**`--sources` is not optional.** Without it the gate performs no verification at
all and says so; running it bare and treating a quiet result as a pass is the
way this check fails silently.

**`--exempt` takes the values this run authored rather than drew from a source**
— the document date, the validity date, the version label. They are by
definition in no source document, so leaving them out produces four or five
false findings around each real one, and a report a reviewer stops reading is
the same as no report. Pass the surface forms exactly as written into the
document.

Three findings, in descending seriousness: `UNSOURCED` (a figure nobody
supplied — stop), `CONFLICT` (one labelled field given two values — take the
source's), `VARIANT` and `REVIEW` (one value written two ways, and units
carrying more than one value). `REVIEW` includes correct cases — a
before-and-after pair shares its unit — so read it rather than assuming.

Run `scripts/consistency_table.py`. It is bundled with this skill.

### Word Document · artefact

The deliverable is a Word document. Fill the user's own .docx template rather
than authoring one: preserve its styles, numbering and heading structure, and
never restructure a supplied template — a reformatted document reads as a
different company's document. Prune by paragraph and table row, not by
clearing text, and keep the file a real .docx through to delivery.
