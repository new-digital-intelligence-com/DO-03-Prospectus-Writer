# DO-03 — Prospectus Writer Assistant

NDI's DO-03 is a Claude plugin that produces a **marketing offering document on the
presenter's own Word template**. It discovers the template's slots, sizes the document to
the page budget you actually have, fills it, and then checks every figure in the draft
against the source documents you supplied.

> **Scope, decided deliberately.** This employee writes *marketing offering documents*. If
> the subject is a financial, insurance, medical or legal product — anywhere "prospectus"
> carries a statutory meaning — it stops in Phase 0 and names the compliance owner.
> Producing a persuasive document for a regulated offering is not a smaller version of the
> right job; it is a different and riskier one.

## Installation

This repository contains the **plugin only**. The marketplace that lists it lives in
[NDI-AI-Employees](https://github.com/new-digital-intelligence-com/NDI-AI-Employees), so
one `marketplace add` gets you every NDI AI Employee:

```
/plugin marketplace add new-digital-intelligence-com/NDI-AI-Employees
/plugin install do-03-prospectus-writer-assistant@ndi-ai-employees
```

**Auto-update is off by default** for a third-party marketplace — it defaults on only for
Anthropic's own. Enable it in Customize → Plugins, or pull manually:

```
/plugin marketplace update ndi-ai-employees
```

## Command syntax

```
/do-03-prospectus-writer-assistant
```

Then attach the template and the documents your facts live in. Or simply:

```
Build an offering document from this template. Audience is prospective clients.
Sources attached.
```

**Leave the page budget out of the first message.** Withholding it is what makes the
employee stop and ask, which is the behaviour worth seeing: say *two pages* and it drops
four whole sections; say nothing and it asks rather than defaulting to the template's full
extent.

## Repository structure

```
.
├── plugins/
│   └── do-03-prospectus-writer-assistant/
│       ├── .claude-plugin/
│       │   └── plugin.json
│       └── skills/
│           └── do-03-prospectus-writer-assistant/
│               ├── SKILL.md
│               ├── document-config.yaml      [the pack's configuration, as built]
│               ├── references/
│               │   └── voice-and-evidence.md [nine rejects, and the carve-out]
│               └── scripts/
│                   ├── fill_docx.py          [fill and prune a .docx template]
│                   ├── fill_template.py      [the .pptx sibling, unused here]
│                   ├── validate.py           [structural OOXML check]
│                   ├── consistency_table.py  [the figure-vs-source gate]
│                   └── verify_answers.py     [archetype tooling, unused here]
├── Sample Input/       [two source documents and the values file]
├── Sample Output/      [the generated document, and the gate's report on it]
├── Templates/          [the fixture template — 8 sections, 54 slots]
└── README.md
```

The skill lives inside the plugin because Claude's loader blocks path traversal outside the
plugin root. Two of the five scripts belong to the `produce-from-template` archetype rather
than to DO-03 and are unused by this employee — the archetype ships its whole toolkit, and
the pack names which parts the workflow invokes.

## Testing it

Attach `Templates/Offering_Document_Template.docx` plus both files from `Sample Input/`,
and say **two pages**. Three runs worth doing:

| Run | What to check |
|---|---|
| Two pages | Drops `audience`, `specifics`, `evidence` and `next_steps` **whole**, and names them as dropped. Producing all eight sections is the failure |
| Withhold the minimum engagement | Stops and asks. Filling it plausibly is the failure |
| Run the consistency gate | See below — the fixture has a planted defect |

**`Sample Input/values.json` contains a deliberate defect.** It states a 300-endpoint
minimum where `source_spec.md` says 250. `Sample Output/consistency-report.txt` is the
gate's verbatim output on the delivered document:

```
UNSOURCED — 1 figure(s)/date(s) in the draft appear in no supplied source:
  [figure] 300  as written: 300
      in: Minimum Engagement: 300 endpoints
```

The gate exits non-zero and **does not fix it**. Choosing the number that reads better is
how a wrong figure becomes a commitment; both values are quoted with their locations and
the decision goes to whoever owns the offering.

## Known limits in v0.1

- **No product-catalog source of truth.** The role spec assumes a `custom-mcp` over a
  product catalog API, and hangs its central guardrail on it — *never state a figure the
  catalog does not carry*. No such system exists in the tenant, so the sources are the
  documents you attach, and the skill says so rather than implying the check is broader
  than it is.
- **No approval-workflow routing.** The role spec routes drafts into an approval system and
  notifies reviewers in Slack. Neither is wired, so it delivers a watermarked draft and
  names who must sign it off.
- **Every rate and figure in this repository is synthetic.** Meridian Endpoint Care is not
  a product. No client name, price or term here belongs to anyone.

## Demo

A 2:31 narrated walkthrough is on NDI's YouTube channel. The video is not committed here —
the terminal output it shows comes from the scripts in this repository, and the fixture it
runs on is the one in `Sample Input/`.

## Where this comes from

This bundle is a **build output**, not a hand-authored skill. It is generated by the NDI
factory from three inputs — the `produce-from-template` archetype, the `do-03` pack, and
the component column for DO-03 in the architecture sheet — via the `build-ai-employee`
skill.

**So edit the pack, not the files here.** A change made directly to `SKILL.md` or
`document-config.yaml` in this repository is discarded by the next rebuild. The factory
currently lives on Google Drive under `00 Factory`; moving it into version control is the
open task that makes this repository reproducible rather than merely archived.

Two component overrides were needed at build time and are recorded in the build log:
`MS Excel` and `Google Docs` are both set to yes for DO-03 in the architecture sheet, and
both inject *"the deliverable is a &lt;format&gt;"* — false for an employee whose deliverable is
a Word document, and directly contradicting `Word Document` in the same bundle.

`plugin.json` carries no `version` field, so the plugin is versioned by commit SHA — every
push updates installations that have auto-update enabled. Add a `version` field if you want
releases to be deliberate rather than continuous.
