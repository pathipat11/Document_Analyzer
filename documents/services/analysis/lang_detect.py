import re

THAI_RE = re.compile(r"[ก-ฮ]")
LATIN_RE = re.compile(r"[A-Za-z]")

def detect_language(text: str) -> str:
    """
    Simple heuristic:
    - Use ratio instead of absolute threshold
    - If Thai chars are dominant -> th
    - Otherwise -> en
    """
    if not text:
        return "en"

    thai = len(THAI_RE.findall(text))
    latin = len(LATIN_RE.findall(text))

    # ถ้ามีไทยอย่างน้อยนิด และมีมากกว่าอังกฤษ -> ไทย
    # (ช่วยให้คำถามไทยสั้น ๆ ไม่หลุดเป็น en)
    if thai == 0:
        return "en"
    if latin == 0:
        return "th"

    return "th" if thai >= latin else "en"
