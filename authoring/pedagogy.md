# Pedagogy: how a page teaches

Reader: a busy engineer who learns best in short, focused chunks, strong in backend work, who may know nothing about this topic. Goal: take them from zero to the level in `depth-target.md`, in one page they can finish in sittings of 10 to 15 minutes.

## Why these rules (use this to handle cases the rules don't cover)
- **Small working memory.** Too many new things at once and nothing sticks. → One idea per part, max 2 new terms per part, each defined where it first appears.
- **Recall beats rereading.** → Every part ends with a check; every rung has an explain-back; Review mode (V) replays only the checks for spaced review.
- **Concrete before abstract.** → Show the situation, then the mechanism, then the name. Names come last.
- **Pictures help only when they show a relationship.** → Diagram only for movement, order over time, structure, or before/after. One diagram that grows across parts beats five different ones.
- **Attention needs a reason.** → Every part opens with a real problem the reader would hit at work, with numbers.
- **Visible progress keeps motivation.** → Short parts with time estimates, a route rail that fills in, a done button per part.

## The route (the same five rungs on every page)

| Rung | Label | Reader can… | Content |
|---|---|---|---|
| 0 | Before you start | (only if needed) | At most 2 prerequisite parts. More needed → name the topic to learn first in `meta.prereqs` and keep going. |
| 1 | Why it exists | Say what problem it solves, in everyday words | The pain without it, an everyday comparison, no jargon |
| 2 | How it works | Walk through the steps | Core flow, the main diagram, predict-before-reveal |
| 3 | Using it | Read or write a correct basic version | Minimal verified code/config, production defaults, a real case |
| 4 | When it breaks | Predict failures and their fixes | Attacks, edge cases, limits, what breaks first at 10× load, traps |
| 5 | When to pick it | Choose it or an alternative and defend it | Comparison table, decision rules, interview drill |

Size: 8 to 14 parts. Rungs 1 and 2 get 1 to 3 parts each; rungs 3, 4 and 5 get 2 to 4 each, because that is where the senior bar sits. A topic too big for 14 parts is split: teach the core now and list the rest in `meta.related`.

## Part template (in this order)

1. `h2`: a plain-language title that says what the part answers ("Why the code is useless to a thief"), not a term ("PKCE").
2. `.ts-bridge` (part 2 onward): "Last part: <takeaway>. Still unsolved: <gap this part fills>."
3. `.ts-problem`: 1 to 2 sentences, a concrete situation with numbers where possible.
4. Comparison (rungs 1 to 2): one everyday thing, mapped explicitly ("the hotel front desk = the login server"). By the end of rung 2, one sentence on where the comparison stops working.
5. Mechanism: `.ts-steps`, max 5 steps. Behaviour first, then the name: "The server never finishes the reply. That's called a stream."
6. Diagram, if the diagram rule triggers. After the mechanism, before code.
7. Example: rungs 1 to 2 a worked scenario (backend/data-engineering flavoured when natural); rungs 3 to 5 minimal code or config plus, where one exists, a verified "In the wild" case.
8. Optional callouts: `ts-legacy`, `ts-trap`, `ts-interview` (rungs 3 to 5).
9. `.ts-takeaway`: one sentence.
10. Checks: at least one. Mix across the page: quizzes for discrimination, order for flows, predict for mechanisms and failures, explain-back once per rung on the rung's central idea.

## Language
- Prose per part: aim for 150 to 300 words, hard limit 450 (the verifier warns). Diagrams, code and checks don't count.
- Sentences of 20 words or fewer. One idea per paragraph.
- Everyday words: "kept open", not "long-lived"; "sent to everyone listening", not "fan-out".
- Define each new term with `<dfn data-def>` at first use, in plain words. No term appears anywhere (diagram labels, quiz options, callouts) before its definition.
- Once a term is chosen, never switch to a synonym. Map official terms once: "the login server (the spec calls it the authorization server)".
- Numbers beat adjectives: "19 of 20 requests wasted" beats "inefficient".
- No praise, filler, hype, emoji or exclamation marks. No "simply", "just", "obviously".

## Diagram rule
Draw when the part has: something moving between components; an order over time that matters; a structure or layout; a before/after or A-vs-B comparison. Don't draw for definitions, lists or analogies. Test: if removing the diagram loses nothing, remove it. Max one diagram per part. Grow one picture across parts: same actors, same positions, add or highlight only the new piece.

## Senior depth in rungs 4 and 5 (see depth-target.md)
- Rung 4 must answer: what breaks first as load grows 10×; what an attacker or a bad client does; what the user sees when it fails; how you detect it (metric, log, alert) and how you fix it.
- Rung 5 must include a comparison table of the realistic alternatives with "pick it when" criteria, and an interview-drill part: 2 to 3 design prompts where this topic is the crux, each with a predict or explain check and a reference answer that states the trade-off explicitly.
- At least three `ts-interview` callouts across rungs 3 to 5.

## Checks: quality bar
- Every check is answerable from what the page has taught up to that point.
- Applied checks use a new situation, not the one from the example.
- Quiz distractors encode real misconceptions; each `data-why` names the wrong belief.
- Explain-back rubric points (`data-points`) are the part's key ideas, phrased so a reader can tick them honestly.
