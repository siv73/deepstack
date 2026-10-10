/* teach-site runtime v1. Shared by every page; pages declare content, this file adds behaviour. No dependencies. */
(() => {
  const VERSION = "1";
  const RUNGS = {
    0: "Before you start",
    1: "Why it exists",
    2: "How it works",
    3: "Using it",
    4: "When it breaks",
    5: "When to pick it",
  };
  const REVIEW_DAYS = [1, 3, 7, 21, 60];
  const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  /* ---------- helpers ---------- */
  function $(sel, root) {
    return (root || document).querySelector(sel);
  }
  function $$(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }
  function el(tag, attrs, kids) {
    const n = document.createElement(tag);
    if (attrs)
      Object.keys(attrs).forEach((k) => {
        if (k === "text") n.textContent = attrs[k];
        else if (k === "html") n.innerHTML = attrs[k];
        else if (k.slice(0, 2) === "on") n.addEventListener(k.slice(2), attrs[k]);
        // CSSOM, never a style attribute: the CSP (style-src 'self') blocks inline style attributes.
        else if (k === "style") n.style.cssText = attrs[k];
        else n.setAttribute(k, attrs[k]);
      });
    (kids || []).forEach((c) => {
      if (c != null) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return n;
  }
  const SVGNS = "http://www.w3.org/2000/svg";
  function sv(tag, attrs, kids) {
    const n = document.createElementNS(SVGNS, tag);
    if (attrs)
      Object.keys(attrs).forEach((k) => {
        if (k === "text") n.textContent = attrs[k];
        else if (k === "style") n.style.cssText = attrs[k];
        else n.setAttribute(k, attrs[k]);
      });
    (kids || []).forEach((c) => {
      if (c) n.appendChild(c);
    });
    return n;
  }
  function readJSON(id, root) {
    const s = typeof id === "string" ? $(`#${id}`, root) : id;
    if (!s) return null;
    try {
      return JSON.parse(s.textContent);
    } catch (e) {
      console.error("[teach-site] bad JSON in", id, e);
      return null;
    }
  }
  function esc(s) {
    return String(s).replace(
      /[&<>"']/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
    );
  }
  function daysBetween(a, b) {
    return Math.floor((b - a) / 86400000);
  }

  const store = {
    ok: (() => {
      try {
        localStorage.setItem("ts:probe", "1");
        localStorage.removeItem("ts:probe");
        return true;
      } catch (_e) {
        return false;
      }
    })(),
    get: function (k, d) {
      if (!this.ok) return d;
      try {
        const v = localStorage.getItem(`ts:v1:${k}`);
        return v == null ? d : JSON.parse(v);
      } catch (_e) {
        return d;
      }
    },
    set: function (k, v) {
      if (!this.ok) return;
      try {
        localStorage.setItem(`ts:v1:${k}`, JSON.stringify(v));
      } catch (_e) {}
    },
  };

  /* ---------- theme ---------- */
  function applyTheme(t) {
    if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
    else document.documentElement.removeAttribute("data-theme");
  }
  applyTheme(store.get("theme", null));
  function toggleTheme() {
    const cur = document.documentElement.getAttribute("data-theme");
    const sysDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
    const isDark = cur ? cur === "dark" : sysDark;
    const next = isDark ? "light" : "dark";
    applyTheme(next);
    store.set("theme", next);
  }

  /* ---------- toast ---------- */
  let toastTimer;
  function toast(msg, actionLabel, action, ms) {
    const t =
      $(".ts-toast") ||
      document.body.appendChild(el("div", { class: "ts-toast", role: "status", "aria-live": "polite" }));
    t.innerHTML = "";
    t.appendChild(el("span", { text: msg }));
    if (actionLabel)
      t.appendChild(
        el("button", {
          type: "button",
          text: actionLabel,
          onclick: () => {
            t.classList.remove("is-on");
            action();
          },
        }),
      );
    t.classList.add("is-on");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      t.classList.remove("is-on");
    }, ms || 4200);
  }

  /* ---------- confetti ---------- */
  function confetti() {
    if (reduceMotion) return;
    const c = el("canvas", { class: "ts-confetti" });
    document.body.appendChild(c);
    c.width = innerWidth;
    c.height = innerHeight;
    const ctx = c.getContext("2d");
    const W = c.width;
    const H = c.height;
    const cs = getComputedStyle(document.documentElement);
    const cols = ["--r1", "--r2", "--r3", "--r4", "--r5"].map((v) => cs.getPropertyValue(v).trim() || "#888");
    const ps = [];
    for (let i = 0; i < 90; i++)
      ps.push({
        x: W / 2,
        y: H * 0.35,
        vx: (Math.random() - 0.5) * 12,
        vy: Math.random() * -11 - 3,
        r: Math.random() * 5 + 3,
        c: cols[i % 5],
        a: Math.random() * 6,
      });
    const start = performance.now();
    (function frame(now) {
      const t = now - start;
      ctx.clearRect(0, 0, W, H);
      ps.forEach((p) => {
        p.vy += 0.35;
        p.x += p.vx;
        p.y += p.vy;
        p.a += 0.1;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.a);
        ctx.fillStyle = p.c;
        ctx.globalAlpha = Math.max(0, 1 - t / 1600);
        ctx.fillRect(-p.r, -p.r / 2, p.r * 2, p.r);
        ctx.restore();
      });
      if (t < 1600) requestAnimationFrame(frame);
      else c.remove();
    })(start);
  }

  /* ---------- clipboard ---------- */
  function copyText(txt, okMsg) {
    function fallback() {
      const ta = el("textarea", { style: "position:fixed;left:-9999px" });
      ta.value = txt;
      document.body.appendChild(ta);
      ta.select();
      let ok = false;
      try {
        ok = document.execCommand("copy");
      } catch (_e) {}
      ta.remove();
      toast(ok ? okMsg : "Copy failed. Select the text and copy it manually.");
    }
    if (navigator.clipboard && window.isSecureContext)
      navigator.clipboard.writeText(txt).then(() => {
        toast(okMsg);
      }, fallback);
    else fallback();
  }

  /* =====================================================================
     DIAGRAMS
     ===================================================================== */
  function textW(s, size) {
    return String(s).length * (size || 13) * 0.56;
  }
  function wrap(s, maxChars) {
    let words = String(s).split(/\s+/),
      lines = [],
      cur = "";
    words.forEach((w) => {
      if (`${cur} ${w}`.trim().length > maxChars && cur) {
        lines.push(cur);
        cur = w;
      } else cur = `${cur} ${w}`.trim();
    });
    if (cur) lines.push(cur);
    return lines;
  }
  function textLines(x, y, lines, cls, anchor, lh) {
    const t = sv("text", { x: x, y: y, "text-anchor": anchor || "middle", class: cls || "" });
    lines.forEach((ln, i) => {
      t.appendChild(sv("tspan", { x: x, dy: i === 0 ? 0 : lh || 16, text: ln }));
    });
    return t;
  }
  function arrowHead(x, y, ang) {
    const s = 10,
      a1 = ang + Math.PI * 0.85,
      a2 = ang - Math.PI * 0.85;
    return sv("polygon", {
      class: "arrowhead",
      points: [x, y, x + s * Math.cos(a1), y + s * Math.sin(a1), x + s * Math.cos(a2), y + s * Math.sin(a2)].join(" "),
    });
  }
  function numBadge(x, y, n) {
    return sv("g", {}, [
      sv("circle", { class: "num", cx: x, cy: y, r: 9 }),
      sv("text", { class: "num-t", x: x, y: y + 4, "text-anchor": "middle", text: String(n) }),
    ]);
  }

  // Sequence diagram: {actors:[{id,label,sub}], steps:[{from,to,label,note,dashed}|{over:"id"|["a","b"],label,note}]}
  function renderSeq(spec) {
    const n = spec.actors.length,
      colW = spec.colWidth || (n >= 5 ? 160 : 190),
      pad = 24;
    const W = pad * 2 + colW * n,
      idx = {};
    spec.actors.forEach((a, i) => {
      idx[a.id] = pad + colW * i + colW / 2;
    });
    const headH = spec.actors.some((a) => a.sub) ? 60 : 46;
    let y = headH + 34,
      rows = [];
    spec.steps.forEach((st, i) => {
      const r = { st: st, i: i + 1 };
      if (st.over) {
        const ids = [].concat(st.over),
          xs = ids.map((d) => idx[d]);
        r.x1 = Math.min.apply(null, xs) - colW / 2 + 12;
        r.x2 = Math.max.apply(null, xs) + colW / 2 - 12;
        r.lines = wrap(st.label, Math.max(10, Math.floor((r.x2 - r.x1 - 16) / 7.3)));
        r.h = 20 + r.lines.length * 16;
        r.y = y;
        y += r.h + 22;
      } else if (st.from === st.to) {
        r.x = idx[st.from];
        r.lines = wrap(st.label, Math.floor((colW - 30) / 7.3));
        r.y = y + 8;
        r.h = 34 + (r.lines.length - 1) * 16;
        y += r.h + 30;
      } else {
        r.x1 = idx[st.from];
        r.x2 = idx[st.to];
        const span = Math.abs(r.x2 - r.x1) - 40;
        r.lines = wrap(st.label, Math.max(12, Math.floor(span / 7.3)));
        r.y = y + (r.lines.length - 1) * 16 + 18;
        y = r.y + 34;
      }
      rows.push(r);
    });
    const H = y + 6;
    const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": spec.title || "Sequence diagram" });
    svg.style.maxWidth = `${Math.round(W * 1.15)}px`;
    spec.actors.forEach((a) => {
      const x = idx[a.id],
        w = colW - 24;
      svg.appendChild(sv("line", { class: "life", x1: x, y1: headH + 8, x2: x, y2: H - 4 }));
      const g = sv("g", { class: "actor" }, [sv("rect", { x: x - w / 2, y: 8, width: w, height: headH - 8, rx: 8 })]);
      g.appendChild(textLines(x, a.sub ? 30 : 36, [a.label], "", "middle"));
      if (a.sub)
        g.appendChild(
          sv("text", {
            x: x,
            y: 48,
            "text-anchor": "middle",
            class: "sub",
            text: a.sub,
            style: "font-size:12px;font-weight:500;fill:var(--muted)",
          }),
        );
      svg.appendChild(g);
    });
    rows.forEach((r) => {
      let st = r.st,
        g;
      if (st.over) {
        g = sv("g", { class: "over", "data-s": r.i });
        g.appendChild(sv("rect", { x: r.x1, y: r.y, width: r.x2 - r.x1, height: r.h, rx: 8 }));
        g.appendChild(textLines((r.x1 + r.x2) / 2, r.y + 22, r.lines, "", "middle"));
        g.appendChild(numBadge(r.x1 + 2, r.y + 2, r.i));
      } else if (st.from === st.to) {
        g = sv("g", { class: `msg${st.dashed ? " dashed" : ""}`, "data-s": r.i });
        const x = r.x,
          yy = r.y;
        g.appendChild(sv("path", { d: `M${x} ${yy} h36 v24 h-30` }));
        g.appendChild(arrowHead(x + 2, yy + 24, Math.PI));
        g.appendChild(textLines(x + 44, yy + 16, r.lines, "", "start"));
        g.appendChild(numBadge(x - 14, yy, r.i));
      } else {
        g = sv("g", { class: `msg${st.dashed ? " dashed" : ""}`, "data-s": r.i });
        const dir = r.x2 > r.x1 ? 1 : -1,
          yA = r.y;
        g.appendChild(sv("line", { x1: r.x1 + dir * 4, y1: yA, x2: r.x2 - dir * 9, y2: yA }));
        g.appendChild(arrowHead(r.x2 - dir * 2, yA, dir > 0 ? 0 : Math.PI));
        const mid = (r.x1 + r.x2) / 2,
          top = yA - 8 - (r.lines.length - 1) * 16;
        const tw = Math.max.apply(
          null,
          r.lines.map((l) => textW(l)),
        );
        g.appendChild(
          sv("rect", {
            class: "lblbg",
            x: mid - tw / 2 - 4,
            y: top - 14,
            width: tw + 8,
            height: r.lines.length * 16 + 2,
            rx: 3,
          }),
        );
        g.appendChild(textLines(mid, top, r.lines, "", "middle"));
        g.appendChild(numBadge(Math.min(r.x1, r.x2) + 16, yA - 14, r.i));
      }
      svg.appendChild(g);
    });
    return { svg: svg, count: rows.length, captions: spec.steps.map((s) => s.note || s.label) };
  }

  // Box-and-arrow graph: {nodes:[{id,label,sub,col,row,step}], edges:[{from,to,label,step,dashed}], captions:[...]}
  function renderGraph(spec) {
    const colW = spec.colWidth || 290,
      rowH = spec.rowHeight || 150,
      pad = 36,
      nw = spec.nodeWidth || 170;
    let maxC = 0,
      maxR = 0,
      pos = {};
    spec.nodes.forEach((n) => {
      maxC = Math.max(maxC, n.col || 0);
      maxR = Math.max(maxR, n.row || 0);
    });
    const W = pad * 2 + colW * (maxC + 1),
      H = pad + maxR * rowH + 30 + 31 + pad;
    const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": spec.title || "Diagram" });
    spec.nodes.forEach((n) => {
      const nh = n.sub ? 62 : 48;
      pos[n.id] = { x: pad + (n.col || 0) * colW + colW / 2, y: pad + (n.row || 0) * rowH + 30, w: nw, h: nh };
    });
    function clip(p, q) {
      // point on border of rect p toward q
      const dx = q.x - p.x,
        dy = q.y - p.y,
        hw = p.w / 2 + 4,
        hh = p.h / 2 + 4;
      const s = Math.min(hw / Math.abs(dx || 1e-6), hh / Math.abs(dy || 1e-6));
      return { x: p.x + dx * s, y: p.y + dy * s };
    }
    const pairs = {};
    spec.edges.forEach((e) => {
      pairs[`${e.from}>${e.to}`] = true;
    });
    const edgeLayer = sv("g"),
      nodeLayer = sv("g"),
      labelLayer = sv("g");
    spec.edges.forEach((e, _i) => {
      const a = pos[e.from],
        b = pos[e.to];
      if (!a || !b) {
        console.error("[teach-site] edge to unknown node", e);
        return;
      }
      const paired = pairs[`${e.to}>${e.from}`],
        off = paired ? 9 : 0;
      const ang = Math.atan2(b.y - a.y, b.x - a.x),
        nx = -Math.sin(ang),
        ny = Math.cos(ang),
        ox = nx * off,
        oy = ny * off;
      const A = { x: a.x + ox, y: a.y + oy, w: a.w, h: a.h },
        B = { x: b.x + ox, y: b.y + oy, w: b.w, h: b.h };
      const p1 = clip(A, B),
        p2 = clip(B, A);
      const attrs = { class: `edge${e.dashed ? " dashed" : ""}` };
      if (e.step) attrs["data-s"] = e.step;
      const g = sv("g", attrs);
      const ex = p2.x - Math.cos(ang) * 8,
        ey = p2.y - Math.sin(ang) * 8;
      g.appendChild(sv("path", { d: `M${p1.x} ${p1.y} L${ex} ${ey}` }));
      g.appendChild(arrowHead(p2.x, p2.y, ang));
      edgeLayer.appendChild(g);
      if (e.label) {
        const lines = wrap(e.label, 20),
          tw = Math.max.apply(
            null,
            lines.map((l) => textW(l)),
          );
        const lh = lines.length * 16 + 4;
        // push the label off the line: along the normal, far enough to clear it (both sides get used by paired edges)
        const len = Math.hypot(p2.x - p1.x, p2.y - p1.y);
        const clear = 10 + (Math.abs(nx) * tw) / 2 + (Math.abs(ny) * lh) / 2; // distance that moves the label off the line
        const push = paired ? clear + 2 : len < tw + 60 ? clear : 0;
        const mx = (p1.x + p2.x) / 2 + nx * push,
          my = (p1.y + p2.y) / 2 + ny * push;
        const lg = sv("g", e.step ? { "data-s": e.step, class: "edge-label" } : { class: "edge-label" });
        lg.appendChild(
          sv("rect", { class: "lblbg", x: mx - tw / 2 - 4, y: my - lh / 2, width: tw + 8, height: lh, rx: 3 }),
        );
        const t = textLines(mx, my - lh / 2 + 15, lines, "", "middle");
        // CSSOM, not a style attribute, so the page's Content-Security-Policy (style-src 'self') allows it.
        t.style.fontSize = "13px";
        t.style.fill = "var(--ink)";
        lg.appendChild(t);
        labelLayer.appendChild(lg);
      }
    });
    spec.nodes.forEach((n) => {
      const p = pos[n.id],
        attrs = { class: "node" };
      if (n.step) attrs["data-s"] = n.step;
      const g = sv("g", attrs, [sv("rect", { x: p.x - p.w / 2, y: p.y - p.h / 2, width: p.w, height: p.h, rx: 10 })]);
      g.appendChild(textLines(p.x, p.y + (n.sub ? -4 : 5), wrap(n.label, 20).slice(0, 2), "", "middle"));
      if (n.sub) g.appendChild(sv("text", { class: "sub", x: p.x, y: p.y + 16, "text-anchor": "middle", text: n.sub }));
      nodeLayer.appendChild(g);
    });
    svg.appendChild(edgeLayer);
    svg.appendChild(nodeLayer);
    svg.appendChild(labelLayer);
    svg.style.maxWidth = `${Math.round(W * 1.15)}px`;
    let count = 0;
    spec.nodes.concat(spec.edges).forEach((x) => {
      count = Math.max(count, x.step || 0);
    });
    return { svg: svg, count: count, captions: spec.captions || [] };
  }

  function stepper(fig, svg, count, captions) {
    if (!count) return;
    fig.classList.add("is-stepping");
    let cur = 1,
      timer = null;
    const cap = el("div", { class: "ts-fig-caption", "aria-live": "polite" });
    const cnt = el("span", { class: "ts-fig-count" });
    const play = el("button", { type: "button", "aria-label": "Play all steps", text: "Play" });
    function show(n) {
      cur = Math.max(1, Math.min(count, n));
      $$("[data-s]", svg).forEach((g) => {
        const s = +g.getAttribute("data-s");
        g.classList.toggle("is-future", s > cur);
        g.classList.toggle("is-past", s < cur);
        g.classList.toggle("is-now", s === cur);
      });
      $$(".ts-packet", svg).forEach((x) => {
        x.remove();
      });
      if (!reduceMotion)
        $$("[data-s].is-now", svg).forEach((g) => {
          let ln = $("line", g),
            pth = $("path", g),
            c;
          if (ln) {
            c = sv("circle", { class: "ts-packet", r: 5, cy: ln.getAttribute("y1") });
            c.appendChild(
              sv("animate", {
                attributeName: "cx",
                from: ln.getAttribute("x1"),
                to: ln.getAttribute("x2"),
                dur: "1.4s",
                repeatCount: "indefinite",
              }),
            );
            g.appendChild(c);
          } else if (pth && (g.classList.contains("edge") || g.classList.contains("msg"))) {
            c = sv("circle", { class: "ts-packet", r: 5 });
            c.appendChild(sv("animateMotion", { path: pth.getAttribute("d"), dur: "1.4s", repeatCount: "indefinite" }));
            g.appendChild(c);
          }
        });
      cnt.textContent = `Step ${cur} of ${count}`;
      cap.innerHTML = `<b>${cur}.</b> ${captions[cur - 1] ? esc(captions[cur - 1]) : ""}`;
    }
    function stop() {
      clearInterval(timer);
      timer = null;
      play.textContent = "Play";
    }
    play.addEventListener("click", () => {
      if (timer) return stop();
      if (cur >= count) show(1);
      play.textContent = "Pause";
      timer = setInterval(() => {
        if (cur >= count) return stop();
        show(cur + 1);
      }, 2600);
    });
    const ctl = el("div", { class: "ts-fig-ctl" }, [
      el("button", {
        type: "button",
        "aria-label": "Previous step",
        text: "←",
        onclick: () => {
          stop();
          show(cur - 1);
        },
      }),
      el("button", {
        type: "button",
        "aria-label": "Next step",
        text: "→",
        onclick: () => {
          stop();
          show(cur + 1);
        },
      }),
      play,
      el("button", {
        type: "button",
        text: "Show all",
        onclick: () => {
          stop();
          show(count);
          $$("[data-s]", svg).forEach((g) => {
            g.classList.remove("is-past");
          });
        },
      }),
      cnt,
    ]);
    fig.appendChild(ctl);
    fig.appendChild(cap);
    fig.setAttribute("tabindex", "0");
    fig.addEventListener("keydown", (e) => {
      if (e.key === "ArrowRight") {
        e.preventDefault();
        stop();
        show(cur + 1);
      }
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        stop();
        show(cur - 1);
      }
    });
    show(1);
  }

  function initFigures() {
    $$(".ts-seq, .ts-graph, .ts-svg").forEach((fig) => {
      fig.classList.add("ts-fig");
      const spec = readJSON($("script[type='application/json']", fig));
      const title = fig.getAttribute("data-title");
      let out;
      try {
        if (fig.classList.contains("ts-seq")) out = renderSeq(spec);
        else if (fig.classList.contains("ts-graph")) out = renderGraph(spec);
        else {
          const s = $("svg", fig);
          const caps = $$("ol.ts-captions li", fig).map((li) => li.textContent);
          const ol = $("ol.ts-captions", fig);
          if (ol) ol.remove();
          let c = 0;
          $$("[data-s]", s).forEach((g) => {
            c = Math.max(c, +g.getAttribute("data-s"));
          });
          out = { svg: s, count: c, captions: caps };
        }
      } catch (e) {
        console.error("[teach-site] diagram failed", e);
        fig.appendChild(el("p", { text: "Diagram failed to render." }));
        return;
      }
      const canvas = el("div", { class: "ts-fig-canvas" }, [out.svg]);
      fig.innerHTML = "";
      if (title) fig.appendChild(el("p", { class: "ts-fig-title", text: title }));
      fig.appendChild(canvas);
      if (fig.hasAttribute("data-small")) fig.classList.add("is-small");
      stepper(fig, out.svg, out.count, out.captions);
    });
  }

  /* =====================================================================
     ROOFLINE CALCULATOR (.ts-roofline): dense model, weights-only roofline.
     Spec JSON: {"gpus":[{"id","label","tflops","tbps","gb"}], "defaults":{"gpu","params","batch","prompt"}}
     tflops = dense peak (TFLOP/s), tbps = memory bandwidth (TB/s), gb = memory (GB).
     ===================================================================== */
  function fmtNum(x, unit) {
    if (!Number.isFinite(x)) return "–";
    const a = Math.abs(x);
    const s = a >= 100 ? Math.round(x).toLocaleString("en-US") : a >= 10 ? x.toFixed(1) : x.toPrecision(2);
    return unit ? `${s} ${unit}` : s;
  }
  function fmtInt(x) {
    return Math.round(x).toLocaleString("en-US");
  }
  function fmtTime(sec) {
    if (sec >= 1) return fmtNum(sec, "s");
    if (sec >= 1e-3) return fmtNum(sec * 1e3, "ms");
    return fmtNum(sec * 1e6, "µs");
  }
  function initRoofline(box, n) {
    const spec = readJSON($("script[type='application/json']", box));
    if (!spec?.gpus?.length) return;
    const d = spec.defaults || {};
    const id = (k) => `ts-rl-${n}-${k}`;
    const title = box.getAttribute("data-title");
    box.classList.add("ts-fig");
    box.innerHTML = "";
    if (title) box.appendChild(el("p", { class: "ts-fig-title", text: title }));
    const gpuSel = el(
      "select",
      { id: id("gpu") },
      spec.gpus.map((g) => el("option", { value: g.id, text: g.label })),
    );
    gpuSel.value = d.gpu || spec.gpus[0].id;
    function num(key, label, val, min, max, step) {
      const inp = el("input", { id: id(key), type: "number", min, max, step, value: val, inputmode: "decimal" });
      return [inp, el("label", { class: "ts-rl-field", for: id(key) }, [el("span", { text: label }), inp])];
    }
    const [pIn, pLab] = num("params", "Model size (billions of parameters)", d.params || 8, 0.1, 2000, "any");
    const [bIn, bLab] = num("batch", "Requests decoded together (batch)", d.batch || 1, 1, 4096, 1);
    const [lIn, lLab] = num("prompt", "Prompt length (tokens)", d.prompt || 2000, 1, 1000000, 1);
    const gLab = el("label", { class: "ts-rl-field", for: id("gpu") }, [el("span", { text: "GPU" }), gpuSel]);
    box.appendChild(el("div", { class: "ts-rl-form" }, [gLab, pLab, bLab, lLab]));

    // log-log chart
    const W = 560,
      H = 300,
      L = 58,
      R = 16,
      T = 14,
      B = 46;
    const X0 = -1,
      X1 = 6,
      Y0 = -1,
      Y1 = 3.5; // log10 ranges: FLOPs/byte, TFLOP/s
    const xp = (i) => L + ((Math.log10(i) - X0) / (X1 - X0)) * (W - L - R);
    const yp = (t) => T + (1 - (Math.log10(t) - Y0) / (Y1 - Y0)) * (H - T - B);
    const clampX = (i) => Math.min(10 ** X1, Math.max(10 ** X0, i));
    const svg = sv("svg", {
      viewBox: `0 0 ${W} ${H}`,
      role: "img",
      class: "ts-rl-chart",
      "aria-label": "Roofline chart: reachable TFLOP/s against FLOPs per byte, log scales",
    });
    const axes = sv("g", { class: "ts-rl-axis" });
    for (let e = X0; e <= X1; e++) {
      const x = xp(10 ** e);
      axes.appendChild(sv("line", { class: "ts-rl-grid", x1: x, x2: x, y1: T, y2: H - B }));
      axes.appendChild(sv("text", { x, y: H - B + 16, "text-anchor": "middle", text: e < 0 ? "0.1" : `1e${e}` }));
    }
    for (let e = Y0; e <= Math.floor(Y1); e++) {
      const y = yp(10 ** e);
      axes.appendChild(sv("line", { class: "ts-rl-grid", x1: L, x2: W - R, y1: y, y2: y }));
      axes.appendChild(sv("text", { x: L - 6, y: y + 4, "text-anchor": "end", text: e < 0 ? "0.1" : String(10 ** e) }));
    }
    axes.appendChild(
      sv("text", { x: (L + W - R) / 2, y: H - 8, "text-anchor": "middle", text: "FLOPs per byte read (log)" }),
    );
    axes.appendChild(
      sv("text", {
        x: 14,
        y: (T + H - B) / 2,
        "text-anchor": "middle",
        transform: `rotate(-90 14 ${(T + H - B) / 2})`,
        text: "TFLOP/s reachable (log)",
      }),
    );
    svg.appendChild(axes);
    const roof = sv("path", { class: "ts-rl-roof" });
    const ridgeLn = sv("line", { class: "ts-rl-ridge" });
    const ridgeTx = sv("text", { class: "ts-rl-ridge-t" });
    svg.appendChild(roof);
    svg.appendChild(ridgeLn);
    svg.appendChild(ridgeTx);
    function point(cls, label) {
      const g = sv("g", { class: `ts-rl-pt ${cls}` });
      const c = sv("circle", { r: 7 });
      const t = sv("text", { "text-anchor": "middle", text: label });
      g.appendChild(c);
      g.appendChild(t);
      svg.appendChild(g);
      return { c, t };
    }
    const decPt = point("is-decode", "decode"),
      prePt = point("is-prefill", "prefill");
    box.appendChild(el("div", { class: "ts-fig-canvas" }, [svg]));
    const out = el("div", { class: "ts-rl-out", "aria-live": "polite" });
    box.appendChild(out);

    function row(k, v, cls) {
      return el("div", { class: `ts-rl-row${cls ? ` ${cls}` : ""}` }, [el("dt", { text: k }), el("dd", { text: v })]);
    }
    function update() {
      const g = spec.gpus.find((x) => x.id === gpuSel.value) || spec.gpus[0];
      const P = Math.max(0.1, +pIn.value || 0.1) * 1e9;
      const batch = Math.max(1, Math.round(+bIn.value || 1));
      const prompt = Math.max(1, Math.round(+lIn.value || 1));
      const F = g.tflops * 1e12,
        BW = g.tbps * 1e12;
      const weights = 2 * P; // BF16 bytes
      const ridge = F / BW;
      const pass = (tokens) => {
        const c = (2 * P * tokens) / F,
          m = weights / BW;
        return { t: Math.max(c, m), bound: c > m ? "compute" : "memory", used: c / Math.max(c, m) };
      };
      const dec = pass(batch),
        pre = pass(prompt * batch);
      // roof: memory slope up to the ridge, then flat at the peak
      const yAt = (i) => Math.min(g.tflops, g.tbps * i); // TB/s × FLOPs/byte = TFLOP/s
      const xr = clampX(ridge);
      roof.setAttribute(
        "d",
        `M${xp(10 ** X0)},${yp(Math.max(10 ** Y0, yAt(10 ** X0)))} L${xp(xr)},${yp(yAt(xr))} L${xp(10 ** X1)},${yp(g.tflops)}`,
      );
      ridgeLn.setAttribute("x1", xp(xr));
      ridgeLn.setAttribute("x2", xp(xr));
      ridgeLn.setAttribute("y1", yp(g.tflops));
      ridgeLn.setAttribute("y2", H - B);
      // label sits under the flat roof, beside the dashed ridge line
      const leftSide = xp(xr) > W - R - 170;
      ridgeTx.setAttribute("text-anchor", leftSide ? "end" : "start");
      ridgeTx.setAttribute("x", xp(xr) + (leftSide ? -6 : 6));
      ridgeTx.setAttribute("y", yp(g.tflops) + 40);
      ridgeTx.textContent = `ridge ≈ ${fmtInt(ridge)} FLOPs/byte`;
      function place(pt, intensity, above) {
        const i = clampX(intensity);
        const x = xp(i),
          y = yp(Math.max(10 ** Y0, yAt(i)));
        pt.c.setAttribute("cx", x);
        pt.c.setAttribute("cy", y);
        // decode label up-left of its point, prefill label below: both clear of the roof line
        pt.t.setAttribute("text-anchor", above ? "end" : "middle");
        pt.t.setAttribute("x", above ? Math.max(L + 50, x - 12) : Math.min(W - R - 26, Math.max(L + 26, x)));
        pt.t.setAttribute("y", above ? y - 14 : y + 22);
      }
      place(decPt, batch, true);
      place(prePt, prompt * batch, false);

      out.innerHTML = "";
      const fits = weights <= g.gb * 1e9;
      const dl = el("dl", { class: "ts-rl-list" }, [
        row(
          "Weights in BF16",
          `${fmtNum(weights / 1e9, "GB")} of ${fmtNum(g.gb, "GB")} ${fits ? "(fits)" : "(does not fit on one GPU)"}`,
          fits ? "" : "is-bad",
        ),
        row("Ridge point", `${fmtInt(ridge)} FLOPs per byte`),
        row(
          "Decode step",
          `${fmtInt(batch)} FLOPs/byte → ${dec.bound}-bound, ${fmtTime(dec.t)} per token, compute ${fmtNum(dec.used * 100)}% busy`,
          dec.bound === "memory" ? "is-mem" : "is-cmp",
        ),
        row("Decode throughput", `${fmtInt(batch / dec.t)} tokens/s across ${fmtInt(batch)} request(s)`),
        row(
          "Prefill",
          `${fmtInt(prompt * batch)} FLOPs/byte → ${pre.bound}-bound, ${fmtTime(pre.t)} for the prompt(s)`,
          pre.bound === "memory" ? "is-mem" : "is-cmp",
        ),
      ]);
      out.appendChild(dl);
      out.appendChild(
        el("p", {
          class: "ts-rl-note",
          text: "Best case: weights only, 100% of peak. Real servers reach less, and attention's own reads (Part 2) are left out.",
        }),
      );
    }
    [gpuSel, pIn, bIn, lIn].forEach((x) => {
      x.addEventListener("input", update);
      x.addEventListener("change", update);
    });
    update();
  }
  function initRooflines() {
    $$(".ts-roofline").forEach((b, i) => {
      try {
        initRoofline(b, i + 1);
      } catch (e) {
        console.error("[teach-site] roofline failed", e);
      }
    });
  }

  /* =====================================================================
     KV CACHE CALCULATOR (.ts-kvcalc): cache size, capacity, decode with KV reads.
     Spec JSON: {"models":[{"id","label","params","layers","q_heads","kv_heads","head_dim"}],
                 "gpus":[{"id","label","tflops","tbps","gb"}], "dtypes":[{"id","label","bytes"}],
                 "defaults":{"model","gpu","dtype","context","batch","util","reserve"}}
     params in billions, tflops dense peak, tbps TB/s, gb memory, reserve GB. Weights in BF16.
     Same model as examples/llm-serving-2/kv_cache.py.
     ===================================================================== */
  function fmtBytes(b) {
    const sig3 = (x) => Number(x.toPrecision(3)).toLocaleString("en-US");
    if (b < 1e6) return `${fmtInt(b)} bytes`;
    if (b < 1e9) return `${sig3(b / 1e6)} MB`;
    return `${sig3(b / 1e9)} GB`;
  }
  function initKvCalc(box, n) {
    const spec = readJSON($("script[type='application/json']", box));
    if (!spec?.models?.length || !spec?.gpus?.length) return;
    const d = spec.defaults || {};
    const dtypes = spec.dtypes?.length ? spec.dtypes : [{ id: "bf16", label: "BF16 (2 bytes)", bytes: 2 }];
    const id = (k) => `ts-kv-${n}-${k}`;
    const title = box.getAttribute("data-title");
    box.classList.add("ts-fig");
    box.innerHTML = "";
    if (title) box.appendChild(el("p", { class: "ts-fig-title", text: title }));
    function sel(key, label, items, val) {
      const s = el(
        "select",
        { id: id(key) },
        items.map((x) => el("option", { value: x.id, text: x.label })),
      );
      s.value = val;
      return [s, el("label", { class: "ts-rl-field", for: id(key) }, [el("span", { text: label }), s])];
    }
    function num(key, label, val, min, max, step) {
      const inp = el("input", { id: id(key), type: "number", min, max, step, value: val, inputmode: "decimal" });
      return [inp, el("label", { class: "ts-rl-field", for: id(key) }, [el("span", { text: label }), inp])];
    }
    const custom = { id: "custom", label: "Custom" };
    const m0 = spec.models.find((m) => m.id === d.model) || spec.models[0];
    const [mSel, mLab] = sel("model", "Model", spec.models.concat([custom]), m0.id);
    const [pIn, pLab] = num("params", "Parameters (billions)", m0.params, 0.1, 2000, "any");
    const [lyIn, lyLab] = num("layers", "Layers", m0.layers, 1, 512, 1);
    const [qIn, qLab] = num("qheads", "Query heads", m0.q_heads, 1, 1024, 1);
    const [kIn, kLab] = num("kvheads", "Key/value heads", m0.kv_heads, 1, 1024, 1);
    const [hIn, hLab] = num("headdim", "Head dimension", m0.head_dim, 1, 1024, 1);
    const [gSel, gLab] = sel("gpu", "GPU", spec.gpus, d.gpu || spec.gpus[0].id);
    const [tSel, tLab] = sel("dtype", "KV cache data type", dtypes, d.dtype || dtypes[0].id);
    const [cIn, cLab] = num("context", "Tokens per request (context)", d.context || 8192, 1, 2000000, 1);
    const [bIn, bLab] = num("batch", "Requests decoding together", d.batch || 64, 1, 100000, 1);
    const [uIn, uLab] = num("util", "gpu_memory_utilization", d.util || 0.92, 0.05, 1, 0.01);
    const [rIn, rLab] = num("reserve", "Other reserved memory (GB)", d.reserve ?? 3, 0, 1000, "any");
    box.appendChild(
      el("div", { class: "ts-rl-form" }, [mLab, pLab, lyLab, qLab, kLab, hLab, gLab, tLab, cLab, bLab, uLab, rLab]),
    );
    const shapeIns = [pIn, lyIn, qIn, kIn, hIn];
    mSel.addEventListener("change", () => {
      const m = spec.models.find((x) => x.id === mSel.value);
      if (m) {
        pIn.value = m.params;
        lyIn.value = m.layers;
        qIn.value = m.q_heads;
        kIn.value = m.kv_heads;
        hIn.value = m.head_dim;
      }
      update();
    });
    shapeIns.forEach((x) => {
      x.addEventListener("input", () => {
        mSel.value = "custom";
      });
    });

    // memory bar: one GPU's memory, split into weights, reserve, KV in use, KV free, unrequested
    const W = 560,
      BH = 30;
    const svg = sv("svg", {
      viewBox: `0 0 ${W} ${BH + 4}`,
      role: "img",
      class: "ts-kv-chart",
      "aria-label":
        "How one GPU's memory splits into weights, reserve, KV cache in use, free KV cache, and memory vLLM leaves unrequested",
    });
    const segDefs = [
      ["w", "Weights"],
      ["r", "Other reserved"],
      ["u", "KV cache in use"],
      ["f", "KV cache free"],
      ["x", "Not requested (1 − utilization)"],
    ];
    const segs = {};
    segDefs.forEach(([k]) => {
      segs[k] = sv("rect", { class: `ts-kv-seg is-${k}`, y: 2, height: BH });
      svg.appendChild(segs[k]);
    });
    svg.appendChild(sv("rect", { class: "ts-kv-frame", x: 1, y: 2, width: W - 2, height: BH }));
    box.appendChild(el("div", { class: "ts-fig-canvas" }, [svg]));
    box.appendChild(
      el(
        "ul",
        { class: "ts-kv-legend" },
        segDefs.map(([k, t]) => el("li", {}, [el("span", { class: `ts-kv-sw is-${k}` }), el("span", { text: t })])),
      ),
    );
    const out = el("div", { class: "ts-rl-out", "aria-live": "polite" });
    box.appendChild(out);
    function row(k, v, cls) {
      return el("div", { class: `ts-rl-row${cls ? ` ${cls}` : ""}` }, [el("dt", { text: k }), el("dd", { text: v })]);
    }
    const pos = (inp, lo, def) => Math.max(lo, +inp.value || def);

    function update() {
      const g = spec.gpus.find((x) => x.id === gSel.value) || spec.gpus[0];
      const dt = dtypes.find((x) => x.id === tSel.value) || dtypes[0];
      const P = pos(pIn, 0.1, 8) * 1e9;
      const L = Math.round(pos(lyIn, 1, 32)),
        Hq = Math.round(pos(qIn, 1, 32)),
        Hkv = Math.min(Hq, Math.round(pos(kIn, 1, 8))),
        hd = Math.round(pos(hIn, 1, 128));
      const ctx = Math.round(pos(cIn, 1, 8192)),
        batch = Math.round(pos(bIn, 1, 64));
      const util = Math.min(1, pos(uIn, 0.01, 0.92)),
        reserve = Math.max(0, +rIn.value || 0) * 1e9;
      const F = g.tflops * 1e12,
        BW = g.tbps * 1e12,
        mem = g.gb * 1e9,
        ridge = F / BW;
      const perTok = 2 * L * Hkv * hd * dt.bytes;
      const perReq = perTok * ctx;
      const weights = 2 * P;
      const budget = mem * util - weights - reserve;
      const fit = budget > 0 ? Math.floor(budget / perReq) : 0;
      const attnF = 4 * L * Hq * hd * ctx; // FLOPs per request per step for attention over the cache
      const flops = batch * (2 * P + attnF);
      const bytes = weights + batch * perReq;
      const cS = flops / F,
        mS = bytes / BW,
        t = Math.max(cS, mS);
      const bound = cS > mS ? "compute" : "memory";
      const perReqF = 2 * P + attnF;
      const cross = perReqF > ridge * perReq ? Math.ceil((ridge * weights) / (perReqF - ridge * perReq)) : null;

      // bar
      const sc = (b) => (Math.max(0, b) / mem) * (W - 2);
      const used = Math.min(Math.max(0, budget), batch * perReq);
      const parts = {
        w: Math.min(weights, mem),
        r: Math.min(reserve, Math.max(0, mem - weights)),
        u: used,
        f: Math.max(0, budget) - used,
        x: mem * (1 - util),
      };
      let x = 1;
      segDefs.forEach(([k]) => {
        const w = Math.min(sc(parts[k]), W - 1 - x);
        segs[k].setAttribute("x", x);
        segs[k].setAttribute("width", Math.max(0, w));
        x += Math.max(0, w);
      });

      out.innerHTML = "";
      const rows = [
        row("KV per token", `2 × ${L} layers × ${Hkv} KV heads × ${hd} × ${dt.bytes} bytes = ${fmtInt(perTok)} bytes`),
        row("KV per request", `${fmtInt(ctx)} tokens → ${fmtBytes(perReq)}`),
      ];
      if (budget <= 0) {
        rows.push(
          row(
            "KV budget",
            `${fmtNum(util, "")} × ${fmtBytes(g.gb * 1e9)} − ${fmtBytes(weights)} weights − ${fmtBytes(reserve)} reserve: nothing left. The weights do not fit on one GPU at this setting.`,
            "is-bad",
          ),
        );
      } else {
        rows.push(
          row(
            "KV budget",
            `${fmtNum(util, "")} × ${fmtBytes(g.gb * 1e9)} − ${fmtBytes(weights)} weights − ${fmtBytes(reserve)} reserve = ${fmtBytes(budget)}`,
          ),
          row(
            "Requests that fit",
            `${fmtInt(budget / perTok)} tokens of cache → ${fmtInt(fit)} request(s) of ${fmtInt(ctx)} tokens`,
            fit < 1 ? "is-bad" : "",
          ),
        );
        rows.push(
          row(
            "Decode step",
            `${fmtInt(batch)} request(s): reads ${fmtBytes(weights)} weights + ${fmtBytes(batch * perReq)} KV (${fmtNum((100 * batch * perReq) / bytes)}% KV) → ${fmtNum(flops / bytes)} FLOPs/byte, ${bound}-bound, ${fmtTime(t)} per step, ${fmtInt(batch / t)} tokens/s`,
            bound === "memory" ? "is-mem" : "is-cmp",
          ),
        );
        if (batch > fit)
          rows.push(row("Warning", `Only ${fmtInt(fit)} request(s) of this length fit in the cache budget.`, "is-bad"));
      }
      rows.push(
        row(
          "Compute-bound from",
          cross === null
            ? `never at ${fmtInt(ctx)} tokens: each request adds KV reads as fast as it adds work (weights only, Part 1: about ${fmtInt(Math.ceil(ridge))})`
            : `a batch of ${fmtInt(cross)} (weights only, Part 1: about ${fmtInt(Math.ceil(ridge))})`,
        ),
      );
      out.appendChild(el("dl", { class: "ts-rl-list" }, rows));
      out.appendChild(
        el("p", {
          class: "ts-rl-note",
          text: "Best case at 100% of peak. Weights in BF16 (2 bytes per parameter). vLLM measures the reserve at startup; 3 GB is a stand-in.",
        }),
      );
    }
    [gSel, tSel, cIn, bIn, uIn, rIn].concat(shapeIns).forEach((inp) => {
      inp.addEventListener("input", update);
      inp.addEventListener("change", update);
    });
    update();
  }
  function initKvCalcs() {
    $$(".ts-kvcalc").forEach((b, i) => {
      try {
        initKvCalc(b, i + 1);
      } catch (e) {
        console.error("[teach-site] kv calculator failed", e);
      }
    });
  }

  /* =====================================================================
     CODE + TABS
     ===================================================================== */
  const KW =
    /\b(def|return|import|from|as|if|else|elif|for|in|while|class|const|let|var|function|async|await|try|except|catch|finally|throw|raise|new|with|yield|None|True|False|null|true|false|export|default)\b/;
  function highlight(src, lang) {
    if (!/^(python|py|js|javascript|ts|typescript|bash|sh|shell)$/.test(lang || "")) return esc(src);
    const re = /(#[^\n]*|\/\/[^\n]*)|("(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'|`(?:[^`\\]|\\.)*`)|(\b[A-Za-z_]\w*\b)/g;
    let out = "",
      last = 0,
      m;
    const hashComments = /^(python|py|bash|sh|shell)$/.test(lang);
    for (m = re.exec(src); m !== null; m = re.exec(src)) {
      out += esc(src.slice(last, m.index));
      last = re.lastIndex;
      if (m[1]) {
        const isHash = m[1][0] === "#";
        if (isHash !== hashComments) {
          out += esc(m[1].slice(0, 1));
          re.lastIndex = m.index + 1;
          last = re.lastIndex;
          continue;
        }
        out += `<span class="c">${esc(m[1])}</span>`;
      } else if (m[2]) out += `<span class="s">${esc(m[2])}</span>`;
      else if (KW.test(m[3]) && m[3].match(KW)[0] === m[3]) out += `<span class="k">${esc(m[3])}</span>`;
      else out += esc(m[3]);
    }
    return out + esc(src.slice(last));
  }
  // Scrollable regions must be reachable by keyboard (WCAG 2.1.1).
  function makeScrollRegionsFocusable() {
    $$(".ts-code pre, .ts-fig-canvas, .ts-table-wrap").forEach((n) => {
      n.setAttribute("tabindex", "0");
      if (!n.hasAttribute("aria-label")) n.setAttribute("aria-label", "Scrollable content");
    });
  }
  function initCode() {
    $$(".ts-code").forEach((box) => {
      const pre = $("pre", box),
        code = $("code", pre) || pre,
        lang = box.getAttribute("data-lang") || "";
      const raw = code.textContent.replace(/^\n+|\s+$/g, "");
      code.innerHTML = highlight(raw, lang);
      const right = el("span", {}, [
        box.getAttribute("data-verified") === "ran"
          ? el("span", { class: "ts-verified-code", text: "Ran and checked  " })
          : null,
        el("button", {
          type: "button",
          class: "ts-copy",
          text: "Copy",
          onclick: () => {
            copyText(raw, "Code copied.");
          },
        }),
      ]);
      box.insertBefore(
        el("div", { class: "ts-code-bar" }, [el("span", { text: box.getAttribute("data-title") || lang }), right]),
        pre,
      );
    });
  }
  function initTabs() {
    $$(".ts-tabs").forEach((box, bi) => {
      const panels = $$(":scope > [data-tab]", box);
      const list = el("div", { class: "ts-tablist", role: "tablist" });
      panels.forEach((p, i) => {
        const id = `tsp-${bi}-${i}`;
        p.id = id;
        p.setAttribute("role", "tabpanel");
        if (i) p.hidden = true;
        const b = el("button", {
          type: "button",
          role: "tab",
          "aria-controls": id,
          "aria-selected": i ? "false" : "true",
          text: p.getAttribute("data-tab"),
        });
        b.addEventListener("click", () => {
          $$("button", list).forEach((x) => {
            x.setAttribute("aria-selected", "false");
          });
          panels.forEach((x) => {
            x.hidden = true;
          });
          b.setAttribute("aria-selected", "true");
          p.hidden = false;
        });
        list.appendChild(b);
      });
      box.insertBefore(list, box.firstChild);
    });
  }

  /* =====================================================================
     TERMS, CALLOUTS, CITATIONS
     ===================================================================== */
  function initTerms() {
    let tip = null;
    function show(d) {
      hide();
      tip = el("div", { class: "ts-tip", role: "tooltip", text: d.getAttribute("data-def") });
      document.body.appendChild(tip);
      const r = d.getBoundingClientRect(),
        tw = tip.offsetWidth;
      const left = Math.min(Math.max(8, r.left + scrollX), scrollX + innerWidth - tw - 8);
      tip.style.left = `${left}px`;
      tip.style.top = `${r.bottom + scrollY + 8}px`;
    }
    function hide() {
      if (tip) {
        tip.remove();
        tip = null;
      }
    }
    $$("dfn[data-def]").forEach((d) => {
      d.setAttribute("tabindex", "0");
      d.addEventListener("mouseenter", () => {
        show(d);
      });
      d.addEventListener("mouseleave", hide);
      d.addEventListener("focus", () => {
        show(d);
      });
      d.addEventListener("blur", hide);
      d.addEventListener("click", (e) => {
        e.stopPropagation();
        tip ? hide() : show(d);
      });
    });
    document.addEventListener("click", hide);
    addEventListener("scroll", hide, { passive: true });
  }
  const CALLOUTS = {
    "ts-takeaway": "Takeaway",
    "ts-legacy": "Legacy: you will meet this, don't build it new",
    "ts-trap": "Production trap",
    "ts-interview": "Senior interview lens",
    "ts-case": "In the wild",
    "ts-note": "Note",
  };
  function initCallouts() {
    Object.keys(CALLOUTS).forEach((c) => {
      $$(`.${c}`).forEach((b) => {
        if ($(".ts-callout-label", b)) return;
        b.insertBefore(
          el("span", { class: "ts-callout-label", text: b.getAttribute("data-label") || CALLOUTS[c] }),
          b.firstChild,
        );
      });
    });
  }
  function initCitations(ledger) {
    const sources = ledger?.sources || [],
      byId = {},
      order = [];
    sources.forEach((s) => {
      byId[s.id] = s;
    });
    $$("[data-src]").forEach((node) => {
      node
        .getAttribute("data-src")
        .split(/\s+/)
        .filter(Boolean)
        .forEach((id) => {
          if (!byId[id]) {
            console.error("[teach-site] unknown source", id);
            return;
          }
          if (order.indexOf(id) < 0) order.push(id);
          const n = order.indexOf(id) + 1;
          node.insertAdjacentElement(
            "afterend",
            el("a", { class: "ts-cite", href: `#src-${id}`, title: byId[id].title, text: String(n) }),
          );
        });
    });
    const box = $("#ts-sources");
    if (!box) return;
    const list = el("ol");
    sources
      .slice()
      .sort((a, b) => {
        const ia = order.indexOf(a.id),
          ib = order.indexOf(b.id);
        return (ia < 0 ? 999 : ia) - (ib < 0 ? 999 : ib);
      })
      .forEach((s) => {
        const li = el("li", { id: `src-${s.id}` });
        li.appendChild(el("a", { href: s.url, target: "_blank", rel: "noopener", text: s.title }));
        if (s.locator) li.appendChild(document.createTextNode(`, ${s.locator}`));
        li.appendChild(
          el("span", {
            class: `ts-src-kind${s.kind === "primary" ? " primary" : ""}`,
            text: s.kind === "primary" ? "Official" : s.kind || "Secondary",
          }),
        );
        if (s.accessed) li.appendChild(el("span", { class: "ts-src-kind", text: `Checked ${s.accessed}` }));
        list.appendChild(li);
      });
    box.appendChild(list);
    const claims = ledger?.claims || [];
    if (claims.length) {
      const ok = claims.filter((c) => c.status === "verified").length,
        cut = (ledger.cut || []).length;
      const det = el("details", { class: "ts-audit" }, [
        el("summary", {
          text: `How this page was checked: ${ok} facts confirmed twice against sources${ledger.strict ? " and audited by an independent reviewer" : ""}${cut ? `, ${cut} left out` : ""}`,
        }),
      ]);
      det.appendChild(
        el("p", {
          text: "Each fact was read in its source while researching, then re-checked in a separate fetch before it went on the page. Facts that could not be confirmed were left out.",
        }),
      );
      const tb = el("table");
      tb.appendChild(el("tr", {}, [el("th", { text: "Fact" }), el("th", { text: "Sources" })]));
      claims.forEach((c) => {
        tb.appendChild(
          el("tr", {}, [
            el("td", { text: c.text }),
            el("td", { text: (c.sources || []).map((id) => (byId[id] ? byId[id].title : id)).join("; ") }),
          ]),
        );
      });
      det.appendChild(tb);
      if (cut) {
        det.appendChild(el("p", { html: "<b>Left out (could not confirm):</b>" }));
        det.appendChild(
          el(
            "ul",
            {},
            (ledger.cut || []).map((c) => el("li", { text: c.text + (c.reason ? ` (${c.reason})` : "") })),
          ),
        );
      }
      box.appendChild(det);
    }
  }

  /* =====================================================================
     CHECKS
     ===================================================================== */
  const checkHooks = [];
  function checkLabel(txt) {
    return el("span", { class: "ts-check-label", text: txt });
  }
  function onCheckDone(root, firstTry) {
    checkHooks.forEach((f) => {
      f(root, firstTry);
    });
  }

  function initQuiz(q) {
    q.classList.add("ts-check");
    const ans = q.getAttribute("data-answer"),
      items = $$("ol > li", q),
      whyRight = $(".ts-why", q);
    if (whyRight) whyRight.remove();
    const ol = $("ol", q),
      opts = el("ol", { class: "ts-opts" }),
      fb = el("div", { class: "ts-feedback ts-hidden", "aria-live": "polite" });
    let tries = 0,
      finished = false;
    items.forEach((li, i) => {
      const key = li.getAttribute("data-key") || String.fromCharCode(97 + i);
      const b = el("button", { type: "button" }, [
        el("span", { class: "key", text: key.toUpperCase() }),
        el("span", { html: li.innerHTML }),
      ]);
      b.addEventListener("click", () => {
        if (finished) return;
        tries++;
        if (key === ans) {
          finished = true;
          b.classList.add("is-right");
          disableAll();
          fb.innerHTML = `<b class="ok">${tries === 1 ? "Right." : "Right, on the second try."}</b> ${whyRight ? whyRight.innerHTML : ""}`;
          onCheckDone(q, tries === 1);
        } else {
          b.classList.add("is-wrong");
          b.disabled = true;
          const why = li.getAttribute("data-why") || "";
          if (tries >= 2) {
            finished = true;
            disableAll();
            const right = $$("button", opts)[
              items.findIndex((x, j) => (x.getAttribute("data-key") || String.fromCharCode(97 + j)) === ans)
            ];
            if (right) right.classList.add("is-right");
            fb.innerHTML = `<b class="bad">Not this one.</b> ${esc(why)}<br><b>Answer: ${ans.toUpperCase()}.</b> ${whyRight ? whyRight.innerHTML : ""}`;
            onCheckDone(q, false);
          } else {
            fb.innerHTML = `<b class="bad">Not this one.</b> ${esc(why)} Try once more.`;
          }
        }
        fb.classList.remove("ts-hidden");
      });
      opts.appendChild(el("li", {}, [b]));
    });
    function disableAll() {
      $$("button", opts).forEach((x) => {
        x.disabled = true;
      });
    }
    ol.replaceWith(opts);
    q.appendChild(fb);
    q.insertBefore(checkLabel("Quick check"), q.firstChild);
    q._reset = () => {
      tries = 0;
      finished = false;
      $$("button", opts).forEach((x) => {
        x.disabled = false;
        x.classList.remove("is-right", "is-wrong");
      });
      fb.classList.add("ts-hidden");
    };
  }

  function shuffled(arr) {
    let a = arr.slice(),
      same = true,
      guard = 0;
    while (same && guard++ < 20) {
      for (let i = a.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        const t = a[i];
        a[i] = a[j];
        a[j] = t;
      }
      same = a.every((x, i) => x === arr[i]);
    }
    return a;
  }
  function initOrder(q) {
    q.classList.add("ts-check");
    const items = $$("ol > li", q).map((li, i) => ({ html: li.innerHTML, i: i }));
    const why = $(".ts-why", q);
    if (why) why.remove();
    let list = el("ol", { class: "ts-order-list" }),
      picked = [],
      fb = el("div", { class: "ts-feedback ts-hidden", "aria-live": "polite" });
    const check = el("button", { type: "button", class: "ts-btn", text: "Check order", disabled: "" });
    const again = el("button", { type: "button", class: "ts-btn ghost ts-hidden", text: "Try again" });
    const reveal = el("button", { type: "button", class: "ts-btn ghost ts-hidden", text: "Show correct order" });
    let attempts = 0,
      btns = [];
    function paint() {
      btns.forEach((b) => {
        const p = picked.indexOf(b._i);
        b.classList.toggle("is-picked", p >= 0);
        $(".slot", b).textContent = p >= 0 ? String(p + 1) : "";
      });
      if (picked.length === items.length) check.removeAttribute("disabled");
      else check.setAttribute("disabled", "");
    }
    function build() {
      list.innerHTML = "";
      btns = [];
      shuffled(items).forEach((it) => {
        const b = el("button", { type: "button" }, [el("span", { class: "slot" }), el("span", { html: it.html })]);
        b._i = it.i;
        b.setAttribute("data-i", String(it.i));
        b.addEventListener("click", () => {
          if (b.classList.contains("is-right") || b.classList.contains("is-wrong")) return;
          const p = picked.indexOf(it.i);
          if (p >= 0) picked = picked.slice(0, p);
          else picked.push(it.i);
          paint();
        });
        btns.push(b);
        list.appendChild(el("li", {}, [b]));
      });
      picked = [];
      paint();
    }
    check.addEventListener("click", () => {
      attempts++;
      let allRight = true;
      btns.forEach((b) => {
        const ok = picked.indexOf(b._i) === b._i;
        allRight = allRight && ok;
        b.classList.add(ok ? "is-right" : "is-wrong");
      });
      check.setAttribute("disabled", "");
      fb.classList.remove("ts-hidden");
      if (allRight) {
        fb.innerHTML = `<b class="ok">Correct order.</b> ${why ? why.innerHTML : ""}`;
        onCheckDone(q, attempts === 1);
      } else {
        fb.innerHTML = '<b class="bad">Some steps are out of place.</b> Red ones moved.';
        again.classList.remove("ts-hidden");
        reveal.classList.remove("ts-hidden");
      }
    });
    again.addEventListener("click", () => {
      again.classList.add("ts-hidden");
      reveal.classList.add("ts-hidden");
      fb.classList.add("ts-hidden");
      build();
    });
    reveal.addEventListener("click", () => {
      list.innerHTML = "";
      items.forEach((it, i) => {
        list.appendChild(
          el("li", {}, [
            el("button", { type: "button", class: "is-right" }, [
              el("span", { class: "slot", text: String(i + 1) }),
              el("span", { html: it.html }),
            ]),
          ]),
        );
      });
      again.classList.add("ts-hidden");
      reveal.classList.add("ts-hidden");
      fb.innerHTML = `<b>Correct order shown.</b> ${why ? why.innerHTML : ""}`;
      onCheckDone(q, false);
    });
    $("ol", q).replaceWith(list);
    q.appendChild(el("div", { class: "ts-row" }, [check, again, reveal]));
    q.appendChild(fb);
    q.insertBefore(checkLabel("Put it in order: tap the steps in sequence"), q.firstChild);
    build();
    q._reset = () => {
      attempts = 0;
      fb.classList.add("ts-hidden");
      again.classList.add("ts-hidden");
      reveal.classList.add("ts-hidden");
      build();
    };
  }

  function initPredict(q) {
    q.classList.add("ts-check");
    const rev = $(".ts-reveal", q);
    rev.classList.add("ts-hidden");
    const ta = el("textarea", {
      "aria-label": "Your prediction",
      placeholder: "Your guess, in a few words. Committing first is what makes it stick.",
    });
    const go = el("button", { type: "button", class: "ts-btn", text: "Reveal", disabled: "" });
    const idk = el("button", { type: "button", class: "ts-btn ghost", text: "No idea, show me" });
    ta.addEventListener("input", () => {
      if (ta.value.trim()) go.removeAttribute("disabled");
      else go.setAttribute("disabled", "");
    });
    function show(guessed) {
      rev.classList.remove("ts-hidden");
      go.setAttribute("disabled", "");
      idk.setAttribute("disabled", "");
      onCheckDone(q, guessed);
    }
    go.addEventListener("click", () => {
      show(true);
    });
    idk.addEventListener("click", () => {
      show(false);
    });
    q.insertBefore(el("div", {}, [ta, el("div", { class: "ts-row" }, [go, idk])]), rev);
    q.insertBefore(checkLabel("Predict first"), q.firstChild);
    q._reset = () => {
      ta.value = "";
      rev.classList.add("ts-hidden");
      idk.removeAttribute("disabled");
    };
  }

  function initExplain(q, meta) {
    q.classList.add("ts-check");
    const model = $(".ts-model", q);
    model.classList.add("ts-hidden");
    const points = (q.getAttribute("data-points") || "")
      .split("|")
      .map((s) => s.trim())
      .filter(Boolean);
    const prompt = $(".q", q)?.textContent || "";
    const ta = el("textarea", {
      "aria-label": "Your explanation",
      placeholder: "Explain it like you would to a teammate. Plain words, 3 to 5 sentences.",
    });
    let timerEl = el("span", { class: "ts-timer" }),
      tId = null;
    const timerBtn = el("button", { type: "button", class: "ts-btn ghost", text: "2-minute timer" });
    timerBtn.addEventListener("click", () => {
      if (tId) {
        clearInterval(tId);
        tId = null;
        timerEl.textContent = "";
        timerBtn.textContent = "2-minute timer";
        return;
      }
      let left = 120;
      timerBtn.textContent = "Stop timer";
      tId = setInterval(() => {
        left--;
        timerEl.textContent = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
        if (left <= 0) {
          clearInterval(tId);
          tId = null;
          timerEl.textContent = "Time. Check yourself.";
          timerBtn.textContent = "2-minute timer";
        }
      }, 1000);
      timerEl.textContent = "2:00";
      ta.focus();
    });
    const checkBtn = el("button", { type: "button", class: "ts-btn", text: "Check myself" });
    const gradeBtn = el("button", { type: "button", class: "ts-btn ghost", text: "Get graded by Claude" });
    const score = el("p", { class: "ts-score ts-hidden" });
    const pts = el("ul", { class: "ts-points" });
    points.forEach((p) => {
      const cb = el("input", { type: "checkbox" });
      cb.addEventListener("change", upd);
      pts.appendChild(el("li", {}, [el("label", {}, [cb, el("span", { text: p })])]));
    });
    function upd() {
      const n = $$("input:checked", pts).length;
      score.textContent = `You covered ${n} of ${points.length} key points.${n === points.length ? " Solid." : n >= points.length - 1 ? " Close: reread the one you missed." : " Reread this part, then try again tomorrow."}`;
      score.classList.remove("ts-hidden");
    }
    checkBtn.addEventListener("click", () => {
      model.classList.remove("ts-hidden");
      if (!model.contains(pts) && points.length) {
        model.appendChild(el("p", { html: "<b>Tick the points your answer covered:</b>" }));
        model.appendChild(pts);
        model.appendChild(score);
      }
      onCheckDone(q, true);
    });
    gradeBtn.addEventListener("click", () => {
      if (!ta.value.trim()) {
        toast("Write your answer first.");
        ta.focus();
        return;
      }
      const part = q.closest(".ts-part"),
        h = part ? $("h2", part).textContent : "";
      const txt =
        "Grade my explain-back. Use the teach-back grading format (Score, Right, Gap, Why, Next) and pass mark 8/10. Be blunt and specific.\n\n" +
        "Topic: " +
        (meta?.title || document.title) +
        "\nPart: " +
        h +
        "\nQuestion: " +
        prompt.trim() +
        "\nRubric (key points):\n" +
        points.map((p) => `- ${p}`).join("\n") +
        "\nReference answer (for the grader): " +
        model.textContent.replace(/\s+/g, " ").trim().slice(0, 900) +
        "\n\nMy answer:\n" +
        ta.value.trim();
      copyText(txt, "Copied. Paste it into a Claude chat to get graded.");
    });
    q.insertBefore(el("div", {}, [ta, el("div", { class: "ts-row" }, [checkBtn, gradeBtn, timerBtn, timerEl])]), model);
    q.insertBefore(checkLabel("Explain it back"), q.firstChild);
    q._reset = () => {
      ta.value = "";
      model.classList.add("ts-hidden");
      $$("input", pts).forEach((c) => {
        c.checked = false;
      });
      score.classList.add("ts-hidden");
    };
  }

  /* =====================================================================
     TOPIC PAGE SHELL
     ===================================================================== */
  function initTopic() {
    const meta = readJSON("ts-meta") || {},
      ledger = readJSON("ts-ledger") || {};
    const slug = meta.slug || document.body.getAttribute("data-slug") || "page";
    const state = store.get(`topic:${slug}`, {
      done: [],
      last: null,
      quiz: {},
      reviews: [],
      completedAt: null,
      firstSeen: null,
    });
    if (!state.firstSeen) {
      state.firstSeen = Date.now();
    }
    function save() {
      store.set(`topic:${slug}`, state);
      store.set("last", { slug: slug, title: meta.title, at: Date.now() });
    }
    save();

    const parts = $$(".ts-part"),
      total = parts.length;
    const rail = $(".ts-rail"),
      railList = el("ol");
    let lastRung = null;
    parts.forEach((p, i) => {
      const rung = p.getAttribute("data-rung") || "1";
      if (!p.id) p.id = `p${i + 1}`;
      const h2 = $("h2", p),
        min = p.getAttribute("data-min");
      const kicker = el("div", { class: "ts-part-kicker" }, [
        el("span", { class: "pill", text: `Part ${i + 1} of ${total}` }),
        el("span", { text: RUNGS[rung] || "" }),
        min ? el("span", { class: "min", text: `about ${min} min` }) : null,
      ]);
      const head = el("div", { class: "ts-part-head" });
      p.insertBefore(head, h2);
      head.appendChild(kicker);
      head.appendChild(h2);
      if (rung !== lastRung) {
        railList.appendChild(el("li", { class: "ts-rung-head", "data-rung": rung, text: RUNGS[rung] }));
        lastRung = rung;
      }
      const li = el("li", { "data-rung": rung, "data-part": p.id }, [
        el("a", { href: `#${p.id}` }, [
          el("i", { class: "st", "aria-hidden": "true" }),
          el("span", { text: h2.textContent }),
          min ? el("small", { text: `${min} min` }) : null,
        ]),
      ]);
      railList.appendChild(li);
      const btn = el("button", { type: "button", class: "ts-btn ghost" });
      const nextLink = parts[i + 1]
        ? el("a", { href: `#${parts[i + 1].id}`, text: `Next: ${$("h2", parts[i + 1]).textContent}` })
        : null;
      p.appendChild(el("div", { class: "ts-done-row" }, [btn, nextLink]));
      function paintBtn() {
        const d = state.done.indexOf(p.id) >= 0;
        btn.textContent = d ? "Done ✓" : "Mark this part done";
        btn.classList.toggle("is-done", d);
        btn.classList.toggle("ghost", !d);
        li.classList.toggle("is-done", d);
      }
      btn.addEventListener("click", () => {
        const k = state.done.indexOf(p.id);
        if (k >= 0) state.done.splice(k, 1);
        else state.done.push(p.id);
        paintBtn();
        progress();
        save();
        if (k < 0) {
          if (state.done.length === total && !state.completedAt) {
            state.completedAt = Date.now();
            save();
            confetti();
            toast("Topic complete. First review is due tomorrow: press V then.");
          } else if (nextLink && !document.body.classList.contains("mode-focus"))
            toast("Part done.", "Next part", () => {
              location.hash = parts[i + 1].id;
              parts[i + 1].scrollIntoView();
            });
          else if (document.body.classList.contains("mode-focus")) focusGo(1);
        }
      });
      p._paint = paintBtn;
      paintBtn();
    });
    if (rail) rail.appendChild(railList);

    const bar = $(".ts-progress > i");
    function progress() {
      if (bar) bar.style.width = `${(100 * state.done.length) / Math.max(1, total)}%`;
    }
    progress();

    // current part tracking
    let nowId = null;
    if ("IntersectionObserver" in window) {
      const io = new IntersectionObserver(
        (ents) => {
          ents.forEach((e) => {
            if (e.isIntersecting) {
              nowId = e.target.id;
              $$(".ts-rail li[data-part]").forEach((li) => {
                li.classList.toggle("is-now", li.getAttribute("data-part") === nowId);
              });
              state.last = nowId;
              save();
            }
          });
        },
        { rootMargin: "-30% 0px -60% 0px" },
      );
      parts.forEach((p) => {
        io.observe(p);
      });
    }

    // checks
    $$(".ts-quiz").forEach(initQuiz);
    $$(".ts-order").forEach(initOrder);
    $$(".ts-predict").forEach(initPredict);
    $$(".ts-explain").forEach((q) => {
      initExplain(q, meta);
    });
    let reviewSeen = new Set(),
      reviewFirst = 0;
    checkHooks.push((root, firstTry) => {
      if (!document.body.classList.contains("mode-review")) return;
      if (reviewSeen.has(root)) return;
      reviewSeen.add(root);
      if (firstTry) reviewFirst++;
      const all = $$(".ts-check").filter((c) => c.offsetParent !== null);
      if (reviewSeen.size >= all.length) {
        state.reviews.push(Date.now());
        save();
        const next = REVIEW_DAYS[Math.min(state.reviews.length, REVIEW_DAYS.length - 1)];
        toast(
          `Review logged: ${reviewFirst} of ${all.length} right first try. Next review in ${next} days.`,
          null,
          null,
          7000,
        );
      }
    });

    initFigures();
    initRooflines();
    initKvCalcs();
    initCode();
    initTabs();
    initTerms();
    initCallouts();
    initCitations(ledger);
    makeScrollRegionsFocusable();

    // resume
    if (state.last && !location.hash && $(`#${state.last}`) && state.last !== parts[0].id) {
      toast(
        "Pick up where you left off?",
        "Resume",
        () => {
          const t = $(`#${state.last}`);
          if (t) t.scrollIntoView();
        },
        8000,
      );
    }
    // review due banner
    if (state.completedAt) {
      const due = nextDue(state);
      if (due !== null && due <= 0)
        toast(
          "A review is due for this topic.",
          "Start review",
          () => {
            setMode("review", true);
          },
          9000,
        );
    }

    /* ---- modes ---- */
    const focusNav = el("div", { class: "ts-focus-nav" }, [
      el("button", {
        type: "button",
        class: "ts-btn ghost",
        text: "← Previous",
        onclick: () => {
          focusGo(-1);
        },
      }),
      el("button", {
        type: "button",
        class: "ts-btn ghost",
        text: "Exit focus",
        onclick: () => {
          setMode("focus", false);
        },
      }),
      el("button", {
        type: "button",
        class: "ts-btn",
        text: "Next →",
        onclick: () => {
          focusGo(1);
        },
      }),
    ]);
    $(".ts-main").appendChild(focusNav);
    function focusIdx() {
      const i = parts.findIndex((p) => p.classList.contains("is-focus"));
      return i < 0 ? 0 : i;
    }
    function focusGo(d) {
      const i = Math.max(0, Math.min(total - 1, focusIdx() + d));
      parts.forEach((p, j) => {
        p.classList.toggle("is-focus", j === i);
      });
      $$(".ts-rail li[data-part]").forEach((li) => {
        li.classList.toggle("is-now", li.getAttribute("data-part") === parts[i].id);
      });
      state.last = parts[i].id;
      save();
      scrollTo(0, 0);
    }
    const modeBtns = {};
    function setMode(m, on) {
      ["focus", "recap", "review"].forEach((x) => {
        const active = x === m ? on : false;
        document.body.classList.toggle(`mode-${x}`, active);
        if (modeBtns[x]) modeBtns[x].setAttribute("aria-pressed", active ? "true" : "false");
      });
      if (m === "focus" && on) {
        const start = parts.findIndex((p) => p.id === (nowId || state.last));
        parts.forEach((p, j) => {
          p.classList.toggle("is-focus", j === Math.max(0, start));
        });
        scrollTo(0, 0);
      }
      if (m === "review" && on) {
        reviewSeen = new Set();
        reviewFirst = 0;
        $$(".ts-check").forEach((c) => {
          if (c._reset) c._reset();
        });
        toast("Review mode: questions only. Answer from memory before peeking.");
        scrollTo(0, 0);
      }
      if (m === "recap" && on)
        $$(".ts-fig").forEach((f) => {
          const b = $$(".ts-fig-ctl button", f)[3];
          if (b) b.click();
        });
    }
    function toggleMode(m) {
      setMode(m, !document.body.classList.contains(`mode-${m}`));
    }

    const tools = $(".ts-tools");
    if (tools) {
      [
        ["focus", "Focus", "One part at a time (F)"],
        ["recap", "Recap", "Takeaways and diagrams only (R)"],
        ["review", "Review", "Questions only, for spaced review (V)"],
      ].forEach((d) => {
        const b = el("button", { type: "button", class: "ts-tool", "aria-pressed": "false", title: d[2] }, [
          el("span", { text: d[1] }),
        ]);
        b.addEventListener("click", () => {
          toggleMode(d[0]);
        });
        modeBtns[d[0]] = b;
        tools.appendChild(b);
      });
      tools.appendChild(sprintButton());
      tools.appendChild(
        el("button", {
          type: "button",
          class: "ts-tool",
          title: "Light or dark (T)",
          "aria-label": "Toggle theme",
          text: "◐",
          onclick: toggleTheme,
        }),
      );
      tools.appendChild(
        el("button", {
          type: "button",
          class: "ts-tool ts-help",
          title: "Keyboard shortcuts (?)",
          "aria-label": "Keyboard shortcuts",
          text: "?",
          onclick: help,
        }),
      );
    }

    document.addEventListener("keydown", (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target;
      if (t && (t.tagName === "TEXTAREA" || t.tagName === "INPUT" || t.isContentEditable)) return;
      const k = e.key.toLowerCase();
      if (k === "f") toggleMode("focus");
      else if (k === "r") toggleMode("recap");
      else if (k === "v") toggleMode("review");
      else if (k === "t") toggleTheme();
      else if (k === "s") $(".ts-sprint")?.click();
      else if (k === "?") help();
      else if (k === "escape") {
        setMode("focus", false);
      } else if (k === "j" || k === "n") {
        if (document.body.classList.contains("mode-focus")) focusGo(1);
        else jump(1);
      } else if (k === "k" || k === "p") {
        if (document.body.classList.contains("mode-focus")) focusGo(-1);
        else jump(-1);
      }
    });
    function jump(d) {
      const i = parts.findIndex((p) => p.id === nowId);
      const n = parts[Math.max(0, Math.min(total - 1, (i < 0 ? 0 : i) + d))];
      if (n) n.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
    }
  }

  function sprintButton() {
    const b = el("button", { type: "button", class: "ts-tool ts-sprint", title: "10-minute focus sprint (S)" }, [
      el("span", { text: "Sprint" }),
    ]);
    let id = null,
      end = 0;
    b.addEventListener("click", () => {
      if (id) {
        clearInterval(id);
        id = null;
        b.setAttribute("aria-pressed", "false");
        b.firstChild.textContent = "Sprint";
        toast("Sprint stopped.");
        return;
      }
      end = Date.now() + 10 * 60000;
      b.setAttribute("aria-pressed", "true");
      toast("10-minute sprint started. One part, no tab switching.");
      id = setInterval(() => {
        const left = Math.max(0, Math.round((end - Date.now()) / 1000));
        b.firstChild.textContent = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
        if (!left) {
          clearInterval(id);
          id = null;
          b.setAttribute("aria-pressed", "false");
          b.firstChild.textContent = "Sprint";
          confetti();
          toast("Sprint done. Stand up for 2 minutes, then go again.", null, null, 9000);
        }
      }, 1000);
    });
    return b;
  }

  function help() {
    let d = $("dialog.ts-dialog");
    if (!d) {
      d = el("dialog", { class: "ts-dialog" });
      const rows = [
        ["F", "Focus: one part at a time"],
        ["R", "Recap: takeaways and diagrams"],
        ["V", "Review: questions only"],
        ["J / K", "Next / previous part"],
        ["S", "10-minute sprint timer"],
        ["T", "Light or dark"],
        ["← →", "Step a focused diagram"],
        ["Esc", "Leave focus mode"],
      ];
      const g = el("div", { class: "ts-keys" });
      rows.forEach((r) => {
        g.appendChild(el("span", {}, [el("kbd", { text: r[0] })]));
        g.appendChild(el("span", { text: r[1] }));
      });
      d.appendChild(el("h2", { text: "Keyboard shortcuts" }));
      d.appendChild(g);
      d.appendChild(
        el("div", { class: "ts-row" }, [
          el("button", {
            type: "button",
            class: "ts-btn",
            text: "Close",
            onclick: () => {
              d.close();
            },
          }),
        ]),
      );
      document.body.appendChild(d);
    }
    if (d.showModal) d.showModal();
  }

  function nextDue(st) {
    if (!st?.completedAt) return null;
    const n = (st.reviews || []).length,
      gap = REVIEW_DAYS[Math.min(n, REVIEW_DAYS.length - 1)];
    const base = n ? st.reviews[n - 1] : st.completedAt;
    return daysBetween(Date.now(), base + gap * 86400000);
  }

  /* =====================================================================
     INDEX PAGE
     ===================================================================== */
  function initIndex() {
    const data = readJSON("ts-topics") || { topics: [] },
      topics = data.topics || [];
    const root = $("#ix-list"),
      q = $(".ix-search");
    const last = store.get("last", null);
    if (last?.slug) {
      const t = topics.find((x) => x.slug === last.slug);
      if (t) {
        const st = store.get(`topic:${t.slug}`, {});
        const left = (t.parts || []).length - (st.done || []).length;
        $("#ix-continue").appendChild(
          el("div", { class: "ix-continue" }, [
            el("span", { text: left > 0 ? `Continue ${t.title}: ${left} parts left.` : `Last studied: ${t.title}.` }),
            el("a", {
              href: `${t.slug}/index.html${st.last ? `#${st.last}` : ""}`,
              text: left > 0 ? "Resume" : "Open",
            }),
          ]),
        );
      }
    }
    function card(t) {
      const st = store.get(`topic:${t.slug}`, { done: [] }),
        done = st.done || [];
      const parts = t.parts || [];
      const line = el("div", { class: "ix-line", "aria-label": `${done.length} of ${parts.length} parts done` });
      [1, 2, 3, 4, 5].forEach((r) => {
        const inR = parts.filter((p) => +p.rung === r);
        const allDone = inR.length && inR.every((p) => done.indexOf(p.id) >= 0);
        line.appendChild(el("span", { "data-rung": String(r), class: allDone ? "is-done" : "", title: RUNGS[r] }));
      });
      const badges = el("div", { class: "ix-badges" });
      badges.appendChild(
        el("span", {
          class: `ix-badge${done.length === parts.length && parts.length ? " done" : ""}`,
          text: `${done.length} of ${parts.length} parts`,
        }),
      );
      if (t.minutes) badges.appendChild(el("span", { class: "ix-badge", text: `about ${t.minutes} min` }));
      const due = nextDue(st);
      if (due !== null)
        badges.appendChild(
          el("span", {
            class: `ix-badge${due <= 0 ? " due" : ""}`,
            text: due <= 0 ? "Review due" : `Review in ${due}${due === 1 ? " day" : " days"}`,
          }),
        );
      if (t.verified) {
        const age = daysBetween(new Date(t.verified).getTime(), Date.now());
        badges.appendChild(
          el("span", {
            class: `ix-badge${age > 180 ? " stale" : ""}`,
            text: age > 180 ? `Checked ${t.verified}: ask for a refresh` : `Checked ${t.verified}`,
          }),
        );
      }
      return el("li", { class: "ix-item", "data-q": `${t.title} ${t.tldr} ${t.category || ""}`.toLowerCase() }, [
        el("h3", {}, [el("a", { href: `${t.slug}/index.html`, text: t.title })]),
        el("p", { text: t.tldr }),
        line,
        badges,
      ]);
    }
    function render(filter) {
      root.innerHTML = "";
      const f = (filter || "").toLowerCase().trim();
      const shown = topics.filter(
        (t) => !f || `${t.title} ${t.tldr} ${t.category || ""}`.toLowerCase().indexOf(f) >= 0,
      );
      if (!topics.length) {
        root.appendChild(
          el("div", { class: "ix-empty", text: "No topics yet. Ask Claude to teach you something as a page." }),
        );
        return;
      }
      if (!shown.length) {
        root.appendChild(el("div", { class: "ix-empty", text: `Nothing matches “${filter}”.` }));
        return;
      }
      const groups = {};
      shown.forEach((t) => {
        const g = t.category || "Other";
        groups[g] = groups[g] || [];
        groups[g].push(t);
      });
      Object.keys(groups)
        .sort()
        .forEach((g) => {
          const sec = el("section", { class: "ix-group" }, [el("h2", { text: g })]);
          const ul = el("ul", { class: "ix-list" });
          groups[g]
            .sort((a, b) => a.title.localeCompare(b.title))
            .forEach((t) => {
              ul.appendChild(card(t));
            });
          sec.appendChild(ul);
          root.appendChild(sec);
        });
    }
    if (q)
      q.addEventListener("input", () => {
        render(q.value);
      });
    render("");
    const tools = $(".ts-tools");
    if (tools)
      tools.appendChild(
        el("button", {
          type: "button",
          class: "ts-tool",
          title: "Light or dark",
          "aria-label": "Toggle theme",
          text: "◐",
          onclick: toggleTheme,
        }),
      );
    if (!store.ok)
      $("#ix-continue").appendChild(
        el("p", {
          class: "ts-foot",
          text: "This browser blocks saved progress for local files. Chrome keeps it; Safari may not.",
        }),
      );
  }

  function boot() {
    if (document.body.classList.contains("ts-index")) initIndex();
    else if (document.body.classList.contains("ts-page")) initTopic();
    document.documentElement.setAttribute("data-ts", VERSION);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
