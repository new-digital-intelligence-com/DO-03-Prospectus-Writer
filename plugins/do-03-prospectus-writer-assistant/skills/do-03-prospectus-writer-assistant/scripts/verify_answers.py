#!/usr/bin/env python3
"""Verify that every answer marked "confirmed" actually quotes the transcript.

    verify_answers.py --questionnaire Q.yaml --answers A.json --transcript T.txt
                      [--json OUT.json]
    verify_answers.py --print-answers-schema

The guardrail this exists for, in one sentence: **an inference must never reach a
scoping document dressed as something the customer said.**

Everything else in a discovery workflow degrades gracefully. This does not. A
requirement recorded as "the customer confirmed the ERP is the source of truth" when
nobody said so gets built, priced and delivered against, and the transcript it claims
to come from is 90 minutes long so nobody checks.

So: an answer whose `status` is `confirmed` must carry at least one evidence quote, and
every quote must appear in the transcript. The check is verbatim after whitespace and
case normalisation — a quote that has been tidied, joined across speakers, or had its
"um" removed is reported as EDITED, not passed. Tidying a quote is exactly how a
paraphrase becomes a citation.

Four other things it will not let past:

  - **a figure in the answer that appears in none of its evidence.** "Approximately 400
    invoices per month", cited to a quote saying "quite a lot, a few hundred maybe",
    passes every other check here: the quote is real, verbatim, and correctly attributed.
    And 400 is in the pricing model by Thursday. This is the check that closes the gap
    the verbatim test leaves open.
  - an answer for a question that is not in the questionnaire (invented question)
  - a required question missing from the answers file entirely (silently skipped)
  - `confirmed` with no evidence at all

Coverage is reported against **required** questions, and counts only answers that
survived verification. Counting a failed confirmed answer towards coverage inflates the
headline number using precisely the answers that are wrong.

What it does NOT check, and cannot: whether an answer is a fair reading of the quote it
cites. A quote that exists, is verbatim, contains the right numbers and still does not
support the conclusion drawn from it will pass. That judgement is the consultant's.
"""
import argparse, json, re, sys, unicodedata, zipfile
from pathlib import Path

import yaml

SCHEMA = {
    "_comment": "One entry per questionnaire question id. Every question in the "
                "questionnaire must appear, including the ones with no answer — "
                "omitting a question and answering it 'open' are different claims.",
    "Q03": {
        "status": "confirmed | inferred | open",
        "answer": "The ERP is the source of truth for customer status; the portal "
                  "syncs nightly.",
        "evidence": [
            {"quote": "the ERP is authoritative and the portal syncs overnight",
             "speaker": "Customer — Ines Roth",
             "timestamp": "00:41:32"}
        ],
        "note": "confirmed requires >=1 evidence quote that appears in the transcript. "
                "inferred may cite context but is never presented as a customer "
                "statement. open means not covered — say what would settle it.",
    },
}

_WT = re.compile(r'<w:t(?:\s[^>]*)?>(.*?)</w:t>', re.S)
_TAG = re.compile(r'<[^>]+>')


def read_text(path: Path) -> str:
    if path.suffix.lower() in ('.docx', '.dotx'):
        with zipfile.ZipFile(path) as z:
            xml = z.read('word/document.xml').decode('utf-8', 'replace')
        t = _TAG.sub(' ', ''.join(_WT.findall(xml)))
        return (t.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                 .replace('&quot;', '"').replace('&apos;', "'"))
    return path.read_text(encoding='utf-8', errors='replace')


def norm(s: str) -> str:
    """Whitespace and case only. Deliberately does NOT strip punctuation or filler:
    a quote that needed those removed to match was edited, and the point of the check
    is to notice that."""
    s = unicodedata.normalize('NFKC', s)
    s = s.replace('’', "'").replace('‘', "'")
    s = s.replace('“', '"').replace('”', '"')
    s = s.replace('–', '-').replace('—', '-')
    return re.sub(r'\s+', ' ', s).strip().casefold()


def word_seq(s: str) -> list:
    return re.findall(r"[a-z0-9']+", norm(s))


def is_subsequence(needle: list, hay: list) -> bool:
    """Every word of the quote, in order, somewhere in the transcript — the signature
    of a quote with words removed."""
    if not needle:
        return False
    i = 0
    for w in hay:
        if w == needle[i]:
            i += 1
            if i == len(needle):
                return True
    return False


def locate(quote: str, transcript: str, t_words: list) -> str:
    """'exact' | 'edited' | 'absent'."""
    q = norm(quote)
    if not q:
        return 'absent'
    if q in norm(transcript):
        return 'exact'
    if is_subsequence(word_seq(quote), t_words):
        return 'edited'
    return 'absent'


FIGURE = re.compile(r'(?<![\w.])(\d[\d.,]*)\s*(%|k|m|bn?)?(?![\w])', re.I)

# Words that carry a number without writing one. An answer saying "ten years" on a quote
# saying "ten years" must not be flagged; an answer saying "400" on a quote saying "a few
# hundred" must be.
WORD_NUM = {'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
            'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
            'eleven': '11', 'twelve': '12', 'twenty': '20', 'thirty': '30',
            'forty': '40', 'fifty': '50', 'hundred': '100', 'thousand': '1000',
            'million': '1000000'}


def figures_in(text: str) -> set:
    """Numbers in a string, as canonical strings. Spelled-out numbers included."""
    if not text:
        return set()
    out = set()
    for m in FIGURE.finditer(text):
        raw = m.group(1).rstrip('.,').replace(',', '').replace(' ', '')
        try:
            v = float(raw)
        except ValueError:
            continue
        out.add(f'{v:g}')
    for w, d in WORD_NUM.items():
        if re.search(rf'\b{w}\b', text, re.I):
            out.add(f'{float(d):g}')
    return out


def unsupported_figures(answer: str, quotes: list) -> set:
    """Figures asserted in the answer that appear in none of its evidence.

    This is the gap the verbatim check alone leaves open, and it is the dangerous one.
    An answer of "approximately 400 invoices per month" cited to a quote saying "quite a
    lot, a few hundred maybe" passes every other check in this file: the quote is real,
    the quote is verbatim, the status is confirmed. And 400 is in the pricing model by
    Thursday.

    Dates and timestamps are excluded — they come from the transcript's own metadata
    rather than from what anyone said.
    """
    a = figures_in(re.sub(r'\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}:\d{2}(:\d{2})?\b', ' ',
                          answer or ''))
    ev = set()
    for q in quotes:
        ev |= figures_in(q)
    return a - ev


def verify(questions: list, answers: dict, transcript: str) -> dict:
    t_words = word_seq(transcript)
    by_id = {str(q['id']): q for q in questions if q.get('id') is not None}
    failures, warnings, rows = [], [], []
    invalid = set()          # ids whose confirmed status did not survive verification

    for qid in answers:
        if qid not in by_id:
            failures.append({
                'kind': 'UNKNOWN_QUESTION', 'id': qid,
                'detail': 'answered a question that is not in the questionnaire — a '
                          'question nobody asked cannot have an answer nobody can '
                          'trace',
            })

    for qid, q in by_id.items():
        required = bool(q.get('required'))
        a = answers.get(qid)
        if a is None:
            (failures if required else warnings).append({
                'kind': 'MISSING' if required else 'MISSING_OPTIONAL', 'id': qid,
                'detail': f'{"required " if required else ""}question absent from the '
                          f'answers file. Omitting a question and recording it "open" '
                          f'are different claims',
                'question': q.get('question'),
            })
            rows.append({'id': qid, 'required': required, 'status': 'ABSENT',
                         'evidence': 0, 'section': q.get('section')})
            continue

        status = str(a.get('status', '')).strip().lower()
        ev = a.get('evidence') or []
        if status not in ('confirmed', 'inferred', 'open'):
            failures.append({
                'kind': 'BAD_STATUS', 'id': qid,
                'detail': f'status "{a.get("status")}" is not one of confirmed, '
                          f'inferred, open',
            })

        checked = []
        for e in ev:
            quote = (e or {}).get('quote', '')
            where = locate(quote, transcript, t_words)
            checked.append({'quote': quote[:160], 'speaker': (e or {}).get('speaker'),
                            'timestamp': (e or {}).get('timestamp'), 'match': where})
            if where == 'absent':
                invalid.add(qid)
                failures.append({
                    'kind': 'QUOTE_NOT_IN_TRANSCRIPT', 'id': qid,
                    'detail': f'evidence quote does not appear in the transcript: '
                              f'"{quote[:120]}"',
                })
            elif where == 'edited':
                warnings.append({
                    'kind': 'QUOTE_EDITED', 'id': qid,
                    'detail': f'the quote\'s words appear in order but not contiguously '
                              f'— it has been tidied or joined, so it is not verbatim: '
                              f'"{quote[:120]}"',
                })

        if status == 'confirmed':
            if not ev:
                invalid.add(qid)
                failures.append({
                    'kind': 'CONFIRMED_WITHOUT_EVIDENCE', 'id': qid,
                    'detail': 'marked confirmed with no evidence quote. Confirmed means '
                              'the customer said it — so quote them, or mark it inferred',
                })
            elif not any(c['match'] == 'exact' for c in checked):
                invalid.add(qid)
                failures.append({
                    'kind': 'CONFIRMED_WITHOUT_VERBATIM_EVIDENCE', 'id': qid,
                    'detail': 'marked confirmed but no quote matches the transcript '
                              'verbatim. Either quote exactly or downgrade to inferred',
                })
            bad = unsupported_figures(a.get('answer') or '',
                                      [(e or {}).get('quote', '') for e in ev])
            if bad:
                invalid.add(qid)
                failures.append({
                    'kind': 'FIGURE_NOT_IN_EVIDENCE', 'id': qid,
                    'detail': f'the answer states {", ".join(sorted(bad))} but no '
                              f'evidence quote contains that figure. A number nobody '
                              f'said is the one thing that reaches the price model '
                              f'unchallenged — quote the number, or mark this inferred '
                              f'and say what it was derived from',
                })
        if status == 'open' and a.get('answer'):
            warnings.append({
                'kind': 'OPEN_WITH_ANSWER', 'id': qid,
                'detail': 'marked open but carries an answer. If there is an answer it '
                          'is confirmed or inferred; if there is not, remove it',
            })

        rows.append({'id': qid, 'required': required, 'status': status.upper(),
                     'evidence': len(ev),
                     'verbatim': sum(1 for c in checked if c['match'] == 'exact'),
                     'section': q.get('section'), 'checks': checked})

    req = [r for r in rows if r['required']]
    # Coverage counts only answers that SURVIVED verification. Counting a failed
    # confirmed answer towards coverage inflates the headline number using precisely
    # the answers that are wrong — and the headline number is what gets quoted.
    req_confirmed = [r for r in req
                     if r['status'] == 'CONFIRMED' and r['id'] not in invalid]
    return {
        'questions': len(by_id),
        'required': len(req),
        'required_confirmed': len(req_confirmed),
        'invalid_confirmed': sorted(invalid),
        'coverage_pct': round(100 * len(req_confirmed) / len(req)) if req else None,
        'by_status': {s: sum(1 for r in rows if r['status'] == s)
                      for s in ('CONFIRMED', 'INFERRED', 'OPEN', 'ABSENT')},
        'failures': failures, 'warnings': warnings, 'rows': rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--questionnaire')
    ap.add_argument('--answers')
    ap.add_argument('--transcript')
    ap.add_argument('--json', default=None)
    ap.add_argument('--print-answers-schema', action='store_true')
    a = ap.parse_args()

    if a.print_answers_schema:
        print(json.dumps(SCHEMA, indent=2))
        return
    if not (a.questionnaire and a.answers and a.transcript):
        sys.exit('--questionnaire, --answers and --transcript are all required')

    qdoc = yaml.safe_load(Path(a.questionnaire).read_text(encoding='utf-8')) or {}
    questions = qdoc.get('questions') or []
    if not questions:
        print('FAIL  the questionnaire declares no questions. Verifying answers '
              'against an empty questionnaire passes everything, which is the most '
              'misleading output available here.')
        sys.exit(2)

    answers = json.loads(Path(a.answers).read_text(encoding='utf-8'))
    if isinstance(answers, dict) and 'answers' in answers:
        answers = answers['answers']
    transcript = read_text(Path(a.transcript))

    res = verify(questions, answers, transcript)
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=2, sort_keys=True),
                                encoding='utf-8')

    bs = res['by_status']
    print(f'{res["questions"]} questions · {res["required"]} required · '
          f'coverage {res["coverage_pct"]}% of required confirmed AND VERIFIED')
    if res['invalid_confirmed']:
        print(f'  ({len(res["invalid_confirmed"])} answer(s) marked confirmed did not '
              f'survive verification and are excluded from coverage: '
              f'{", ".join(res["invalid_confirmed"])})')
    print(f'  confirmed {bs["CONFIRMED"]} · inferred {bs["INFERRED"]} · '
          f'open {bs["OPEN"]} · absent {bs["ABSENT"]}')
    print()

    if res['failures']:
        print(f'FAIL — {len(res["failures"])} problem(s) that must be fixed before this '
              f'goes in a scoping document:')
        for f in res['failures']:
            print(f'  [{f["kind"]}] {f["id"]}')
            print(f'      {f["detail"]}')
        print()

    if res['warnings']:
        print(f'WARN — {len(res["warnings"])}:')
        for w in res['warnings']:
            print(f'  [{w["kind"]}] {w["id"]}')
            print(f'      {w["detail"]}')
        print()

    still_open = [r for r in res['rows']
                  if r['required'] and r['status'] in ('OPEN', 'ABSENT', 'INFERRED')]
    if still_open:
        print(f'REQUIRED AND NOT CONFIRMED — {len(still_open)}. These are the questions '
              f'to raise before the call ends:')
        for r in sorted(still_open, key=lambda x: (x['section'] or '', x['id'])):
            print(f'  {r["id"]}  [{r["status"]}]  {r["section"] or ""}')
        print()

    if res['failures']:
        sys.exit(1)
    print('Every confirmed answer quotes the transcript verbatim.')


if __name__ == '__main__':
    main()
