# DO-03 · What survives a reviewer, and what does not

Read this before drafting prose, and again before running the consistency gate. It is
a **reject list**, not a writing style: each item is a thing to catch and remove, not a
formula to apply. If the list forces more than five changes in one section, the section
is built on facts you do not have — go back to Phase 2 and ask, rather than rewriting
around the gap.

---

## The carve-out, first

**A stated caveat, a declared assumption, a validity date or an admission that a figure
is unavailable is never padding to cut.** Removing them makes the document more
confident than its sources support, which is the one failure this employee exists to
prevent. "Pricing valid to 31 March 2027" and "indicative, subject to site survey" stay
in. What follows is about unearned confidence, not about hedging.

---

## Nine rejects

**1 · The unattributed superlative.** "Market-leading", "best-in-class",
"industry-standard", "world-class", "cutting-edge". Every one of these is a claim about
a comparison nobody made. Either name the comparison and its source, or state the
capability plainly. *Reject:* "our market-leading response times". *Keep:* "a
four-business-hour on-site response, committed contractually".

**2 · The benefit with no mechanism.** A benefit the reader cannot trace to something in
the offering is decoration. *Reject:* "dramatically improves efficiency". *Keep:*
"removes the second approval step, which is where the current process waits longest" —
if, and only if, a source says so.

**3 · The number with no unit or basis.** "Up to 40% faster" — faster than what,
measured how, over what period? A figure without its basis cannot be checked, so it
will not be believed by the reader who matters. Every figure carries its basis or comes
out.

**4 · The invented round number.** Watch yourself for 30%, 50%, 3x, "hundreds of". A
tidy figure that appeared during drafting rather than from a source is the single most
common way an offering document becomes untrue. This is what the consistency gate's
unsourced check is for; do not let it be the first place the problem is noticed.

**5 · The reference used without permission.** A named client is a legal and commercial
matter, not a persuasion tactic. If naming permission was not explicitly stated in the
brief, the reference is anonymised — "a European logistics operator with 4,000
endpoints" — or dropped. Never assume permission from the fact that the logo is on a
website.

**6 · The specification that drifted.** The tier that is "up to 500 users" in the
offering section and "up to 750" in the tiers table. Reviewers catch these, and each one
costs their attention on the parts that need judgement. The consistency gate finds them
mechanically; that is not a reason to write them.

**7 · The term stated as a benefit.** Notice periods, minimums and liability caps are
commitments, and dressing them as advantages reads as evasive to anyone who reads
contracts for a living. State them flatly in the terms section.

**8 · The three-adjective sentence.** "A flexible, scalable and robust platform." Three
adjectives in a row means none of them was chosen. Pick the one that is true and
evidenced, cut the others.

**9 · The closing paragraph that asks for nothing.** "We look forward to hearing from
you." A document that names no next step, no owner and no date leaves the reader with
nothing to do. One concrete step, from the brief.

---

## Before delivery

- Every figure, date and named entity appears in a source document. The gate checks
  this; run it with `--sources` or the check does nothing.
- Every reference is either named with stated permission, or anonymised.
- The disclaimer and validity date are present and correct.
- The draft is watermarked until someone has signed it off. A clean-looking document
  circulates, and a circulated draft becomes a commitment.
