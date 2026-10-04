# Verification protocol

The user's rule: **a wrong answer hurts more than no answer.** Nothing factual reaches the page unless it was read in an official source, then confirmed again in a separate, later tool call. When in doubt, cut it and record the cut.

## Contents
1. What counts as a claim
2. Source tiers
3. The ledger (`ledger.json`)
4. Pass 1: research
5. Pass 2: fresh re-check
6. Cross-verification and conflicts
7. Current vs legacy conventions
8. Code
9. Strict mode (independent reviewer)
10. Refreshing an existing page

---

## 1. What counts as a claim

A claim is any statement a reader could act on that could be false:
- what a spec or standard requires, recommends or forbids
- names: parameters, headers, fields, flags, functions, error codes
- defaults, limits, sizes, timeouts, counts, percentages
- versions, release or publication dates, "deprecated", "removed", "replaced by"
- what a named product, cloud service or company does or did (including "In the wild" cases)
- performance or security properties ("X prevents Y")

Not claims: analogies, plain framing ("imagine a hotel key card"), and conclusions that follow from claims already on the page. Every quiz answer, predict reveal and comparison-table cell that rests on facts must point at claims via `data-claims`.

## 2. Source tiers

| Tier | `kind` | Examples | Can support a claim alone? |
|---|---|---|---|
| Normative | primary | RFCs and IETF drafts (rfc-editor.org, datatracker.ietf.org), W3C/WHATWG specs, OpenID Foundation specs, language specs, NIST, OWASP cheat sheets | Yes |
| Official vendor/project docs | primary | docs of the product the claim is about (postgresql.org, docs.python.org, learn.microsoft.com, cloud.google.com, kafka.apache.org, the project's own repo docs) | Yes, for claims about that product |
| Maintainer / engineering blogs, conference talks, postmortems | secondary | company engineering blogs, talks by maintainers | Only for "In the wild" cases, with the company's own page as the source |
| Everything else | not allowed | tutorials, Medium, Stack Overflow, AI summaries, aggregator sites | Never. Use them to find the primary source, then cite that. |

Every claim needs at least one primary source. If only secondary sources exist, the claim is cut.

## 3. The ledger (`ledger.json`)

Keep it in the work directory from the first search onward; update it as you go, never reconstruct it at the end.

```json
{
  "verified": "2026-09-27",
  "volatility": "evolving",
  "strict": true,
  "sources": [
    {"id": "s1", "title": "RFC 9700: Best Current Practice for OAuth 2.0 Security", "url": "https://www.rfc-editor.org/rfc/rfc9700",
     "kind": "primary", "publisher": "IETF", "accessed": "2026-09-27", "locator": "Section 2.1.2"}
  ],
  "claims": [
    {"id": "c1", "text": "Exact sentence as it appears on the page.", "sources": ["s1"], "status": "verified",
     "checks": [
       {"pass": 1, "source": "s1", "locator": "Section 2.1.2", "result": "supported", "at": "2026-09-27T10:12"},
       {"pass": 2, "source": "s1", "locator": "Section 2.1.2", "result": "supported", "at": "2026-09-27T11:40"}
     ]}
  ],
  "cut": [
    {"text": "Claim we wanted but could not confirm", "reason": "only found in a blog post"}
  ]
}
```
- `claims[].text` must match what the page says. If you reword the page sentence, the claim must be re-checked (pass 2) against the new wording.
- `status` is only ever `verified`. Anything unconfirmed moves to `cut` with a reason. The page shows the cut list in its "How this page was checked" panel, so the reader knows what was deliberately left out.
- `result` values: `supported`, `contradicted`, `not_found`. One `contradicted` or `not_found` blocks the claim until fixed.

## 4. Pass 1: research

1. Start from the normative source (search `site:rfc-editor.org <topic>`, `site:datatracker.ietf.org`, the vendor docs domain). Open it with WebFetch; don't rely on the search snippet.
2. For each fact you intend to teach, record the claim, the source and the locator (section number, heading, or anchor) in the ledger immediately.
3. Check status of the document itself: is the RFC obsoleted or updated by a newer one? Is the draft still active or expired? Is the doc page for the current version of the product? Record the answer as its own claim if the page mentions it.
4. Find what changed recently: search the topic with the current year and "deprecated", "best current practice", "security", "migration". Anything newer supersedes older guidance (see 7).

WebFetch prompt pattern for pass 1 (ask for locators, not summaries):
```
List the specific requirements this document states about <sub-topic>. For each, give the section number or heading, and a paraphrase under 20 words. Mark MUST / SHOULD / MAY where used. If the document says it is obsoleted, updated or superseded, say by what. Also report the last section number present in the content you received; for anything after it, answer NOT IN CONTENT instead of guessing.
```

## 5. Pass 2: fresh re-check

**Known trap: WebFetch truncates long documents.** RFC 6749, RFC 9700, OpenID Connect Core and similar long specs are cut off after the first sections. When asked about a later section, WebFetch's summarising model may answer from its own memory instead of the page. Treat any WebFetch answer about a long document as unverified unless the prompt included "If it is not in the content you received, answer NOT IN CONTENT" and it didn't say that.

**Preferred method for long or normative documents: read the exact text in the browser.** Open the document in the built-in browser (or Claude in Chrome) and pull the section text with the JavaScript tool, then judge the claim against that verbatim text yourself:
```js
// rfc-editor.org HTML: sections have ids like "section-4.1.2"
const g=id=>{const s=document.getElementById('section-'+id); if(!s) return id+': MISSING';
  const c=s.cloneNode(true); c.querySelectorAll('section').forEach(x=>x.remove());
  return id+': '+c.innerText.replace(/\s+/g,' ').trim();};
['2.1','2.1.1'].map(g).join('\n\n')
```
```js
// any page: confirm an exact phrase exists (use for pass 2 of a reworded claim)
const t=document.body.innerText.replace(/\s+/g,' ');
const q=s=>{const i=t.indexOf(s); return i<0?'NOT FOUND: '+s:'FOUND: '+t.slice(i,i+s.length+80)};
[q('MUST NOT be used')].join('\n')
```
Older plain-text RFCs (e.g. RFC 6749) have no section ids in the HTML; search the page text for the section heading instead, skipping the table-of-contents hit. Batch several sections of one document into one call. Ask for site access once per domain with scope "site" (rfc-editor.org, datatracker.ietf.org, openid.net cover most specs). Record `"method": "browser: verbatim section text"` in the check. Pass 1 and pass 2 must be separate reads.

WebFetch is fine for short pages (a blog post, a product doc page, a datatracker status page), always with the NOT IN CONTENT guard.

### Pass 2 procedure

After the page text is drafted, and before building, re-open each source in a **new WebFetch call** and test the claims as written on the page. Group up to 8 claims per source per call.

```
For each numbered statement, answer SUPPORTED, CONTRADICTED or NOT FOUND based only on this page, and give the section or heading where it is supported or contradicted. Do not use outside knowledge. If the needed part is not in the content you received, answer NOT IN CONTENT.
1. <claim text exactly as on the page>
2. ...
```
- SUPPORTED with a locator → add the pass 2 check.
- CONTRADICTED → fix the sentence to match the source, then re-run pass 2 for it.
- NOT FOUND or NOT IN CONTENT → read the section verbatim in the browser (above). Still not found → cut it.
- A WebFetch failure (site blocked, timeout) is not a pass. Try the same document from another official mirror (e.g. rfc-editor.org vs datatracker.ietf.org html). No mirror → cut.
- Neutral prompts only: never ask "confirm that X", which invites agreement.

## 6. Cross-verification and conflicts

- When a second primary source covers the same fact (the spec and a major provider's docs, two related RFCs), check it too and list both in `sources`.
- If primary sources disagree (e.g. the spec says SHOULD, a provider enforces MUST): do not pick one silently. Either teach both, attributed ("The spec recommends X; Google requires it"), each as its own claim, or cut. This is also the trigger for strict mode.
- Spec vs practice gaps are good rung-4 material, as long as both sides are claims.

## 7. Current vs legacy conventions

- Teach the current convention as the default everywhere: in diagrams, code and checks.
- Anything deprecated, superseded, or discouraged by a newer best-practice document goes in a `ts-legacy` box: what it was, what replaced it, why (all claims). Never in the main flow, never as a quiz's correct answer except for "why is this discouraged?" questions.
- Record the document that establishes "current" (e.g. a BCP RFC or the product's current docs) and state on the page which document the page follows, as a claim.
- A draft that is not yet a standard is labelled as a draft on the page. Don't present draft-only features as the standard.

## 8. Code

- Runnable code lives in `examples/<slug>/` with pytest tests (`test_*.py`) that assert every behaviour the page claims ("the replayed code is rejected with invalid_grant"). For network calls, test against a local stub (a tiny `http.server` on port 0) that mirrors the documented request/response shapes. The page embeds the file with `data-file` and gets `data-verified="ran"` only when `make test` passes. Dependencies go in `pyproject.toml`'s `examples` group via `uv add --group examples <pkg>`, never a global install.
- Non-runnable (raw HTTP exchanges, config for a hosted service): every parameter, header, field and value must be covered by verified claims; mark `data-verified="spec" data-claims="..."`.
- Use the libraries the official docs currently recommend; check their current API in the library's docs (a claim), not from memory. `uv.lock` pins the version the tests ran with.

## 9. Strict mode (independent reviewer)

Turn strict mode on (and set `"strict": true` in the ledger) when any of these hold:
- the topic is security-sensitive (auth, crypto, secrets, access control, payments)
- the topic is fast-moving (a product, cloud service or library that has had notable changes in the last two years)
- primary sources disagree, or the topic includes drafts
- a pass 2 check failed for more than 10% of claims

In strict mode, after pass 2 and before building, spawn one reviewer with the Agent tool (general-purpose). It must not see your drafting reasoning. Give it only the ledger (claims and sources) and the list of quiz answer keys, with this brief:

```
You are auditing a technical lesson for factual errors. Wrong facts are worse than missing ones.
For every claim below, open its sources with WebFetch and answer SUPPORTED / CONTRADICTED / NOT FOUND with a section locator.
Also flag any claim that is outdated (a newer RFC, BCP, or current product doc says otherwise) even if the cited source supports it.
Then check each quiz: does the marked correct answer follow from the claims it cites, and is any wrong option actually defensible?
Return a table: id | verdict | locator | note. Do not rewrite the lesson.
<ledger JSON>
<quiz list: question, options, marked answer, cited claims>
```
Tell the reviewer about the truncation trap (it must answer NOT IN CONTENT rather than guess). Its NOT IN CONTENT verdicts are yours to resolve with verbatim browser reads. Also expect it to catch wording problems pass 2 misses: a SHOULD stated as MUST, a missing condition ("only if the first request had one"), a quiz distractor that is actually defensible. Fix or cut everything it flags, then re-run pass 2 on any changed sentence. Record the reviewer's verdicts as `"pass": 3` checks.

## 10. Refreshing an existing page

"Refresh <topic>" or a stale badge (checked more than 180 days ago):
1. Mirror the project (SKILL.md Step 2); the lesson source is `content/<slug>/` and its code is `examples/<slug>/`.
2. Search for changes since the ledger's `verified` date (new RFCs, BCPs, deprecations, new major versions).
3. Re-run pass 2 on every claim. Update or cut; add new parts only if the topic changed.
4. Keep part `id`s stable so the reader's progress survives. Set `verified` to today. Rebuild and re-run all checks.
