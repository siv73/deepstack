"""Turn a toy loop trace into the HTML table rows the page shows (used by the tests)."""


def short(name):
    return name.removeprefix("seller-")


def rows(trace):
    out = []
    for now, what, ready, timers in trace:
        ready_text = ", ".join(short(n) for n in ready) or "empty"
        heap_text = ", ".join(f"{short(n)} {at}" for at, n in timers) or "empty"
        out.append(f"<tr><td>{now}</td><td>{what}</td><td>{ready_text}</td><td>{heap_text}</td></tr>")
    return out
