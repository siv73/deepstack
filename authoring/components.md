# Components: the HTML contract

Write only `body.html`: a sequence of `<section class="ts-part">` elements. `build.py` wraps it in the shared shell (top bar, route rail, hero, sources, next steps). `ts.js` turns the declarative markup below into interactive components. Never add `<style>`, `<script src>`, inline event handlers, external images, fonts or CDNs: every page must look identical and work offline. If a component you want doesn't exist, use the nearest one; don't invent CSS.

## Contents
1. Part
2. Text elements (bridge, problem, steps, terms, claims)
3. Callouts
4. Diagrams (sequence, graph, raw SVG)
5. Code and tabs
6. Tables
7. Checks (quiz, order, predict, explain)

---

## 1. Part

```html
<section class="ts-part" id="auth-code-flow" data-rung="2" data-min="4">
  <h2>The authorization code flow, step by step</h2>
  ...
</section>
```
- `id`: short kebab-case, unique. It becomes the URL fragment and the progress key; never rename it on refresh.
- `data-rung`: 0 (prerequisite) to 5. Non-decreasing through the page. Rungs 1 to 5 must all appear.
- `data-min`: honest reading-plus-checks estimate. Target 3 to 6.
- The shell adds the "Part N of M · rung · about X min" kicker, the rail station, the "Mark this part done" button and the "Next:" link. Don't write those.

## 2. Text elements

```html
<p class="ts-bridge">Last part: the app never sees your password. Still unsolved: how does the app prove it's allowed in?</p>
<p class="ts-problem">A photo-printing site wants 40 photos from your Google account. ...</p>
<ol class="ts-steps"><li>...</li></ol>          <!-- numbered mechanism steps, max 5, rung-coloured -->
<dfn data-def="Plain one-line definition.">access token</dfn>   <!-- first use of a new term; hover/tap shows the definition -->
<span class="ts-claim" data-claim="c7" data-src="s1 s3">Exact sentence stating a checked fact.</span>
```
- `.ts-claim`: wraps every sentence that states a fact that could be wrong (spec requirements, parameter names, defaults, limits, versions, dates, deprecations, numbers, "X does Y" about a real product). `data-claim` must be a verified ledger claim; `data-src` lists the source ids to cite (each must be in that claim's `sources`). Citation chips are added automatically.
- Analogies, framing and your own reasoning are not claims; don't wrap them. If a sentence mixes both, split it.

## 3. Callouts

All take normal HTML inside. The label is added automatically (override with `data-label="..."` only when the default would mislead).

| Class | Label shown | Use for |
|---|---|---|
| `ts-takeaway` | Takeaway | Exactly one per part, last before the checks. One sentence, the line to remember. |
| `ts-legacy` | Legacy: you will meet this, don't build it new | Old conventions still found in real code or interviews. Say what replaced it and why, with claims. |
| `ts-trap` | Production trap | A failure mode seen in production. Rungs 3 to 5. |
| `ts-interview` | Senior interview lens | The probing question an interviewer asks at this point and what a strong senior answer contains. Rungs 3 to 5, at least 3 per topic. |
| `ts-case` | In the wild | A real company or project, what they did, why, link. Must be a verified claim. No case found → skip it, never invent. |
| `ts-note` | Note | Anything else worth a box. Use rarely. |

## 4. Diagrams

Use a diagram only when the part shows movement between components, an order over time, a structure, or a before/after (see pedagogy.md). Reuse the same actor/node ids and labels across parts so the picture grows instead of changing.

### Sequence diagram (protocols, request flows)
```html
<figure class="ts-seq" data-title="Authorization code flow">
<script type="application/json">
{"actors": [
   {"id": "user", "label": "You", "sub": "browser"},
   {"id": "app",  "label": "Photo app", "sub": "client"},
   {"id": "as",   "label": "Login server", "sub": "authorization server"}],
 "steps": [
   {"from": "user", "to": "app", "label": "Click Connect Google Photos", "note": "Caption shown under the diagram for this step."},
   {"from": "app", "to": "user", "label": "302 redirect to login server", "dashed": true, "note": "..."},
   {"over": ["user", "as"], "label": "You sign in and approve", "note": "..."},
   {"from": "as", "to": "as", "label": "Creates one-time code", "note": "..."}]}
</script>
</figure>
```
- `dashed: true` = a response or a redirect. Keep that meaning consistent.
- Labels: max about 45 characters; they wrap. Every step needs a `note`: the caption, one or two plain sentences.
- 3 to 5 actors. More than 5 makes the phone view scroll; split the diagram instead.

### Box-and-arrow graph (architecture, components, trust boundaries)
```html
<figure class="ts-graph" data-title="Who trusts whom">
<script type="application/json">
{"nodes": [
   {"id": "app", "label": "Photo app", "sub": "client", "col": 0, "row": 0},
   {"id": "as",  "label": "Login server", "col": 1, "row": 0, "step": 1},
   {"id": "api", "label": "Photos API", "sub": "resource server", "col": 1, "row": 1, "step": 2}],
 "edges": [
   {"from": "app", "to": "as", "label": "asks for a token", "step": 1},
   {"from": "as", "to": "app", "label": "access token", "step": 1, "dashed": true},
   {"from": "app", "to": "api", "label": "calls with token", "step": 2}],
 "captions": ["Step 1 caption.", "Step 2 caption."]}
</script>
</figure>
```
- Grid positions: `col` 0 to 3, `row` 0 to 3; one node per cell. Keep the layout the same wherever the same nodes appear.
- `step` is optional. If any element has a step, `captions` must have exactly one entry per step. Elements without `step` are always visible.
- Edge labels: max about 30 characters.

### Raw SVG (only when neither fits, e.g. a token's internal structure)
```html
<figure class="ts-svg" data-title="What is inside a JWT">
  <svg viewBox="0 0 700 180" role="img" aria-label="...">
    <g class="node" data-s="1"><rect .../><text ...>Header</text></g>
    ...
  </svg>
  <ol class="ts-captions"><li>Step 1 caption</li><li>Step 2 caption</li></ol>
</figure>
```
Use the existing classes (`node`, `edge`, `msg`, `over`, `lblbg`, `arrowhead`) and CSS variables (`var(--ink)`, `var(--surface-2)`, `var(--line)`, `var(--rc)`) only. No hard-coded colours: they break dark mode.

### Roofline calculator (compute-bound vs memory-bound, for GPU/LLM topics)
```html
<div class="ts-roofline" data-title="Roofline calculator">
<script type="application/json">
{"gpus": [{"id": "h100-sxm", "label": "H100 SXM", "tflops": 989.5, "tbps": 3.35, "gb": 80}],
 "defaults": {"gpu": "h100-sxm", "params": 8, "batch": 1, "prompt": 2000}}
</script>
</div>
```
- Renders inputs (GPU, model size in billions, batch, prompt tokens), a log-log roofline with decode and prefill points, and the weights-only estimate (BF16, 2 FLOPs and 2 bytes per parameter).
- `tflops` is the dense peak, `tbps` memory bandwidth in TB/s, `gb` memory. Every figure must also appear on the page as a verified claim (e.g. in a spec table next to it).

### KV cache calculator (cache size, capacity, decode with KV reads)
```html
<div class="ts-kvcalc" data-title="KV cache calculator">
<script type="application/json">
{"models": [{"id": "llama-3.1-8b", "label": "Llama 3.1 8B", "params": 8, "layers": 32, "q_heads": 32, "kv_heads": 8, "head_dim": 128}],
 "gpus": [{"id": "h100-sxm", "label": "H100 SXM", "tflops": 989.5, "tbps": 3.35, "gb": 80}],
 "dtypes": [{"id": "bf16", "label": "BF16 (2 bytes)", "bytes": 2}],
 "defaults": {"model": "llama-3.1-8b", "gpu": "h100-sxm", "dtype": "bf16", "context": 8192, "batch": 64, "util": 0.92, "reserve": 3}}
</script>
</div>
```
- Renders a model preset (plus Custom: params in billions, layers, query heads, KV heads, head dimension), GPU, KV data type, tokens per request, batch, `gpu_memory_utilization` and other reserved GB; a memory bar (weights, reserve, KV in use, KV free, unrequested); and KV bytes per token and per request, the KV budget, requests that fit, the decode step including KV reads, and the batch where decode turns compute-bound.
- Same arithmetic as `examples/llm-serving-2/kv_cache.py`: weights in BF16, attention FLOPs of 4 × layers × query heads × head_dim per cached token. Model shapes and GPU figures must appear on the page as verified claims.

### Slot timeline (batching policies over time, stepped column by column)
```html
<figure class="ts-slots" data-title="Six requests, three slots">
<script type="application/json">
{"slots": 3,
 "requests": [{"id": "A", "arrives": 0, "tokens": 2}],
 "lanes": [{"label": "Static batching", "cols": [["wait", "wait", "wait"], ["P:A", "P:B", "P:C"]]},
           {"label": "Continuous batching", "cols": [["P:A", "P:B", ""]]}],
 "captions": ["One caption per column of the longest lane."]}
</script>
</figure>
```
- Cell kinds: `P:<id>` prefill, `d:<id>` decode, `pad:<id>` a finished row still in the batch, `wait` an empty slot while the GPU waits, `""` an empty slot. `arrives` is a 0-based column; the axis is labelled from 1.
- Generate the JSON from tested code and assert in a test that the page's block matches it (see `examples/llm-serving-3/test_batching.py`).

### Batch trade-off calculator (continuous batching in steady state)
```html
<div class="ts-batchcalc" data-title="Batch trade-off calculator">
<script type="application/json">
{"models": [{"id": "llama-3.1-8b", "label": "Llama 3.1 8B", "params": 8, "layers": 32, "q_heads": 32, "kv_heads": 8, "head_dim": 128}],
 "gpus": [{"id": "h100-sxm", "label": "H100 SXM", "tflops": 989.5, "tbps": 3.35, "gb": 80}],
 "defaults": {"model": "llama-3.1-8b", "gpu": "h100-sxm", "rate": 10, "prompt": 1000, "output": 250, "max_seqs": 1024, "util": 0.92, "reserve": 3}}
</script>
</div>
```
- Inputs: model, GPU, arrival rate, prompt and output length, max batch (max_num_seqs), `gpu_memory_utilization`, reserve. Outputs: running requests, throughput, TPOT, TTFT estimate, KV memory used, prefill share; a chart of tokens/s and TPOT against batch size with every slot full.
- Same arithmetic as `examples/llm-serving-3/steady_state.py`. Model shapes and GPU figures must appear on the page as verified claims.

## 5. Code and tabs

```html
<!-- Runnable code: lives in examples/<slug>/client.py, tested by examples/<slug>/test_client.py.
     build.py fills this block with the file's contents, so the page always shows the tested code. -->
<div class="ts-code" data-lang="python" data-title="client.py" data-file="client.py" data-verified="ran"></div>

<!-- Non-runnable snippet (raw HTTP, hosted-service config): written inline, names backed by claims. -->
<div class="ts-code" data-lang="http" data-title="The token request" data-verified="spec" data-claims="c3 c4">
<pre><code>...escaped code...</code></pre>
</div>
```
- `data-verified="ran"` requires `data-file`: the code must be an example file whose tests pass (`make test`). The verifier rejects "ran" code written inline.
- `data-verified="spec" data-claims="..."`: it can't run offline; every parameter, header and field name in it is backed by the listed verified claims. Escape `<`, `>` and `&` inside `<code>`.
- Languages highlighted: python, js/ts, bash. Others (http, json, yaml, sql) render plain, which is fine.
- Keep blocks under 25 lines. Show the minimum that works.

```html
<div class="ts-tabs">
  <div data-tab="HTTP request"> ...code block... </div>
  <div data-tab="Python"> ...code block... </div>
</div>
```

## 6. Tables

```html
<div class="ts-table-wrap"><table class="ts-table">
  <thead><tr><th>Option</th><th>Pick it when</th><th>Cost</th></tr></thead>
  <tbody>
    <tr><td>...</td><td>...</td><td>...</td></tr>
  </tbody>
</table></div>
```
Always use `<thead>` and `<tbody>`; `make lint` validates the generated HTML.
Rung 5 comparison tables: rows are options, columns are the decision criteria. Factual cells are claims (wrap the cell text in `.ts-claim`).

## 7. Checks

Every part ends with at least one check, after its takeaway. Answer keys must trace to verified facts: add `data-claims="c1 c2"` listing the claims the correct answer rests on. Use `data-kind="reasoning"` instead only when the answer follows purely from what the page already taught (e.g. ordering the steps of a flow shown in the diagram).

### Quiz (one right answer)
```html
<div class="ts-quiz" data-answer="b" data-claims="c4">
  <p class="q">The app gets a code back in the redirect. Why doesn't the login server send the access token there directly?</p>
  <ol>
    <li data-why="Speed isn't the reason; the extra hop is slower.">It's faster</li>
    <li>The redirect passes through the browser, where the URL can leak</li>
    <li data-why="The code is also short-lived; length isn't the point.">Tokens are too long for a URL</li>
  </ol>
  <p class="ts-why">The explanation shown once they get it right.</p>
</div>
```
- 3 or 4 options. Every wrong option has `data-why`: the specific wrong belief behind it, not "incorrect".
- Distractors are mistakes real engineers make, not jokes.
- Behaviour: a wrong pick shows its `data-why` and allows one more try; a second miss reveals the answer.

### Order (sequence)
```html
<div class="ts-order" data-kind="reasoning">
  <p class="q">Put the flow in order.</p>
  <ol><li>First (write items in the CORRECT order)</li><li>Second</li><li>Third</li></ol>
  <p class="ts-why">Why this order.</p>
</div>
```
3 to 6 items. The page shuffles them.

### Predict (commit a guess before the reveal)
```html
<div class="ts-predict" data-claims="c9">
  <p class="q">An attacker replays a stolen code 10 seconds later. What happens?</p>
  <div class="ts-reveal"><p>...</p></div>
</div>
```
Best placed before a mechanism is explained (rung 2) or for failure scenarios (rung 4).

### Explain back (self-graded, or graded by Claude)
```html
<div class="ts-explain" data-points="The app never sees the password|The code is useless without the client's secret or PKCE verifier|Tokens travel server to server, not through the browser">
  <p class="q">In your own words: why does the code flow have two hops instead of one?</p>
  <div class="ts-model"><p>Reference answer, 3 to 5 plain sentences.</p></div>
</div>
```
- `data-points`: 2 to 4 key points separated by `|`. These are the grading rubric.
- The reader can tick the points they covered, or press "Get graded by Claude", which copies a teach-back-format grading prompt (rubric, reference answer, their answer) to paste into a chat.
- One explain-back per rung at minimum, on the rung's central idea.
