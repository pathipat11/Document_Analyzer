import re
from collections import Counter
from documents.models import DocumentChunk

WORD = re.compile(r"[A-Za-zก-๙0-9]+")

def _tok(s: str):
    return [w.lower() for w in WORD.findall(s or "")]

def retrieve_top_chunks(doc_id: int, query: str, k: int = 6):
    q = _tok(query)
    if not q:
        return []

    qcount = Counter(q)

    scored = []
    for ch in DocumentChunk.objects.filter(document_id=doc_id):
        w = _tok(ch.content)
        if not w:
            continue
        c = Counter(w)

        # simple overlap score (fast + ok for prototype)
        score = 0
        for term, qt in qcount.items():
            score += min(c.get(term, 0), qt) * 2
        # small boost for shorter chunks not needed; keep simple

        if score > 0:
            scored.append((score, ch))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [ch for _, ch in scored[:k]]
