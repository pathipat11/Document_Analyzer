import re

THAI_RE = re.compile(r"[ก-ฮ]")

def detect_language(text: str) -> str:
    if not text:
        return "en"
    thai_count = len(THAI_RE.findall(text))
    
    return "th" if thai_count >= 20 else "en"
