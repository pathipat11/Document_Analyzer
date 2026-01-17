import re
from collections import Counter
from dataclasses import dataclass
from documents.models import DocumentChunk

WORD = re.compile(r"[A-Za-zก-๙0-9]+")

# stopwords แบบ lightweight (เพิ่มได้เรื่อย ๆ)
STOP_TH = {
    "ที่","และ","หรือ","คือ","เป็น","ได้","ใน","ของ","กับ","จาก","ให้","แล้ว","ยัง","ไม่","มี","จะ","ก็","มา","ไป",
    "ทำ","การ","ว่า","นี้","นั้น","ค่ะ","ครับ","คับ","ๆ","ๆๆ",
}
STOP_EN = {
    "the","a","an","and","or","is","are","was","were","to","of","in","on","for","with","from","as","at","by",
    "what","how","why","can","could","should","would","do","does","did","i","you","we","they","it",
}

def _tok(s: str):
    toks = [w.lower() for w in WORD.findall(s or "")]
    out = []
    for t in toks:
        if len(t) <= 1:
            continue
        if t.isdigit():
            out.append(t)  # ตัวเลขเก็บไว้
            continue
        if t in STOP_TH or t in STOP_EN:
            continue
        out.append(t)
    return out

@dataclass
class ScoredChunk:
    idx: int
    content: str
    score: int
    matched_terms: int

def retrieve_top_chunks(doc_id: int, query: str, k: int = 6):
    q = _tok(query)
    if not q:
        return []

    qcount = Counter(q)
    q_terms = set(qcount.keys())

    scored = []
    for ch in DocumentChunk.objects.filter(document_id=doc_id):
        w = _tok(ch.content)
        if not w:
            continue
        c = Counter(w)
        c_terms = set(c.keys())

        overlap_terms = q_terms & c_terms
        if not overlap_terms:
            continue

        score = 0
        for term in overlap_terms:
            score += min(c.get(term, 0), qcount.get(term, 0)) * 2

        if score > 0:
            scored.append((score, len(overlap_terms), ch))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    top = scored[:k]

    # คืนเป็น ScoredChunk (มี score + matched_terms)
    return [
        ScoredChunk(
            idx=ch.idx,
            content=ch.content,
            score=score,
            matched_terms=mt
        )
        for score, mt, ch in top
    ]
