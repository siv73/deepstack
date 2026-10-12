# Pedagogy: how a page teaches

Reader: a busy engineer, strong in backend work, who may know nothing about this topic and learns best with one idea at a time. Goal: take them from zero to the level in `depth-target.md`. Explanations are complete: no skipped reasoning steps, no assumed background. There is no length limit on prose or on the number of parts; a part is as long as its one idea needs to be fully understood.

## Why these rules (use this to handle cases the rules don't cover)
- **Small working memory.** Too many new things at once and nothing sticks. → One idea per part. Introduce new terms one at a time, each defined where it first appears, and only the terms the part's idea needs.
- **Recall beats rereading.** → Every part ends with a check; every rung has an explain-back; Review mode (V) replays only the checks for spaced review.
- **Concrete before abstract, then a crisp definition.** → Open with the situation and its numbers, then give the formal definition in a box, then the mechanism. The reader meets the need before the name, and still gets an exact definition to revise from.
- **Familiar structure lowers effort.** → Every part uses the same textbook layout (below), so the reader always knows where the definition, the working, the solved example and the summary are.
- **Pictures help only when they show a relationship.** → Diagram only for movement, order over time, structure, or before/after. One diagram that grows across parts beats five different ones.
- **Attention needs a reason.** → Every part opens with a real problem the reader would hit at work, with numbers.
- **Visible progress keeps motivation.** → Every part has a time estimate (`data-min`), a route rail that fills in, and a done button. Long parts are fine; the reader can stop at any heading and resume.
- **Gaps in reasoning lose the reader.** → Explain why before how, walk through every step, and never state a rule without the reason behind it.

## The route (the same five rungs on every page)

| Rung | Label | Reader can… | Content |
|---|---|---|---|
| 0 | Before you start | (only if needed) | At most 2 prerequisite parts. More needed → name the topic to learn first in `meta.prereqs` and keep going. In a cumulative series, earlier pages are the prerequisites: recap, don't re-teach. |
| 1 | Why it exists | Say what problem it solves, in everyday words | The pain without it, an everyday comparison, no jargon |
| 2 | How it works | Walk through the steps | Core flow, the main diagram, predict-before-reveal |
| 3 | Using it | Read or write a correct basic version | Verified code/config, production defaults, a real case |
| 4 | When it breaks | Predict failures and their fixes | Attacks, edge cases, limits, what breaks first at 10× load, traps |
| 5 | When to pick it | Choose it or an alternative and defend it | Comparison table, decision rules, interview drill |

Every rung appears on every page. Use as many parts per rung as the idea needs; rungs 3, 4 and 5 usually need the most, because that is where the senior bar sits. A topic too big for one page becomes a cumulative series (below).

## Part template: textbook style (in this order)

Pages follow the explanation style of Indian-authored computer science textbooks: every part is a small chapter with fixed, labelled sections, a formal definition, numbered working, a solved example with every intermediate value, and a "points to remember" summary. Use `h3` for the section headings below; skip a section only when it truly has nothing to say (e.g. no diagram).

1. `h2`: a plain-language title that says what the part answers ("Why the code is useless to a thief"), not a term ("PKCE").
2. `.ts-bridge` (part 2 onward): "Last part: <takeaway>. Still unsolved: <gap this part fills>."
3. `.ts-problem`: a concrete situation with numbers where possible.
4. `h3` **Introduction**: 1 to 3 short paragraphs on where this idea sits and the question the part answers.
5. Comparison (rungs 1 to 2): one everyday thing, mapped explicitly as a list ("the hotel front desk = the login server"). Then one sentence on where the comparison stops working.
6. `h3` **Definition**: `<div class="ts-note" data-label="Definition">` with the term as `<dfn data-def>` and a one- or two-sentence formal definition. Then explain any word in the definition that needs it. Several new terms → `h3` **Definitions** with a numbered list, each term defined before any diagram or code uses it.
7. `h3` **Working**: `.ts-steps`, as many steps as the flow really has. Follow it with **Why each step is needed**: one bullet per step saying what would go wrong without it.
8. `h3` **Diagram** (if the diagram rule triggers), followed by **Explanation of the diagram**: walk every step or arrow in prose; the diagram never carries meaning the text doesn't.
9. `h3` **Solved example**: **Given:** (the inputs, with real values), **Step 1.**, **Step 2.**, … showing every intermediate value, then **Result:** in one or two sentences. A table works when the example compares cases. Values computed by code must come from `examples/<slug>/`, with a test that asserts the page shows them.
10. `h3` **Program** (rungs 3 to 5): one sentence on what it does and why, the code block, then `h3` **Explanation of the program**: a numbered walk through the important lines. Add **Testing the program** (a table of cases and results) when tests exist. Add, where one exists, a verified "In the wild" case.
11. Comparison tables where there are alternatives: `h3` **Difference between X and Y**, **Advantages**, **Limitations**, or **Production defaults vs tutorial defaults** (rung 3). Rows are points of comparison.
12. Callouts: at least one common misunderstanding per rung, as `<div class="ts-note" data-label="Common misunderstanding">`: **Wrong belief**, **Why people hold it** (when it helps), **Why it is wrong**. `ts-trap`, `ts-legacy`, `ts-interview` (rungs 3 to 5) as needed. Rung 4 parts also state what the user sees, the signal to watch (metric, log, alert) and the fix, often as one table.
13. `<div class="ts-note" data-label="Points to remember">`: 2 to 4 bullets, the part's revision notes.
14. `.ts-takeaway`: one sentence.
15. Checks: at least one. Mix across the page: quizzes for discrimination, order for flows, predict for mechanisms and failures, explain-back once per rung on the rung's central idea.

Checked facts keep their own sentences inside these sections (`.ts-claim`); the textbook layout changes the structure around them, never their wording.

## Language
- Explanations are elaborate; words are simple. Say everything needed, in the plainest words that are still exact.
- Every concept follows: the problem (with numbers) → the definition → how it works → a solved example → where it breaks.
- Textbook phrasing is welcome: "Let us understand this with an example", "Consider…", "Hence…", numbered points, labelled sections. Keep it plain and exact, never ornamental.
- Prefer short sentences and one idea per paragraph. Split a sentence that carries two ideas.
- Everyday words: "kept open", not "long-lived"; "sent to everyone listening", not "fan-out".
- Define each new term with `<dfn data-def>` at first use, in plain words. No term appears anywhere (diagram labels, quiz options, callouts) before its definition. No unexplained acronyms.
- Once a term is chosen, never switch to a synonym. Map official terms once: "the login server (the spec calls it the authorization server)".
- Numbers beat adjectives: "19 of 20 requests wasted" beats "inefficient".
- No praise, filler, hype, emoji or exclamation marks. No "simply", "just", "obviously".

## Diagram rule
Draw when the part has: something moving between components; an order over time that matters; a structure or layout; a before/after or A-vs-B comparison. Don't draw for definitions, lists or analogies. Test: if removing the diagram loses nothing, remove it. Max one diagram per part. Grow one picture across parts: same actors, same positions, add or highlight only the new piece.

## Cumulative series
A topic larger than one page is a series of pages that build one running system. The last page is the culmination of every earlier page, not a new topic.

- **Plan the whole series first.** Before writing page 1, fix the running system, the list of pages, and for each page: the one layer it adds, what it reuses from earlier pages, and what it leaves broken for the next page. Record the plan in page 1's `meta.related`, and keep it unchanged unless the user asks.
- **One running system.** Every page works on the same system with the same actors, names and data. A page adds exactly one layer to it.
- **Series diagram.** Every page opens with "The system so far": a short recap of what earlier pages built, and the series architecture diagram with all earlier components shown and the new one highlighted. Same actors and positions on every page.
- **Close the loop.** Every page ends with "What this page added" and "What is still broken", which the next page fixes.
- **Cumulative code.** `examples/<topic>-N/` starts as a copy of `examples/<topic>-(N-1)/` and adds only the new layer. Every earlier test must still pass on every later page. The last page's folder is the complete system.
- **Cumulative checks.** From page 2 on, include at least one check that needs an earlier page's idea together with this page's idea.
- **The last page integrates.** It teaches no new mechanism. It assembles the whole system, sizes it, walks its failure modes across layers, and runs a full mock interview that draws on every earlier page.
- **Links.** Each page lists the previous page in `meta.prereqs` and the next in `meta.related`, and ends with "Next: Part N — <title>".

## Senior depth in rungs 4 and 5 (see depth-target.md)
- Rung 4 must answer: what breaks first as load grows 10×; what an attacker or a bad client does; what the user sees when it fails; how you detect it (metric, log, alert) and how you fix it.
- Rung 5 must include a comparison table of the realistic alternatives with "pick it when" criteria, and an interview-drill part: 2 to 3 design prompts where this topic is the crux, each with a predict or explain check and a reference answer that states the trade-off explicitly.
- At least three `ts-interview` callouts across rungs 3 to 5.

## Checks: quality bar
- Every check is answerable from what the page (and, in a series, earlier pages) has taught up to that point.
- Applied checks use a new situation, not the one from the example.
- Quiz distractors encode real misconceptions; each `data-why` names the wrong belief.
- Explain-back rubric points (`data-points`) are the part's key ideas, phrased so a reader can tick them honestly.
