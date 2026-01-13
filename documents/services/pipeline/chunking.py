import re

def chunk_text(text: str, *, chunk_size=900, overlap=150):
    t = (text or "").strip()
    if not t:
        return []
    t = re.sub(r"\n{3,}", "\n\n", t)
    out = []
    i = 0
    while i < len(t):
        out.append(t[i:i+chunk_size].strip())
        i += max(1, chunk_size - overlap)
    return [c for c in out if c]
