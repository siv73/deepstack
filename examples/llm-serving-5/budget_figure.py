"""Draws the page's step-through figure from the simulator: the same 50,000-token prompt and
20 decoding streams, with chunked prefill off and with an 8,192-token budget. Widths are time.

Usage: uv run budget_figure.py > figure.svg
"""

from scenarios import stall

X0, PX_PER_S, LANES = 120, 340, (70, 200)  # left edge, pixels per second, top of each lane


def _label(x: float, y: float, text: str, anchor: str = "middle") -> str:
    return f'<text x="{x:.1f}" y="{y}" text-anchor="{anchor}">{text}</text>'


def _bg(x: float, y: float, w: int) -> str:
    return f'<rect class="lblbg" x="{x:.1f}" y="{y}" width="{w}" height="20"/>'


def _steps_svg(steps: list[dict], top: int, s: int) -> tuple[str, list[str]]:
    """Rectangles for every step that carries prefill, plus ticks for a few decode-only steps."""
    out, x, ticks = [], float(X0), 0
    for st in steps:
        w = st["dt"] * PX_PER_S
        if st["prefill"]:
            out.append(f'<rect x="{x:.1f}" y="{top}" width="{w:.1f}" height="56" rx="4"/>')
            if w > 40:
                out.append(_label(x + w / 2, top + 33, f"{st['dt'] * 1000:,.0f} ms"))
        elif ticks < 4:
            out.append(f'<rect x="{x:.1f}" y="{top + 20}" width="2" height="16" rx="1"/>')
            ticks += 1
        x += w
    return f'<g class="node" data-s="{s}">' + "".join(out) + "</g>", out


def figure() -> str:
    off, on = stall(65536, chunked=False), stall(8192)
    y1, y2 = LANES
    t_off, t_on = X0 + off["long_ttft_s"] * PX_PER_S, X0 + on["long_ttft_s"] * PX_PER_S
    axis = "".join(
        f'<line class="life" x1="{X0 + t * PX_PER_S:.0f}" y1="316" x2="{X0 + t * PX_PER_S:.0f}" y2="322"/>'
        f'<text x="{X0 + t * PX_PER_S:.0f}" y="338" text-anchor="middle" class="num">{t:.1f} s</text>'
        for t in (0, 0.5, 1.0, 1.5)
    )
    worst = max(on["steps"], key=lambda st: st["dt"] if st["prefill"] else 0)
    worst_x = X0 + sum(st["dt"] for st in on["steps"][: on["steps"].index(worst)]) * PX_PER_S
    parts = [
        '<svg viewBox="0 0 700 350" role="img" aria-label="Two timelines of the same work. '
        "With chunked prefill off, one step of 1,471 ms carries all 50,000 prompt tokens and every "
        "stream waits that long for its next token. With an 8,192-token budget, seven steps of "
        '41 to 327 ms carry the prompt in chunks while every stream gets a token each step.">',
        f'<g><line class="life" x1="{X0}" y1="316" x2="680" y2="316"/>{axis}'
        f'<text x="10" y="{y1 + 33}" class="num">Chunking off</text>'
        f'<text x="10" y="{y2 + 25}" class="num">Budget</text>'
        f'<text x="10" y="{y2 + 43}" class="num">8,192</text></g>',
        f'<g class="over" data-s="1"><rect x="{X0 - 4}" y="30" width="8" height="280" rx="3"/>'
        f'<rect class="lblbg" x="{X0 + 10}" y="6" width="330" height="20"/>'
        f'<text x="{X0 + 14}" y="21">50,000-token prompt arrives; 20 streams decoding</text></g>',
        _steps_svg(off["steps"], y1, 2)[0],
        _steps_svg(on["steps"], y2, 3)[0],
        f'<g class="edge" data-s="4"><path d="M{X0},{y1 + 66} L{t_off:.1f},{y1 + 66}"/>'
        + _bg(X0 + 60, y1 + 72, 320)
        + _label(X0 + 220, y1 + 87, f"every stream waits {off['worst_itl_s'] * 1000:,.0f} ms for one token")
        + f'<path d="M{worst_x:.1f},{y2 + 66} L{worst_x + worst["dt"] * PX_PER_S:.1f},{y2 + 66}"/>'
        + _bg(worst_x - 120, y2 + 72, 250)
        + _label(worst_x + 5, y2 + 87, f"longest gap: {on['worst_itl_s'] * 1000:,.0f} ms")
        + "</g>",
        f'<g class="over" data-s="5"><rect x="{t_off - 3:.1f}" y="{y1 - 8}" width="6" height="72" rx="3"/>'
        f'<rect x="{t_on - 3:.1f}" y="{y2 - 8}" width="6" height="72" rx="3"/>'
        + _bg(t_off - 210, y1 - 30, 250)
        + _label(t_off - 85, y1 - 15, f"long prompt's first token: {off['long_ttft_s']:.3f} s")
        + _bg(t_on - 210, y2 - 30, 250)
        + _label(t_on - 85, y2 - 15, f"long prompt's first token: {on['long_ttft_s']:.3f} s")
        + "</g>",
        "</svg>",
    ]
    return "\n".join(parts)


if __name__ == "__main__":
    print(figure())
