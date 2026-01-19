import re

def _best_break(text: str, start: int, target_end: int, window: int = 180) -> int:
    n = len(text)
    lo = max(start + 50, target_end - window)
    hi = min(n, target_end + window)

    region = text[lo:hi]
    if not region:
        return min(n, target_end)

    candidates = []

    def add(pattern: str, bonus: int):
        for m in re.finditer(pattern, region):
            candidates.append((lo + m.start(), bonus))

    add(r"\n\s*\n", 40)
    add(r"\n", 25)
    add(r"\.\s", 15)      
    add(r"[。！？]\s*", 15)
    add(r"\s", 5)

    if not candidates:
        return min(n, target_end)

    best = None
    for pos, bonus in candidates:
        dist = abs(pos - target_end)
        score = -dist + bonus
        if best is None or score > best[0]:
            best = (score, pos)

    cut = best[1]
    return min(n, cut + 1)

def chunk_text(text: str, *, chunk_size=900, overlap=150):
    t = (text or "").strip()
    if not t:
        return []

    t = re.sub(r"\r\n?", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)

    out = []
    i = 0
    n = len(t)

    while i < n:
        target_end = min(n, i + chunk_size)
        end = target_end

        if target_end < n:
            end = _best_break(t, i, target_end, window=180)

        chunk = t[i:end].strip()
        if chunk:
            out.append(chunk)

        if end >= n:
            break
        i = max(i + 1, end - overlap)

    return out
