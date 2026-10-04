"""BRIN modelled in Python: one (min, max) summary per block range."""


def summarize(pages, pages_per_range, summarized_pages=None):
    """pages: list of value lists, one per table page. Ranges past summarized_pages stay None."""
    limit = len(pages) if summarized_pages is None else summarized_pages
    out = []
    for start in range(0, len(pages), pages_per_range):
        if start >= limit:
            out.append(None)  # not summarized yet: VACUUM or brin_summarize_new_values() fills it
            continue
        vals = [v for p in pages[start : start + pages_per_range] for v in p]
        out.append((min(vals), max(vals)))
    return out


def pages_to_read(summary, lo, hi, pages_per_range, n_pages):
    """Lossy: every page of a matching or unsummarized range; the executor rechecks each row."""
    read = []
    for r, s in enumerate(summary):
        if s is None or (s[0] <= hi and lo <= s[1]):
            read.extend(range(r * pages_per_range, min((r + 1) * pages_per_range, n_pages)))
    return read
