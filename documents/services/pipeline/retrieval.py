import re
from collections import Counter
from dataclasses import dataclass
from documents.models import DocumentChunk

WORD = re.compile(r"[A-Za-zก-๙0-9]+")

STOP_TH = {
    "ที่","และ","หรือ","คือ","เป็น","ได้","ใน","ของ","กับ","จาก","ให้","แล้ว","ยัง","ไม่","มี","จะ","ก็","มา","ไป",
    "ว่า","นี้","นั้น","ค่ะ","ครับ","คับ","ๆ","ๆๆ",
}
STOP_EN = {
    "the","a","an","and","or","is","are","was","were","to","of","in","on","for","with","from","as","at","by",
    "i","you","we","they","it",
}

def _tok(s: str):
    toks = [w.lower() for w in WORD.findall(s or "")]
    out = []
    for t in toks:
        if len(t) <= 1:
            continue
        if t.isdigit():
            out.append(t)
            continue
        if t in STOP_TH or t in STOP_EN:
            continue
        out.append(t)
    return out

def _tok_loose(s: str):
    toks = [w.lower() for w in WORD.findall(s or "")]
    return [t for t in toks if len(t) > 1][:20]

def _snippet_around_terms(text: str, terms: list[str], window: int = 240) -> str:
    """
    ตัดเฉพาะส่วนที่ใกล้คำที่ match เพื่อลด prompt noise
    """
    if not text:
        return ""
    t = text.strip()
    if not terms:
        return t[: min(len(t), 600)]

    low = t.lower()

    # หา occurrence แรกของ term ใด ๆ
    best_pos = None
    for term in terms[:10]:
        p = low.find(term.lower())
        if p != -1:
            best_pos = p if best_pos is None else min(best_pos, p)

    if best_pos is None:
        return t[: min(len(t), 600)]

    start = max(0, best_pos - window)
    end = min(len(t), best_pos + window)

    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(t) else ""
    return prefix + t[start:end].strip() + suffix

@dataclass
class ScoredChunk:
    idx: int
    content: str
    score: float
    matched_terms: int

def retrieve_top_chunks(doc_id: int, query: str, k: int = 6):
    q = _tok(query)
    if not q:
        q = _tok_loose(query)
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

        raw = 0
        for term in overlap_terms:
            raw += min(c.get(term, 0), qcount.get(term, 0)) * 2

        matched = len(overlap_terms)
        if raw <= 0:
            continue

        # normalization แบบง่าย:
        # - ให้ matched_terms มีผลมากขึ้น
        # - penalty เล็กน้อยถ้า chunk ยาวมาก (กัน spam)
        length_penalty = max(0.85, min(1.0, 900 / max(1, len(ch.content))))
        score = (raw + matched * 1.2) * length_penalty

        # ทำ excerpt รอบ ๆ คำที่ match เพื่อลด noise
        excerpt = _snippet_around_terms(ch.content, list(overlap_terms), window=260)

        scored.append((score, matched, excerpt, ch.idx))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    top = scored[:k]

    return [
        ScoredChunk(
            idx=idx,
            content=excerpt,
            score=float(score),
            matched_terms=int(matched),
        )
        for score, matched, excerpt, idx in top
    ]
